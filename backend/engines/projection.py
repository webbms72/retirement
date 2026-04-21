"""Projection Engine — single-year and multi-year retirement simulations.

All functions are pure (no DB access). The Projection Engine orchestrates
the Tax Engine and Withdrawal Optimizer on a year-by-year basis.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from backend.engines.tax import TaxInput, TaxResult, calculate_taxes
from backend.engines.withdrawal import (
    AccountState,
    WithdrawalInput,
    WithdrawalResult,
    calculate_rmd,
    optimize_withdrawals,
)


@dataclass
class ScenarioParams:
    """All scenario configuration needed to run a full projection."""

    retirement_age_you: int
    retirement_age_spouse: int
    annual_spending: float
    spending_glide_path: dict[str, float]
    ss_claim_age_you: int
    ss_claim_age_spouse: int
    ss_monthly_you: float
    ss_monthly_spouse: float
    withdrawal_strategy: str
    manual_withdrawal_order: list[str] | None
    roth_conversion_enabled: bool
    roth_conversion_target_bracket: str | None
    healthcare_monthly_pre_medicare: float
    stock_allocation: float
    expected_return_stocks: float
    expected_return_bonds: float
    inflation_rate: float
    pension_monthly_you: float
    pension_start_age_you: int
    rental_annual_income: float
    nqdc_schedule: list[dict[str, Any]]
    life_expectancy_you: int
    life_expectancy_spouse: int
    dob_year_you: int
    dob_year_spouse: int
    base_year: int
    filing_status: str
    state: str


@dataclass
class ProjectionYear:
    """Computed results for a single projection year."""

    year: int
    age_you: int
    age_spouse: int
    portfolio_balance: float
    balances_by_account: dict[str, float]
    gross_income: float
    income_by_source: dict[str, float]
    federal_tax: float
    state_tax: float
    effective_rate: float
    marginal_rate: float
    roth_conversion_amount: float
    withdrawal_notes: list[str]
    early_withdrawal_penalty: float = 0.0
    irmaa_annual: float = 0.0


def _blended_return(params: ScenarioParams) -> float:
    stock_w = params.stock_allocation
    bond_w = 1.0 - stock_w
    return (
        stock_w * params.expected_return_stocks + bond_w * params.expected_return_bonds
    )


def _get_spending(
    age_you: int, params: ScenarioParams, inflation_factor: float
) -> float:
    glide = params.spending_glide_path or {}
    override = glide.get(str(age_you))
    base = override if override is not None else params.annual_spending
    return base * inflation_factor


def _get_nqdc_payout(year: int, params: ScenarioParams) -> float:
    # NQDC schedules are user-entered in nominal dollars (the plan specifies a
    # fixed payout amount), so no inflation adjustment is applied here.
    total = 0.0
    for entry in params.nqdc_schedule:
        entry_year = int(entry["date"][:4])
        if entry_year == year:
            total += float(entry["amount"])
    return total


def _get_ss_income(
    age_you: int,
    age_spouse: int,
    params: ScenarioParams,
    inflation_factor: float,
) -> tuple[float, float]:
    ss_you = (
        params.ss_monthly_you * 12 * inflation_factor
        if age_you >= params.ss_claim_age_you
        else 0.0
    )
    ss_spouse = (
        params.ss_monthly_spouse * 12 * inflation_factor
        if age_spouse >= params.ss_claim_age_spouse
        else 0.0
    )
    return ss_you, ss_spouse


def _target_bracket_ceiling(
    target_bracket_str: str | None,
    filing_status: str,
    inflation_factor: float,
) -> tuple[float | None, float | None]:
    if not target_bracket_str:
        return None, None
    from backend.engines.tax import (
        MFJ_BRACKETS_2024,
        SINGLE_BRACKETS_2024,
        _inflate_brackets,
    )

    brackets = MFJ_BRACKETS_2024 if filing_status == "mfj" else SINGLE_BRACKETS_2024
    inflated = _inflate_brackets(brackets, inflation_factor)
    rate_str = target_bracket_str.strip().rstrip("%")
    try:
        target_rate = float(rate_str) / 100.0
    except ValueError:
        return None, None
    for upper, rate in inflated:
        if abs(rate - target_rate) < 0.001:
            return target_rate, upper
    return None, None


def project_one_year(
    year: int,
    age_you: int,
    age_spouse: int,
    accounts: list[AccountState],
    params: ScenarioParams,
    prior_year_magi: float,
    cumulative_inflation: float,
    is_retired_you: bool,
    is_retired_spouse: bool,
    first_death_year: int | None,
) -> ProjectionYear:
    """Simulate a single year of retirement."""
    inflation = cumulative_inflation

    # Capture pre-growth 401k balances before returns are applied.
    # IRS RMDs are based on December 31 balance of the prior year, which in
    # a year-by-year simulation corresponds to the beginning-of-year balance.
    pretax_pre_growth: dict[str, float] = {
        f"401k_{acct.owner}": acct.balance
        for acct in accounts
        if acct.account_type == "401k"
    }

    # 1. Apply investment returns
    blended = _blended_return(params)
    for acct in accounts:
        if acct.account_type not in ("nqdc", "pension", "real_estate"):
            acct.balance = acct.balance * (1.0 + blended)

    # 1b. Add annual contributions — per person, stops at their own retirement
    for acct in accounts:
        if acct.account_type in ("nqdc", "pension", "real_estate"):
            continue
        if acct.owner == "you" and not is_retired_you:
            acct.balance += acct.annual_contribution
        elif acct.owner == "spouse" and not is_retired_spouse:
            acct.balance += acct.annual_contribution

    # 2. NQDC payout
    nqdc_income = _get_nqdc_payout(year, params)

    # 3. Pension income
    pension_annual = 0.0
    if params.pension_start_age_you > 0 and age_you >= params.pension_start_age_you:
        pension_annual = params.pension_monthly_you * 12 * inflation

    # 4. Rental income
    rental_annual = params.rental_annual_income * inflation

    # 5. Social Security
    ss_you_annual, ss_spouse_annual = _get_ss_income(
        age_you, age_spouse, params, inflation
    )

    # 6. Spending — household spending starts when either spouse retires
    either_retired = is_retired_you or is_retired_spouse
    spending = _get_spending(age_you, params, inflation) if either_retired else 0.0

    # 7. Healthcare — needed when either person is retired and under 65
    needs_healthcare = (is_retired_you and age_you < 65) or (
        is_retired_spouse and age_spouse > 0 and age_spouse < 65
    )
    healthcare_annual = (
        params.healthcare_monthly_pre_medicare * 12 * inflation
        if needs_healthcare
        else 0.0
    )

    # 8. RMDs (mandatory) — each account uses its owner's age (SECURE 2.0, age 73+).
    # Use the pre-growth balance captured above; IRS divisors apply to prior-year balance.
    rmd_income: dict[str, float] = {}
    for acct in accounts:
        if acct.account_type == "401k":
            owner_age = age_you if acct.owner == "you" else age_spouse
            key = f"401k_{acct.owner}"
            prior_balance = pretax_pre_growth.get(key, acct.balance)
            rmd = calculate_rmd(prior_year_balance=prior_balance, age=owner_age)
            if rmd > 0:
                rmd_income[key] = rmd_income.get(key, 0.0) + rmd
                acct.balance = max(0.0, acct.balance - rmd)

    total_rmd = sum(rmd_income.values())

    # 9. Compute discretionary gap
    guaranteed_income = (
        nqdc_income
        + pension_annual
        + rental_annual
        + ss_you_annual
        + ss_spouse_annual
        + total_rmd
    )
    tax_estimate = max(0.0, (spending + healthcare_annual) * 0.20)
    discretionary_gap = max(
        0.0,
        spending + healthcare_annual + tax_estimate - guaranteed_income,
    )

    # 10. Withdrawal Optimizer
    target_rate, target_ceiling = _target_bracket_ceiling(
        params.roth_conversion_target_bracket,
        params.filing_status,
        inflation,
    )
    # RMDs already taken in step 8 above; pass 0 so the optimizer skips its own Step 0.
    prior_pretax_balance = 0.0

    wi = WithdrawalInput(
        required_amount=discretionary_gap,
        account_states=accounts,
        age_you=age_you,
        age_spouse=age_spouse,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=guaranteed_income,
        filing_status=params.filing_status,
        healthcare_amount=healthcare_annual,
        roth_conversion_enabled=params.roth_conversion_enabled,
        target_bracket_rate=target_rate,
        target_bracket_ceiling=target_ceiling,
        current_year=year,
        prior_year_pretax_balance=prior_pretax_balance,
    )
    wr: WithdrawalResult = optimize_withdrawals(wi)

    # Roth conversion is passed separately to TaxInput — do not include here.
    ordinary_from_withdrawals = wr.withdrawals_by_account.get("401k", 0.0)
    ltcg_income = wr.withdrawals_by_account.get("brokerage", 0.0)

    total_ordinary = (
        nqdc_income
        + pension_annual
        + rental_annual
        + total_rmd
        + ordinary_from_withdrawals
    )

    retirement_income_you = (
        pension_annual + total_rmd + wr.withdrawals_by_account.get("401k", 0.0)
    )
    # Spouse's qualifying DE retirement income: their own RMD.
    # Discretionary 401k withdrawals are pooled by the optimizer and can't be
    # split per owner, so only the attributable RMD portion is tracked here.
    retirement_income_spouse = rmd_income.get("401k_spouse", 0.0)

    # 11. Tax Engine
    ti = TaxInput(
        filing_status=params.filing_status,
        age_you=age_you,
        age_spouse=age_spouse,
        ordinary_income=total_ordinary,
        ss_income_you=ss_you_annual,
        ss_income_spouse=ss_spouse_annual,
        ltcg_income=ltcg_income,
        roth_conversion=wr.roth_conversion_amount,
        retirement_income_you=retirement_income_you,
        retirement_income_spouse=retirement_income_spouse,
        prior_year_magi=prior_year_magi,
        inflation_factor=inflation,
    )
    tax_result: TaxResult = calculate_taxes(ti)

    # 12. Assemble ProjectionYear
    # Sum balances by account_type (aggregating both spouses' same-type accounts)
    balances: dict[str, float] = {}
    for a in accounts:
        balances[a.account_type] = balances.get(a.account_type, 0.0) + a.balance
    balances = {k: round(v, 2) for k, v in balances.items()}
    # Total from all individual accounts (not the deduped dict)
    portfolio_balance = round(sum(a.balance for a in accounts), 2)

    income_by_source = {
        "ss_you": round(ss_you_annual, 2),
        "ss_spouse": round(ss_spouse_annual, 2),
        "nqdc": round(nqdc_income, 2),
        "pension": round(pension_annual, 2),
        "rental": round(rental_annual, 2),
        "rmd": round(total_rmd, 2),
        "401k_withdrawal": round(wr.withdrawals_by_account.get("401k", 0.0), 2),
        "roth_withdrawal": round(wr.withdrawals_by_account.get("roth_ira", 0.0), 2),
        "brokerage_withdrawal": round(ltcg_income, 2),
        "hsa_withdrawal": round(wr.withdrawals_by_account.get("hsa", 0.0), 2),
        "roth_conversion": round(wr.roth_conversion_amount, 2),
    }

    return ProjectionYear(
        year=year,
        age_you=age_you,
        age_spouse=age_spouse,
        portfolio_balance=round(portfolio_balance, 2),
        balances_by_account=balances,
        gross_income=round(tax_result.gross_income, 2),
        income_by_source=income_by_source,
        federal_tax=round(tax_result.federal_total, 2),
        state_tax=round(tax_result.state_tax, 2),
        effective_rate=round(tax_result.effective_rate, 4),
        marginal_rate=round(tax_result.marginal_rate, 4),
        roth_conversion_amount=round(wr.roth_conversion_amount, 2),
        withdrawal_notes=wr.notes + tax_result.notes,
        early_withdrawal_penalty=round(wr.early_withdrawal_penalty, 2),
        irmaa_annual=round(tax_result.irmaa_annual, 2),
    )


def run_projection(
    start_year: int,
    age_you_at_start: int,
    age_spouse_at_start: int,
    accounts: list[AccountState],
    params: ScenarioParams,
) -> list[ProjectionYear]:
    """Run a full year-by-year projection from start_year through life expectancy.

    Handles death event: switches filing status, adjusts survivor SS.
    """
    death_year_you = start_year + (params.life_expectancy_you - age_you_at_start)
    death_year_spouse = start_year + (
        params.life_expectancy_spouse - age_spouse_at_start
    )
    end_year = max(death_year_you, death_year_spouse)

    current_accounts = copy.deepcopy(accounts)

    results: list[ProjectionYear] = []
    prior_year_magi = 0.0
    cumulative_inflation = 1.0
    current_filing_status = params.filing_status
    first_death_year: int | None = None

    retirement_year_you = start_year + (params.retirement_age_you - age_you_at_start)
    retirement_year_spouse = start_year + (
        params.retirement_age_spouse - age_spouse_at_start
    )

    ss_monthly_you = params.ss_monthly_you
    ss_monthly_spouse = params.ss_monthly_spouse

    for year in range(start_year, end_year + 1):
        age_you = age_you_at_start + (year - start_year)
        age_spouse = age_spouse_at_start + (year - start_year)
        is_retired_you = year >= retirement_year_you
        is_retired_spouse = year >= retirement_year_spouse

        # Death event — check if a spouse has reached life expectancy this year
        if first_death_year is None:
            if age_you >= params.life_expectancy_you:
                first_death_year = year
                current_filing_status = "single"
                ss_monthly_spouse = max(ss_monthly_spouse, ss_monthly_you)
                ss_monthly_you = 0.0
            elif age_spouse >= params.life_expectancy_spouse:
                first_death_year = year
                current_filing_status = "single"
                ss_monthly_you = max(ss_monthly_you, ss_monthly_spouse)
                ss_monthly_spouse = 0.0

        # Stop after both spouses have reached life expectancy
        if (
            age_you > params.life_expectancy_you
            and age_spouse > params.life_expectancy_spouse
        ):
            break

        year_params = copy.copy(params)
        year_params.filing_status = current_filing_status
        year_params.ss_monthly_you = ss_monthly_you
        year_params.ss_monthly_spouse = ss_monthly_spouse

        py = project_one_year(
            year=year,
            age_you=age_you,
            age_spouse=age_spouse,
            accounts=current_accounts,
            params=year_params,
            prior_year_magi=prior_year_magi,
            cumulative_inflation=cumulative_inflation,
            is_retired_you=is_retired_you,
            is_retired_spouse=is_retired_spouse,
            first_death_year=first_death_year,
        )
        results.append(py)

        prior_year_magi = py.gross_income
        cumulative_inflation *= 1.0 + params.inflation_rate

    return results
