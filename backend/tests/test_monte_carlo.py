"""Tests for the Monte Carlo Engine — Task 12."""

from __future__ import annotations

import pytest

from backend.engines.monte_carlo import (
    MCInput,
    run_monte_carlo,
)
from backend.engines.projection import ScenarioParams


def _make_mc_input(n_simulations: int = 100) -> MCInput:
    params = ScenarioParams(
        retirement_age_you=57,
        retirement_age_spouse=57,
        annual_spending=120_000.0,
        spending_glide_path={},
        ss_claim_age_you=67,
        ss_claim_age_spouse=67,
        ss_monthly_you=3_100.0,
        ss_monthly_spouse=2_000.0,
        withdrawal_strategy="optimized",
        manual_withdrawal_order=None,
        roth_conversion_enabled=False,
        roth_conversion_target_bracket=None,
        healthcare_monthly_pre_medicare=2_200.0,
        stock_allocation=0.65,
        expected_return_stocks=0.07,
        expected_return_bonds=0.04,
        inflation_rate=0.025,
        pension_monthly_you=0.0,
        pension_start_age_you=0,
        rental_annual_income=0.0,
        nqdc_schedule=[],
        life_expectancy_you=85,
        life_expectancy_spouse=87,
        dob_year_you=1972,
        dob_year_spouse=1974,
        base_year=2024,
        filing_status="mfj",
        state="DE",
    )
    from backend.engines.withdrawal import AccountState

    accounts = [
        AccountState(
            account_type="401k",
            balance=800_000.0,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=True,
        ),
        AccountState(
            account_type="roth_ira",
            balance=120_000.0,
            basis=120_000.0,
            owner="you",
        ),
        AccountState(
            account_type="brokerage",
            balance=200_000.0,
            basis=100_000.0,
            owner="you",
        ),
        AccountState(account_type="hsa", balance=40_000.0, basis=0.0, owner="you"),
    ]
    return MCInput(
        scenario_params=params,
        accounts=accounts,
        start_year=2026,
        age_you_at_start=54,
        age_spouse_at_start=52,
        n_simulations=n_simulations,
        random_seed=42,
    )


def test_mc_returns_correct_simulation_count():
    result = run_monte_carlo(_make_mc_input(100))
    assert result.num_simulations == 100


def test_mc_survival_rate_between_0_and_1():
    result = run_monte_carlo(_make_mc_input(100))
    assert 0.0 <= result.survival_rate <= 1.0


def test_mc_percentile_bands_exist():
    result = run_monte_carlo(_make_mc_input(100))
    assert len(result.percentile_10) > 0
    assert len(result.percentile_25) > 0
    assert len(result.percentile_50) > 0
    assert len(result.percentile_75) > 0
    assert len(result.percentile_90) > 0


def test_mc_percentile_ordering():
    result = run_monte_carlo(_make_mc_input(100))
    years = sorted(result.percentile_10.keys())
    for yr in years:
        p10 = result.percentile_10[yr]
        p25 = result.percentile_25[yr]
        p50 = result.percentile_50[yr]
        p75 = result.percentile_75[yr]
        p90 = result.percentile_90[yr]
        assert (
            p10 <= p25 <= p50 <= p75 <= p90
        ), f"Year {yr}: ordering violated ({p10:.0f}, {p25:.0f}, {p50:.0f}, {p75:.0f}, {p90:.0f})"


def test_mc_sensitivity_has_six_variables():
    result = run_monte_carlo(_make_mc_input(100))
    expected_keys = {
        "retirement_age",
        "annual_spending",
        "ss_claim_age",
        "expected_return_stocks",
        "inflation_rate",
        "stock_allocation",
    }
    assert set(result.sensitivity.keys()) == expected_keys


def test_mc_deterministic_with_seed():
    result_a = run_monte_carlo(_make_mc_input(50))
    result_b = run_monte_carlo(_make_mc_input(50))
    assert result_a.survival_rate == pytest.approx(result_b.survival_rate, abs=0.001)


def test_mc_higher_spending_reduces_survival():
    import copy

    inp_base = _make_mc_input(100)
    inp_high = _make_mc_input(100)
    inp_high.scenario_params = copy.deepcopy(inp_base.scenario_params)
    inp_high.scenario_params.annual_spending = 200_000.0

    result_base = run_monte_carlo(inp_base)
    result_high = run_monte_carlo(inp_high)

    assert result_high.survival_rate <= result_base.survival_rate + 0.05
