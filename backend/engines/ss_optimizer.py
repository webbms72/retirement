"""Social Security Optimizer — exhaustively evaluates all 81 claiming combinations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SSInput:
    benefit_at_62_you: float
    benefit_at_fra_you: float
    benefit_at_70_you: float
    fra_age_you: int
    benefit_at_62_spouse: float
    benefit_at_fra_spouse: float
    benefit_at_70_spouse: float
    fra_age_spouse: int
    life_expectancy_you: int
    life_expectancy_spouse: int
    survivor_benefit_pct: float
    current_age_you: int
    current_age_spouse: int


@dataclass
class SSClaimResult:
    claim_age_you: int
    claim_age_spouse: int
    monthly_benefit_you: float
    monthly_benefit_spouse: float
    lifetime_benefit: float
    survivor_monthly_benefit: float
    notes: list[str] = field(default_factory=list)


def _benefit_at_age(
    benefit_at_62: float,
    benefit_at_fra: float,
    benefit_at_70: float,
    fra_age: int,
    claim_age: int,
) -> float:
    """Return monthly benefit for a given claim age using linear interpolation."""
    if claim_age <= 62:
        return benefit_at_62
    if claim_age >= 70:
        return benefit_at_70
    if claim_age == fra_age:
        return benefit_at_fra
    if claim_age < fra_age:
        years_before_fra = fra_age - 62
        years_before_claim = fra_age - claim_age
        fraction = years_before_claim / years_before_fra
        return benefit_at_fra - fraction * (benefit_at_fra - benefit_at_62)
    # claim_age > fra_age < 70
    years_after_fra = 70 - fra_age
    years_after_claim = claim_age - fra_age
    fraction = years_after_claim / years_after_fra
    return benefit_at_fra + fraction * (benefit_at_70 - benefit_at_fra)


def _lifetime_benefit_single(
    monthly_benefit: float,
    claim_age: int,
    life_expectancy: int,
) -> float:
    if life_expectancy <= claim_age:
        return 0.0
    return monthly_benefit * 12 * (life_expectancy - claim_age)


def optimize_ss(inp: SSInput) -> list[SSClaimResult]:
    """Evaluate all 81 SS claiming combinations (ages 62–70 × 62–70)."""
    results: list[SSClaimResult] = []

    you_years_remaining = inp.life_expectancy_you - inp.current_age_you
    spouse_years_remaining = inp.life_expectancy_spouse - inp.current_age_spouse
    you_dies_first = you_years_remaining <= spouse_years_remaining

    for claim_you in range(62, 71):
        monthly_you = _benefit_at_age(
            inp.benefit_at_62_you,
            inp.benefit_at_fra_you,
            inp.benefit_at_70_you,
            inp.fra_age_you,
            claim_you,
        )

        for claim_spouse in range(62, 71):
            monthly_spouse = _benefit_at_age(
                inp.benefit_at_62_spouse,
                inp.benefit_at_fra_spouse,
                inp.benefit_at_70_spouse,
                inp.fra_age_spouse,
                claim_spouse,
            )

            benefit_you = _lifetime_benefit_single(
                monthly_you, claim_you, inp.life_expectancy_you
            )
            benefit_spouse = _lifetime_benefit_single(
                monthly_spouse, claim_spouse, inp.life_expectancy_spouse
            )

            if you_dies_first:
                survivor_age_at_death = inp.current_age_spouse + you_years_remaining
                survivor_own_monthly = monthly_spouse
                deceased_monthly = monthly_you
                survivor_life_exp = inp.life_expectancy_spouse
            else:
                survivor_age_at_death = inp.current_age_you + spouse_years_remaining
                survivor_own_monthly = monthly_you
                deceased_monthly = monthly_spouse
                survivor_life_exp = inp.life_expectancy_you

            survivor_benefit_from_deceased = deceased_monthly * inp.survivor_benefit_pct
            survivor_monthly = max(survivor_own_monthly, survivor_benefit_from_deceased)

            survivor_delta = 0.0
            if survivor_monthly > survivor_own_monthly:
                survivor_years = max(0, survivor_life_exp - survivor_age_at_death)
                survivor_delta = (
                    (survivor_monthly - survivor_own_monthly) * 12 * survivor_years
                )

            lifetime_total = benefit_you + benefit_spouse + survivor_delta

            notes: list[str] = []
            if claim_you == 70:
                notes.append(
                    f"Delaying to 70 maximizes survivor benefit: "
                    f"${monthly_you:,.0f}/mo passes to survivor"
                )
            if claim_you < inp.fra_age_you:
                pct = round(
                    (inp.benefit_at_fra_you - monthly_you)
                    / inp.benefit_at_fra_you
                    * 100,
                    1,
                )
                notes.append(f"Early claim reduces your benefit by {pct}%")
            if claim_spouse < inp.fra_age_spouse:
                pct = round(
                    (inp.benefit_at_fra_spouse - monthly_spouse)
                    / inp.benefit_at_fra_spouse
                    * 100,
                    1,
                )
                notes.append(f"Spouse early claim reduces their benefit by {pct}%")

            results.append(
                SSClaimResult(
                    claim_age_you=claim_you,
                    claim_age_spouse=claim_spouse,
                    monthly_benefit_you=round(monthly_you, 2),
                    monthly_benefit_spouse=round(monthly_spouse, 2),
                    lifetime_benefit=round(lifetime_total, 2),
                    survivor_monthly_benefit=round(survivor_monthly, 2),
                    notes=notes,
                )
            )

    results.sort(key=lambda r: r.lifetime_benefit, reverse=True)
    return results
