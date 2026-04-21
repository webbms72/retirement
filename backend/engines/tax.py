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
    for upper, rate in brackets:
        if taxable_income <= upper:
            return rate
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


# ── Social Security Inclusion ─────────────────────────────────────────────────

SS_BASE_THRESHOLD_MFJ = 32_000.0
SS_UPPER_THRESHOLD_MFJ = 44_000.0
SS_BASE_THRESHOLD_SINGLE = 25_000.0
SS_UPPER_THRESHOLD_SINGLE = 34_000.0


def calculate_ss_inclusion(
    ss_gross: float,
    other_income: float,
    filing_status: str,
) -> float:
    """Calculate the taxable portion of Social Security benefits.

    IRS 'combined income' = other income + (SS / 2).
    Below base threshold: 0% taxable.
    Between base and upper: up to 50% taxable.
    Above upper threshold: up to 85% taxable.
    """
    if ss_gross <= 0:
        return 0.0

    if filing_status == "mfj":
        base = SS_BASE_THRESHOLD_MFJ
        upper = SS_UPPER_THRESHOLD_MFJ
    else:
        base = SS_BASE_THRESHOLD_SINGLE
        upper = SS_UPPER_THRESHOLD_SINGLE

    combined = other_income + ss_gross / 2.0

    if combined <= base:
        return 0.0

    if combined <= upper:
        tier1 = min(0.50 * ss_gross, 0.50 * (combined - base))
        return round(tier1, 2)

    # Tier 2: 85% rule
    tier1_max = 0.50 * (upper - base)
    tier2 = 0.85 * (combined - upper) + tier1_max
    taxable_ss = min(0.85 * ss_gross, tier2)
    return round(taxable_ss, 2)


# ── Long-Term Capital Gains Tax ───────────────────────────────────────────────

LTCG_THRESHOLDS: dict[str, tuple[float, float]] = {
    "mfj": (94_050.0, 583_750.0),
    "single": (47_025.0, 518_900.0),
}


def calculate_ltcg_tax(
    ltcg_income: float,
    ordinary_taxable_income: float,
    filing_status: str,
    inflation_factor: float = 1.0,
) -> float:
    """Calculate federal long-term capital gains tax.

    LTCG is stacked on top of ordinary income.
    """
    if ltcg_income <= 0:
        return 0.0

    zero_limit, fifteen_limit = LTCG_THRESHOLDS.get(
        filing_status, LTCG_THRESHOLDS["single"]
    )
    zero_limit *= inflation_factor
    fifteen_limit *= inflation_factor

    ltcg_stack_start = ordinary_taxable_income
    ltcg_stack_end = ordinary_taxable_income + ltcg_income

    tax = 0.0

    # 15% band
    fifteen_band_start = max(ltcg_stack_start, zero_limit)
    fifteen_band_end = min(ltcg_stack_end, fifteen_limit)
    if fifteen_band_end > fifteen_band_start:
        tax += (fifteen_band_end - fifteen_band_start) * 0.15

    # 20% band
    twenty_band_start = max(ltcg_stack_start, fifteen_limit)
    if ltcg_stack_end > twenty_band_start:
        tax += (ltcg_stack_end - twenty_band_start) * 0.20

    return round(tax, 2)


# ── IRMAA Surcharge ───────────────────────────────────────────────────────────

IRMAA_MFJ_TIERS: list[tuple[float, float]] = [
    (206_000.0, 0.00),
    (258_000.0, 69.90),
    (322_000.0, 174.70),
    (386_000.0, 279.50),
    (750_000.0, 384.30),
    (float("inf"), 419.30),
]

IRMAA_SINGLE_TIERS: list[tuple[float, float]] = [
    (103_000.0, 0.00),
    (129_000.0, 69.90),
    (161_000.0, 174.70),
    (193_000.0, 279.50),
    (500_000.0, 384.30),
    (float("inf"), 419.30),
]


def calculate_irmaa_annual(
    prior_year_magi: float,
    filing_status: str,
    num_people: int = 2,
    inflation_factor: float = 1.0,
) -> float:
    """Calculate annual IRMAA Medicare Part B surcharge (2-year lookback).

    Thresholds are inflation-adjusted from their 2024 base values so that
    nominal income growth from inflation alone does not trigger higher tiers.
    """
    tiers = IRMAA_MFJ_TIERS if filing_status == "mfj" else IRMAA_SINGLE_TIERS
    no_surcharge_threshold = tiers[0][0] * inflation_factor

    if prior_year_magi <= no_surcharge_threshold:
        return 0.0

    monthly_per_person = 0.0
    for threshold, surcharge in tiers[1:]:
        inflated_threshold = (
            threshold * inflation_factor if threshold != float("inf") else float("inf")
        )
        if prior_year_magi <= inflated_threshold:
            monthly_per_person = surcharge
            break
    else:
        monthly_per_person = tiers[-1][1]

    return round(monthly_per_person * num_people * 12, 2)


