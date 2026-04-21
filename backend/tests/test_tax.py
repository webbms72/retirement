"""Tests for the Tax Engine — federal ordinary income tax (Task 4)."""

from __future__ import annotations

import pytest

from backend.engines.tax import (
    calculate_delaware_tax,
    calculate_federal_ordinary_income_tax,
)


# ── Basic MFJ cases ───────────────────────────────────────────────────────────


def test_mfj_zero_income():
    """Zero taxable income → zero tax."""
    result = calculate_federal_ordinary_income_tax(
        taxable_income=0.0, filing_status="mfj"
    )
    assert result == 0.0


def test_mfj_within_10pct_bracket():
    """$20,000 MFJ taxable income — entirely in 10% bracket."""
    # Tax = 20,000 * 0.10 = 2,000
    result = calculate_federal_ordinary_income_tax(
        taxable_income=20_000.0, filing_status="mfj"
    )
    assert result == pytest.approx(2_000.0, abs=1.0)


def test_mfj_spans_two_brackets():
    """$50,000 MFJ — spans 10% and 12% brackets.
    10%: $23,200 → $2,320
    12%: $26,800 → $3,216
    Total: $5,536
    """
    result = calculate_federal_ordinary_income_tax(
        taxable_income=50_000.0, filing_status="mfj"
    )
    assert result == pytest.approx(5_536.0, abs=1.0)


def test_mfj_six_figures():
    """$150,000 MFJ — spans 10%, 12%, 22% brackets.
    10%: $23,200 → $2,320
    12%: $71,100 → $8,532
    22%: $55,700 → $12,254
    Total: $23,106
    """
    result = calculate_federal_ordinary_income_tax(
        taxable_income=150_000.0, filing_status="mfj"
    )
    assert result == pytest.approx(23_106.0, abs=1.0)


def test_mfj_top_bracket():
    """$800,000 MFJ — reaches 37% bracket."""
    # 10%: 23,200 → 2,320
    # 12%: 71,100 → 8,532
    # 22%: 106,750 → 23,485
    # 24%: 182,850 → 43,884
    # 32%: 103,550 → 33,136
    # 35%: 243,750 → 85,312.50
    # 37%: 68,800 → 25,456
    # Total = 222,125.50
    result = calculate_federal_ordinary_income_tax(
        taxable_income=800_000.0, filing_status="mfj"
    )
    assert result == pytest.approx(222_125.50, abs=2.0)


# ── Single filer cases ────────────────────────────────────────────────────────


def test_single_within_10pct():
    """$10,000 single — entirely in 10% bracket."""
    result = calculate_federal_ordinary_income_tax(
        taxable_income=10_000.0, filing_status="single"
    )
    assert result == pytest.approx(1_000.0, abs=1.0)


def test_single_spans_two_brackets():
    """$30,000 single — spans 10% and 12%.
    10%: 11,600 → 1,160
    12%: 18,400 → 2,208
    Total: 3,368
    """
    result = calculate_federal_ordinary_income_tax(
        taxable_income=30_000.0, filing_status="single"
    )
    assert result == pytest.approx(3_368.0, abs=1.0)


# ── Standard deduction helper ─────────────────────────────────────────────────


def test_standard_deduction_mfj_under_65():
    from backend.engines.tax import get_standard_deduction

    assert (
        get_standard_deduction(filing_status="mfj", age_you=60, age_spouse=58)
        == 29_200.0
    )


def test_standard_deduction_mfj_both_65():
    from backend.engines.tax import get_standard_deduction

    # Base $29,200 + $1,550 * 2 = $32,300
    assert (
        get_standard_deduction(filing_status="mfj", age_you=66, age_spouse=66)
        == 32_300.0
    )


def test_standard_deduction_mfj_one_65():
    from backend.engines.tax import get_standard_deduction

    # Base $29,200 + $1,550 = $30,750
    assert (
        get_standard_deduction(filing_status="mfj", age_you=65, age_spouse=62)
        == 30_750.0
    )


def test_standard_deduction_single_under_65():
    from backend.engines.tax import get_standard_deduction

    assert (
        get_standard_deduction(filing_status="single", age_you=58, age_spouse=0)
        == 14_600.0
    )


def test_standard_deduction_single_65_plus():
    from backend.engines.tax import get_standard_deduction

    # $14,600 + $1,550 = $16,150
    assert (
        get_standard_deduction(filing_status="single", age_you=67, age_spouse=0)
        == 16_150.0
    )


# ── Delaware State Tax Tests (Task 5) ─────────────────────────────────────────


def test_de_zero_income():
    from backend.engines.tax import calculate_delaware_tax

    result = calculate_delaware_tax(
        de_taxable_income=0.0,
        filing_status="mfj",
        num_people=2,
    )
    assert result == 0.0


def test_de_below_standard_deduction():
    from backend.engines.tax import calculate_delaware_tax

    # MFJ standard deduction $6,500 + personal exemptions $220 = $6,720
    # Income $5,000 → taxable after deductions = 0
    result = calculate_delaware_tax(
        de_taxable_income=5_000.0,
        filing_status="mfj",
        num_people=2,
    )
    assert result == 0.0


