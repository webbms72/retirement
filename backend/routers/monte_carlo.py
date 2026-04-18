"""Monte Carlo run + fetch endpoints, plus SS optimizer."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account, MCResult, Profile, Scenario, SocialSecurity
from backend.engines.monte_carlo import MCInput, run_monte_carlo
from backend.engines.ss_optimizer import SSInput, optimize_ss
from backend.routers.projections import _build_scenario_params

router = APIRouter()


class RunMCRequest(BaseModel):
    num_simulations: int = 10000


@router.post("/monte-carlo/{scenario_id}/run")
def run_mc_endpoint(
    scenario_id: int, body: RunMCRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    profiles = db.query(Profile).all()
    accounts = db.query(Account).all()
    ss_list = db.query(SocialSecurity).all()

    # Cache key
    cache_data = {
        "scenario_id": scenario_id,
        "num_simulations": body.num_simulations,
        "scenario": {
            k: v for k, v in scenario.__dict__.items() if not k.startswith("_")
        },
    }
    input_hash = hashlib.sha256(
        json.dumps(cache_data, sort_keys=True, default=str).encode()
    ).hexdigest()

    cached = (
        db.query(MCResult)
        .filter(MCResult.scenario_id == scenario_id, MCResult.input_hash == input_hash)
        .first()
    )
    if cached:
        return _mc_to_dict(cached) | {"cached": True}

    params, account_states, start_year, age_you, age_spouse = _build_scenario_params(
        scenario, profiles, accounts, ss_list
    )
    mc_input = MCInput(
        scenario_params=params,
        accounts=account_states,
        start_year=start_year,
        age_you_at_start=age_you,
        age_spouse_at_start=age_spouse,
        n_simulations=body.num_simulations,
        random_seed=None,
    )
    result = run_monte_carlo(mc_input)

    # Clear stale
    db.query(MCResult).filter(MCResult.scenario_id == scenario_id).delete()

    row = MCResult(
        scenario_id=scenario_id,
        input_hash=input_hash,
        num_simulations=body.num_simulations,
        survival_rate=result.survival_rate,
        run_at=datetime.now(timezone.utc),
    )
    row.percentile_10 = {str(k): v for k, v in result.percentile_10.items()}
    row.percentile_25 = {str(k): v for k, v in result.percentile_25.items()}
    row.percentile_50 = {str(k): v for k, v in result.percentile_50.items()}
    row.percentile_75 = {str(k): v for k, v in result.percentile_75.items()}
    row.percentile_90 = {str(k): v for k, v in result.percentile_90.items()}
    row.sensitivity = result.sensitivity
    db.add(row)
    db.commit()
    db.refresh(row)
    return _mc_to_dict(row) | {"cached": False}


@router.get("/monte-carlo/{scenario_id}")
def get_mc_endpoint(scenario_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = (
        db.query(MCResult)
        .filter(MCResult.scenario_id == scenario_id)
        .order_by(MCResult.id.desc())
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=404,
            detail="No Monte Carlo result found. Run simulations first.",
        )
    return _mc_to_dict(row)


@router.get("/ss-optimizer")
def ss_optimizer_endpoint(
    benefit_62_you: float = Query(...),
    benefit_fra_you: float = Query(...),
    benefit_70_you: float = Query(...),
    fra_age_you: int = Query(67),
    benefit_62_spouse: float = Query(0),
    benefit_fra_spouse: float = Query(0),
    benefit_70_spouse: float = Query(0),
    fra_age_spouse: int = Query(67),
    life_exp_you: int = Query(88),
    life_exp_spouse: int = Query(90),
    current_age_you: int = Query(54),
    current_age_spouse: int = Query(52),
    survivor_benefit_pct: float = Query(1.0),
) -> list[dict[str, Any]]:
    inp = SSInput(
        benefit_at_62_you=benefit_62_you,
        benefit_at_fra_you=benefit_fra_you,
        benefit_at_70_you=benefit_70_you,
        fra_age_you=fra_age_you,
        benefit_at_62_spouse=benefit_62_spouse,
        benefit_at_fra_spouse=benefit_fra_spouse,
        benefit_at_70_spouse=benefit_70_spouse,
        fra_age_spouse=fra_age_spouse,
        life_expectancy_you=life_exp_you,
        life_expectancy_spouse=life_exp_spouse,
        survivor_benefit_pct=survivor_benefit_pct,
        current_age_you=current_age_you,
        current_age_spouse=current_age_spouse,
    )
    results = optimize_ss(inp)
    return [
        {
            "rank": i + 1,
            "claim_age_you": r.claim_age_you,
            "claim_age_spouse": r.claim_age_spouse,
            "monthly_benefit_you": r.monthly_benefit_you,
            "monthly_benefit_spouse": r.monthly_benefit_spouse,
            "lifetime_benefit": r.lifetime_benefit,
            "survivor_monthly_benefit": r.survivor_monthly_benefit,
            "notes": r.notes,
        }
        for i, r in enumerate(results[:10])
    ]


def _mc_to_dict(row: MCResult) -> dict:
    return {
        "scenario_id": row.scenario_id,
        "num_simulations": row.num_simulations,
        "survival_rate": row.survival_rate,
        "percentile_10": row.percentile_10,
        "percentile_25": row.percentile_25,
        "percentile_50": row.percentile_50,
        "percentile_75": row.percentile_75,
        "percentile_90": row.percentile_90,
        "sensitivity": row.sensitivity,
        "run_at": row.run_at.isoformat() if row.run_at else None,
    }
