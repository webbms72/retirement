"""Tax Engine — federal and Delaware state income tax calculations.

All functions are pure (no DB access). Call calculate_taxes() as the main
entry point from the Projection Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── 2024 Federal Tax Brackets ─────────────────────────────────────────────────
# Format: list of (upper_bound, rate) pairs in ascending order.
# Source: IRS Rev. Proc. 2023-34

MFJ_BRACKETS_2024: list[tuple[float, float]] = [
    (23_200.0, 0.10),
    (94_300.0, 0.12),
    (201_050.0, 0.22),
    (383_900.0, 0.24),
    (487_450.0, 0.32),
    (731_200.0, 0.35),
    (float("inf"), 0.37),
]

SINGLE_BRACKETS_2024: list[tuple[float, float]] = [
    (11_600.0, 0.10),
    (47_150.0, 0.12),
    (100_525.0, 0.22),
    (191_950.0, 0.24),
    (243_725.0, 0.32),
    (609_350.0, 0.35),
    (float("inf"), 0.37),
]

# Standard deductions 2024
STANDARD_DEDUCTION_MFJ = 29_200.0
STANDARD_DEDUCTION_SINGLE = 14_600.0
ADDITIONAL_DEDUCTION_AGE_65 = 1_550.0  # per qualifying person

# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class TaxInput:
    """All inputs required for a single year's tax calculation."""

    filing_status: str  # "mfj" or "single"
    age_you: int
    age_spouse: int  # 0 if single
    ordinary_income: float  # wages, 401k withdrawals, NQDC, pensions, RMDs
    ss_income_you: float = 0.0  # gross SS benefit (before inclusion calc)
    ss_income_spouse: float = 0.0
    ltcg_income: float = 0.0  # long-term capital gains + qualified dividends
    roth_conversion: float = 0.0
    retirement_income_you: float = 0.0  # pension/IRA for DE exclusion
    retirement_income_spouse: float = 0.0
    prior_year_magi: float = 0.0  # for IRMAA lookback
    inflation_factor: float = 1.0  # cumulative inflation since 2024 base year


@dataclass
class TaxResult:
    """Per-year tax calculation results."""

    federal_ordinary_tax: float = 0.0
    federal_ltcg_tax: float = 0.0
    federal_ss_included: float = 0.0  # taxable portion of SS
    irmaa_annual: float = 0.0
    federal_total: float = 0.0
    state_tax: float = 0.0
    total_tax: float = 0.0
    effective_rate: float = 0.0
    marginal_rate: float = 0.0
    gross_income: float = 0.0
    notes: list[str] = field(default_factory=list)


# ── Bracket helpers ───────────────────────────────────────────────────────────


def _get_brackets(filing_status: str) -> list[tuple[float, float]]:
    if filing_status == "mfj":
        return MFJ_BRACKETS_2024
    return SINGLE_BRACKETS_2024


def _inflate_brackets(
    brackets: list[tuple[float, float]], factor: float
) -> list[tuple[float, float]]:
    """Scale bracket thresholds by cumulative inflation factor."""
    return [
        (upper * factor if upper != float("inf") else float("inf"), rate)
        for upper, rate in brackets
    ]


def get_standard_deduction(
    filing_status: str, age_you: int, age_spouse: int, inflation_factor: float = 1.0
) -> float:
    """Return the standard deduction including age-65+ add-on amounts."""
    if filing_status == "mfj":
        base = STANDARD_DEDUCTION_MFJ * inflation_factor
        extra = 0.0
        if age_you >= 65:
            extra += ADDITIONAL_DEDUCTION_AGE_65 * inflation_factor
        if age_spouse >= 65:
            extra += ADDITIONAL_DEDUCTION_AGE_65 * inflation_factor
        return base + extra
    else:
        base = STANDARD_DEDUCTION_SINGLE * inflation_factor
        extra = ADDITIONAL_DEDUCTION_AGE_65 * inflation_factor if age_you >= 65 else 0.0
        return base + extra


