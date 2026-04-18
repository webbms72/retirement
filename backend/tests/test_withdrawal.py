"""Tests for the Withdrawal Optimizer — Task 7 (ordering + Rule of 55)."""

from __future__ import annotations

import pytest

from backend.engines.withdrawal import (
    AccountState,
    WithdrawalInput,
    optimize_withdrawals,
)


def _default_accounts(
    k401=500_000.0,
    roth=150_000.0,
    brokerage=200_000.0,
    hsa=40_000.0,
) -> list[AccountState]:
    return [
        AccountState(
            account_type="401k",
            balance=k401,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=False,
        ),
        AccountState(
            account_type="roth_ira",
            balance=roth,
            basis=roth,
            owner="you",
            roth_conversion_cohorts={},
        ),
        AccountState(
            account_type="brokerage", balance=brokerage, basis=100_000.0, owner="you"
        ),
        AccountState(account_type="hsa", balance=hsa, basis=0.0, owner="you"),
    ]


def test_zero_required_amount():
    wi = WithdrawalInput(
        required_amount=0.0,
        account_states=_default_accounts(),
        age_you=58,
        age_spouse=56,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=80_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.total_withdrawn == pytest.approx(0.0, abs=0.01)
    assert all(v == 0.0 for v in result.withdrawals_by_account.values())


def test_brokerage_first_when_0pct_ltcg_available():
    wi = WithdrawalInput(
        required_amount=20_000.0,
        account_states=_default_accounts(),
        age_you=58,
        age_spouse=56,
        current_marginal_rate=0.12,
        current_ordinary_taxable_income=40_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.withdrawals_by_account.get("brokerage", 0.0) == pytest.approx(
        20_000.0, abs=1.0
    )
    assert result.withdrawals_by_account.get("401k", 0.0) == 0.0
    assert result.withdrawals_by_account.get("roth_ira", 0.0) == 0.0


def test_roth_drawn_last():
    wi = WithdrawalInput(
        required_amount=400_000.0,
        account_states=_default_accounts(
            k401=200_000.0, brokerage=100_000.0, roth=150_000.0
        ),
        age_you=62,
        age_spouse=60,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    brokerage_amount = result.withdrawals_by_account.get("brokerage", 0.0)
    k401_amount = result.withdrawals_by_account.get("401k", 0.0)
    roth_amount = result.withdrawals_by_account.get("roth_ira", 0.0)
    assert brokerage_amount == pytest.approx(100_000.0, abs=1.0)
    assert k401_amount == pytest.approx(200_000.0, abs=1.0)
    assert roth_amount > 0


def test_hsa_covers_healthcare_first():
    wi = WithdrawalInput(
        required_amount=30_000.0,
        account_states=_default_accounts(hsa=40_000.0),
        age_you=60,
        age_spouse=58,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=80_000.0,
        filing_status="mfj",
        healthcare_amount=10_000.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.withdrawals_by_account.get("hsa", 0.0) == pytest.approx(
        10_000.0, abs=1.0
    )
    assert "HSA" in " ".join(result.notes)


def test_no_penalty_with_rule_of_55():
    accounts = [
        AccountState(
            account_type="401k",
            balance=500_000.0,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=True,
        ),
        AccountState(account_type="roth_ira", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="brokerage", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="hsa", balance=0.0, basis=0.0, owner="you"),
    ]
    wi = WithdrawalInput(
        required_amount=50_000.0,
        account_states=accounts,
        age_you=57,
        age_spouse=55,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.early_withdrawal_penalty == pytest.approx(0.0, abs=0.01)
    assert result.withdrawals_by_account.get("401k", 0.0) == pytest.approx(
        50_000.0, abs=1.0
    )


def test_penalty_applies_without_rule_of_55():
    accounts = [
        AccountState(
            account_type="401k",
            balance=500_000.0,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=False,
        ),
        AccountState(account_type="roth_ira", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="brokerage", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="hsa", balance=0.0, basis=0.0, owner="you"),
    ]
    wi = WithdrawalInput(
        required_amount=50_000.0,
        account_states=accounts,
        age_you=57,
        age_spouse=55,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.early_withdrawal_penalty == pytest.approx(
        result.withdrawals_by_account.get("401k", 0.0) * 0.10, abs=1.0
    )


def test_no_penalty_after_59_half():
    accounts = [
        AccountState(
            account_type="401k",
            balance=500_000.0,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=False,
        ),
        AccountState(account_type="roth_ira", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="brokerage", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="hsa", balance=0.0, basis=0.0, owner="you"),
    ]
    wi = WithdrawalInput(
        required_amount=50_000.0,
        account_states=accounts,
        age_you=60,
        age_spouse=58,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.early_withdrawal_penalty == 0.0


# ── RMD Tests (Task 8) ────────────────────────────────────────────────────────


def test_rmd_age_73_calculation():
    """Age 73 with $500,000 pre-tax balance → RMD = $500,000 / 26.5 = $18,867.92."""
    from backend.engines.withdrawal import calculate_rmd

    result = calculate_rmd(prior_year_balance=500_000.0, age=73)
    assert result == pytest.approx(18_867.92, abs=1.0)


def test_rmd_age_75():
    """Age 75, $400,000 balance → RMD = $400,000 / 24.6 = $16,260.16."""
    from backend.engines.withdrawal import calculate_rmd

    result = calculate_rmd(prior_year_balance=400_000.0, age=75)
    assert result == pytest.approx(16_260.16, abs=1.0)


def test_rmd_age_80():
    """Age 80, $600,000 → RMD = $600,000 / 20.2 = $29,702.97."""
    from backend.engines.withdrawal import calculate_rmd

    result = calculate_rmd(prior_year_balance=600_000.0, age=80)
    assert result == pytest.approx(29_702.97, abs=1.0)


def test_rmd_below_73_returns_zero():
    """No RMD before age 73 (SECURE 2.0)."""
    from backend.engines.withdrawal import calculate_rmd

    result = calculate_rmd(prior_year_balance=1_000_000.0, age=72)
    assert result == 0.0


def test_rmd_age_95():
    """Age 95, $200,000 → RMD = $200,000 / 8.9 = $22,471.91."""
    from backend.engines.withdrawal import calculate_rmd

    result = calculate_rmd(prior_year_balance=200_000.0, age=95)
    assert result == pytest.approx(22_471.91, abs=1.0)


# ── Roth 5-year rule tests ────────────────────────────────────────────────────


def test_roth_conversion_seasoned_accessible():
    """Conversion from 2025 is accessible penalty-free in 2030 (5 years)."""
    from backend.engines.withdrawal import is_roth_conversion_accessible

    result = is_roth_conversion_accessible(
        conversion_year=2025, current_year=2030, age_you=58
    )
    assert result is True


def test_roth_conversion_not_yet_seasoned():
    """Conversion from 2028 is NOT accessible in 2030 (only 2 years)."""
    from backend.engines.withdrawal import is_roth_conversion_accessible

    result = is_roth_conversion_accessible(
        conversion_year=2028, current_year=2030, age_you=58
    )
    assert result is False


def test_roth_5_year_rule_bypassed_after_59_half():
    """After age 60, 5-year rule no longer blocks access."""
    from backend.engines.withdrawal import is_roth_conversion_accessible

    result = is_roth_conversion_accessible(
        conversion_year=2029, current_year=2030, age_you=61
    )
    assert result is True


def test_rmd_included_before_discretionary_gap():
    """When age 73+, RMD is taken first from 401k; optimizer covers remaining gap."""
    from backend.engines.withdrawal import (
        AccountState,
        WithdrawalInput,
        optimize_withdrawals,
    )

    accounts = [
        AccountState(
            account_type="401k",
            balance=600_000.0,
            basis=0.0,
            owner="you",
            is_rule_of_55_eligible=False,
        ),
        AccountState(
            account_type="roth_ira", balance=100_000.0, basis=100_000.0, owner="you"
        ),
        AccountState(
            account_type="brokerage", balance=50_000.0, basis=25_000.0, owner="you"
        ),
        AccountState(account_type="hsa", balance=20_000.0, basis=0.0, owner="you"),
    ]
    wi = WithdrawalInput(
        required_amount=60_000.0,
        account_states=accounts,
        age_you=73,
        age_spouse=71,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2045,
        prior_year_pretax_balance=600_000.0,
    )
    result = optimize_withdrawals(wi)
    # RMD = 600,000 / 26.5 = 22,641.51 — taken from 401k automatically
    rmd = result.rmd_taken.get("401k", 0.0)
    assert rmd == pytest.approx(22_641.51, abs=1.0)
    assert result.total_withdrawn >= 60_000.0 - 0.01
