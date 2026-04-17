"""Tests for the Tax Engine — federal ordinary income tax (Task 4)."""

from __future__ import annotations

import pytest

from backend.engines.tax import (
    TaxInput,
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
