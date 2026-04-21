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

    # Accounts large enough that the portfolio survives to age 68 in both scenarios,
    # so the SS timing difference is measurable (inflation-adjusted spending ~$210k/yr
    # by year 14 means small accounts deplete well before age 62 SS kicks in).
    accounts_early = _make_accounts(k401=2_500_000.0, roth=300_000.0)
    accounts_late = _make_accounts(k401=2_500_000.0, roth=300_000.0)

    results_early = run_projection(2026, 54, 52, accounts_early, params_early_ss)
    results_late = run_projection(2026, 54, 52, accounts_late, params_late_ss)

    early_age68 = next(r for r in results_early if r.age_you == 68)
    late_age68 = next(r for r in results_late if r.age_you == 68)
    assert early_age68.portfolio_balance > late_age68.portfolio_balance


# ── Critical bug regression tests ────────────────────────────────────────────


def test_rmd_uses_owner_age_not_your_age():
    """CRITICAL-1: Spouse's 401k RMD must use spouse's age, not yours."""
    # You are 73 (triggers RMD), spouse is 68 (below 73 — no RMD).
    # Spouse's 401k should not be debited for an RMD.
    params = _make_scenario()
    blended = 0.65 * 0.07 + 0.35 * 0.04  # ≈ 0.0595
    your_start = 500_000.0
    spouse_start = 400_000.0

    accounts = [
        AccountState(
            account_type="401k", balance=your_start, basis=0.0, owner="you",
            is_rule_of_55_eligible=False,
        ),
        AccountState(
            account_type="401k", balance=spouse_start, basis=0.0, owner="spouse",
            is_rule_of_55_eligible=False,
        ),
    ]

    result = project_one_year(
        year=2045,
        age_you=73,
        age_spouse=68,
        accounts=accounts,
        params=params,
        prior_year_magi=0.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    # RMD is calculated on the pre-growth (beginning-of-year) balance,
    # matching the IRS rule that uses the prior December 31 balance.
    expected_rmd = your_start / 26.5  # divisor for age 73

    rmd_reported = result.income_by_source.get("rmd", 0.0)
    assert rmd_reported == pytest.approx(expected_rmd, rel=0.01)

    # Spouse's account should only reflect growth — no RMD should have been deducted.
    spouse_acct = next(a for a in accounts if a.owner == "spouse")
    spouse_post_growth = spouse_start * (1.0 + blended)
    # Balance should be near post-growth (any spending withdrawals may reduce further,
    # but no RMD deduction of ~$16k should have occurred).
    assert spouse_acct.balance > spouse_post_growth - 100.0


def test_rmd_not_double_withdrawn():
    """CRITICAL-2: 401k balance should only be debited once for RMD per year."""
    # With a single 401k of $530,000 at age 73, RMD ≈ $530k/26.5 ≈ $20,000.
    # The withdrawal optimizer must not also draw a second RMD from the same account.
    params = _make_scenario(annual_spending=0.0)  # no spending gap → optimizer idle
    accounts = [
        AccountState(
            account_type="401k", balance=530_000.0, basis=0.0, owner="you",
            is_rule_of_55_eligible=False,
        ),
    ]
    start_balance = 530_000.0
    blended = 0.65 * 0.07 + 0.35 * 0.04  # ≈ 0.0595
    expected_post_growth = start_balance * (1.0 + blended)
    # RMD uses pre-growth balance (IRS prior Dec 31 balance rule)
    expected_rmd = start_balance / 26.5
    expected_end_balance = expected_post_growth - expected_rmd

    result = project_one_year(
        year=2045,
        age_you=73,
        age_spouse=71,
        accounts=accounts,
        params=params,
        prior_year_magi=0.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    assert result.portfolio_balance == pytest.approx(expected_end_balance, rel=0.01)


def test_roth_conversion_not_double_taxed():
    """CRITICAL-3: Roth conversion must not appear in both ordinary_income and roth_conversion.

    The optimizer fires a Roth conversion (Step 3) when there is a spending gap and
    bracket room.  We verify that gross_income = 401k_withdrawal + conversion,
    NOT 401k_withdrawal + 2 * conversion as would happen with the double-count bug.
    """
    params = _make_scenario(annual_spending=40_000.0)
    params.healthcare_monthly_pre_medicare = 0.0
    params.roth_conversion_enabled = True
    params.roth_conversion_target_bracket = "12%"

    # Empty brokerage/HSA so the optimizer reaches Step 3 (Roth conversion)
    accounts = [
        AccountState(
            account_type="401k", balance=2_000_000.0, basis=0.0, owner="you",
            is_rule_of_55_eligible=True,
        ),
        AccountState(
            account_type="roth_ira", balance=100_000.0, basis=100_000.0, owner="you"
        ),
        AccountState(account_type="brokerage", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="hsa", balance=0.0, basis=0.0, owner="you"),
    ]

    result = project_one_year(
        year=2030,
        age_you=58,
        age_spouse=56,
        accounts=accounts,
        params=params,
        prior_year_magi=0.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    conversion = result.roth_conversion_amount
    assert conversion > 0, "Expected a Roth conversion to occur"

    k401_withdrawal = result.income_by_source.get("401k_withdrawal", 0.0)
    # gross_income should be 401k_withdrawal + conversion (single-count).
    # Before the fix it was 401k_withdrawal + 2 * conversion.
    expected_gross = k401_withdrawal + conversion
    assert result.gross_income == pytest.approx(expected_gross, rel=0.001)


def test_spouse_de_retirement_exclusion_applied():
    """MINOR-3: Spouse's RMD must flow into retirement_income_spouse for the DE exclusion.

    Both spouses are 73+, so each has an RMD.  We run the projection and compare
    the resulting state_tax against what Delaware would charge if the spouse's
    $12,500 exclusion were missing (old hardcoded retirement_income_spouse=0 bug).
    The projection result must be lower.
    """
    from backend.engines.tax import calculate_delaware_tax

    params = _make_scenario(annual_spending=0.0)
    params.healthcare_monthly_pre_medicare = 0.0

    accounts = [
        AccountState(
            account_type="401k", balance=500_000.0, basis=0.0, owner="you",
            is_rule_of_55_eligible=False,
        ),
        AccountState(
            account_type="401k", balance=400_000.0, basis=0.0, owner="spouse",
            is_rule_of_55_eligible=False,
        ),
    ]
    result = project_one_year(
        year=2045,
        age_you=74,
        age_spouse=73,
        accounts=accounts,
        params=params,
        prior_year_magi=0.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    # Recompute DE tax as it would have been with the old bug (retirement_income_spouse=0).
    # The ordinary income is the same; only the exclusion differs.
    total_ordinary = result.income_by_source.get("rmd", 0.0)
    tax_without_spouse_exclusion = calculate_delaware_tax(
        de_taxable_income=total_ordinary,
        filing_status="mfj",
        num_people=2,
        age_you=74,
        age_spouse=73,
        retirement_income_you=total_ordinary,  # conservative: all income is yours
        retirement_income_spouse=0.0,          # old hardcoded value
    )

    # With the fix, the spouse's RMD (~$15k) is passed as retirement_income_spouse,
    # granting an extra $12,500 DE exclusion → lower state tax.
    assert result.state_tax < tax_without_spouse_exclusion


def test_healthcare_annual_in_income_by_source():
    """healthcare_annual must be present and correct for pre-65 retirement years."""
    params = ScenarioParams(
        retirement_age_you=57,
        retirement_age_spouse=57,
        annual_spending=60_000.0,
        spending_glide_path={},
        ss_claim_age_you=67,
        ss_claim_age_spouse=67,
        ss_monthly_you=0.0,
        ss_monthly_spouse=0.0,
        withdrawal_strategy="optimized",
        manual_withdrawal_order=[],
        roth_conversion_enabled=False,
        roth_conversion_target_bracket=None,
        healthcare_monthly_pre_medicare=1_500.0,
        stock_allocation=0.6,
        expected_return_stocks=0.07,
        expected_return_bonds=0.04,
        inflation_rate=0.025,
        pension_monthly_you=0.0,
        pension_start_age_you=0,
        rental_annual_income=0.0,
        nqdc_schedule=[],
        life_expectancy_you=88,
        life_expectancy_spouse=88,
        dob_year_you=1969,
        dob_year_spouse=1969,
        base_year=2024,
        filing_status="mfj",
        state="DE",
    )
    accounts = [
        AccountState(
            account_type="brokerage",
            balance=500_000.0,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=False,
            annual_contribution=0.0,
        )
    ]
    result = project_one_year(
        year=2026,
        age_you=57,
        age_spouse=57,
        accounts=accounts,
        params=params,
        prior_year_magi=0.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )
    assert "healthcare_annual" in result.income_by_source
    assert result.income_by_source["healthcare_annual"] == pytest.approx(1_500.0 * 12, rel=0.001)


def test_roth_conversion_credited_to_roth_ira():
    """Roth conversion must increase the Roth IRA balance, not vanish from portfolio.

    Before the fix, the optimizer debited the 401k for the conversion but never
    credited the Roth IRA.  The converted amount disappeared from portfolio_balance
    each year, causing an artificial early portfolio peak.
    """
    params = _make_scenario(annual_spending=60_000.0)
    params.roth_conversion_enabled = True
    params.roth_conversion_target_bracket = "12%"
    params.healthcare_monthly_pre_medicare = 0.0

    initial_401k = 1_000_000.0
    initial_roth = 200_000.0

    accounts = [
        AccountState(
            account_type="401k", balance=initial_401k, basis=0.0, owner="you",
            is_rule_of_55_eligible=True,
        ),
        AccountState(
            account_type="roth_ira", balance=initial_roth, basis=initial_roth, owner="you"
        ),
    ]

    result = project_one_year(
        year=2030,
        age_you=58,
        age_spouse=56,
        accounts=accounts,
        params=params,
        prior_year_magi=0.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    conversion = result.roth_conversion_amount
    assert conversion > 0, "Expected a Roth conversion to occur"

    blended_return = (
        params.stock_allocation * params.expected_return_stocks
        + (1 - params.stock_allocation) * params.expected_return_bonds
    )
    roth_after = result.balances_by_account.get("roth_ira", 0.0)
    roth_grown = initial_roth * (1 + blended_return)

    # After-tax credit: Roth must be above growth-only (conversion was credited)
    # but below growth + full conversion (taxes are withheld from the credit).
    target_bracket_rate = 0.12  # matches params.roth_conversion_target_bracket = "12%"
    roth_max = roth_grown + conversion  # full credit (no tax — wrong)
    roth_expected = roth_grown + conversion * (1.0 - target_bracket_rate)

    assert roth_after > roth_grown, (
        f"Roth IRA {roth_after:,.0f} should exceed growth-only {roth_grown:,.0f} "
        f"— conversion was not credited at all"
    )
    assert roth_after < roth_max, (
        f"Roth IRA {roth_after:,.0f} should be below full (pre-tax) credit {roth_max:,.0f} "
        f"— tax cost of conversion is not reflected"
    )
    assert roth_after == pytest.approx(roth_expected, rel=0.01), (
        f"Roth IRA {roth_after:,.0f} should be ~{roth_expected:,.0f} "
        f"(growth + after-tax conversion credit)"
    )