def calculate_federal_ordinary_income_tax(
    taxable_income: float,
    filing_status: str,
    inflation_factor: float = 1.0,
) -> float:
    """Apply progressive federal brackets to taxable ordinary income.

    Args:
        taxable_income: Income after standard deduction. Must be >= 0.
        filing_status: "mfj" or "single".
        inflation_factor: Cumulative CPI factor to scale bracket thresholds.

    Returns:
        Federal ordinary income tax as a float.
    """
    if taxable_income <= 0:
        return 0.0

    brackets = _inflate_brackets(_get_brackets(filing_status), inflation_factor)
    tax = 0.0
    prev_upper = 0.0

    for upper, rate in brackets:
        if taxable_income <= prev_upper:
            break
        bracket_income = min(taxable_income, upper) - prev_upper
        tax += bracket_income * rate
        prev_upper = upper

    return round(tax, 2)


def get_marginal_rate(
    taxable_income: float,
    filing_status: str,
    inflation_factor: float = 1.0,
) -> float:
    """Return the marginal tax rate for the given taxable income level."""
    if taxable_income <= 0:
        return 0.0
    brackets = _inflate_brackets(_get_brackets(filing_status), inflation_factor)
    prev_upper = 0.0
    for upper, rate in brackets:
        if taxable_income <= upper:
            return rate
        prev_upper = upper
    return brackets[-1][1]


# ── Delaware State Tax ────────────────────────────────────────────────────────
# Brackets 2024 — (upper_bound, rate)
# Source: Delaware Division of Revenue, Tax Rate Tables 2024

DE_BRACKETS_2024: list[tuple[float, float]] = [
    (2_000.0, 0.000),
    (5_000.0, 0.022),
    (10_000.0, 0.039),
    (20_000.0, 0.048),
    (25_000.0, 0.052),
    (60_000.0, 0.0555),
    (float("inf"), 0.066),
]

DE_STANDARD_DEDUCTION_MFJ = 6_500.0
DE_STANDARD_DEDUCTION_SINGLE = 3_250.0
DE_PERSONAL_EXEMPTION = 110.0  # per person
DE_RETIREMENT_EXCLUSION_PER_PERSON = 12_500.0  # after age 60


def calculate_delaware_tax(
    de_taxable_income: float,
    filing_status: str,
    num_people: int = 1,
    age_you: int = 0,
    age_spouse: int = 0,
    retirement_income_you: float = 0.0,
    retirement_income_spouse: float = 0.0,
    inflation_factor: float = 1.0,
) -> float:
    """Calculate Delaware state income tax.

    Delaware does not tax Social Security income. The caller should pass
    de_taxable_income as gross income minus SS income.

    Retirement income exclusion: $12,500 per person for pension/IRA/retirement
    income, available after age 60.
    """
    if de_taxable_income <= 0:
        return 0.0

    # Apply retirement income exclusion (post-age-60, $12,500/person cap)
    exclusion = 0.0
    if age_you >= 60:
        exclusion += min(retirement_income_you, DE_RETIREMENT_EXCLUSION_PER_PERSON)
    if age_spouse >= 60 and filing_status == "mfj":
        exclusion += min(retirement_income_spouse, DE_RETIREMENT_EXCLUSION_PER_PERSON)

    income_after_exclusion = max(0.0, de_taxable_income - exclusion)

    # Standard deduction
    std_deduction = (
        DE_STANDARD_DEDUCTION_MFJ
        if filing_status == "mfj"
        else DE_STANDARD_DEDUCTION_SINGLE
    ) * inflation_factor

    # Personal exemptions
    personal_exemptions = DE_PERSONAL_EXEMPTION * num_people * inflation_factor

    taxable = max(0.0, income_after_exclusion - std_deduction - personal_exemptions)

    if taxable <= 0:
        return 0.0

    # Apply brackets
    brackets = _inflate_brackets(DE_BRACKETS_2024, inflation_factor)
    tax = 0.0
    prev_upper = 0.0

    for upper, rate in brackets:
        if taxable <= prev_upper:
            break
        bracket_income = min(taxable, upper) - prev_upper
        tax += bracket_income * rate
        prev_upper = upper

    return round(tax, 2)
