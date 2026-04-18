"""Monte Carlo Engine — runs N simulations of the Projection Engine with
sampled return and inflation values to estimate survival probability and
portfolio percentile bands.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np

from backend.engines.projection import ScenarioParams, run_projection
from backend.engines.withdrawal import AccountState


@dataclass
class MCInput:
    scenario_params: ScenarioParams
    accounts: list[AccountState]
    start_year: int
    age_you_at_start: int
    age_spouse_at_start: int
    n_simulations: int = 10_000
    random_seed: int | None = None


@dataclass
class MCResult:
    num_simulations: int
    survival_rate: float
    percentile_10: dict[int, float]
    percentile_25: dict[int, float]
    percentile_50: dict[int, float]
    percentile_75: dict[int, float]
    percentile_90: dict[int, float]
    sensitivity: dict[str, float]


STOCK_RETURN_SIGMA = 0.15
BOND_RETURN_SIGMA = 0.06
INFLATION_SIGMA = 0.01


def _sample_scenario_params(
    base_params: ScenarioParams,
    stock_return: float,
    bond_return: float,
    inflation_rate: float,
) -> ScenarioParams:
    p = copy.copy(base_params)
    p.expected_return_stocks = stock_return
    p.expected_return_bonds = bond_return
    p.inflation_rate = inflation_rate
    return p


def _run_single_simulation(
    params: ScenarioParams,
    accounts: list[AccountState],
    start_year: int,
    age_you_at_start: int,
    age_spouse_at_start: int,
) -> tuple[bool, dict[int, float]]:
    accounts_copy = copy.deepcopy(accounts)
    projection = run_projection(
        start_year=start_year,
        age_you_at_start=age_you_at_start,
        age_spouse_at_start=age_spouse_at_start,
        accounts=accounts_copy,
        params=params,
    )
    balances = {py.year: py.portfolio_balance for py in projection}
    final_balance = projection[-1].portfolio_balance if projection else 0.0
    return final_balance > 0.0, balances


def run_monte_carlo(inp: MCInput) -> MCResult:
    """Run N Monte Carlo simulations and compute survival statistics."""
    rng = np.random.default_rng(inp.random_seed)

    stock_returns = rng.normal(
        inp.scenario_params.expected_return_stocks,
        STOCK_RETURN_SIGMA,
        inp.n_simulations,
    ).clip(-0.50, 0.50)

    bond_returns = rng.normal(
        inp.scenario_params.expected_return_bonds,
        BOND_RETURN_SIGMA,
        inp.n_simulations,
    ).clip(-0.30, 0.30)

    inflation_rates = rng.normal(
        inp.scenario_params.inflation_rate,
        INFLATION_SIGMA,
        inp.n_simulations,
    ).clip(0.0, 0.10)

    survival_flags: list[bool] = []
    all_balances: list[dict[int, float]] = []

    for i in range(inp.n_simulations):
        params_i = _sample_scenario_params(
            inp.scenario_params,
            float(stock_returns[i]),
            float(bond_returns[i]),
            float(inflation_rates[i]),
        )
        survived, balances = _run_single_simulation(
            params=params_i,
            accounts=inp.accounts,
            start_year=inp.start_year,
            age_you_at_start=inp.age_you_at_start,
            age_spouse_at_start=inp.age_spouse_at_start,
        )
        survival_flags.append(survived)
        all_balances.append(balances)

    survival_rate = sum(survival_flags) / inp.n_simulations

    all_years = sorted({yr for bal in all_balances for yr in bal.keys()})
    pct_bands: dict[int, list[float]] = {yr: [] for yr in all_years}
    for bal in all_balances:
        for yr in all_years:
            pct_bands[yr].append(bal.get(yr, 0.0))

    def _pct(p: int) -> dict[int, float]:
        return {
            yr: round(float(np.percentile(pct_bands[yr], p)), 2) for yr in all_years
        }

    sensitivity = _run_sensitivity(inp, survival_rate)

    return MCResult(
        num_simulations=inp.n_simulations,
        survival_rate=round(survival_rate, 4),
        percentile_10=_pct(10),
        percentile_25=_pct(25),
        percentile_50=_pct(50),
        percentile_75=_pct(75),
        percentile_90=_pct(90),
        sensitivity=sensitivity,
    )


def _sensitivity_survival(
    inp: MCInput,
    params_override: ScenarioParams,
    n: int = 50,
    seed: int = 99,
) -> float:
    sub_rng = np.random.default_rng(seed)
    stock_r = sub_rng.normal(
        params_override.expected_return_stocks, STOCK_RETURN_SIGMA, n
    ).clip(-0.50, 0.50)
    bond_r = sub_rng.normal(
        params_override.expected_return_bonds, BOND_RETURN_SIGMA, n
    ).clip(-0.30, 0.30)
    inf_r = sub_rng.normal(params_override.inflation_rate, INFLATION_SIGMA, n).clip(
        0.0, 0.10
    )

    survived = 0
    for i in range(n):
        p = _sample_scenario_params(
            params_override, float(stock_r[i]), float(bond_r[i]), float(inf_r[i])
        )
        ok, _ = _run_single_simulation(
            p,
            inp.accounts,
            inp.start_year,
            inp.age_you_at_start,
            inp.age_spouse_at_start,
        )
        if ok:
            survived += 1
    return survived / n


def _run_sensitivity(inp: MCInput, baseline_survival: float) -> dict[str, float]:
    base = inp.scenario_params
    sensitivity: dict[str, float] = {}

    def _delta(high_params: ScenarioParams, low_params: ScenarioParams) -> float:
        return round(
            _sensitivity_survival(inp, high_params)
            - _sensitivity_survival(inp, low_params),
            4,
        )

    p_retire_late = copy.copy(base)
    p_retire_late.retirement_age_you = base.retirement_age_you + 2
    p_retire_early = copy.copy(base)
    p_retire_early.retirement_age_you = base.retirement_age_you - 2
    sensitivity["retirement_age"] = _delta(p_retire_late, p_retire_early)

    p_spend_low = copy.copy(base)
    p_spend_low.annual_spending = base.annual_spending * 0.85
    p_spend_high = copy.copy(base)
    p_spend_high.annual_spending = base.annual_spending * 1.15
    sensitivity["annual_spending"] = _delta(p_spend_low, p_spend_high)

    p_ss_70 = copy.copy(base)
    p_ss_70.ss_claim_age_you = 70
    p_ss_62 = copy.copy(base)
    p_ss_62.ss_claim_age_you = 62
    sensitivity["ss_claim_age"] = _delta(p_ss_70, p_ss_62)

    p_return_high = copy.copy(base)
    p_return_high.expected_return_stocks = base.expected_return_stocks + 0.01
    p_return_low = copy.copy(base)
    p_return_low.expected_return_stocks = base.expected_return_stocks - 0.01
    sensitivity["expected_return_stocks"] = _delta(p_return_high, p_return_low)

    p_inf_low = copy.copy(base)
    p_inf_low.inflation_rate = max(0.0, base.inflation_rate - 0.01)
    p_inf_high = copy.copy(base)
    p_inf_high.inflation_rate = base.inflation_rate + 0.01
    sensitivity["inflation_rate"] = _delta(p_inf_low, p_inf_high)

    p_alloc_high = copy.copy(base)
    p_alloc_high.stock_allocation = min(1.0, base.stock_allocation + 0.10)
    p_alloc_low = copy.copy(base)
    p_alloc_low.stock_allocation = max(0.0, base.stock_allocation - 0.10)
    sensitivity["stock_allocation"] = _delta(p_alloc_high, p_alloc_low)

    return sensitivity
