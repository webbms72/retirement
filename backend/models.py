"""SQLAlchemy ORM models — all tables in retirement.db."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class _JSONColumn:
    """Mixin helpers — SQLite has no native JSON; store as TEXT."""

    @staticmethod
    def dumps(val: Any) -> str | None:
        return json.dumps(val) if val is not None else None

    @staticmethod
    def loads(val: str | None) -> Any:
        return json.loads(val) if val is not None else None


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    dob: Mapped[str] = mapped_column(String(10), nullable=False)
    life_expectancy_age: Mapped[int] = mapped_column(Integer, default=88)
    state: Mapped[str] = mapped_column(String(2), default="DE")
    filing_status: Mapped[str] = mapped_column(String(16), default="mfj")
    pre_retirement_income: Mapped[float] = mapped_column(Float, default=0.0)

    accounts: Mapped[list[Account]] = relationship(
        "Account", back_populates="owner", cascade="all, delete-orphan"
    )
    social_security: Mapped[SocialSecurity | None] = relationship(
        "SocialSecurity",
        back_populates="owner",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False
    )
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    annual_return: Mapped[float] = mapped_column(Float, default=0.07)
    annual_contribution: Mapped[float] = mapped_column(Float, default=0.0)
    _nqdc_schedule: Mapped[str | None] = mapped_column(
        "nqdc_schedule", Text, nullable=True
    )
    pension_monthly: Mapped[float | None] = mapped_column(Float, nullable=True)
    pension_start_age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rental_annual_income: Mapped[float | None] = mapped_column(Float, nullable=True)

    owner: Mapped[Profile] = relationship("Profile", back_populates="accounts")

    @property
    def nqdc_schedule(self) -> list[dict] | None:
        return _JSONColumn.loads(self._nqdc_schedule)

    @nqdc_schedule.setter
    def nqdc_schedule(self, val: list[dict] | None) -> None:
        self._nqdc_schedule = _JSONColumn.dumps(val)


class SocialSecurity(Base):
    __tablename__ = "social_security"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("profiles.id"), nullable=False, unique=True
    )
    benefit_at_62: Mapped[float] = mapped_column(Float, default=0.0)
    benefit_at_fra: Mapped[float] = mapped_column(Float, default=0.0)
    fra_age: Mapped[int] = mapped_column(Integer, default=67)
    benefit_at_70: Mapped[float] = mapped_column(Float, default=0.0)
    survivor_benefit_pct: Mapped[float] = mapped_column(Float, default=1.0)

    owner: Mapped[Profile] = relationship("Profile", back_populates="social_security")


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    retirement_age_you: Mapped[int] = mapped_column(Integer, default=57)
    retirement_age_spouse: Mapped[int] = mapped_column(Integer, default=57)
    annual_spending: Mapped[float] = mapped_column(Float, default=120000.0)
    _spending_glide_path: Mapped[str | None] = mapped_column(
        "spending_glide_path", Text, nullable=True
    )
    ss_claim_age_you: Mapped[int] = mapped_column(Integer, default=67)
    ss_claim_age_spouse: Mapped[int] = mapped_column(Integer, default=67)
    withdrawal_strategy: Mapped[str] = mapped_column(String(16), default="optimized")
    _manual_withdrawal_order: Mapped[str | None] = mapped_column(
        "manual_withdrawal_order", Text, nullable=True
    )
    roth_conversion_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    roth_conversion_target_bracket: Mapped[str | None] = mapped_column(
        String(8), nullable=True
    )
    healthcare_monthly_pre_medicare: Mapped[float] = mapped_column(Float, default=0.0)
    stock_allocation: Mapped[float] = mapped_column(Float, default=0.60)
    expected_return_stocks: Mapped[float] = mapped_column(Float, default=0.07)
    expected_return_bonds: Mapped[float] = mapped_column(Float, default=0.04)
    inflation_rate: Mapped[float] = mapped_column(Float, default=0.025)

    projections: Mapped[list[Projection]] = relationship(
        "Projection", back_populates="scenario", cascade="all, delete-orphan"
    )
    mc_results: Mapped[list[MCResult]] = relationship(
        "MCResult", back_populates="scenario", cascade="all, delete-orphan"
    )

    @property
    def spending_glide_path(self) -> dict | None:
        return _JSONColumn.loads(self._spending_glide_path)

    @spending_glide_path.setter
    def spending_glide_path(self, val: dict | None) -> None:
        self._spending_glide_path = _JSONColumn.dumps(val)

    @property
    def manual_withdrawal_order(self) -> list[str] | None:
        return _JSONColumn.loads(self._manual_withdrawal_order)

    @manual_withdrawal_order.setter
    def manual_withdrawal_order(self, val: list[str] | None) -> None:
        self._manual_withdrawal_order = _JSONColumn.dumps(val)


class Projection(Base):
    __tablename__ = "projections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scenarios.id"), nullable=False
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    age_you: Mapped[int] = mapped_column(Integer, nullable=False)
    age_spouse: Mapped[int] = mapped_column(Integer, nullable=False)
    portfolio_balance: Mapped[float] = mapped_column(Float, default=0.0)
    _balances_by_account: Mapped[str | None] = mapped_column(
        "balances_by_account", Text, nullable=True
    )
    gross_income: Mapped[float] = mapped_column(Float, default=0.0)
    _income_by_source: Mapped[str | None] = mapped_column(
        "income_by_source", Text, nullable=True
    )
    federal_tax: Mapped[float] = mapped_column(Float, default=0.0)
    state_tax: Mapped[float] = mapped_column(Float, default=0.0)
    effective_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roth_conversion_amount: Mapped[float] = mapped_column(Float, default=0.0)
    _withdrawal_notes: Mapped[str | None] = mapped_column(
        "withdrawal_notes", Text, nullable=True
    )

    scenario: Mapped[Scenario] = relationship("Scenario", back_populates="projections")

    @property
    def balances_by_account(self) -> dict | None:
        return _JSONColumn.loads(self._balances_by_account)

    @balances_by_account.setter
    def balances_by_account(self, val: dict | None) -> None:
        self._balances_by_account = _JSONColumn.dumps(val)

    @property
    def income_by_source(self) -> dict | None:
        return _JSONColumn.loads(self._income_by_source)

    @income_by_source.setter
    def income_by_source(self, val: dict | None) -> None:
        self._income_by_source = _JSONColumn.dumps(val)

    @property
    def withdrawal_notes(self) -> list | None:
        return _JSONColumn.loads(self._withdrawal_notes)

    @withdrawal_notes.setter
    def withdrawal_notes(self, val: list | None) -> None:
        self._withdrawal_notes = _JSONColumn.dumps(val)


class MCResult(Base):
    __tablename__ = "mc_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scenario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scenarios.id"), nullable=False
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    num_simulations: Mapped[int] = mapped_column(Integer, default=10000)
    survival_rate: Mapped[float] = mapped_column(Float, default=0.0)
    _percentile_10: Mapped[str | None] = mapped_column(
        "percentile_10", Text, nullable=True
    )
    _percentile_25: Mapped[str | None] = mapped_column(
        "percentile_25", Text, nullable=True
    )
    _percentile_50: Mapped[str | None] = mapped_column(
        "percentile_50", Text, nullable=True
    )
    _percentile_75: Mapped[str | None] = mapped_column(
        "percentile_75", Text, nullable=True
    )
    _percentile_90: Mapped[str | None] = mapped_column(
        "percentile_90", Text, nullable=True
    )
    _sensitivity: Mapped[str | None] = mapped_column("sensitivity", Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    scenario: Mapped[Scenario] = relationship("Scenario", back_populates="mc_results")

    @property
    def percentile_10(self) -> dict | None:
        return _JSONColumn.loads(self._percentile_10)

    @percentile_10.setter
    def percentile_10(self, val: dict | None) -> None:
        self._percentile_10 = _JSONColumn.dumps(val)

    @property
    def percentile_25(self) -> dict | None:
        return _JSONColumn.loads(self._percentile_25)

    @percentile_25.setter
    def percentile_25(self, val: dict | None) -> None:
        self._percentile_25 = _JSONColumn.dumps(val)

    @property
    def percentile_50(self) -> dict | None:
        return _JSONColumn.loads(self._percentile_50)

    @percentile_50.setter
    def percentile_50(self, val: dict | None) -> None:
        self._percentile_50 = _JSONColumn.dumps(val)

    @property
    def percentile_75(self) -> dict | None:
        return _JSONColumn.loads(self._percentile_75)

    @percentile_75.setter
    def percentile_75(self, val: dict | None) -> None:
        self._percentile_75 = _JSONColumn.dumps(val)

    @property
    def percentile_90(self) -> dict | None:
        return _JSONColumn.loads(self._percentile_90)

    @percentile_90.setter
    def percentile_90(self, val: dict | None) -> None:
        self._percentile_90 = _JSONColumn.dumps(val)

    @property
    def sensitivity(self) -> dict | None:
        return _JSONColumn.loads(self._sensitivity)

    @sensitivity.setter
    def sensitivity(self, val: dict | None) -> None:
        self._sensitivity = _JSONColumn.dumps(val)
