"""Tests for the Projection Engine — Task 9 (single year step)."""

from __future__ import annotations

import pytest

from backend.engines.projection import (
    AccountState,
    ProjectionYear,
    ScenarioParams,
    project_one_year,
)


def _make_scenario(
    retirement_age_you: int = 57,
    retirement_age_spouse: int = 57,
    annual_spending: float = 120_000.0,
    ss_claim_age_you: int = 67,
    ss_claim_age_spouse: int = 67,
    stock_allocation: float = 0.65,
    expected_return_stocks: float = 0.07,
    expected_return_bonds: float = 0.04,
    inflation_rate: float = 0.025,
) -> ScenarioParams:
    return ScenarioParams(
        retirement_age_you=retirement_age_you,
        retirement_age_spouse=retirement_age_spouse,
        annual_spending=annual_spending,
        spending_glide_path={},
        ss_claim_age_you=ss_claim_age_you,
        ss_claim_age_spouse=ss_claim_age_spouse,
        ss_monthly_you=3_100.0,
        ss_monthly_spouse=2_000.0,
        withdrawal_strategy="optimized",
        manual_withdrawal_order=None,
        roth_conversion_enabled=False,
        roth_conversion_target_bracket=None,
        healthcare_monthly_pre_medicare=2_200.0,
        stock_allocation=stock_allocation,
        expected_return_stocks=expected_return_stocks,
        expected_return_bonds=expected_return_bonds,
        inflation_rate=inflation_rate,
        pension_monthly_you=0.0,
        pension_start_age_you=0,
        rental_annual_income=0.0,
        nqdc_schedule=[],
        life_expectancy_you=88,
        life_expectancy_spouse=90,
        dob_year_you=1972,
        dob_year_spouse=1974,
        base_year=2024,
        filing_status="mfj",
        state="DE",
    )


def _make_accounts(
    k401: float = 500_000.0,
    roth: float = 100_000.0,
    brokerage: float = 150_000.0,
    hsa: float = 30_000.0,
) -> list[AccountState]:
    return [
        AccountState(
            account_type="401k",
            balance=k401,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=True,
        ),
        AccountState(account_type="roth_ira", balance=roth, basis=roth, owner="you"),
        AccountState(
            account_type="brokerage", balance=brokerage, basis=75_000.0, owner="you"
        ),
        AccountState(account_type="hsa", balance=hsa, basis=0.0, owner="you"),
    ]