def test_de_mfj_moderate_income():
    """$60,000 gross DE income for MFJ couple, both under 60 — no retirement exclusion.

    DE standard deduction: $6,500
    Personal exemptions: $110 * 2 = $220
    Taxable: $60,000 - $6,500 - $220 = $53,280

    Brackets on $53,280:
    0%  : $0–$2,000    → $0
    2.2%: $2,000–$5,000 = $3,000 → $66
    3.9%: $5,000–$10,000 = $5,000 → $195
    4.8%: $10,000–$20,000 = $10,000 → $480
    5.2%: $20,000–$25,000 = $5,000 → $260
    5.55%: $25,000–$53,280 = $28,280 → $1,569.54
    Total: $2,570.54
    """
    result = calculate_delaware_tax(
        de_taxable_income=60_000.0,
        filing_status="mfj",
        num_people=2,
        age_you=58,
        age_spouse=56,
        retirement_income_you=0.0,
        retirement_income_spouse=0.0,
    )
    assert result == pytest.approx(2_570.54, abs=2.0)


def test_de_retirement_exclusion_both_over_60():
    """MFJ couple both over 60 with $50,000 retirement income each.

    Exclusion: $12,500 per person = $25,000 total excluded.
    Gross DE income: $100,000
    After exclusion: $75,000
    DE standard deduction: $6,500
    Personal exemptions: $220
    Taxable: $68,280

    Brackets on $68,280:
    0%   : $2,000 → $0
    2.2% : $3,000 → $66
    3.9% : $5,000 → $195
    4.8% : $10,000 → $480
    5.2% : $5,000 → $260
    5.55%: $35,000 → $1,942.50
    6.6% : $8,280 → $546.48
    Total: $3,489.98
    """
    result = calculate_delaware_tax(
        de_taxable_income=100_000.0,
        filing_status="mfj",
        num_people=2,
        age_you=62,
        age_spouse=61,
        retirement_income_you=50_000.0,
        retirement_income_spouse=50_000.0,
    )
    assert result == pytest.approx(3_489.98, abs=2.0)


def test_de_single_filer():
    """Single filer, age 62, $40,000 income of which $30,000 is retirement.

    Retirement exclusion: min($30,000, $12,500) = $12,500
    After exclusion: $27,500
    DE standard deduction: $3,250
    Personal exemption: $110
    Taxable: $24,140

    Brackets:
    0%   : $2,000 → $0
    2.2% : $3,000 → $66
    3.9% : $5,000 → $195
    4.8% : $10,000 → $480
    5.2% : $4,140 → $215.28
    Total: $956.28
    """
    result = calculate_delaware_tax(
        de_taxable_income=40_000.0,
        filing_status="single",
        num_people=1,
        age_you=62,
        age_spouse=0,
        retirement_income_you=30_000.0,
        retirement_income_spouse=0.0,
    )
    assert result == pytest.approx(956.28, abs=2.0)


# ── SS Inclusion Tests (Task 6) ───────────────────────────────────────────────


def test_ss_inclusion_below_base_threshold():
    """Combined income below $32k MFJ → 0% SS included."""
    from backend.engines.tax import calculate_ss_inclusion

    # Combined income = other_income + (ss_gross / 2)
    # SS = $24,000/yr; other_income = $18,000 → combined = $18,000 + $12,000 = $30,000 < $32,000
    result = calculate_ss_inclusion(
        ss_gross=24_000.0, other_income=18_000.0, filing_status="mfj"
    )
    assert result == 0.0


def test_ss_inclusion_middle_tier_mfj():
    """Combined income between $32k–$44k MFJ → 50% rule applies."""
    from backend.engines.tax import calculate_ss_inclusion

    # SS = $20,000; other = $24,000 → combined = $24,000 + $10,000 = $34,000
    # In middle tier: taxable SS = min(0.50 * SS, 0.50 * (combined - $32,000))
    # = min($10,000, 0.50 * $2,000) = min($10,000, $1,000) = $1,000
    result = calculate_ss_inclusion(
        ss_gross=20_000.0, other_income=24_000.0, filing_status="mfj"
    )
    assert result == pytest.approx(1_000.0, abs=1.0)


def test_ss_inclusion_above_upper_threshold_mfj():
    """Combined income above $44k MFJ → up to 85% SS included."""
    from backend.engines.tax import calculate_ss_inclusion

    # SS = $36,000/yr; other_income = $60,000 → combined = $60,000 + $18,000 = $78,000
    # Above $44k → 85% of SS = $30,600
    result = calculate_ss_inclusion(
        ss_gross=36_000.0, other_income=60_000.0, filing_status="mfj"
    )
    assert result == pytest.approx(30_600.0, abs=1.0)


# ── LTCG Rate Tests ───────────────────────────────────────────────────────────