# ── Main calculate_taxes() Entry Point ───────────────────────────────────────


def calculate_taxes(ti: TaxInput) -> TaxResult:
    """Calculate all federal and DE state taxes for a single projection year.

    Flow:
    1. Calculate SS inclusion on combined SS gross.
    2. Add SS included + Roth conversion to ordinary income for federal AGI.
    3. Apply standard deduction to get federal taxable ordinary income.
    4. Calculate federal ordinary income tax.
    5. Calculate LTCG tax (stacked on top of ordinary taxable income).
    6. Calculate IRMAA from prior-year MAGI.
    7. Calculate Delaware state tax (SS excluded, retirement exclusion applied).
    8. Aggregate results.
    """
    result = TaxResult()

    filing_status = ti.filing_status
    inflation = ti.inflation_factor

    # 1. SS inclusion
    total_ss_gross = ti.ss_income_you + ti.ss_income_spouse
    combined_non_ss = ti.ordinary_income + ti.ltcg_income + ti.roth_conversion
    ss_included = calculate_ss_inclusion(
        ss_gross=total_ss_gross,
        other_income=combined_non_ss,
        filing_status=filing_status,
    )
    result.federal_ss_included = ss_included

    # 2. Federal AGI
    federal_agi = ti.ordinary_income + ss_included + ti.roth_conversion

    # 3. Standard deduction
    std_ded = get_standard_deduction(
        filing_status=filing_status,
        age_you=ti.age_you,
        age_spouse=ti.age_spouse,
        inflation_factor=inflation,
    )
    federal_taxable_ordinary = max(0.0, federal_agi - std_ded)

    # 4. Federal ordinary income tax
    fed_ordinary = calculate_federal_ordinary_income_tax(
        taxable_income=federal_taxable_ordinary,
        filing_status=filing_status,
        inflation_factor=inflation,
    )
    result.federal_ordinary_tax = fed_ordinary

    # 5. LTCG tax
    fed_ltcg = calculate_ltcg_tax(
        ltcg_income=ti.ltcg_income,
        ordinary_taxable_income=federal_taxable_ordinary,
        filing_status=filing_status,
        inflation_factor=inflation,
    )
    result.federal_ltcg_tax = fed_ltcg

    # 6. IRMAA
    num_people = 2 if filing_status == "mfj" else 1
    irmaa = calculate_irmaa_annual(
        prior_year_magi=ti.prior_year_magi,
        filing_status=filing_status,
        num_people=num_people,
        inflation_factor=inflation,
    )
    result.irmaa_annual = irmaa

    # 7. Federal total
    result.federal_total = round(fed_ordinary + fed_ltcg + irmaa, 2)

    # 8. Delaware state tax (SS excluded per DE law)
    de_taxable = ti.ordinary_income + ti.roth_conversion + ti.ltcg_income
    state_tax = calculate_delaware_tax(
        de_taxable_income=de_taxable,
        filing_status=filing_status,
        num_people=num_people,
        age_you=ti.age_you,
        age_spouse=ti.age_spouse,
        retirement_income_you=ti.retirement_income_you,
        retirement_income_spouse=ti.retirement_income_spouse,
        inflation_factor=inflation,
    )
    result.state_tax = state_tax

    # 9. Totals
    result.total_tax = round(result.federal_total + state_tax, 2)
    result.gross_income = round(
        ti.ordinary_income + total_ss_gross + ti.ltcg_income + ti.roth_conversion, 2
    )
    if result.gross_income > 0:
        result.effective_rate = round(result.total_tax / result.gross_income, 4)

    result.marginal_rate = get_marginal_rate(
        taxable_income=federal_taxable_ordinary,
        filing_status=filing_status,
        inflation_factor=inflation,
    )

    result.notes = [
        f"SS included: ${ss_included:,.0f} of ${total_ss_gross:,.0f} gross",
        f"Federal taxable ordinary: ${federal_taxable_ordinary:,.0f}",
        f"Marginal rate: {result.marginal_rate:.0%}",
        f"IRMAA: ${irmaa:,.0f}/yr" if irmaa > 0 else "No IRMAA surcharge",
    ]

    return result