def test_project_one_year_accounts_grow():
    """With no withdrawals needed (zero spending), all account balances grow."""
    params = _make_scenario(annual_spending=0.0, retirement_age_you=57)
    accounts = _make_accounts()
    initial_total = sum(a.balance for a in accounts)

    result = project_one_year(
        year=2030,
        age_you=58,
        age_spouse=56,
        accounts=accounts,
        params=params,
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    assert isinstance(result, ProjectionYear)
    assert result.portfolio_balance > initial_total


def test_project_one_year_spending_reduces_portfolio():
    """Annual spending draws down the portfolio compared to zero-spend baseline."""
    params_spend = _make_scenario(annual_spending=120_000.0)
    params_zero = _make_scenario(annual_spending=0.0)

    accounts_spend = _make_accounts()
    accounts_zero = _make_accounts()

    result_spend = project_one_year(
        year=2030,
        age_you=58,
        age_spouse=56,
        accounts=accounts_spend,
        params=params_spend,
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )
    result_zero = project_one_year(
        year=2030,
        age_you=58,
        age_spouse=56,
        accounts=accounts_zero,
        params=params_zero,
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    assert result_spend.portfolio_balance < result_zero.portfolio_balance


def test_project_one_year_ss_income_starts_at_claim_age():
    """SS income appears in income_by_source only after ss_claim_age_you is reached."""
    params_before_ss = _make_scenario(ss_claim_age_you=67)
    params_after_ss = _make_scenario(ss_claim_age_you=67)

    # Age 65 — before SS
    result_before = project_one_year(
        year=2037,
        age_you=65,
        age_spouse=63,
        accounts=_make_accounts(),
        params=params_before_ss,
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )
    # Age 68 — after SS claim at 67
    result_after = project_one_year(
        year=2040,
        age_you=68,
        age_spouse=66,
        accounts=_make_accounts(),
        params=params_after_ss,
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    assert result_before.income_by_source.get("ss_you", 0.0) == 0.0
    assert result_after.income_by_source.get("ss_you", 0.0) > 0.0


def test_project_one_year_returns_correct_ages():
    """ProjectionYear should record the exact ages passed in."""
    result = project_one_year(
        year=2035,
        age_you=63,
        age_spouse=61,
        accounts=_make_accounts(),
        params=_make_scenario(),
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )
    assert result.year == 2035
    assert result.age_you == 63
    assert result.age_spouse == 61


def test_project_one_year_nqdc_schedule():
    """NQDC payout appears in income_by_source in the correct year."""
    params = _make_scenario()
    params.nqdc_schedule = [{"date": "2031-01-15", "amount": 50_000.0}]

    result_with_nqdc = project_one_year(
        year=2031,
        age_you=59,
        age_spouse=57,
        accounts=_make_accounts(),
        params=params,
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )
    result_without_nqdc = project_one_year(
        year=2030,
        age_you=58,
        age_spouse=56,
        accounts=_make_accounts(),
        params=params,
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    assert result_with_nqdc.income_by_source.get("nqdc", 0.0) == pytest.approx(
        50_000.0, abs=1.0
    )
    assert result_without_nqdc.income_by_source.get("nqdc", 0.0) == 0.0


# ── Multi-year simulation tests (Task 10) ─────────────────────────────────────


def test_run_projection_length():
    """Projection runs from start year through longer life expectancy."""
    from backend.engines.projection import run_projection

    params = _make_scenario()
    accounts = _make_accounts()
    results = run_projection(
        start_year=2026,
        age_you_at_start=54,
        age_spouse_at_start=52,
        accounts=accounts,
        params=params,
    )

    years = [r.year for r in results]
    assert years[0] == 2026
    assert years[-1] == 2064  # spouse life exp 90, born 1974, dies 2064
    assert len(results) == 2064 - 2026 + 1


def test_run_projection_portfolio_can_deplete():
    """With very high spending, portfolio eventually reaches near zero."""
    from backend.engines.projection import run_projection

    params = _make_scenario(annual_spending=300_000.0)
    accounts = _make_accounts(
        k401=200_000.0, roth=50_000.0, brokerage=50_000.0, hsa=10_000.0
    )

    results = run_projection(
        start_year=2026,
        age_you_at_start=54,
        age_spouse_at_start=52,
        accounts=accounts,
        params=params,
    )

    final_balance = results[-1].portfolio_balance
    assert final_balance < 100_000.0


def test_run_projection_filing_status_switches_after_death():
    """After first death, projection continues through survivor's life expectancy."""
    from backend.engines.projection import run_projection

    params = _make_scenario()
    params.life_expectancy_you = 70
    params.life_expectancy_spouse = 90

    accounts = _make_accounts()
    results = run_projection(
        start_year=2026,
        age_you_at_start=54,
        age_spouse_at_start=52,
        accounts=accounts,
        params=params,
    )

    year_of_death = 2026 + (70 - 54)  # = 2042
    after_death = next((r for r in results if r.year == year_of_death + 1), None)

    assert after_death is not None
    assert after_death.portfolio_balance >= 0


def test_run_projection_ss_increases_portfolio_stability():
    """Earlier SS claim produces higher portfolio balance by age 68 vs delayed claim."""
    from backend.engines.projection import run_projection

    params_early_ss = _make_scenario(ss_claim_age_you=62, ss_claim_age_spouse=62)
    params_late_ss = _make_scenario(ss_claim_age_you=70, ss_claim_age_spouse=70)

    accounts_early = _make_accounts(k401=400_000.0, roth=80_000.0)
    accounts_late = _make_accounts(k401=400_000.0, roth=80_000.0)

    results_early = run_projection(2026, 54, 52, accounts_early, params_early_ss)
    results_late = run_projection(2026, 54, 52, accounts_late, params_late_ss)

    early_age68 = next(r for r in results_early if r.age_you == 68)
    late_age68 = next(r for r in results_late if r.age_you == 68)
    assert early_age68.portfolio_balance > late_age68.portfolio_balance
