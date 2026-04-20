"""Projection run + fetch endpoints."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account, Profile, Projection, Scenario, SocialSecurity
from backend.engines.projection import ScenarioParams, run_projection
from backend.engines.withdrawal import AccountState

router = APIRouter()


def _current_year() -> int:
    return date.today().year


def _dob_to_year(dob_str: str) -> int:
    """Extract birth year from ISO date string YYYY-MM-DD."""
    try:
        return int(str(dob_str)[:4])
    except (ValueError, TypeError):
        return 1970


def _age_at_year(dob_str: str, year: int) -> int:
    """Approximate age at given year (ignores birth month)."""
    return year - _dob_to_year(dob_str)


def _build_input_hash(
    scenario: Scenario, profiles: list, accounts: list, ss_list: list
) -> str:
    payload = {
        "scenario_id": scenario.id,
        "scenario": {
            k: v for k, v in scenario.__dict__.items() if not k.startswith("_")
        },
        "profiles": [
            {k: v for k, v in p.__dict__.items() if not k.startswith("_")}
            for p in profiles
        ],
        "accounts": [
            {k: v for k, v in a.__dict__.items() if not k.startswith("_")}
            for a in accounts
        ],
        "ss": [
            {k: v for k, v in s.__dict__.items() if not k.startswith("_")}
            for s in ss_list
        ],
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _build_scenario_params(
    scenario: Scenario, profiles: list, accounts: list, ss_list: list
) -> tuple[ScenarioParams, list[AccountState], int, int, int]:
    """Build ScenarioParams + AccountState list from DB models.

    Returns (params, account_states, start_year, age_you, age_spouse)
    """
    ss_map = {s.owner_id: s for s in ss_list}

    # Identify you vs spouse by profile order or name
    you = next(
        (p for p in profiles if p.name == "You"), profiles[0] if profiles else None
    )
    spouse = next(
        (p for p in profiles if p.name == "Spouse"),
        profiles[1] if len(profiles) > 1 else None,
    )

    if not you:
        raise HTTPException(
            status_code=400, detail="No 'You' profile found. Add profiles first."
        )

    start_year = _current_year()
    age_you = _age_at_year(you.dob, start_year)
    age_spouse = _age_at_year(spouse.dob, start_year) if spouse else 0

    ss_you = ss_map.get(you.id)
    ss_spouse = ss_map.get(spouse.id) if spouse else None

    def ss_monthly_at_claim(ss_record, claim_age):
        if not ss_record:
            return 0.0
        fra = ss_record.fra_age or 67
        if claim_age <= 62:
            return float(ss_record.benefit_at_62 or 0)
        if claim_age >= 70:
            return float(ss_record.benefit_at_70 or 0)
        if claim_age == fra:
            return float(ss_record.benefit_at_fra or 0)
        if claim_age < fra:
            # Interpolate between 62 and FRA
            frac = (claim_age - 62) / (fra - 62)
            return float(ss_record.benefit_at_62 or 0) + frac * (
                float(ss_record.benefit_at_fra or 0)
                - float(ss_record.benefit_at_62 or 0)
            )
        # Between FRA and 70
        frac = (claim_age - fra) / (70 - fra)
        return float(ss_record.benefit_at_fra or 0) + frac * (
            float(ss_record.benefit_at_70 or 0) - float(ss_record.benefit_at_fra or 0)
        )

    ss_monthly_you = ss_monthly_at_claim(ss_you, scenario.ss_claim_age_you)
    ss_monthly_spouse = ss_monthly_at_claim(ss_spouse, scenario.ss_claim_age_spouse)

    # Extract pension and rental from accounts
    pension_monthly_you = 0.0
    pension_start_age_you = 0
    rental_annual = 0.0
    nqdc_schedule = []

    for acct in accounts:
        if acct.account_type == "pension" and acct.owner_id == you.id:
            pension_monthly_you = float(acct.pension_monthly or 0)
            pension_start_age_you = acct.pension_start_age or 0
        elif acct.account_type == "real_estate":
            rental_annual += float(acct.rental_annual_income or 0)
        elif acct.account_type == "nqdc":
            nqdc_schedule.extend(acct.nqdc_schedule or [])

    # Build AccountState list (exclude pension and real_estate — handled separately)
    account_states = []
    is_rule_of_55 = scenario.retirement_age_you >= 55

    for acct in accounts:
        if acct.account_type in ("pension", "real_estate"):
            continue
        owner = "you" if acct.owner_id == you.id else "spouse"
        account_states.append(
            AccountState(
                account_type=acct.account_type,
                balance=float(acct.balance or 0),
                basis=0.0,
                owner=owner,
                is_rule_of_55_eligible=(
                    acct.account_type == "401k" and is_rule_of_55 and owner == "you"
                ),
                annual_contribution=float(acct.annual_contribution or 0),
            )
        )

    params = ScenarioParams(
        retirement_age_you=scenario.retirement_age_you,
        retirement_age_spouse=scenario.retirement_age_spouse,
        annual_spending=float(scenario.annual_spending or 0),
        spending_glide_path=scenario.spending_glide_path or {},
        ss_claim_age_you=scenario.ss_claim_age_you,
        ss_claim_age_spouse=scenario.ss_claim_age_spouse,
        ss_monthly_you=ss_monthly_you,
        ss_monthly_spouse=ss_monthly_spouse,
        withdrawal_strategy=scenario.withdrawal_strategy or "optimized",
        manual_withdrawal_order=scenario.manual_withdrawal_order or [],
        roth_conversion_enabled=bool(scenario.roth_conversion_enabled),
        roth_conversion_target_bracket=scenario.roth_conversion_target_bracket or "22%",
        healthcare_monthly_pre_medicare=float(
            scenario.healthcare_monthly_pre_medicare or 0
        ),
        stock_allocation=float(scenario.stock_allocation or 0.6),
        expected_return_stocks=float(scenario.expected_return_stocks or 0.07),
        expected_return_bonds=float(scenario.expected_return_bonds or 0.04),
        inflation_rate=float(scenario.inflation_rate or 0.025),
        pension_monthly_you=pension_monthly_you,
        pension_start_age_you=pension_start_age_you,
        rental_annual_income=rental_annual,
        nqdc_schedule=nqdc_schedule,
        life_expectancy_you=you.life_expectancy_age or 88,
        life_expectancy_spouse=spouse.life_expectancy_age if spouse else 90,
        dob_year_you=_dob_to_year(you.dob),
        dob_year_spouse=_dob_to_year(spouse.dob) if spouse else 1974,
        base_year=2024,
        filing_status=you.filing_status or "mfj",
        state=you.state or "DE",
    )

    return params, account_states, start_year, age_you, age_spouse


def _proj_year_to_dict(py) -> dict:
    return {
        "year": py.year,
        "age_you": py.age_you,
        "age_spouse": py.age_spouse,
        "portfolio_balance": py.portfolio_balance,
        "balances_by_account": py.balances_by_account,
        "gross_income": py.gross_income,
        "income_by_source": py.income_by_source,
        "federal_tax": py.federal_tax,
        "state_tax": py.state_tax,
        "effective_rate": py.effective_rate,
        "roth_conversion_amount": py.roth_conversion_amount,
        "withdrawal_notes": py.withdrawal_notes,
    }


@router.post("/{scenario_id}/run")
def run_projection_endpoint(
    scenario_id: int, db: Session = Depends(get_db)
) -> dict[str, Any]:
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    profiles = db.query(Profile).all()
    accounts = db.query(Account).all()
    ss_list = db.query(SocialSecurity).all()

    input_hash = _build_input_hash(scenario, profiles, accounts, ss_list)

    # Check cache
    cached = (
        db.query(Projection)
        .filter(
            Projection.scenario_id == scenario_id, Projection.input_hash == input_hash
        )
        .first()
    )
    if cached:
        existing = (
            db.query(Projection)
            .filter(Projection.scenario_id == scenario_id)
            .order_by(Projection.year)
            .all()
        )
        return {"years": [_proj_year_to_dict(p) for p in existing], "cached": True}

    # Clear stale cache
    db.query(Projection).filter(Projection.scenario_id == scenario_id).delete()

    params, account_states, start_year, age_you, age_spouse = _build_scenario_params(
        scenario, profiles, accounts, ss_list
    )
    year_results = run_projection(
        start_year=start_year,
        age_you_at_start=age_you,
        age_spouse_at_start=age_spouse,
        accounts=account_states,
        params=params,
    )

    for yr in year_results:
        row = Projection(
            scenario_id=scenario_id,
            input_hash=input_hash,
            year=yr.year,
            age_you=yr.age_you,
            age_spouse=yr.age_spouse,
            portfolio_balance=yr.portfolio_balance,
            gross_income=yr.gross_income,
            federal_tax=yr.federal_tax,
            state_tax=yr.state_tax,
            effective_rate=yr.effective_rate,
            roth_conversion_amount=yr.roth_conversion_amount,
        )
        row.balances_by_account = yr.balances_by_account
        row.income_by_source = yr.income_by_source
        row.withdrawal_notes = yr.withdrawal_notes
        db.add(row)
    db.commit()

    saved = (
        db.query(Projection)
        .filter(Projection.scenario_id == scenario_id)
        .order_by(Projection.year)
        .all()
    )
    return {"years": [_proj_year_to_dict(p) for p in saved], "cached": False}


@router.get("/{scenario_id}")
def get_projection_endpoint(
    scenario_id: int, db: Session = Depends(get_db)
) -> dict[str, Any]:
    rows = (
        db.query(Projection)
        .filter(Projection.scenario_id == scenario_id)
        .order_by(Projection.year)
        .all()
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No projection found. Run the projection first from the Scenarios tab.",
        )
    return {"years": [_proj_year_to_dict(p) for p in rows]}
