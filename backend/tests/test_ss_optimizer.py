"""Tests for the SS Optimizer — Task 11."""

from __future__ import annotations

import pytest

from backend.engines.ss_optimizer import (
    SSInput,
    SSClaimResult,
    optimize_ss,
)


def _default_input() -> SSInput:
    return SSInput(
        benefit_at_62_you=2_200.0,
        benefit_at_fra_you=3_100.0,
        benefit_at_70_you=3_900.0,
        fra_age_you=67,
        benefit_at_62_spouse=1_400.0,
        benefit_at_fra_spouse=2_000.0,
        benefit_at_70_spouse=2_500.0,
        fra_age_spouse=67,
        life_expectancy_you=85,
        life_expectancy_spouse=88,
        survivor_benefit_pct=1.0,
        current_age_you=54,
        current_age_spouse=52,
    )


def test_optimize_ss_returns_81_combinations():
    results = optimize_ss(_default_input())
    assert len(results) == 81


def test_optimize_ss_sorted_descending():
    results = optimize_ss(_default_input())
    benefits = [r.lifetime_benefit for r in results]
    assert benefits == sorted(benefits, reverse=True)


def test_optimize_ss_claim_ages_in_range():
    results = optimize_ss(_default_input())
    for r in results:
        assert 62 <= r.claim_age_you <= 70
        assert 62 <= r.claim_age_spouse <= 70


def test_delayed_to_70_generally_best_for_high_earner():
    results = optimize_ss(_default_input())
    top_10 = results[:10]
    claim_ages_you = [r.claim_age_you for r in top_10]
    assert 70 in claim_ages_you


def test_early_claim_62_lower_benefit():
    results = optimize_ss(_default_input())
    both_62 = next(
        r for r in results if r.claim_age_you == 62 and r.claim_age_spouse == 62
    )
    rank = results.index(both_62)
    assert rank > 40


def test_benefit_reduction_at_62():
    inp = _default_input()
    results = optimize_ss(inp)
    claim_62 = next(
        r for r in results if r.claim_age_you == 62 and r.claim_age_spouse == 67
    )
    assert claim_62.monthly_benefit_you < inp.benefit_at_fra_you


def test_survivor_benefit_noted_for_high_earner_delay():
    results = optimize_ss(_default_input())
    top_result_with_70 = next(r for r in results if r.claim_age_you == 70)
    assert any("survivor" in note.lower() for note in top_result_with_70.notes)


def test_top_10_returned():
    results = optimize_ss(_default_input())
    top_10 = results[:10]
    assert len(top_10) == 10
    assert top_10[-1].lifetime_benefit >= results[10].lifetime_benefit