def test_ltcg_0pct_within_threshold():
    """MFJ ordinary income $50,000 + LTCG $20,000 — LTCG at 0% (below $94,050 threshold)."""
    from backend.engines.tax import calculate_ltcg_tax

    result = calculate_ltcg_tax(
        ltcg_income=20_000.0, ordinary_taxable_income=50_000.0, filing_status="mfj"
    )
    assert result == 0.0


def test_ltcg_partially_in_15pct():
    """MFJ ordinary income $80,000 + LTCG $30,000 — LTCG straddles 0%/15% threshold.

    0% threshold for MFJ 2024: $94,050
    Income already using: $80,000 ordinary
    Room in 0% band: $94,050 - $80,000 = $14,050 at 0%
    Remaining LTCG: $30,000 - $14,050 = $15,950 at 15%
    Tax: $15,950 * 0.15 = $2,392.50
    """
    from backend.engines.tax import calculate_ltcg_tax

    result = calculate_ltcg_tax(
        ltcg_income=30_000.0, ordinary_taxable_income=80_000.0, filing_status="mfj"
    )
    assert result == pytest.approx(2_392.50, abs=1.0)


def test_ltcg_20pct_threshold():
    """MFJ ordinary income $560,000 + LTCG $30,000 — straddles 15%/20% threshold.
    15%/20% threshold: $583,750
    ordinary = $560k; LTCG starts at $560k
    First $23,750 of LTCG ($560k→$583,750) at 15%: $23,750 * 0.15 = $3,562.50
    Remaining $6,250 at 20%: $6,250 * 0.20 = $1,250.00
    Total: $4,812.50
    """
    from backend.engines.tax import calculate_ltcg_tax

    result = calculate_ltcg_tax(
        ltcg_income=30_000.0, ordinary_taxable_income=560_000.0, filing_status="mfj"
    )
    assert result == pytest.approx(4_812.50, abs=1.0)


# ── IRMAA Tests ───────────────────────────────────────────────────────────────


def test_irmaa_below_threshold():
    """Prior-year MAGI $200,000 MFJ → no IRMAA."""
    from backend.engines.tax import calculate_irmaa_annual

    result = calculate_irmaa_annual(prior_year_magi=200_000.0, filing_status="mfj")
    assert result == 0.0


def test_irmaa_tier_1_mfj():
    """Prior-year MAGI $230,000 MFJ → Tier 1: $69.90/month * 2 people * 12."""
    from backend.engines.tax import calculate_irmaa_annual

    result = calculate_irmaa_annual(prior_year_magi=230_000.0, filing_status="mfj")
    assert result == pytest.approx(69.90 * 2 * 12, abs=1.0)


def test_irmaa_tier_3_mfj():
    """Prior-year MAGI $340,000 MFJ → Tier 3: $279.50/month * 2 people * 12."""
    from backend.engines.tax import calculate_irmaa_annual

    result = calculate_irmaa_annual(prior_year_magi=340_000.0, filing_status="mfj")
    assert result == pytest.approx(279.50 * 2 * 12, abs=1.0)


def test_irmaa_thresholds_inflate_with_factor():
    """IMPORTANT-4: IRMAA threshold at inflation_factor=2.0 should double.

    $230k MAGI is Tier 1 at 2024 levels (threshold $206k). At 2x inflation
    the threshold becomes $412k, so $230k should trigger no surcharge.
    """
    from backend.engines.tax import calculate_irmaa_annual

    # Without inflation — $230k is in Tier 1
    baseline = calculate_irmaa_annual(
        prior_year_magi=230_000.0, filing_status="mfj", inflation_factor=1.0
    )
    assert baseline == pytest.approx(69.90 * 2 * 12, abs=1.0)

    # With 2x inflation — $230k is below the inflated $412k threshold
    inflated = calculate_irmaa_annual(
        prior_year_magi=230_000.0, filing_status="mfj", inflation_factor=2.0
    )
    assert inflated == 0.0


# ── calculate_taxes() integration test ───────────────────────────────────────


def test_calculate_taxes_full_mfj():
    """Full integration: MFJ couple, age 62/60, moderate retirement income."""
    from backend.engines.tax import TaxInput, calculate_taxes

    ti = TaxInput(
        filing_status="mfj",
        age_you=62,
        age_spouse=60,
        ordinary_income=80_000.0,
        ss_income_you=37_200.0,
        ss_income_spouse=0.0,
        ltcg_income=10_000.0,
        roth_conversion=0.0,
        retirement_income_you=80_000.0,
        retirement_income_spouse=0.0,
        prior_year_magi=100_000.0,
        inflation_factor=1.0,
    )
    result = calculate_taxes(ti)

    assert result.federal_total > 0
    assert result.state_tax > 0
    assert result.total_tax == pytest.approx(
        result.federal_total + result.state_tax, abs=1.0
    )
    assert 0.0 < result.effective_rate < 0.30
    assert result.federal_ss_included > 0
    assert result.irmaa_annual == 0.0  # below IRMAA threshold
