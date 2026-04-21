"""Withdrawal Optimizer — determines most tax-efficient source order each year.

All functions are pure (no DB access).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AccountState:
    """Current state of one account at the start of a projection year."""

    account_type: str
    balance: float
    basis: float
    owner: str
    is_rule_of_55_eligible: bool = False
    annual_contribution: float = 0.0
    roth_conversion_cohorts: dict[int, float] = field(default_factory=dict)


@dataclass
class WithdrawalInput:
    """Inputs for the withdrawal optimizer for a single projection year."""

    required_amount: float
    account_states: list[AccountState]
    age_you: int
    age_spouse: int
    current_marginal_rate: float
    current_ordinary_taxable_income: float
    filing_status: str
    healthcare_amount: float
    roth_conversion_enabled: bool
    target_bracket_rate: float | None
    target_bracket_ceiling: float | None
    current_year: int
    prior_year_pretax_balance: float = 0.0


@dataclass
class WithdrawalResult:
    """Result of the withdrawal optimizer for a single year."""

    withdrawals_by_account: dict[str, float] = field(default_factory=dict)
    roth_conversion_amount: float = 0.0
    total_withdrawn: float = 0.0
    early_withdrawal_penalty: float = 0.0
    rmd_taken: dict[str, float] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


LTCG_0PCT_CEILING_MFJ = 94_050.0
LTCG_0PCT_CEILING_SINGLE = 47_025.0

RMD_MIN_AGE = 73

RMD_DIVISORS: dict[int, float] = {
    72: 27.4,
    73: 26.5,
    74: 25.5,
    75: 24.6,
    76: 23.7,
    77: 22.9,
    78: 22.0,
    79: 21.1,
    80: 20.2,
    81: 19.4,
    82: 18.5,
    83: 17.7,
    84: 16.8,
    85: 16.0,
    86: 15.2,
    87: 14.4,
    88: 13.7,
    89: 12.9,
    90: 12.2,
    91: 11.5,
    92: 10.8,
    93: 10.1,
    94: 9.5,
    95: 8.9,
    96: 8.4,
    97: 7.8,
    98: 7.3,
    99: 6.8,
    100: 6.4,
}


def calculate_rmd(prior_year_balance: float, age: int) -> float:
    """Calculate Required Minimum Distribution for a pre-tax account.

    Returns 0 if age < 73 (SECURE 2.0).
    """
    if age < RMD_MIN_AGE:
        return 0.0
    divisor = RMD_DIVISORS.get(age, 1.9)
    return round(prior_year_balance / divisor, 2)


def is_roth_conversion_accessible(
    conversion_year: int,
    current_year: int,
    age_you: int,
) -> bool:
    """Determine if a Roth conversion cohort is penalty-free accessible.

    After age 60: 5-year rule does not apply.
    Before age 60: conversion must be >= 5 years old.
    """
    if age_you >= 60:
        return True
    return (current_year - conversion_year) >= 5


def _is_before_59_half(age: int) -> bool:
    # Annual-granularity simplification: age 59 is treated as fully before 59½
    # and age 60+ as fully after. This may slightly over-penalise someone who
    # turns 59½ early in the year, but the error is at most one year's penalty.
    return age < 60


def _has_ltcg_0pct_room(
    current_ordinary_taxable_income: float,
    filing_status: str,
) -> bool:
    ceiling = (
        LTCG_0PCT_CEILING_MFJ if filing_status == "mfj" else LTCG_0PCT_CEILING_SINGLE
    )
    return current_ordinary_taxable_income < ceiling


def optimize_withdrawals(wi: WithdrawalInput) -> WithdrawalResult:
    """Determine optimal withdrawal amounts and sources for a single year.

    Ordering:
    0. RMDs (mandatory, age 73+) — taken before any discretionary amount.
    1. HSA — cover healthcare_amount first.
    2. Brokerage — if 0% LTCG is available.
    3. Roth conversion — if enabled and bracket room exists.
    4. 401k — prefer when Rule of 55 applies.
    5. Roth IRA — last resort.
    """
    result = WithdrawalResult()
    remaining = wi.required_amount

    # Group accounts by type — both spouses may have the same type
    accounts_by_type: dict[str, list[AccountState]] = {}
    for a in wi.account_states:
        accounts_by_type.setdefault(a.account_type, []).append(a)

    def draw(account_type: str, amount: float) -> float:
        """Draw up to `amount` across all accounts of this type (both spouses)."""
        accts = accounts_by_type.get(account_type, [])
        total_drawn = 0.0
        remaining_to_draw = amount
        for acct in accts:
            if acct.balance <= 0 or remaining_to_draw <= 0:
                continue
            drawn = min(acct.balance, remaining_to_draw)
            acct.balance -= drawn
            total_drawn += drawn
            remaining_to_draw -= drawn
        if total_drawn > 0:
            result.withdrawals_by_account[account_type] = (
                result.withdrawals_by_account.get(account_type, 0.0) + total_drawn
            )
        return total_drawn

    # ── Step 0: RMDs ──────────────────────────────────────────────────────────
    if wi.age_you >= RMD_MIN_AGE and wi.prior_year_pretax_balance > 0:
        rmd_amount = calculate_rmd(
            prior_year_balance=wi.prior_year_pretax_balance,
            age=wi.age_you,
        )
        rmd_drawn = draw("401k", rmd_amount)
        if rmd_drawn > 0:
            result.rmd_taken["401k"] = rmd_drawn
            remaining = max(0.0, remaining - rmd_drawn)
            result.notes.append(
                f"RMD: ${rmd_drawn:,.0f} from 401k (age {wi.age_you}, "
                f"divisor {RMD_DIVISORS.get(wi.age_you, 1.9)})"
            )

    if remaining <= 0:
        result.total_withdrawn = wi.required_amount
        return result

    # ── Step 1: HSA for healthcare ────────────────────────────────────────────
    if wi.healthcare_amount > 0:
        hsa_drawn = draw("hsa", min(wi.healthcare_amount, remaining))
        if hsa_drawn > 0:
            remaining -= hsa_drawn
            result.notes.append(
                f"HSA: drew ${hsa_drawn:,.0f} for qualified medical expenses"
            )

    if remaining <= 0:
        result.total_withdrawn = wi.required_amount
        return result

    # ── Step 2: Brokerage ─────────────────────────────────────────────────────
    # Draw brokerage before tax-deferred accounts regardless of LTCG rate.
    # Note whether gains fall within the 0% LTCG ceiling for informational purposes.
    brokerage_drawn = draw("brokerage", remaining)
    if brokerage_drawn > 0:
        remaining -= brokerage_drawn
        ceiling = (
            LTCG_0PCT_CEILING_MFJ
            if wi.filing_status == "mfj"
            else LTCG_0PCT_CEILING_SINGLE
        )
        ltcg_room = max(0.0, ceiling - wi.current_ordinary_taxable_income)
        if ltcg_room >= brokerage_drawn:
            result.notes.append(
                f"Brokerage: drew ${brokerage_drawn:,.0f} at 0% LTCG rate"
            )
        else:
            result.notes.append(
                f"Brokerage: drew ${brokerage_drawn:,.0f} "
                f"(${ltcg_room:,.0f} at 0% LTCG, remainder at higher rate)"
            )

    if remaining <= 0:
        result.total_withdrawn = wi.required_amount
        return result

    # ── Step 3: Roth conversion ───────────────────────────────────────────────
    if (
        wi.roth_conversion_enabled
        and wi.target_bracket_ceiling is not None
        and wi.target_bracket_rate is not None
    ):
        conversion_room = max(
            0.0, wi.target_bracket_ceiling - wi.current_ordinary_taxable_income
        )
        if conversion_room > 0:
            k401_list = accounts_by_type.get("401k", [])
            k401 = next((a for a in k401_list if a.balance > 0), None)
            if k401:
                conversion_amount = min(k401.balance, conversion_room)
                k401.balance -= conversion_amount
                result.roth_conversion_amount = conversion_amount
                result.notes.append(
                    f"Roth conversion: ${conversion_amount:,.0f} "
                    f"(fill to {wi.target_bracket_rate:.0%} bracket)"
                )

    if remaining <= 0:
        result.total_withdrawn = wi.required_amount
        return result

    # ── Step 4: 401k ─────────────────────────────────────────────────────────
    k401_accounts = accounts_by_type.get("401k", [])
    drawn = draw("401k", remaining)
    if drawn > 0:
        remaining -= drawn
        is_pre_59_half = _is_before_59_half(wi.age_you)
        rule55 = any(a.is_rule_of_55_eligible for a in k401_accounts)
        if is_pre_59_half and not rule55:
            penalty = drawn * 0.10
            result.early_withdrawal_penalty += penalty
            result.notes.append(
                f"401k: drew ${drawn:,.0f} — 10% early withdrawal penalty ${penalty:,.0f}"
            )
        else:
            qualifier = "(Rule of 55)" if rule55 else "(age >= 60)"
            result.notes.append(f"401k: drew ${drawn:,.0f}, no penalty {qualifier}")

    if remaining <= 0:
        result.total_withdrawn = wi.required_amount - remaining
        return result

    # ── Step 5: Roth IRA ──────────────────────────────────────────────────────
    roth_drawn = draw("roth_ira", remaining)
    if roth_drawn > 0:
        remaining -= roth_drawn
        result.notes.append(f"Roth IRA: drew ${roth_drawn:,.0f} (tax-free)")

    if remaining > 0:
        result.notes.append(
            f"WARNING: portfolio shortfall of ${remaining:,.0f} — all accounts exhausted"
        )

    result.total_withdrawn = wi.required_amount - max(0.0, remaining)
    return result
