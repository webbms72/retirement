"""Pydantic v2 request/response schemas — one class per resource."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Profiles ──────────────────────────────────────────────────────────────────


class ProfileCreate(BaseModel):
    name: str
    dob: str  # YYYY-MM-DD
    life_expectancy_age: int = 88
    state: str = "DE"
    filing_status: str = "mfj"
    pre_retirement_income: float = 0.0


class ProfileUpdate(ProfileCreate):
    pass


class ProfileOut(ProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── Accounts ──────────────────────────────────────────────────────────────────


class AccountCreate(BaseModel):
    owner_id: int
    account_type: str
    balance: float = 0.0
    annual_return: float = 0.07
    annual_contribution: float = 0.0
    nqdc_schedule: list[dict[str, Any]] | None = None
    pension_monthly: float | None = None
    pension_start_age: int | None = None
    rental_annual_income: float | None = None


class AccountUpdate(AccountCreate):
    pass


class AccountOut(AccountCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── Social Security ───────────────────────────────────────────────────────────


class SocialSecurityCreate(BaseModel):
    owner_id: int
    benefit_at_62: float = 0.0
    benefit_at_fra: float = 0.0
    fra_age: int = 67
    benefit_at_70: float = 0.0
    survivor_benefit_pct: float = 1.0


class SocialSecurityUpdate(SocialSecurityCreate):
    pass


class SocialSecurityOut(SocialSecurityCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ── Scenarios ─────────────────────────────────────────────────────────────────


class ScenarioCreate(BaseModel):
    name: str
    retirement_age_you: int = 57
    retirement_age_spouse: int = 57
    annual_spending: float = 120000.0
    spending_glide_path: dict[str, float] | None = None
    ss_claim_age_you: int = 67
    ss_claim_age_spouse: int = 67
    withdrawal_strategy: str = "optimized"
    manual_withdrawal_order: list[str] | None = None
    roth_conversion_enabled: bool = False
    roth_conversion_target_bracket: str | None = None
    healthcare_monthly_pre_medicare: float = 0.0
    stock_allocation: float = Field(default=0.60, ge=0.0, le=1.0)
    expected_return_stocks: float = 0.07
    expected_return_bonds: float = 0.04
    inflation_rate: float = 0.025


class ScenarioUpdate(ScenarioCreate):
    pass


class ScenarioOut(ScenarioCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
