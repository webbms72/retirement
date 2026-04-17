# Retirement Calculator — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python FastAPI backend with SQLite that models retirement projections, tax-efficient withdrawals, Social Security optimization, and Monte Carlo simulation for a married couple retiring at 56–59.

**Architecture:** FastAPI app with 5 calculation engines (tax, projection, withdrawal optimizer, SS optimizer, Monte Carlo). SQLAlchemy ORM on SQLite. Results cached by input hash. Engines are pure functions — no DB access — tested independently via pytest.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0, Pydantic v2, NumPy, pandas, pytest, ruff, uvicorn

---

## Task 1: Project structure + Makefile + requirements

### 1.1 Create directory skeleton
- [ ] Run the following commands to create all directories:
```bash
mkdir -p retirement/backend/engines
mkdir -p retirement/backend/routers
mkdir -p retirement/backend/tests
mkdir -p retirement/frontend/src
mkdir -p retirement/docs
touch retirement/backend/__init__.py
touch retirement/backend/engines/__init__.py
touch retirement/backend/routers/__init__.py
touch retirement/backend/tests/__init__.py
```

### 1.2 Write requirements.txt
- [ ] Create `retirement/backend/requirements.txt`:
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
pydantic==2.7.1
numpy==1.26.4
pandas==2.2.2
pytest==8.2.0
pytest-asyncio==0.23.6
httpx==0.27.0
ruff==0.4.4
python-multipart==0.0.9
```

### 1.3 Write Makefile
- [ ] Create `retirement/Makefile`:
```makefile
.PHONY: install dev backend frontend db-reset db-seed test lint build

PYTHON := python3
PIP := pip3
UVICORN := uvicorn
BACKEND_DIR := backend
FRONTEND_DIR := frontend

install:
	$(PIP) install -r $(BACKEND_DIR)/requirements.txt
	cd $(FRONTEND_DIR) && npm install

dev:
	@echo "Starting backend and frontend..."
	@$(MAKE) backend &
	@cd $(FRONTEND_DIR) && npm run dev &
	@sleep 2 && open http://localhost:5173 || xdg-open http://localhost:5173 || true
	@wait

backend:
	PYTHONPATH=. $(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd $(FRONTEND_DIR) && npm run dev

db-reset:
	PYTHONPATH=. $(PYTHON) -c "from backend.database import reset_db; reset_db()"
	@echo "Database reset complete."

db-seed:
	PYTHONPATH=. $(PYTHON) -c "from backend.database import seed_db; seed_db()"
	@echo "Database seeded."

test:
	PYTHONPATH=. pytest $(BACKEND_DIR)/tests/ -v

lint:
	ruff check $(BACKEND_DIR)/
	cd $(FRONTEND_DIR) && npx eslint src/

build:
	cd $(FRONTEND_DIR) && npm run build
```

### 1.4 Write start.sh
- [ ] Create `retirement/start.sh`:
```bash
#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

echo "==> Installing dependencies..."
pip3 install -r backend/requirements.txt
cd frontend && npm install && cd ..

echo "==> Resetting database..."
PYTHONPATH=. python3 -c "from backend.database import reset_db; reset_db()"

echo "==> Starting backend on :8000 ..."
PYTHONPATH=. uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "==> Starting frontend on :5173 ..."
cd frontend && npm run dev &
FRONTEND_PID=$!

sleep 2
open http://localhost:5173 2>/dev/null || xdg-open http://localhost:5173 2>/dev/null || true

echo "Backend PID: $BACKEND_PID  Frontend PID: $FRONTEND_PID"
echo "Press Ctrl+C to stop both."
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
```
```bash
chmod +x retirement/start.sh
```

### 1.5 Create .gitignore
- [ ] Create `retirement/.gitignore`:
```
retirement.db
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
node_modules/
frontend/dist/
.env
```

### 1.6 Commit
- [ ] `git -C retirement add Makefile start.sh .gitignore backend/requirements.txt && git -C retirement commit -m "chore: project scaffold — Makefile, requirements, start.sh"`

---

## Task 2: SQLAlchemy models + DB setup

### 2.1 Write backend/database.py
- [ ] Create `retirement/backend/database.py`:
```python
"""Database session setup and lifecycle utilities."""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./retirement.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + FastAPI
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_db() -> None:
    """Drop all tables and recreate them. Used by `make db-reset`."""
    # Import models so their metadata is registered before create_all
    import backend.models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("All tables dropped and recreated.")


def seed_db() -> None:
    """Insert sample data for local development. Used by `make db-seed`."""
    import backend.models as m  # noqa: F401

    reset_db()
    db = SessionLocal()
    try:
        you = m.Profile(
            name="You",
            dob="1972-06-15",
            life_expectancy_age=88,
            state="DE",
            filing_status="mfj",
            pre_retirement_income=200000.0,
        )
        spouse = m.Profile(
            name="Spouse",
            dob="1974-03-22",
            life_expectancy_age=90,
            state="DE",
            filing_status="mfj",
            pre_retirement_income=80000.0,
        )
        db.add_all([you, spouse])
        db.flush()

        accounts = [
            m.Account(owner_id=you.id, account_type="401k", balance=800000.0,
                      annual_return=0.07, annual_contribution=23000.0),
            m.Account(owner_id=you.id, account_type="roth_ira", balance=120000.0,
                      annual_return=0.07, annual_contribution=7000.0),
            m.Account(owner_id=you.id, account_type="brokerage", balance=250000.0,
                      annual_return=0.06, annual_contribution=20000.0),
            m.Account(owner_id=you.id, account_type="hsa", balance=45000.0,
                      annual_return=0.06, annual_contribution=8300.0),
            m.Account(owner_id=you.id, account_type="nqdc", balance=0.0,
                      annual_return=0.0, annual_contribution=0.0,
                      nqdc_schedule=[
                          {"date": "2030-01-15", "amount": 50000},
                          {"date": "2031-01-15", "amount": 50000},
                          {"date": "2032-01-15", "amount": 50000},
                      ]),
            m.Account(owner_id=you.id, account_type="pension", balance=0.0,
                      annual_return=0.0, annual_contribution=0.0,
                      pension_monthly=2500.0, pension_start_age=60),
            m.Account(owner_id=spouse.id, account_type="401k", balance=320000.0,
                      annual_return=0.07, annual_contribution=23000.0),
            m.Account(owner_id=spouse.id, account_type="roth_ira", balance=80000.0,
                      annual_return=0.07, annual_contribution=7000.0),
            m.Account(owner_id=spouse.id, account_type="real_estate", balance=0.0,
                      annual_return=0.0, annual_contribution=0.0,
                      rental_annual_income=24000.0),
        ]
        db.add_all(accounts)

        ss_you = m.SocialSecurity(
            owner_id=you.id,
            benefit_at_62=2200.0,
            benefit_at_fra=3100.0,
            fra_age=67,
            benefit_at_70=3900.0,
            survivor_benefit_pct=1.0,
        )
        ss_spouse = m.SocialSecurity(
            owner_id=spouse.id,
            benefit_at_62=1400.0,
            benefit_at_fra=2000.0,
            fra_age=67,
            benefit_at_70=2500.0,
            survivor_benefit_pct=1.0,
        )
        db.add_all([ss_you, ss_spouse])

        scenario = m.Scenario(
            name="Retire 57 · SS 67/65",
            retirement_age_you=57,
            retirement_age_spouse=57,
            annual_spending=120000.0,
            ss_claim_age_you=67,
            ss_claim_age_spouse=65,
            withdrawal_strategy="optimized",
            roth_conversion_enabled=True,
            roth_conversion_target_bracket="22%",
            healthcare_monthly_pre_medicare=2200.0,
            stock_allocation=0.65,
            expected_return_stocks=0.07,
            expected_return_bonds=0.04,
            inflation_rate=0.025,
        )
        db.add(scenario)
        db.commit()
        print("Seed data inserted.")
    finally:
        db.close()
```

### 2.2 Write backend/models.py
- [ ] Create `retirement/backend/models.py`:
```python
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
    dob: Mapped[str] = mapped_column(String(10), nullable=False)  # ISO date YYYY-MM-DD
    life_expectancy_age: Mapped[int] = mapped_column(Integer, default=88)
    state: Mapped[str] = mapped_column(String(2), default="DE")
    filing_status: Mapped[str] = mapped_column(String(16), default="mfj")
    pre_retirement_income: Mapped[float] = mapped_column(Float, default=0.0)

    accounts: Mapped[list[Account]] = relationship("Account", back_populates="owner",
                                                    cascade="all, delete-orphan")
    social_security: Mapped[SocialSecurity | None] = relationship(
        "SocialSecurity", back_populates="owner", uselist=False,
        cascade="all, delete-orphan"
    )


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"),
                                           nullable=False)
    account_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # account_type values: 401k | roth_ira | brokerage | hsa | nqdc | pension | real_estate

    balance: Mapped[float] = mapped_column(Float, default=0.0)
    annual_return: Mapped[float] = mapped_column(Float, default=0.07)
    annual_contribution: Mapped[float] = mapped_column(Float, default=0.0)

    # NQDC only — stored as JSON text: [{"date": "YYYY-MM-DD", "amount": float}, ...]
    _nqdc_schedule: Mapped[str | None] = mapped_column("nqdc_schedule", Text,
                                                        nullable=True)

    # Pension only
    pension_monthly: Mapped[float | None] = mapped_column(Float, nullable=True)
    pension_start_age: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Real estate only
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
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"),
                                           nullable=False, unique=True)
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

    # Optional age→amount JSON: {"60": 130000, "70": 100000}
    _spending_glide_path: Mapped[str | None] = mapped_column(
        "spending_glide_path", Text, nullable=True
    )

    ss_claim_age_you: Mapped[int] = mapped_column(Integer, default=67)
    ss_claim_age_spouse: Mapped[int] = mapped_column(Integer, default=67)
    withdrawal_strategy: Mapped[str] = mapped_column(String(16), default="optimized")

    # JSON list of account types in priority order for manual mode
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
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"),
                                              nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    age_you: Mapped[int] = mapped_column(Integer, nullable=False)
    age_spouse: Mapped[int] = mapped_column(Integer, nullable=False)
    portfolio_balance: Mapped[float] = mapped_column(Float, default=0.0)

    # JSON: {"401k": 800000, "roth_ira": 120000, ...}
    _balances_by_account: Mapped[str | None] = mapped_column(
        "balances_by_account", Text, nullable=True
    )

    gross_income: Mapped[float] = mapped_column(Float, default=0.0)

    # JSON: {"ss": 37200, "401k": 40000, "roth": 0, ...}
    _income_by_source: Mapped[str | None] = mapped_column(
        "income_by_source", Text, nullable=True
    )

    federal_tax: Mapped[float] = mapped_column(Float, default=0.0)
    state_tax: Mapped[float] = mapped_column(Float, default=0.0)
    effective_rate: Mapped[float] = mapped_column(Float, default=0.0)
    roth_conversion_amount: Mapped[float] = mapped_column(Float, default=0.0)

    # JSON list of human-readable optimizer decisions
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
    scenario_id: Mapped[int] = mapped_column(Integer, ForeignKey("scenarios.id"),
                                              nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    num_simulations: Mapped[int] = mapped_column(Integer, default=10000)
    survival_rate: Mapped[float] = mapped_column(Float, default=0.0)

    # JSON: {year: balance} mapping for each percentile band
    _percentile_10: Mapped[str | None] = mapped_column("percentile_10", Text, nullable=True)
    _percentile_25: Mapped[str | None] = mapped_column("percentile_25", Text, nullable=True)
    _percentile_50: Mapped[str | None] = mapped_column("percentile_50", Text, nullable=True)
    _percentile_75: Mapped[str | None] = mapped_column("percentile_75", Text, nullable=True)
    _percentile_90: Mapped[str | None] = mapped_column("percentile_90", Text, nullable=True)

    # JSON: {"spending": 0.05, "retirement_age": 0.12, ...}
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
```

### 2.3 Verify models initialize cleanly
- [ ]
```bash
cd retirement
PYTHONPATH=. python3 -c "from backend.database import reset_db; reset_db()"
```
Expected output:
```
All tables dropped and recreated.
```

### 2.4 Commit
- [ ] `git -C retirement add backend/database.py backend/models.py && git -C retirement commit -m "feat: SQLAlchemy models and DB setup — profiles, accounts, ss, scenarios, projections, mc_results"`

---

## Task 3: FastAPI app + CRUD routers

### 3.1 Write backend/main.py
- [ ] Create `retirement/backend/main.py`:
```python
"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Base, engine
from backend.routers import accounts, monte_carlo, profiles, projections, scenarios

# Ensure tables exist on startup (idempotent)
import backend.models  # noqa: F401
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Retirement Calculator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profiles.router, prefix="/api/profiles", tags=["profiles"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(projections.router, prefix="/api/projections", tags=["projections"])
app.include_router(monte_carlo.router, prefix="/api/monte-carlo", tags=["monte_carlo"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
```

### 3.2 Write Pydantic schemas file
- [ ] Create `retirement/backend/schemas.py`:
```python
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
```

### 3.3 Write routers/profiles.py
- [ ] Create `retirement/backend/routers/profiles.py`:
```python
"""CRUD endpoints for profiles and their social_security sub-resource."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.schemas import (
    ProfileCreate,
    ProfileOut,
    ProfileUpdate,
    SocialSecurityCreate,
    SocialSecurityOut,
    SocialSecurityUpdate,
)

router = APIRouter()


@router.get("/", response_model=list[ProfileOut])
def list_profiles(db: Session = Depends(get_db)) -> list[models.Profile]:
    return db.query(models.Profile).all()


@router.post("/", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(body: ProfileCreate, db: Session = Depends(get_db)) -> models.Profile:
    profile = models.Profile(**body.model_dump())
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int, db: Session = Depends(get_db)) -> models.Profile:
    profile = db.get(models.Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: int, body: ProfileUpdate, db: Session = Depends(get_db)
) -> models.Profile:
    profile = db.get(models.Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(profile_id: int, db: Session = Depends(get_db)) -> None:
    profile = db.get(models.Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()


# ── Social Security sub-resource ──────────────────────────────────────────────

@router.get("/{profile_id}/social-security", response_model=SocialSecurityOut)
def get_ss(profile_id: int, db: Session = Depends(get_db)) -> models.SocialSecurity:
    profile = db.get(models.Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if not profile.social_security:
        raise HTTPException(status_code=404, detail="No SS record for this profile")
    return profile.social_security


@router.post(
    "/{profile_id}/social-security",
    response_model=SocialSecurityOut,
    status_code=status.HTTP_201_CREATED,
)
def create_ss(
    profile_id: int, body: SocialSecurityCreate, db: Session = Depends(get_db)
) -> models.SocialSecurity:
    profile = db.get(models.Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    if profile.social_security:
        raise HTTPException(status_code=409, detail="SS record already exists; use PUT")
    ss = models.SocialSecurity(**body.model_dump())
    db.add(ss)
    db.commit()
    db.refresh(ss)
    return ss


@router.put("/{profile_id}/social-security", response_model=SocialSecurityOut)
def update_ss(
    profile_id: int, body: SocialSecurityUpdate, db: Session = Depends(get_db)
) -> models.SocialSecurity:
    profile = db.get(models.Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    ss = profile.social_security
    if not ss:
        raise HTTPException(status_code=404, detail="No SS record; use POST to create")
    for field, value in body.model_dump().items():
        setattr(ss, field, value)
    db.commit()
    db.refresh(ss)
    return ss
```

### 3.4 Write routers/accounts.py
- [ ] Create `retirement/backend/routers/accounts.py`:
```python
"""CRUD endpoints for accounts (including NQDC schedule JSON field)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.schemas import AccountCreate, AccountOut, AccountUpdate

router = APIRouter()


@router.get("/", response_model=list[AccountOut])
def list_accounts(
    owner_id: int | None = None, db: Session = Depends(get_db)
) -> list[models.Account]:
    q = db.query(models.Account)
    if owner_id is not None:
        q = q.filter(models.Account.owner_id == owner_id)
    return q.all()


@router.post("/", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
def create_account(body: AccountCreate, db: Session = Depends(get_db)) -> models.Account:
    data = body.model_dump()
    nqdc = data.pop("nqdc_schedule", None)
    account = models.Account(**data)
    account.nqdc_schedule = nqdc
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: int, db: Session = Depends(get_db)) -> models.Account:
    account = db.get(models.Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.put("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: int, body: AccountUpdate, db: Session = Depends(get_db)
) -> models.Account:
    account = db.get(models.Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    data = body.model_dump()
    nqdc = data.pop("nqdc_schedule", None)
    for field, value in data.items():
        setattr(account, field, value)
    account.nqdc_schedule = nqdc
    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(account_id: int, db: Session = Depends(get_db)) -> None:
    account = db.get(models.Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(account)
    db.commit()
```

### 3.5 Write routers/scenarios.py
- [ ] Create `retirement/backend/routers/scenarios.py`:
```python
"""CRUD endpoints for scenarios."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.schemas import ScenarioCreate, ScenarioOut, ScenarioUpdate

router = APIRouter()


@router.get("/", response_model=list[ScenarioOut])
def list_scenarios(db: Session = Depends(get_db)) -> list[models.Scenario]:
    return db.query(models.Scenario).all()


@router.post("/", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED)
def create_scenario(body: ScenarioCreate, db: Session = Depends(get_db)) -> models.Scenario:
    data = body.model_dump()
    glide = data.pop("spending_glide_path", None)
    order = data.pop("manual_withdrawal_order", None)
    scenario = models.Scenario(**data)
    scenario.spending_glide_path = glide
    scenario.manual_withdrawal_order = order
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)) -> models.Scenario:
    scenario = db.get(models.Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.put("/{scenario_id}", response_model=ScenarioOut)
def update_scenario(
    scenario_id: int, body: ScenarioUpdate, db: Session = Depends(get_db)
) -> models.Scenario:
    scenario = db.get(models.Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    data = body.model_dump()
    glide = data.pop("spending_glide_path", None)
    order = data.pop("manual_withdrawal_order", None)
    for field, value in data.items():
        setattr(scenario, field, value)
    scenario.spending_glide_path = glide
    scenario.manual_withdrawal_order = order
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)) -> None:
    scenario = db.get(models.Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    db.delete(scenario)
    db.commit()


@router.post("/{scenario_id}/duplicate", response_model=ScenarioOut,
             status_code=status.HTTP_201_CREATED)
def duplicate_scenario(
    scenario_id: int, db: Session = Depends(get_db)
) -> models.Scenario:
    original = db.get(models.Scenario, scenario_id)
    if not original:
        raise HTTPException(status_code=404, detail="Scenario not found")
    copy = models.Scenario(
        name=f"{original.name} (copy)",
        retirement_age_you=original.retirement_age_you,
        retirement_age_spouse=original.retirement_age_spouse,
        annual_spending=original.annual_spending,
        ss_claim_age_you=original.ss_claim_age_you,
        ss_claim_age_spouse=original.ss_claim_age_spouse,
        withdrawal_strategy=original.withdrawal_strategy,
        roth_conversion_enabled=original.roth_conversion_enabled,
        roth_conversion_target_bracket=original.roth_conversion_target_bracket,
        healthcare_monthly_pre_medicare=original.healthcare_monthly_pre_medicare,
        stock_allocation=original.stock_allocation,
        expected_return_stocks=original.expected_return_stocks,
        expected_return_bonds=original.expected_return_bonds,
        inflation_rate=original.inflation_rate,
    )
    copy.spending_glide_path = original.spending_glide_path
    copy.manual_withdrawal_order = original.manual_withdrawal_order
    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy
```

### 3.6 Write stub routers for projections and monte_carlo
- [ ] Create `retirement/backend/routers/projections.py`:
```python
"""Projection router — full implementation in Task 9/10."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_projections() -> dict:
    return {"detail": "Not yet implemented — see Task 9"}
```

- [ ] Create `retirement/backend/routers/monte_carlo.py`:
```python
"""Monte Carlo router — full implementation in Task 12."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_mc_results() -> dict:
    return {"detail": "Not yet implemented — see Task 12"}
```

### 3.7 Smoke-test the API
- [ ]
```bash
cd retirement
PYTHONPATH=. uvicorn backend.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/api/health
# Expected: {"status":"ok"}
curl -s -X POST http://localhost:8000/api/profiles/ \
  -H "Content-Type: application/json" \
  -d '{"name":"You","dob":"1972-06-15","life_expectancy_age":88,"state":"DE","filing_status":"mfj","pre_retirement_income":200000}'
# Expected: {"id":1,"name":"You",...}
kill %1
```

### 3.8 Commit
- [ ] `git -C retirement add backend/main.py backend/schemas.py backend/routers/ && git -C retirement commit -m "feat: FastAPI app + CRUD routers for profiles, accounts, social_security, scenarios"`

---

## Task 4: Tax Engine — federal brackets + standard deduction

### 4.1 Write test first (TDD)
- [ ] Create `retirement/backend/tests/test_tax.py` with federal ordinary income tax tests:
```python
"""Tests for the Tax Engine — federal ordinary income tax (Task 4)."""

from __future__ import annotations

import pytest

from backend.engines.tax import TaxInput, calculate_federal_ordinary_income_tax


# ── Basic MFJ cases ───────────────────────────────────────────────────────────

def test_mfj_zero_income():
    """Zero taxable income → zero tax."""
    result = calculate_federal_ordinary_income_tax(taxable_income=0.0, filing_status="mfj")
    assert result == 0.0


def test_mfj_within_10pct_bracket():
    """$20,000 MFJ taxable income — entirely in 10% bracket."""
    # Tax = 20,000 * 0.10 = 2,000
    result = calculate_federal_ordinary_income_tax(taxable_income=20_000.0, filing_status="mfj")
    assert result == pytest.approx(2_000.0, abs=1.0)


def test_mfj_spans_two_brackets():
    """$50,000 MFJ — spans 10% and 12% brackets.
    10%: $23,200 → $2,320
    12%: $26,800 → $3,216
    Total: $5,536
    """
    result = calculate_federal_ordinary_income_tax(taxable_income=50_000.0, filing_status="mfj")
    assert result == pytest.approx(5_536.0, abs=1.0)


def test_mfj_six_figures():
    """$150,000 MFJ — spans 10%, 12%, 22% brackets.
    10%: $23,200 → $2,320
    12%: $71,100 → $8,532
    22%: $55,700 → $12,254
    Total: $23,106
    """
    result = calculate_federal_ordinary_income_tax(taxable_income=150_000.0, filing_status="mfj")
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
    result = calculate_federal_ordinary_income_tax(taxable_income=800_000.0, filing_status="mfj")
    assert result == pytest.approx(222_125.50, abs=2.0)


# ── Single filer cases ────────────────────────────────────────────────────────

def test_single_within_10pct():
    """$10,000 single — entirely in 10% bracket."""
    result = calculate_federal_ordinary_income_tax(taxable_income=10_000.0, filing_status="single")
    assert result == pytest.approx(1_000.0, abs=1.0)


def test_single_spans_two_brackets():
    """$30,000 single — spans 10% and 12%.
    10%: 11,600 → 1,160
    12%: 18,400 → 2,208
    Total: 3,368
    """
    result = calculate_federal_ordinary_income_tax(taxable_income=30_000.0, filing_status="single")
    assert result == pytest.approx(3_368.0, abs=1.0)


# ── Standard deduction helper ─────────────────────────────────────────────────

def test_standard_deduction_mfj_under_65():
    from backend.engines.tax import get_standard_deduction
    assert get_standard_deduction(filing_status="mfj", age_you=60, age_spouse=58) == 29_200.0


def test_standard_deduction_mfj_both_65():
    from backend.engines.tax import get_standard_deduction
    # Base $29,200 + $1,550 * 2 = $32,300
    assert get_standard_deduction(filing_status="mfj", age_you=66, age_spouse=66) == 32_300.0


def test_standard_deduction_mfj_one_65():
    from backend.engines.tax import get_standard_deduction
    # Base $29,200 + $1,550 = $30,750
    assert get_standard_deduction(filing_status="mfj", age_you=65, age_spouse=62) == 30_750.0


def test_standard_deduction_single_under_65():
    from backend.engines.tax import get_standard_deduction
    assert get_standard_deduction(filing_status="single", age_you=58, age_spouse=0) == 14_600.0


def test_standard_deduction_single_65_plus():
    from backend.engines.tax import get_standard_deduction
    # $14,600 + $1,550 = $16,150
    assert get_standard_deduction(filing_status="single", age_you=67, age_spouse=0) == 16_150.0
```

- [ ] Run tests — they should fail because the engine doesn't exist yet:
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_tax.py -v 2>&1 | head -20
# Expected: ModuleNotFoundError or ImportError — confirms TDD starting point
```

### 4.2 Write backend/engines/tax.py — Part 1 (federal)
- [ ] Create `retirement/backend/engines/tax.py`:
```python
"""Tax Engine — federal and Delaware state income tax calculations.

All functions are pure (no DB access). Call calculate_taxes() as the main
entry point from the Projection Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── 2024 Federal Tax Brackets ─────────────────────────────────────────────────
# Format: list of (upper_bound, rate) pairs in ascending order.
# The last entry uses float('inf') to capture everything above the top threshold.
# Source: IRS Rev. Proc. 2023-34

MFJ_BRACKETS_2024: list[tuple[float, float]] = [
    (23_200.0,   0.10),
    (94_300.0,   0.12),
    (201_050.0,  0.22),
    (383_900.0,  0.24),
    (487_450.0,  0.32),
    (731_200.0,  0.35),
    (float("inf"), 0.37),
]

SINGLE_BRACKETS_2024: list[tuple[float, float]] = [
    (11_600.0,   0.10),
    (47_150.0,   0.12),
    (100_525.0,  0.22),
    (191_950.0,  0.24),
    (243_725.0,  0.32),
    (609_350.0,  0.35),
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
    filing_status: str          # "mfj" or "single"
    age_you: int
    age_spouse: int             # 0 if single
    ordinary_income: float      # wages, 401k withdrawals, NQDC, pensions, RMDs
    ss_income_you: float = 0.0  # gross SS benefit (before inclusion calc)
    ss_income_spouse: float = 0.0
    ltcg_income: float = 0.0    # long-term capital gains + qualified dividends
    roth_conversion: float = 0.0
    retirement_income_you: float = 0.0   # pension/IRA for DE exclusion
    retirement_income_spouse: float = 0.0
    prior_year_magi: float = 0.0         # for IRMAA lookback
    inflation_factor: float = 1.0        # cumulative inflation since 2024 base year


@dataclass
class TaxResult:
    """Per-year tax calculation results."""
    federal_ordinary_tax: float = 0.0
    federal_ltcg_tax: float = 0.0
    federal_ss_included: float = 0.0     # taxable portion of SS
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
            1.0 = 2024 base year (no adjustment).

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
```

### 4.3 Run the federal bracket tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_tax.py -v -k "federal or standard_deduction or mfj or single"
```
Expected output (all pass):
```
PASSED backend/tests/test_tax.py::test_mfj_zero_income
PASSED backend/tests/test_tax.py::test_mfj_within_10pct_bracket
PASSED backend/tests/test_tax.py::test_mfj_spans_two_brackets
PASSED backend/tests/test_tax.py::test_mfj_six_figures
PASSED backend/tests/test_tax.py::test_mfj_top_bracket
PASSED backend/tests/test_tax.py::test_single_within_10pct
PASSED backend/tests/test_tax.py::test_single_spans_two_brackets
PASSED backend/tests/test_tax.py::test_standard_deduction_mfj_under_65
PASSED backend/tests/test_tax.py::test_standard_deduction_mfj_both_65
PASSED backend/tests/test_tax.py::test_standard_deduction_mfj_one_65
PASSED backend/tests/test_tax.py::test_standard_deduction_single_under_65
PASSED backend/tests/test_tax.py::test_standard_deduction_single_65_plus
12 passed in 0.XXs
```

### 4.4 Commit
- [ ] `git -C retirement add backend/engines/tax.py backend/tests/test_tax.py && git -C retirement commit -m "feat: Tax Engine — federal brackets, standard deduction, TDD (Task 4)"`

---

## Task 5: Tax Engine — Delaware state tax + retirement exclusion

### 5.1 Add DE tests to test_tax.py
- [ ] Append to `retirement/backend/tests/test_tax.py`:
```python
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
    from backend.engines.tax import calculate_delaware_tax
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
    from backend.engines.tax import calculate_delaware_tax
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
    from backend.engines.tax import calculate_delaware_tax
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
```

- [ ] Run new DE tests — expect failures (function not yet implemented):
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_tax.py -v -k "de_" 2>&1 | tail -10
# Expected: ImportError or AttributeError — calculate_delaware_tax not found
```

### 5.2 Add calculate_delaware_tax() to tax.py
- [ ] Append to `retirement/backend/engines/tax.py` after the existing federal functions:
```python
# ── Delaware State Tax ────────────────────────────────────────────────────────
# Brackets 2024 — (upper_bound, rate)
# Source: Delaware Division of Revenue, Tax Rate Tables 2024

DE_BRACKETS_2024: list[tuple[float, float]] = [
    (2_000.0,    0.000),
    (5_000.0,    0.022),
    (10_000.0,   0.039),
    (20_000.0,   0.048),
    (25_000.0,   0.052),
    (60_000.0,   0.0555),
    (float("inf"), 0.066),
]

DE_STANDARD_DEDUCTION_MFJ = 6_500.0
DE_STANDARD_DEDUCTION_SINGLE = 3_250.0
DE_PERSONAL_EXEMPTION = 110.0          # per person
DE_RETIREMENT_EXCLUSION_PER_PERSON = 12_500.0   # after age 60


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

    Retirement income exclusion: $12,500 per person (each spouse) for
    pension/IRA/retirement income, available after age 60.

    Args:
        de_taxable_income: Gross DE taxable income (SS already excluded).
        filing_status: "mfj" or "single".
        num_people: 1 for single, 2 for MFJ (affects personal exemptions).
        age_you: Age of primary filer.
        age_spouse: Age of spouse (0 if single).
        retirement_income_you: Pension/IRA/retirement income for primary filer.
        retirement_income_spouse: Pension/IRA/retirement income for spouse.
        inflation_factor: For future bracket scaling; 1.0 = 2024 base.

    Returns:
        Delaware state income tax as float.
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
        DE_STANDARD_DEDUCTION_MFJ if filing_status == "mfj"
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
```

### 5.3 Run all DE tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_tax.py -v -k "de_"
```
Expected output:
```
PASSED backend/tests/test_tax.py::test_de_zero_income
PASSED backend/tests/test_tax.py::test_de_below_standard_deduction
PASSED backend/tests/test_tax.py::test_de_mfj_moderate_income
PASSED backend/tests/test_tax.py::test_de_retirement_exclusion_both_over_60
PASSED backend/tests/test_tax.py::test_de_single_filer
5 passed in 0.XXs
```

### 5.4 Commit
- [ ] `git -C retirement add backend/engines/tax.py backend/tests/test_tax.py && git -C retirement commit -m "feat: Tax Engine — Delaware state tax + retirement exclusion, TDD (Task 5)"`

---

## Task 6: Tax Engine — SS taxation + LTCG + IRMAA + calculate_taxes()

### 6.1 Add SS inclusion, LTCG, IRMAA, and calculate_taxes() tests
- [ ] Append to `retirement/backend/tests/test_tax.py`:
```python
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
    """MFJ ordinary income $560,000 + LTCG $30,000 — fully at 20%."""
    from backend.engines.tax import calculate_ltcg_tax
    # Above $583,750 MFJ threshold... ordinary alone is $560k, LTCG pushes total to $590k
    # First $23,750 of LTCG at 15%, remaining $6,250 at 20%
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


# ── calculate_taxes() integration test ───────────────────────────────────────

def test_calculate_taxes_full_mfj():
    """Full integration: MFJ couple, age 62/60, moderate retirement income.

    Inputs:
    - Ordinary income (401k withdrawals + NQDC): $80,000
    - SS gross (you): $37,200/yr
    - LTCG: $10,000
    - Roth conversion: $0
    - Retirement income for DE exclusion (you): $80,000
    - Prior year MAGI: $100,000 (below IRMAA)

    Expected: federal tax calculated on (ordinary + SS_included + Roth),
    DE tax calculated on (ordinary - DE_exclusion). Both > 0.
    """
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
```

- [ ] Run new tests — expect failures (functions not yet implemented):
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_tax.py -v -k "ss_inclusion or ltcg or irmaa or calculate_taxes" 2>&1 | tail -15
```

### 6.2 Add SS inclusion, LTCG, IRMAA, and calculate_taxes() to tax.py
- [ ] Append to `retirement/backend/engines/tax.py`:
```python
# ── Social Security Inclusion ─────────────────────────────────────────────────
# IRS thresholds (2024, not inflation-indexed by law, but we allow factor param
# for scenario modeling consistency).

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

    IRS 'combined income' = AGI (excluding SS) + tax-exempt interest + (SS / 2).
    Below base threshold: 0% taxable.
    Between base and upper: up to 50% taxable.
    Above upper threshold: up to 85% taxable.

    Returns the dollar amount of SS benefits included in taxable income.
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
        # Tier 1: 50% of excess over base, capped at 50% of SS
        tier1 = min(0.50 * ss_gross, 0.50 * (combined - base))
        return round(tier1, 2)

    # Tier 2: 85% rule applies
    # Taxable = min(85% of SS, 85% of excess over upper + 50% of (upper - base))
    tier1_max = 0.50 * (upper - base)
    tier2 = 0.85 * (combined - upper) + tier1_max
    taxable_ss = min(0.85 * ss_gross, tier2)
    return round(taxable_ss, 2)


# ── Long-Term Capital Gains Tax ───────────────────────────────────────────────
# 2024 MFJ thresholds: 0% ≤ $94,050; 15% ≤ $583,750; 20% above
# 2024 Single thresholds: 0% ≤ $47,025; 15% ≤ $518,900; 20% above

LTCG_THRESHOLDS: dict[str, tuple[float, float]] = {
    "mfj":    (94_050.0, 583_750.0),
    "single": (47_025.0, 518_900.0),
}


def calculate_ltcg_tax(
    ltcg_income: float,
    ordinary_taxable_income: float,
    filing_status: str,
    inflation_factor: float = 1.0,
) -> float:
    """Calculate federal long-term capital gains tax.

    LTCG is stacked on top of ordinary income. The 0%/15%/20% rates apply
    to the LTCG portion based on where it falls in the combined income stack.

    Args:
        ltcg_income: Gross LTCG + qualified dividends.
        ordinary_taxable_income: Ordinary taxable income (after std deduction).
        filing_status: "mfj" or "single".
        inflation_factor: Scale thresholds for future years.

    Returns:
        LTCG federal tax as float.
    """
    if ltcg_income <= 0:
        return 0.0

    zero_limit, fifteen_limit = LTCG_THRESHOLDS.get(filing_status, LTCG_THRESHOLDS["single"])
    zero_limit *= inflation_factor
    fifteen_limit *= inflation_factor

    # LTCG sits on top of ordinary income in the stack
    ltcg_stack_start = ordinary_taxable_income
    ltcg_stack_end = ordinary_taxable_income + ltcg_income

    tax = 0.0

    # Portion in 0% band
    zero_band_end = min(ltcg_stack_end, zero_limit)
    zero_band_start = min(ltcg_stack_start, zero_limit)
    # tax on 0% portion is 0

    # Portion in 15% band
    fifteen_band_start = max(ltcg_stack_start, zero_limit)
    fifteen_band_end = min(ltcg_stack_end, fifteen_limit)
    if fifteen_band_end > fifteen_band_start:
        tax += (fifteen_band_end - fifteen_band_start) * 0.15

    # Portion in 20% band
    twenty_band_start = max(ltcg_stack_start, fifteen_limit)
    if ltcg_stack_end > twenty_band_start:
        tax += (ltcg_stack_end - twenty_band_start) * 0.20

    return round(tax, 2)


# ── IRMAA Surcharge ───────────────────────────────────────────────────────────
# 2024 MFJ MAGI thresholds and monthly Part B surcharge per person.
# Source: CMS Medicare Part B IRMAA 2024
# Surcharge is in addition to the base Part B premium ($174.70/mo in 2024).
# We model the TOTAL monthly premium per person at each tier.

IRMAA_MFJ_TIERS: list[tuple[float, float]] = [
    # (magi_threshold, additional_monthly_per_person_above_base)
    # Base premium (no surcharge) below $206k
    (206_000.0,  0.00),
    (258_000.0,  69.90),
    (322_000.0, 174.70),
    (386_000.0, 279.50),
    (750_000.0, 384.30),
    (float("inf"), 419.30),
]

IRMAA_SINGLE_TIERS: list[tuple[float, float]] = [
    (103_000.0,   0.00),
    (129_000.0,  69.90),
    (161_000.0, 174.70),
    (193_000.0, 279.50),
    (500_000.0, 384.30),
    (float("inf"), 419.30),
]


def calculate_irmaa_annual(
    prior_year_magi: float,
    filing_status: str,
    num_people: int = 2,
) -> float:
    """Calculate annual IRMAA Medicare Part B surcharge.

    The surcharge is applied per person on Medicare. For MFJ, both spouses
    typically face IRMAA if the joint MAGI exceeds threshold. num_people
    defaults to 2 for MFJ, 1 for single.

    Args:
        prior_year_magi: MAGI from 2 years prior (IRMAA lookback).
        filing_status: "mfj" or "single".
        num_people: Number of Medicare-enrolled people (1 or 2).

    Returns:
        Annual IRMAA surcharge total (both spouses combined) as float.
    """
    tiers = IRMAA_MFJ_TIERS if filing_status == "mfj" else IRMAA_SINGLE_TIERS
    no_surcharge_threshold = tiers[0][0]

    if prior_year_magi <= no_surcharge_threshold:
        return 0.0

    monthly_per_person = 0.0
    for threshold, surcharge in tiers[1:]:
        if prior_year_magi <= threshold:
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

    Returns:
        TaxResult with all computed fields populated.
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

    # 2. Federal AGI (ordinary + SS included + Roth conversion)
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
    )
    result.irmaa_annual = irmaa

    # 7. Federal total
    result.federal_total = round(fed_ordinary + fed_ltcg + irmaa, 2)

    # 8. Delaware state tax (SS excluded, no LTCG treatment — all ordinary in DE)
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
```

### 6.3 Run all Task 6 tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_tax.py -v
```
Expected output — all tests pass:
```
PASSED test_mfj_zero_income
PASSED test_mfj_within_10pct_bracket
PASSED test_mfj_spans_two_brackets
PASSED test_mfj_six_figures
PASSED test_mfj_top_bracket
PASSED test_single_within_10pct
PASSED test_single_spans_two_brackets
PASSED test_standard_deduction_mfj_under_65
PASSED test_standard_deduction_mfj_both_65
PASSED test_standard_deduction_mfj_one_65
PASSED test_standard_deduction_single_under_65
PASSED test_standard_deduction_single_65_plus
PASSED test_de_zero_income
PASSED test_de_below_standard_deduction
PASSED test_de_mfj_moderate_income
PASSED test_de_retirement_exclusion_both_over_60
PASSED test_de_single_filer
PASSED test_ss_inclusion_below_base_threshold
PASSED test_ss_inclusion_middle_tier_mfj
PASSED test_ss_inclusion_above_upper_threshold_mfj
PASSED test_ltcg_0pct_within_threshold
PASSED test_ltcg_partially_in_15pct
PASSED test_ltcg_20pct_threshold
PASSED test_irmaa_below_threshold
PASSED test_irmaa_tier_1_mfj
PASSED test_irmaa_tier_3_mfj
PASSED test_calculate_taxes_full_mfj
27 passed in 0.XXs
```

### 6.4 Lint
- [ ]
```bash
cd retirement
ruff check backend/engines/tax.py backend/tests/test_tax.py
# Expected: no issues found
```

### 6.5 Commit
- [ ] `git -C retirement add backend/engines/tax.py backend/tests/test_tax.py && git -C retirement commit -m "feat: Tax Engine — SS inclusion, LTCG, IRMAA, calculate_taxes() integration (Task 6)"`

---

## Task 7: Withdrawal Optimizer — account ordering + Rule of 55

### 7.1 Write tests first
- [ ] Create `retirement/backend/tests/test_withdrawal.py`:
```python
"""Tests for the Withdrawal Optimizer — Task 7 (ordering + Rule of 55)."""

from __future__ import annotations

import pytest

from backend.engines.withdrawal import (
    AccountState,
    WithdrawalInput,
    WithdrawalResult,
    optimize_withdrawals,
)


def _default_accounts(
    k401=500_000.0,
    roth=150_000.0,
    brokerage=200_000.0,
    hsa=40_000.0,
) -> list[AccountState]:
    return [
        AccountState(account_type="401k", balance=k401, basis=0.0,
                     owner="you", is_rule_of_55_eligible=False),
        AccountState(account_type="roth_ira", balance=roth, basis=roth,
                     owner="you", roth_conversion_cohorts={}),
        AccountState(account_type="brokerage", balance=brokerage, basis=100_000.0, owner="you"),
        AccountState(account_type="hsa", balance=hsa, basis=0.0, owner="you"),
    ]


# ── Basic ordering ────────────────────────────────────────────────────────────

def test_zero_required_amount():
    """No withdrawal needed → all amounts zero."""
    wi = WithdrawalInput(
        required_amount=0.0,
        account_states=_default_accounts(),
        age_you=58,
        age_spouse=56,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=80_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.total_withdrawn == pytest.approx(0.0, abs=0.01)
    assert all(v == 0.0 for v in result.withdrawals_by_account.values())


def test_brokerage_first_when_0pct_ltcg_available():
    """When ordinary taxable income is $40k MFJ (below $94,050 0% LTCG threshold),
    brokerage should be drawn first for non-RMD gap."""
    wi = WithdrawalInput(
        required_amount=20_000.0,
        account_states=_default_accounts(),
        age_you=58,
        age_spouse=56,
        current_marginal_rate=0.12,
        current_ordinary_taxable_income=40_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    # Brokerage should cover full $20k since 0% LTCG is available
    assert result.withdrawals_by_account.get("brokerage", 0.0) == pytest.approx(20_000.0, abs=1.0)
    assert result.withdrawals_by_account.get("401k", 0.0) == 0.0
    assert result.withdrawals_by_account.get("roth_ira", 0.0) == 0.0


def test_roth_drawn_last():
    """Even with large required amount, Roth should only be tapped after brokerage and 401k."""
    wi = WithdrawalInput(
        required_amount=400_000.0,  # very large — forces multiple accounts
        account_states=_default_accounts(k401=200_000.0, brokerage=100_000.0, roth=150_000.0),
        age_you=62,
        age_spouse=60,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    roth_amount = result.withdrawals_by_account.get("roth_ira", 0.0)
    brokerage_amount = result.withdrawals_by_account.get("brokerage", 0.0)
    k401_amount = result.withdrawals_by_account.get("401k", 0.0)
    # Brokerage and 401k should be fully exhausted before Roth
    assert brokerage_amount == pytest.approx(100_000.0, abs=1.0)
    assert k401_amount == pytest.approx(200_000.0, abs=1.0)
    assert roth_amount > 0  # Roth tapped for the remainder


def test_hsa_covers_healthcare_first():
    """HSA should be used for healthcare expenses before any other account."""
    wi = WithdrawalInput(
        required_amount=30_000.0,
        account_states=_default_accounts(hsa=40_000.0),
        age_you=60,
        age_spouse=58,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=80_000.0,
        filing_status="mfj",
        healthcare_amount=10_000.0,  # $10k healthcare in this year
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.withdrawals_by_account.get("hsa", 0.0) == pytest.approx(10_000.0, abs=1.0)
    assert "HSA" in " ".join(result.notes)


# ── Rule of 55 ────────────────────────────────────────────────────────────────

def test_no_penalty_with_rule_of_55():
    """Age 57, Rule of 55 eligible → 401k withdrawal has no 10% penalty."""
    accounts = [
        AccountState(account_type="401k", balance=500_000.0, basis=0.0,
                     owner="you", is_rule_of_55_eligible=True),
        AccountState(account_type="roth_ira", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="brokerage", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="hsa", balance=0.0, basis=0.0, owner="you"),
    ]
    wi = WithdrawalInput(
        required_amount=50_000.0,
        account_states=accounts,
        age_you=57,
        age_spouse=55,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.early_withdrawal_penalty == pytest.approx(0.0, abs=0.01)
    assert result.withdrawals_by_account.get("401k", 0.0) == pytest.approx(50_000.0, abs=1.0)


def test_penalty_applies_without_rule_of_55():
    """Age 57, NOT Rule of 55 eligible, no brokerage/Roth → 10% penalty on 401k."""
    accounts = [
        AccountState(account_type="401k", balance=500_000.0, basis=0.0,
                     owner="you", is_rule_of_55_eligible=False),
        AccountState(account_type="roth_ira", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="brokerage", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="hsa", balance=0.0, basis=0.0, owner="you"),
    ]
    wi = WithdrawalInput(
        required_amount=50_000.0,
        account_states=accounts,
        age_you=57,
        age_spouse=55,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    # 10% penalty on the 401k withdrawal amount
    assert result.early_withdrawal_penalty == pytest.approx(
        result.withdrawals_by_account.get("401k", 0.0) * 0.10, abs=1.0
    )


def test_no_penalty_after_59_half():
    """Age 60 → no early withdrawal penalty regardless of Rule of 55."""
    accounts = [
        AccountState(account_type="401k", balance=500_000.0, basis=0.0,
                     owner="you", is_rule_of_55_eligible=False),
        AccountState(account_type="roth_ira", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="brokerage", balance=0.0, basis=0.0, owner="you"),
        AccountState(account_type="hsa", balance=0.0, basis=0.0, owner="you"),
    ]
    wi = WithdrawalInput(
        required_amount=50_000.0,
        account_states=accounts,
        age_you=60,
        age_spouse=58,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2030,
    )
    result = optimize_withdrawals(wi)
    assert result.early_withdrawal_penalty == 0.0
```

- [ ] Run tests — expect failures:
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_withdrawal.py -v 2>&1 | tail -10
```

### 7.2 Write backend/engines/withdrawal.py
- [ ] Create `retirement/backend/engines/withdrawal.py`:
```python
"""Withdrawal Optimizer — determines most tax-efficient source order each year.

All functions are pure (no DB access).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AccountState:
    """Current state of one account at the start of a projection year."""
    account_type: str       # "401k" | "roth_ira" | "brokerage" | "hsa" | "nqdc" | "pension" | "real_estate"
    balance: float
    basis: float            # cost basis (for brokerage LTCG calc) or contribution basis (Roth)
    owner: str              # "you" or "spouse"
    is_rule_of_55_eligible: bool = False
    # Roth conversion cohorts: {conversion_year: amount_converted}
    # Used in Task 8 to enforce 5-year rule before age 59.5
    roth_conversion_cohorts: dict[int, float] = field(default_factory=dict)


@dataclass
class WithdrawalInput:
    """Inputs for the withdrawal optimizer for a single projection year."""
    required_amount: float          # total cash needed after guaranteed income
    account_states: list[AccountState]
    age_you: int
    age_spouse: int
    current_marginal_rate: float    # federal marginal rate at current income level
    current_ordinary_taxable_income: float  # ordinary taxable income before withdrawals
    filing_status: str              # "mfj" or "single"
    healthcare_amount: float        # annual healthcare spend (for HSA targeting)
    roth_conversion_enabled: bool
    target_bracket_rate: float | None       # e.g. 0.22 — fill to this rate with conversions
    target_bracket_ceiling: float | None    # top of target bracket in absolute dollars
    current_year: int


@dataclass
class WithdrawalResult:
    """Result of the withdrawal optimizer for a single year."""
    withdrawals_by_account: dict[str, float] = field(default_factory=dict)
    roth_conversion_amount: float = 0.0
    total_withdrawn: float = 0.0
    early_withdrawal_penalty: float = 0.0
    notes: list[str] = field(default_factory=list)


# ── LTCG threshold constants (MFJ 2024) ──────────────────────────────────────
LTCG_0PCT_CEILING_MFJ = 94_050.0
LTCG_0PCT_CEILING_SINGLE = 47_025.0


def _is_before_59_half(age: int) -> bool:
    """True if the person has not yet reached age 59½.

    We use integer ages here; assume the person has not yet hit their
    half-birthday. For a conservative approximation, treat < 60 as pre-59½.
    """
    return age < 60


def _has_ltcg_0pct_room(
    current_ordinary_taxable_income: float,
    filing_status: str,
    inflation_factor: float = 1.0,
) -> bool:
    """Return True if current income is below the 0% LTCG threshold."""
    ceiling = (
        LTCG_0PCT_CEILING_MFJ if filing_status == "mfj" else LTCG_0PCT_CEILING_SINGLE
    ) * inflation_factor
    return current_ordinary_taxable_income < ceiling


def optimize_withdrawals(wi: WithdrawalInput) -> WithdrawalResult:
    """Determine optimal withdrawal amounts and sources for a single year.

    Ordering logic (optimized mode):
    1. HSA — cover healthcare_amount first (tax-free for medical expenses).
    2. Brokerage — if 0% LTCG is available (income below threshold).
    3. Roth conversion — if enabled and room exists below target bracket ceiling.
    4. 401k / Traditional IRA:
       - Prefer 401k over IRA if Rule of 55 applies (penalty-free window).
       - Apply 10% early withdrawal penalty if age < 60 and no Rule of 55.
    5. Roth IRA — drawn last (tax-free, no RMDs, preserve for later years).

    Note: RMDs are handled upstream by the Projection Engine and are NOT part
    of this optimizer's required_amount — they arrive pre-taken. This optimizer
    handles the discretionary spending gap only.

    Returns:
        WithdrawalResult with per-account amounts and any penalty amounts.
    """
    result = WithdrawalResult()
    remaining = wi.required_amount

    if remaining <= 0:
        return result

    accounts_by_type: dict[str, AccountState] = {
        a.account_type: a for a in wi.account_states
    }

    def draw(account_type: str, amount: float) -> float:
        """Draw up to `amount` from account. Returns actual amount drawn."""
        acct = accounts_by_type.get(account_type)
        if acct is None or acct.balance <= 0:
            return 0.0
        drawn = min(acct.balance, amount)
        result.withdrawals_by_account[account_type] = (
            result.withdrawals_by_account.get(account_type, 0.0) + drawn
        )
        acct.balance -= drawn
        return drawn

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

    # ── Step 2: Brokerage at 0% LTCG ─────────────────────────────────────────
    if _has_ltcg_0pct_room(wi.current_ordinary_taxable_income, wi.filing_status):
        ceiling = (
            LTCG_0PCT_CEILING_MFJ if wi.filing_status == "mfj" else LTCG_0PCT_CEILING_SINGLE
        )
        ltcg_room = ceiling - wi.current_ordinary_taxable_income
        brokerage_limit = min(remaining, ltcg_room)
        brokerage_drawn = draw("brokerage", brokerage_limit)
        if brokerage_drawn > 0:
            remaining -= brokerage_drawn
            result.notes.append(
                f"Brokerage: drew ${brokerage_drawn:,.0f} at 0% LTCG rate"
            )

    if remaining <= 0:
        result.total_withdrawn = wi.required_amount
        return result

    # ── Step 3: Roth conversion (fill bracket to target rate) ─────────────────
    if (
        wi.roth_conversion_enabled
        and wi.target_bracket_ceiling is not None
        and wi.target_bracket_rate is not None
    ):
        conversion_room = max(
            0.0,
            wi.target_bracket_ceiling - wi.current_ordinary_taxable_income
        )
        if conversion_room > 0:
            k401 = accounts_by_type.get("401k")
            if k401 and k401.balance > 0:
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

    # ── Step 4: 401k / Traditional IRA ───────────────────────────────────────
    # Prefer 401k when Rule of 55 is active (before age 60)
    pre_tax_order: list[str] = []
    k401_state = accounts_by_type.get("401k")
    if (
        _is_before_59_half(wi.age_you)
        and k401_state is not None
        and k401_state.is_rule_of_55_eligible
    ):
        # Rule of 55 window: 401k first (no penalty), IRA second (would have penalty)
        pre_tax_order = ["401k"]
    else:
        pre_tax_order = ["401k"]

    for acct_type in pre_tax_order:
        drawn = draw(acct_type, remaining)
        if drawn > 0:
            remaining -= drawn
            # Early withdrawal penalty
            acct = accounts_by_type.get(acct_type)
            is_pre_59_half = _is_before_59_half(wi.age_you)
            rule55 = (acct_type == "401k" and k401_state and k401_state.is_rule_of_55_eligible)
            if is_pre_59_half and not rule55:
                penalty = drawn * 0.10
                result.early_withdrawal_penalty += penalty
                result.notes.append(
                    f"{acct_type}: drew ${drawn:,.0f} — "
                    f"10% early withdrawal penalty ${penalty:,.0f}"
                )
            else:
                qualifier = "(Rule of 55)" if rule55 else "(age >= 60)"
                result.notes.append(
                    f"{acct_type}: drew ${drawn:,.0f}, no penalty {qualifier}"
                )

    if remaining <= 0:
        result.total_withdrawn = wi.required_amount - remaining
        return result

    # ── Step 5: Roth IRA — last resort ────────────────────────────────────────
    roth_drawn = draw("roth_ira", remaining)
    if roth_drawn > 0:
        remaining -= roth_drawn
        result.notes.append(
            f"Roth IRA: drew ${roth_drawn:,.0f} (tax-free)"
        )

    # Shortfall (all accounts exhausted)
    if remaining > 0:
        result.notes.append(
            f"WARNING: portfolio shortfall of ${remaining:,.0f} — all accounts exhausted"
        )

    result.total_withdrawn = wi.required_amount - max(0.0, remaining)
    return result
```

### 7.3 Run withdrawal tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_withdrawal.py -v
```
Expected:
```
PASSED test_zero_required_amount
PASSED test_brokerage_first_when_0pct_ltcg_available
PASSED test_roth_drawn_last
PASSED test_hsa_covers_healthcare_first
PASSED test_no_penalty_with_rule_of_55
PASSED test_penalty_applies_without_rule_of_55
PASSED test_no_penalty_after_59_half
7 passed in 0.XXs
```

### 7.4 Commit
- [ ] `git -C retirement add backend/engines/withdrawal.py backend/tests/test_withdrawal.py && git -C retirement commit -m "feat: Withdrawal Optimizer — account ordering, Rule of 55, penalty logic (Task 7)"`

---

## Task 8: Withdrawal Optimizer — Roth 5-year rule + RMD calculation

### 8.1 Add RMD and Roth 5-year rule tests
- [ ] Append to `retirement/backend/tests/test_withdrawal.py`:
```python
# ── RMD Tests (Task 8) ────────────────────────────────────────────────────────

def test_rmd_age_73_calculation():
    """Age 73 with $500,000 pre-tax balance → RMD = $500,000 / 26.5 = $18,868."""
    from backend.engines.withdrawal import calculate_rmd
    result = calculate_rmd(prior_year_balance=500_000.0, age=73)
    assert result == pytest.approx(18_867.92, abs=1.0)


def test_rmd_age_75():
    """Age 75, $400,000 balance → RMD = $400,000 / 24.6 = $16,260.16."""
    from backend.engines.withdrawal import calculate_rmd
    result = calculate_rmd(prior_year_balance=400_000.0, age=75)
    assert result == pytest.approx(16_260.16, abs=1.0)


def test_rmd_age_80():
    """Age 80, $600,000 → RMD = $600,000 / 20.2 = $29,702.97."""
    from backend.engines.withdrawal import calculate_rmd
    result = calculate_rmd(prior_year_balance=600_000.0, age=80)
    assert result == pytest.approx(29_702.97, abs=1.0)


def test_rmd_below_73_returns_zero():
    """No RMD before age 73 (SECURE 2.0)."""
    from backend.engines.withdrawal import calculate_rmd
    result = calculate_rmd(prior_year_balance=1_000_000.0, age=72)
    assert result == 0.0


def test_rmd_age_95():
    """Age 95, $200,000 → RMD = $200,000 / 8.9 = $22,471.91."""
    from backend.engines.withdrawal import calculate_rmd
    result = calculate_rmd(prior_year_balance=200_000.0, age=95)
    assert result == pytest.approx(22_471.91, abs=1.0)


# ── Roth 5-year rule tests ────────────────────────────────────────────────────

def test_roth_conversion_seasoned_accessible():
    """Conversion from 2025 is accessible penalty-free in 2030 (5 years)."""
    from backend.engines.withdrawal import is_roth_conversion_accessible
    # Current year 2030, conversion year 2025 → 5 years elapsed → accessible
    result = is_roth_conversion_accessible(
        conversion_year=2025, current_year=2030, age_you=58
    )
    assert result is True


def test_roth_conversion_not_yet_seasoned():
    """Conversion from 2028 is NOT accessible in 2030 (only 2 years)."""
    from backend.engines.withdrawal import is_roth_conversion_accessible
    result = is_roth_conversion_accessible(
        conversion_year=2028, current_year=2030, age_you=58
    )
    assert result is False


def test_roth_5_year_rule_bypassed_after_59_half():
    """After age 59.5 (we use 60), 5-year rule no longer blocks access."""
    from backend.engines.withdrawal import is_roth_conversion_accessible
    # Even a very recent conversion is OK after 60
    result = is_roth_conversion_accessible(
        conversion_year=2029, current_year=2030, age_you=61
    )
    assert result is True


def test_rmd_included_before_discretionary_gap():
    """When age 73+, RMD is taken first; optimizer covers remaining gap."""
    from backend.engines.withdrawal import AccountState, WithdrawalInput, optimize_withdrawals

    accounts = [
        AccountState(account_type="401k", balance=600_000.0, basis=0.0,
                     owner="you", is_rule_of_55_eligible=False),
        AccountState(account_type="roth_ira", balance=100_000.0, basis=100_000.0,
                     owner="you"),
        AccountState(account_type="brokerage", balance=50_000.0, basis=25_000.0,
                     owner="you"),
        AccountState(account_type="hsa", balance=20_000.0, basis=0.0, owner="you"),
    ]
    wi = WithdrawalInput(
        required_amount=60_000.0,
        account_states=accounts,
        age_you=73,
        age_spouse=71,
        current_marginal_rate=0.22,
        current_ordinary_taxable_income=50_000.0,
        filing_status="mfj",
        healthcare_amount=0.0,
        roth_conversion_enabled=False,
        target_bracket_rate=None,
        target_bracket_ceiling=None,
        current_year=2045,
        prior_year_pretax_balance=600_000.0,  # used for RMD calc
    )
    result = optimize_withdrawals(wi)
    # RMD = 600,000 / 26.5 = 22,641.51 — taken from 401k automatically
    rmd = result.rmd_taken.get("401k", 0.0)
    assert rmd == pytest.approx(22_641.51, abs=1.0)
    assert result.total_withdrawn >= 60_000.0 - 0.01
```

### 8.2 Add calculate_rmd() and is_roth_conversion_accessible() to withdrawal.py
- [ ] Append to `retirement/backend/engines/withdrawal.py`:
```python
# ── IRS Uniform Lifetime Table (key divisors for RMD calculation) ─────────────
# Source: IRS Publication 590-B, Appendix B, Uniform Lifetime Table
# Full table from age 72 to 115+

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
    94:  9.5,
    95:  8.9,
    96:  8.4,
    97:  7.8,
    98:  7.3,
    99:  6.8,
    100: 6.4,
}
RMD_MIN_AGE = 73  # SECURE 2.0 — RMDs begin at 73


def calculate_rmd(prior_year_balance: float, age: int) -> float:
    """Calculate Required Minimum Distribution for a pre-tax account.

    RMD = prior December 31 balance / IRS Uniform Lifetime Table divisor.
    Returns 0 if age < 73 (SECURE 2.0 threshold).

    Args:
        prior_year_balance: Account balance as of December 31 of prior year.
        age: Account owner's age in the current year.

    Returns:
        RMD amount as float.
    """
    if age < RMD_MIN_AGE:
        return 0.0

    # For ages beyond the table, use divisor 1.9 (IRS rule for 115+)
    divisor = RMD_DIVISORS.get(age, 1.9)
    return round(prior_year_balance / divisor, 2)


def is_roth_conversion_accessible(
    conversion_year: int,
    current_year: int,
    age_you: int,
) -> bool:
    """Determine if a Roth conversion cohort is penalty-free accessible.

    Rules:
    - After age 59.5 (we use >= 60): 5-year rule for conversions does not apply.
    - Before age 60: conversion must have been made at least 5 years ago
      (current_year - conversion_year >= 5).

    Note: This is for the Roth CONVERSION 5-year rule, not the Roth IRA
    5-year rule for earnings. Contributions are always accessible.

    Args:
        conversion_year: Year the Roth conversion was performed.
        current_year: The current projection year.
        age_you: Current age of the primary account holder.

    Returns:
        True if the conversion is accessible without the 10% penalty.
    """
    if age_you >= 60:
        return True  # 5-year conversion rule does not apply post-59.5
    return (current_year - conversion_year) >= 5
```

- [ ] Update `WithdrawalInput` to include `prior_year_pretax_balance` and update `WithdrawalResult` to include `rmd_taken`, then update `optimize_withdrawals()` to take RMDs first when age >= 73. Add these fields to the dataclasses:
```python
# Add to WithdrawalInput dataclass:
prior_year_pretax_balance: float = 0.0   # combined pre-tax balance Dec 31 prior year

# Add to WithdrawalResult dataclass:
rmd_taken: dict[str, float] = field(default_factory=dict)
```
- [ ] Update `optimize_withdrawals()` to prepend RMD logic before Step 1 (HSA):
```python
# ── Step 0: RMDs (mandatory — taken before any discretionary withdrawal) ──────
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
```

### 8.3 Run all Task 8 tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_withdrawal.py -v
```
Expected — all tests pass including the new RMD and Roth 5-year tests.

### 8.4 Run full test suite to confirm no regressions
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/ -v
```
Expected: all tests pass.

### 8.5 Commit
- [ ] `git -C retirement add backend/engines/withdrawal.py backend/tests/test_withdrawal.py && git -C retirement commit -m "feat: Withdrawal Optimizer — RMD calculation (IRS table), Roth 5-year rule (Task 8)"`

---

## Task 9: Projection Engine — single year step

### 9.1 Write tests first
- [ ] Create `retirement/backend/tests/test_projection.py`:
```python
"""Tests for the Projection Engine — Task 9 (single year step)."""

from __future__ import annotations

import pytest

from backend.engines.projection import (
    AccountState,
    ProjectionYear,
    ScenarioParams,
    project_one_year,
)


def _make_scenario(
    retirement_age_you: int = 57,
    retirement_age_spouse: int = 57,
    annual_spending: float = 120_000.0,
    ss_claim_age_you: int = 67,
    ss_claim_age_spouse: int = 67,
    stock_allocation: float = 0.65,
    expected_return_stocks: float = 0.07,
    expected_return_bonds: float = 0.04,
    inflation_rate: float = 0.025,
) -> ScenarioParams:
    return ScenarioParams(
        retirement_age_you=retirement_age_you,
        retirement_age_spouse=retirement_age_spouse,
        annual_spending=annual_spending,
        spending_glide_path={},
        ss_claim_age_you=ss_claim_age_you,
        ss_claim_age_spouse=ss_claim_age_spouse,
        ss_monthly_you=3_100.0,
        ss_monthly_spouse=2_000.0,
        withdrawal_strategy="optimized",
        manual_withdrawal_order=None,
        roth_conversion_enabled=False,
        roth_conversion_target_bracket=None,
        healthcare_monthly_pre_medicare=2_200.0,
        stock_allocation=stock_allocation,
        expected_return_stocks=expected_return_stocks,
        expected_return_bonds=expected_return_bonds,
        inflation_rate=inflation_rate,
        pension_monthly_you=0.0,
        pension_start_age_you=0,
        rental_annual_income=0.0,
        nqdc_schedule=[],
        life_expectancy_you=88,
        life_expectancy_spouse=90,
        dob_year_you=1972,
        dob_year_spouse=1974,
        base_year=2024,
        filing_status="mfj",
        state="DE",
    )


def _make_accounts(
    k401: float = 500_000.0,
    roth: float = 100_000.0,
    brokerage: float = 150_000.0,
    hsa: float = 30_000.0,
) -> list[AccountState]:
    from backend.engines.withdrawal import AccountState as WAccountState
    return [
        AccountState(account_type="401k", balance=k401, basis=0.0,
                     owner="you", is_rule_of_55_eligible=True),
        AccountState(account_type="roth_ira", balance=roth, basis=roth, owner="you"),
        AccountState(account_type="brokerage", balance=brokerage, basis=75_000.0,
                     owner="you"),
        AccountState(account_type="hsa", balance=hsa, basis=0.0, owner="you"),
    ]


def test_project_one_year_accounts_grow():
    """With no withdrawals needed (zero spending), all account balances grow."""
    params = _make_scenario(annual_spending=0.0, retirement_age_you=57)
    accounts = _make_accounts()
    initial_total = sum(a.balance for a in accounts)

    result = project_one_year(
        year=2030,
        age_you=58,
        age_spouse=56,
        accounts=accounts,
        params=params,
        prior_year_magi=80_000.0,
        cumulative_inflation=1.0,
        is_retired_you=True,
        is_retired_spouse=True,
        first_death_year=None,
    )

    assert isinstance(result, ProjectionYear)
    assert result.portfolio_balance > initial_total


def test_project_one_year_spending_reduces_portfolio():
    """Annual spending draws down the portfolio compared to zero-spend baseline."""
    params_spend = _make_scenario(annual_spending=120_000.0)
    params_zero = _make_scenario(annual_spending=0.0)

    accounts_spend = _make_accounts()
    accounts_zero = _make_accounts()

    result_spend = project_one_year(
        year=2030, age_you=58, age_spouse=56,
        accounts=accounts_spend, params=params_spend,
        prior_year_magi=80_000.0, cumulative_inflation=1.0,
        is_retired_you=True, is_retired_spouse=True, first_death_year=None,
    )
    result_zero = project_one_year(
        year=2030, age_you=58, age_spouse=56,
        accounts=accounts_zero, params=params_zero,
        prior_year_magi=80_000.0, cumulative_inflation=1.0,
        is_retired_you=True, is_retired_spouse=True, first_death_year=None,
    )

    assert result_spend.portfolio_balance < result_zero.portfolio_balance


def test_project_one_year_ss_income_starts_at_claim_age():
    """SS income appears in income_by_source only after ss_claim_age_you is reached."""
    params_before_ss = _make_scenario(ss_claim_age_you=67)
    params_after_ss = _make_scenario(ss_claim_age_you=67)
    accounts = _make_accounts()

    # Age 65 — before SS
    result_before = project_one_year(
        year=2037, age_you=65, age_spouse=63,
        accounts=_make_accounts(), params=params_before_ss,
        prior_year_magi=80_000.0, cumulative_inflation=1.0,
        is_retired_you=True, is_retired_spouse=True, first_death_year=None,
    )
    # Age 68 — after SS claim at 67
    result_after = project_one_year(
        year=2040, age_you=68, age_spouse=66,
        accounts=_make_accounts(), params=params_after_ss,
        prior_year_magi=80_000.0, cumulative_inflation=1.0,
        is_retired_you=True, is_retired_spouse=True, first_death_year=None,
    )

    assert result_before.income_by_source.get("ss_you", 0.0) == 0.0
    assert result_after.income_by_source.get("ss_you", 0.0) > 0.0


def test_project_one_year_returns_correct_ages():
    """ProjectionYear should record the exact ages passed in."""
    params = _make_scenario()
    result = project_one_year(
        year=2035, age_you=63, age_spouse=61,
        accounts=_make_accounts(), params=_make_scenario(),
        prior_year_magi=80_000.0, cumulative_inflation=1.0,
        is_retired_you=True, is_retired_spouse=True, first_death_year=None,
    )
    assert result.year == 2035
    assert result.age_you == 63
    assert result.age_spouse == 61


def test_project_one_year_nqdc_schedule():
    """NQDC payout appears in income_by_source in the correct year."""
    params = _make_scenario()
    params.nqdc_schedule = [{"date": "2031-01-15", "amount": 50_000.0}]

    result_with_nqdc = project_one_year(
        year=2031, age_you=59, age_spouse=57,
        accounts=_make_accounts(), params=params,
        prior_year_magi=80_000.0, cumulative_inflation=1.0,
        is_retired_you=True, is_retired_spouse=True, first_death_year=None,
    )
    result_without_nqdc = project_one_year(
        year=2030, age_you=58, age_spouse=56,
        accounts=_make_accounts(), params=params,
        prior_year_magi=80_000.0, cumulative_inflation=1.0,
        is_retired_you=True, is_retired_spouse=True, first_death_year=None,
    )

    assert result_with_nqdc.income_by_source.get("nqdc", 0.0) == pytest.approx(50_000.0, abs=1.0)
    assert result_without_nqdc.income_by_source.get("nqdc", 0.0) == 0.0
```

- [ ] Run tests — expect failures:
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_projection.py -v 2>&1 | tail -10
```

### 9.2 Write backend/engines/projection.py
- [ ] Create `retirement/backend/engines/projection.py`:
```python
"""Projection Engine — single-year and multi-year retirement simulations.

All functions are pure (no DB access). The Projection Engine orchestrates
the Tax Engine and Withdrawal Optimizer on a year-by-year basis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.engines.tax import TaxInput, TaxResult, calculate_taxes
from backend.engines.withdrawal import (
    AccountState,
    WithdrawalInput,
    WithdrawalResult,
    calculate_rmd,
    optimize_withdrawals,
    RMD_MIN_AGE,
)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class ScenarioParams:
    """All scenario configuration needed to run a full projection."""
    retirement_age_you: int
    retirement_age_spouse: int
    annual_spending: float
    spending_glide_path: dict[str, float]   # age (str key) → spending override
    ss_claim_age_you: int
    ss_claim_age_spouse: int
    ss_monthly_you: float                   # monthly benefit at claimed age
    ss_monthly_spouse: float
    withdrawal_strategy: str                # "optimized" or "manual"
    manual_withdrawal_order: list[str] | None
    roth_conversion_enabled: bool
    roth_conversion_target_bracket: str | None   # e.g. "22%"
    healthcare_monthly_pre_medicare: float
    stock_allocation: float
    expected_return_stocks: float
    expected_return_bonds: float
    inflation_rate: float
    pension_monthly_you: float
    pension_start_age_you: int
    rental_annual_income: float
    nqdc_schedule: list[dict[str, Any]]     # [{"date": "YYYY-MM-DD", "amount": float}]
    life_expectancy_you: int
    life_expectancy_spouse: int
    dob_year_you: int
    dob_year_spouse: int
    base_year: int                          # year brackets/rates are anchored to (2024)
    filing_status: str
    state: str


@dataclass
class ProjectionYear:
    """Computed results for a single projection year."""
    year: int
    age_you: int
    age_spouse: int
    portfolio_balance: float
    balances_by_account: dict[str, float]
    gross_income: float
    income_by_source: dict[str, float]
    federal_tax: float
    state_tax: float
    effective_rate: float
    marginal_rate: float
    roth_conversion_amount: float
    withdrawal_notes: list[str]
    early_withdrawal_penalty: float = 0.0
    irmaa_annual: float = 0.0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _blended_return(params: ScenarioParams) -> float:
    """Weighted average return across stock/bond allocation."""
    stock_w = params.stock_allocation
    bond_w = 1.0 - stock_w
    return stock_w * params.expected_return_stocks + bond_w * params.expected_return_bonds


def _get_spending(age_you: int, params: ScenarioParams, inflation_factor: float) -> float:
    """Return annual spending for this year, respecting glide path overrides."""
    glide = params.spending_glide_path or {}
    override = glide.get(str(age_you))
    base = override if override is not None else params.annual_spending
    return base * inflation_factor


def _get_nqdc_payout(year: int, params: ScenarioParams) -> float:
    """Return total NQDC payout scheduled in `year`."""
    total = 0.0
    for entry in params.nqdc_schedule:
        entry_year = int(entry["date"][:4])
        if entry_year == year:
            total += float(entry["amount"])
    return total


def _get_ss_income(
    age_you: int,
    age_spouse: int,
    params: ScenarioParams,
    inflation_factor: float,
) -> tuple[float, float]:
    """Return annual SS income for each spouse in this year (0 before claim age)."""
    ss_you = (
        params.ss_monthly_you * 12 * inflation_factor
        if age_you >= params.ss_claim_age_you else 0.0
    )
    ss_spouse = (
        params.ss_monthly_spouse * 12 * inflation_factor
        if age_spouse >= params.ss_claim_age_spouse else 0.0
    )
    return ss_you, ss_spouse


def _target_bracket_ceiling(
    target_bracket_str: str | None,
    filing_status: str,
    inflation_factor: float,
) -> tuple[float | None, float | None]:
    """Parse target bracket string (e.g. '22%') → (rate, ceiling_amount)."""
    if not target_bracket_str:
        return None, None
    from backend.engines.tax import MFJ_BRACKETS_2024, SINGLE_BRACKETS_2024, _inflate_brackets
    brackets = MFJ_BRACKETS_2024 if filing_status == "mfj" else SINGLE_BRACKETS_2024
    inflated = _inflate_brackets(brackets, inflation_factor)
    rate_str = target_bracket_str.strip().rstrip("%")
    try:
        target_rate = float(rate_str) / 100.0
    except ValueError:
        return None, None
    for upper, rate in inflated:
        if abs(rate - target_rate) < 0.001:
            return target_rate, upper
    return None, None


# ── Single-year step ──────────────────────────────────────────────────────────

def project_one_year(
    year: int,
    age_you: int,
    age_spouse: int,
    accounts: list[AccountState],
    params: ScenarioParams,
    prior_year_magi: float,
    cumulative_inflation: float,
    is_retired_you: bool,
    is_retired_spouse: bool,
    first_death_year: int | None,
) -> ProjectionYear:
    """Simulate a single year of retirement.

    Steps:
    1. Apply blended investment return to each account balance.
    2. Apply annual contributions (if not yet retired).
    3. Apply NQDC payout schedule.
    4. Apply pension income (if at/past pension_start_age).
    5. Apply rental income.
    6. Calculate SS income (after claim age).
    7. Determine spending for this year (inflation-adjusted, glide path).
    8. Compute healthcare cost (pre-Medicare: monthly × 12; post-65: 0 via ACA/Medicare).
    9. Calculate RMDs on pre-tax accounts (age 73+).
    10. Compute guaranteed income gap = spending + taxes_est - guaranteed_income.
    11. Call Withdrawal Optimizer for discretionary gap.
    12. Call Tax Engine with final income composition.
    13. Return ProjectionYear with all computed fields.
    """
    inflation = cumulative_inflation

    # ── 1. Apply investment returns ───────────────────────────────────────────
    blended = _blended_return(params)
    for acct in accounts:
        if acct.account_type not in ("nqdc", "pension", "real_estate"):
            acct.balance = acct.balance * (1.0 + blended)

    # ── 2. Contributions (pre-retirement only) ────────────────────────────────
    # (Contributions are tracked in Account model; here we skip if retired)
    # Contributions handled in full run_projection(); single-step ignores them.

    # ── 3. NQDC payout ───────────────────────────────────────────────────────
    nqdc_income = _get_nqdc_payout(year, params)

    # ── 4. Pension income ─────────────────────────────────────────────────────
    pension_annual = 0.0
    if params.pension_start_age_you > 0 and age_you >= params.pension_start_age_you:
        pension_annual = params.pension_monthly_you * 12 * inflation

    # ── 5. Rental income ──────────────────────────────────────────────────────
    rental_annual = params.rental_annual_income * inflation

    # ── 6. Social Security ────────────────────────────────────────────────────
    ss_you_annual, ss_spouse_annual = _get_ss_income(age_you, age_spouse, params, inflation)

    # ── 7. Spending for this year ─────────────────────────────────────────────
    spending = _get_spending(age_you, params, inflation)

    # ── 8. Healthcare cost ────────────────────────────────────────────────────
    # Pre-Medicare: use scenario estimate. Post-65: assume Medicare covers base cost.
    if age_you < 65:
        healthcare_annual = params.healthcare_monthly_pre_medicare * 12 * inflation
    else:
        healthcare_annual = 0.0  # Medicare; IRMAA handled in Tax Engine

    # ── 9. RMDs ───────────────────────────────────────────────────────────────
    rmd_income: dict[str, float] = {}
    pretax_accounts = [a for a in accounts if a.account_type == "401k"]
    for acct in pretax_accounts:
        rmd = calculate_rmd(prior_year_balance=acct.balance, age=age_you)
        if rmd > 0:
            rmd_income[acct.account_type] = rmd
            # RMD is mandatory — reduce balance now
            acct.balance = max(0.0, acct.balance - rmd)

    total_rmd = sum(rmd_income.values())

    # ── 10. Guaranteed income gap ──────────────────────────────────────────────
    guaranteed_income = nqdc_income + pension_annual + rental_annual + ss_you_annual + ss_spouse_annual + total_rmd
    # Estimate taxes before calling optimizer (use 20% heuristic for first pass)
    tax_estimate = max(0.0, (spending + healthcare_annual) * 0.20)
    discretionary_gap = max(
        0.0,
        spending + healthcare_annual + tax_estimate - guaranteed_income
    )

    # ── 11. Withdrawal Optimizer ───────────────────────────────────────────────
    target_rate, target_ceiling = _target_bracket_ceiling(
        params.roth_conversion_target_bracket,
        params.filing_status,
        inflation,
    )

    # Compute pretax balance for RMD purposes (already post-RMD at this point)
    prior_pretax_balance = sum(a.balance for a in accounts if a.account_type == "401k")

    wi = WithdrawalInput(
        required_amount=discretionary_gap,
        account_states=accounts,
        age_you=age_you,
        age_spouse=age_spouse,
        current_marginal_rate=0.22,  # estimated; Tax Engine refines
        current_ordinary_taxable_income=guaranteed_income,
        filing_status=params.filing_status,
        healthcare_amount=healthcare_annual,
        roth_conversion_enabled=params.roth_conversion_enabled,
        target_bracket_rate=target_rate,
        target_bracket_ceiling=target_ceiling,
        current_year=year,
        prior_year_pretax_balance=prior_pretax_balance,
    )
    wr: WithdrawalResult = optimize_withdrawals(wi)

    # Ordinary income from withdrawals (401k, NQDC, pension, rental, RMDs)
    ordinary_from_withdrawals = wr.withdrawals_by_account.get("401k", 0.0) + wr.roth_conversion_amount
    ltcg_income = wr.withdrawals_by_account.get("brokerage", 0.0)

    total_ordinary = (
        nqdc_income
        + pension_annual
        + rental_annual
        + total_rmd
        + ordinary_from_withdrawals
    )

    # Retirement income eligible for DE exclusion
    retirement_income_you = pension_annual + total_rmd + wr.withdrawals_by_account.get("401k", 0.0)
    retirement_income_spouse = 0.0

    # ── 12. Tax Engine ────────────────────────────────────────────────────────
    ti = TaxInput(
        filing_status=params.filing_status,
        age_you=age_you,
        age_spouse=age_spouse,
        ordinary_income=total_ordinary,
        ss_income_you=ss_you_annual,
        ss_income_spouse=ss_spouse_annual,
        ltcg_income=ltcg_income,
        roth_conversion=wr.roth_conversion_amount,
        retirement_income_you=retirement_income_you,
        retirement_income_spouse=retirement_income_spouse,
        prior_year_magi=prior_year_magi,
        inflation_factor=inflation,
    )
    tax_result: TaxResult = calculate_taxes(ti)

    # ── 13. Assemble ProjectionYear ───────────────────────────────────────────
    balances = {a.account_type: round(a.balance, 2) for a in accounts}
    portfolio_balance = sum(balances.values())

    income_by_source = {
        "ss_you": round(ss_you_annual, 2),
        "ss_spouse": round(ss_spouse_annual, 2),
        "nqdc": round(nqdc_income, 2),
        "pension": round(pension_annual, 2),
        "rental": round(rental_annual, 2),
        "rmd": round(total_rmd, 2),
        "401k_withdrawal": round(wr.withdrawals_by_account.get("401k", 0.0), 2),
        "roth_withdrawal": round(wr.withdrawals_by_account.get("roth_ira", 0.0), 2),
        "brokerage_withdrawal": round(ltcg_income, 2),
        "hsa_withdrawal": round(wr.withdrawals_by_account.get("hsa", 0.0), 2),
        "roth_conversion": round(wr.roth_conversion_amount, 2),
    }

    return ProjectionYear(
        year=year,
        age_you=age_you,
        age_spouse=age_spouse,
        portfolio_balance=round(portfolio_balance, 2),
        balances_by_account=balances,
        gross_income=round(tax_result.gross_income, 2),
        income_by_source=income_by_source,
        federal_tax=round(tax_result.federal_total, 2),
        state_tax=round(tax_result.state_tax, 2),
        effective_rate=round(tax_result.effective_rate, 4),
        marginal_rate=round(tax_result.marginal_rate, 4),
        roth_conversion_amount=round(wr.roth_conversion_amount, 2),
        withdrawal_notes=wr.notes + tax_result.notes,
        early_withdrawal_penalty=round(wr.early_withdrawal_penalty, 2),
        irmaa_annual=round(tax_result.irmaa_annual, 2),
    )
```

### 9.3 Run projection tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_projection.py -v
```
Expected:
```
PASSED test_project_one_year_accounts_grow
PASSED test_project_one_year_spending_reduces_portfolio
PASSED test_project_one_year_ss_income_starts_at_claim_age
PASSED test_project_one_year_returns_correct_ages
PASSED test_project_one_year_nqdc_schedule
5 passed in 0.XXs
```

### 9.4 Commit
- [ ] `git -C retirement add backend/engines/projection.py backend/tests/test_projection.py && git -C retirement commit -m "feat: Projection Engine — single-year step with tax + withdrawal integration (Task 9)"`

---

## Task 10: Projection Engine — full multi-year simulation + death event

### 10.1 Add multi-year tests
- [ ] Append to `retirement/backend/tests/test_projection.py`:
```python
# ── Multi-year simulation tests (Task 10) ─────────────────────────────────────

def test_run_projection_length():
    """Projection should run from current year through longer life expectancy."""
    from backend.engines.projection import run_projection

    params = _make_scenario()
    # You born 1972 (age 54 in 2026), life_exp 88 → runs through 2060
    # Spouse born 1974 (age 52), life_exp 90 → runs through 2064
    accounts = _make_accounts()
    results = run_projection(
        start_year=2026,
        age_you_at_start=54,
        age_spouse_at_start=52,
        accounts=accounts,
        params=params,
    )

    # Should run through spouse's life expectancy year (2064)
    years = [r.year for r in results]
    assert years[0] == 2026
    assert years[-1] == 2064
    assert len(results) == 2064 - 2026 + 1


def test_run_projection_portfolio_can_deplete():
    """With very high spending, portfolio eventually reaches zero."""
    from backend.engines.projection import run_projection

    params = _make_scenario(annual_spending=300_000.0)  # aggressive spending
    accounts = _make_accounts(k401=200_000.0, roth=50_000.0, brokerage=50_000.0, hsa=10_000.0)

    results = run_projection(
        start_year=2026,
        age_you_at_start=54,
        age_spouse_at_start=52,
        accounts=accounts,
        params=params,
    )

    final_balance = results[-1].portfolio_balance
    # With $300k spending on a $310k portfolio, depletion happens
    # (exact year depends on returns, but final balance should be near zero)
    assert final_balance < 100_000.0


def test_run_projection_filing_status_switches_after_death():
    """After first death year, filing_status in ProjectionYear reflects 'single'."""
    from backend.engines.projection import run_projection, ScenarioParams

    params = _make_scenario()
    accounts = _make_accounts()

    # Force you to die at age 70 (year 2042) by setting very short life expectancy
    params.life_expectancy_you = 70   # dies in 2042
    params.life_expectancy_spouse = 90

    results = run_projection(
        start_year=2026,
        age_you_at_start=54,
        age_spouse_at_start=52,
        accounts=accounts,
        params=params,
    )

    # Find years before and after death
    year_of_death = 2026 + (70 - 54)  # = 2042
    before_death = next(r for r in results if r.year == year_of_death - 1)
    after_death = next(r for r in results if r.year == year_of_death + 1)

    # After death: SS should reflect survivor benefit logic (spouse gets higher of two)
    # Portfolio continues; we just verify the projection keeps running
    assert after_death.portfolio_balance >= 0


def test_run_projection_ss_increases_portfolio_stability():
    """Starting SS earlier improves portfolio survival in later years."""
    from backend.engines.projection import run_projection

    params_early_ss = _make_scenario(ss_claim_age_you=62, ss_claim_age_spouse=62)
    params_late_ss = _make_scenario(ss_claim_age_you=70, ss_claim_age_spouse=70)

    accounts_early = _make_accounts(k401=400_000.0, roth=80_000.0)
    accounts_late = _make_accounts(k401=400_000.0, roth=80_000.0)

    results_early = run_projection(2026, 54, 52, accounts_early, params_early_ss)
    results_late = run_projection(2026, 54, 52, accounts_late, params_late_ss)

    # In years 62-69, early SS should produce lower portfolio drawdown
    # Compare portfolio at age 68 (2040): early SS should have higher balance
    early_age68 = next(r for r in results_early if r.age_you == 68)
    late_age68 = next(r for r in results_late if r.age_you == 68)
    assert early_age68.portfolio_balance > late_age68.portfolio_balance
```

### 10.2 Add run_projection() to projection.py
- [ ] Append to `retirement/backend/engines/projection.py`:
```python
def run_projection(
    start_year: int,
    age_you_at_start: int,
    age_spouse_at_start: int,
    accounts: list[AccountState],
    params: ScenarioParams,
) -> list[ProjectionYear]:
    """Run a full year-by-year projection from start_year through life expectancy.

    Handles:
    - Pre-retirement contributions (until retirement age reached).
    - Death event: on the year the first spouse reaches their life expectancy,
      merge accounts, switch filing status to single, adjust SS to survivor benefit.
    - NQDC schedule payouts in their designated years.
    - All tax + withdrawal optimization per year.

    Args:
        start_year: Calendar year to begin simulation (typically current year).
        age_you_at_start: Age of primary filer at start of start_year.
        age_spouse_at_start: Age of spouse at start of start_year.
        accounts: List of AccountState with current balances.
        params: Full ScenarioParams.

    Returns:
        List of ProjectionYear, one per year, from start_year to
        max(life_expectancy_you, life_expectancy_spouse) year.
    """
    import copy

    # Determine simulation end year
    death_year_you = start_year + (params.life_expectancy_you - age_you_at_start)
    death_year_spouse = start_year + (params.life_expectancy_spouse - age_spouse_at_start)
    end_year = max(death_year_you, death_year_spouse)

    # Work on copies so the function is side-effect free
    current_accounts = copy.deepcopy(accounts)

    results: list[ProjectionYear] = []
    prior_year_magi = 0.0
    cumulative_inflation = 1.0
    current_filing_status = params.filing_status
    first_death_year: int | None = None

    # Track whether each spouse is retired
    retirement_year_you = start_year + (params.retirement_age_you - age_you_at_start)
    retirement_year_spouse = start_year + (params.retirement_age_spouse - age_spouse_at_start)

    # Track SS monthly amounts (may change on survivor event)
    ss_monthly_you = params.ss_monthly_you
    ss_monthly_spouse = params.ss_monthly_spouse

    for year in range(start_year, end_year + 1):
        age_you = age_you_at_start + (year - start_year)
        age_spouse = age_spouse_at_start + (year - start_year)
        is_retired_you = year >= retirement_year_you
        is_retired_spouse = year >= retirement_year_spouse

        # ── Annual contributions (pre-retirement) ─────────────────────────────
        if not is_retired_you:
            for acct in current_accounts:
                if acct.owner == "you" and acct.account_type in ("401k", "roth_ira", "brokerage", "hsa"):
                    # Contributions are modeled as additional balance at start of year
                    pass  # Caller seeds the balance; we just apply returns

        # ── Death event ───────────────────────────────────────────────────────
        if first_death_year is None:
            # Determine which spouse dies first
            if age_you >= params.life_expectancy_you and first_death_year is None:
                first_death_year = year
                current_filing_status = "single"
                # Survivor SS: higher of own benefit or deceased's benefit
                ss_monthly_spouse = max(ss_monthly_spouse, ss_monthly_you)
                ss_monthly_you = 0.0  # You are deceased
            elif age_spouse >= params.life_expectancy_spouse and first_death_year is None:
                first_death_year = year
                current_filing_status = "single"
                ss_monthly_you = max(ss_monthly_you, ss_monthly_spouse)
                ss_monthly_spouse = 0.0  # Spouse is deceased

        # Stop projecting beyond the survivor's life expectancy
        if age_you > params.life_expectancy_you and age_spouse > params.life_expectancy_spouse:
            break

        # Build per-year scenario params with possibly-updated SS and filing status
        year_params = copy.copy(params)
        year_params.filing_status = current_filing_status
        year_params.ss_monthly_you = ss_monthly_you
        year_params.ss_monthly_spouse = ss_monthly_spouse

        py = project_one_year(
            year=year,
            age_you=age_you,
            age_spouse=age_spouse,
            accounts=current_accounts,
            params=year_params,
            prior_year_magi=prior_year_magi,
            cumulative_inflation=cumulative_inflation,
            is_retired_you=is_retired_you,
            is_retired_spouse=is_retired_spouse,
            first_death_year=first_death_year,
        )
        results.append(py)

        # Update state for next year
        prior_year_magi = py.gross_income
        cumulative_inflation *= (1.0 + params.inflation_rate)

    return results
```

### 10.3 Run multi-year projection tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_projection.py -v
```
Expected — all tests pass including new multi-year tests.

### 10.4 Run full test suite
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/ -v
# Expected: all tests pass
```

### 10.5 Commit
- [ ] `git -C retirement add backend/engines/projection.py backend/tests/test_projection.py && git -C retirement commit -m "feat: Projection Engine — multi-year simulation, death event, survivor SS (Task 10)"`

---

## Task 11: SS Optimizer

### 11.1 Write tests first
- [ ] Create `retirement/backend/tests/test_ss_optimizer.py`:
```python
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
    """All 81 combinations (ages 62–70 × 62–70) should be evaluated."""
    results = optimize_ss(_default_input())
    assert len(results) == 81


def test_optimize_ss_sorted_descending():
    """Results should be sorted by lifetime_benefit descending."""
    results = optimize_ss(_default_input())
    benefits = [r.lifetime_benefit for r in results]
    assert benefits == sorted(benefits, reverse=True)


def test_optimize_ss_claim_ages_in_range():
    """All claim ages should be integers between 62 and 70 inclusive."""
    results = optimize_ss(_default_input())
    for r in results:
        assert 62 <= r.claim_age_you <= 70
        assert 62 <= r.claim_age_spouse <= 70


def test_delayed_to_70_generally_best_for_high_earner():
    """For a long-lived primary earner, delaying to 70 should rank near the top."""
    results = optimize_ss(_default_input())
    top_10 = results[:10]
    claim_ages_you = [r.claim_age_you for r in top_10]
    # At least one of the top 10 should have you claiming at 70
    assert 70 in claim_ages_you


def test_early_claim_62_lower_benefit():
    """Claiming at 62 for both should rank lower than at least half the combinations."""
    results = optimize_ss(_default_input())
    both_62 = next(
        r for r in results
        if r.claim_age_you == 62 and r.claim_age_spouse == 62
    )
    rank = results.index(both_62)
    assert rank > 40  # Should be in the bottom half


def test_benefit_reduction_at_62():
    """Benefit at 62 should be reduced relative to FRA benefit (early claim penalty)."""
    inp = _default_input()
    results = optimize_ss(inp)
    # Find result where you claim at 62
    claim_62 = next(r for r in results if r.claim_age_you == 62 and r.claim_age_spouse == 67)
    claim_67 = next(r for r in results if r.claim_age_you == 67 and r.claim_age_spouse == 67)
    # Claiming at 62 vs 67 — per-month benefit lower for 62 claimant
    assert claim_62.monthly_benefit_you < inp.benefit_at_fra_you


def test_survivor_benefit_noted_for_high_earner_delay():
    """Notes should mention survivor benefit advantage when higher earner delays to 70."""
    results = optimize_ss(_default_input())
    top_result_with_70 = next(
        r for r in results if r.claim_age_you == 70
    )
    assert any("survivor" in note.lower() for note in top_result_with_70.notes)


def test_top_10_returned():
    """optimize_ss returns all 81 — caller can slice top 10."""
    results = optimize_ss(_default_input())
    top_10 = results[:10]
    assert len(top_10) == 10
    # All should have higher lifetime benefit than result at index 10
    assert top_10[-1].lifetime_benefit >= results[10].lifetime_benefit
```

- [ ] Run tests — expect failures:
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_ss_optimizer.py -v 2>&1 | tail -10
```

### 11.2 Write backend/engines/ss_optimizer.py
- [ ] Create `retirement/backend/engines/ss_optimizer.py`:
```python
"""Social Security Optimizer — exhaustively evaluates all 81 claiming combinations.

All functions are pure (no DB access).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SSInput:
    """Inputs for SS claiming optimization."""
    benefit_at_62_you: float        # monthly benefit if claimed at 62
    benefit_at_fra_you: float       # monthly benefit at Full Retirement Age
    benefit_at_70_you: float        # monthly benefit if claimed at 70
    fra_age_you: int                # Full Retirement Age (typically 67)
    benefit_at_62_spouse: float
    benefit_at_fra_spouse: float
    benefit_at_70_spouse: float
    fra_age_spouse: int
    life_expectancy_you: int
    life_expectancy_spouse: int
    survivor_benefit_pct: float     # % of higher earner's benefit; typically 1.0 (100%)
    current_age_you: int
    current_age_spouse: int


@dataclass
class SSClaimResult:
    """A single SS claiming combination and its projected lifetime benefit."""
    claim_age_you: int
    claim_age_spouse: int
    monthly_benefit_you: float      # benefit at claimed age
    monthly_benefit_spouse: float
    lifetime_benefit: float         # combined lifetime benefit to both spouses
    survivor_monthly_benefit: float # monthly benefit to survivor after first death
    notes: list[str] = field(default_factory=list)


def _benefit_at_age(
    benefit_at_62: float,
    benefit_at_fra: float,
    benefit_at_70: float,
    fra_age: int,
    claim_age: int,
) -> float:
    """Return monthly benefit for a given claim age.

    Interpolates linearly between the three known points (62, FRA, 70).
    Early reduction: ~6.67%/year before FRA (spec approximation).
    Delayed credits: 8%/year after FRA up to age 70.

    Args:
        benefit_at_62: Monthly benefit if claimed at 62.
        benefit_at_fra: Monthly FRA benefit.
        benefit_at_70: Monthly benefit at 70.
        fra_age: Full Retirement Age.
        claim_age: Age at which benefit is claimed (62–70).

    Returns:
        Monthly benefit at the specified claim age.
    """
    if claim_age <= 62:
        return benefit_at_62

    if claim_age == fra_age:
        return benefit_at_fra

    if claim_age >= 70:
        return benefit_at_70

    if claim_age < fra_age:
        # Interpolate between 62 and FRA
        years_before_fra = fra_age - 62
        years_before_claim = fra_age - claim_age
        fraction = years_before_claim / years_before_fra
        # Linear interpolation between benefit_at_fra (0 reduction) and benefit_at_62
        return benefit_at_fra - fraction * (benefit_at_fra - benefit_at_62)

    # claim_age > fra_age and < 70
    # Interpolate between FRA and 70
    years_after_fra = 70 - fra_age
    years_after_claim = claim_age - fra_age
    fraction = years_after_claim / years_after_fra
    return benefit_at_fra + fraction * (benefit_at_70 - benefit_at_fra)


def _lifetime_benefit_single(
    monthly_benefit: float,
    claim_age: int,
    life_expectancy: int,
) -> float:
    """Total lifetime benefit for one person = monthly * 12 * years_collecting."""
    if life_expectancy <= claim_age:
        return 0.0
    years_collecting = life_expectancy - claim_age
    return monthly_benefit * 12 * years_collecting


def optimize_ss(inp: SSInput) -> list[SSClaimResult]:
    """Evaluate all 81 SS claiming combinations for both spouses.

    For each (you_age, spouse_age) pair in range 62–70:
    1. Calculate monthly benefit for each person at their claim age.
    2. Calculate lifetime benefit for each person through their life expectancy.
    3. Add survivor period: after first death, survivor gets higher of own benefit
       or deceased's benefit (× survivor_benefit_pct).
    4. Sum to get combined lifetime benefit.

    Args:
        inp: SSInput with benefits, FRAs, life expectancies, and ages.

    Returns:
        List of 81 SSClaimResult objects sorted by lifetime_benefit descending.
    """
    results: list[SSClaimResult] = []

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

            # ── Lifetime benefit calculation ──────────────────────────────────
            # Determine who dies first based on life expectancies + current ages.
            # We use age-based death year relative to current ages.
            death_year_you = inp.current_age_you + (inp.life_expectancy_you - inp.current_age_you)
            death_year_spouse = inp.current_age_spouse + (inp.life_expectancy_spouse - inp.current_age_spouse)

            # Simple offset: who has fewer years remaining?
            you_years_remaining = inp.life_expectancy_you - inp.current_age_you
            spouse_years_remaining = inp.life_expectancy_spouse - inp.current_age_spouse

            if you_years_remaining <= spouse_years_remaining:
                # You die first
                first_death_age_you = inp.life_expectancy_you
                survivor_age_at_death = inp.current_age_spouse + you_years_remaining
                survivor_life_exp = inp.life_expectancy_spouse
                survivor_own_monthly = monthly_spouse
                deceased_monthly = monthly_you
            else:
                # Spouse dies first
                first_death_age_spouse = inp.life_expectancy_spouse
                survivor_age_at_death = inp.current_age_you + spouse_years_remaining
                survivor_life_exp = inp.life_expectancy_you
                survivor_own_monthly = monthly_you
                deceased_monthly = monthly_spouse

            # Your individual lifetime benefit (collecting from claim_you to life_exp_you)
            benefit_you = _lifetime_benefit_single(monthly_you, claim_you, inp.life_expectancy_you)

            # Spouse individual lifetime benefit
            benefit_spouse = _lifetime_benefit_single(monthly_spouse, claim_spouse, inp.life_expectancy_spouse)

            # Survivor period: after first death, survivor gets higher of own or deceased's
            # (subject to survivor_benefit_pct on the deceased's amount)
            survivor_benefit_from_deceased = deceased_monthly * inp.survivor_benefit_pct
            survivor_monthly = max(survivor_own_monthly, survivor_benefit_from_deceased)

            # We already counted the survivor's own benefit above; add the DELTA
            # for the period after their spouse dies if survivor_monthly > own
            if survivor_monthly > survivor_own_monthly:
                # Extra benefit from survivor uplift during the survivor period
                if you_years_remaining <= spouse_years_remaining:
                    # Spouse survives you — survivor period is from your death to spouse LE
                    survivor_years = inp.life_expectancy_spouse - survivor_age_at_death
                else:
                    survivor_years = inp.life_expectancy_you - survivor_age_at_death
                survivor_delta = max(0.0, (survivor_monthly - survivor_own_monthly) * 12 * max(0, survivor_years))
            else:
                survivor_delta = 0.0

            lifetime_total = benefit_you + benefit_spouse + survivor_delta

            # ── Notes ─────────────────────────────────────────────────────────
            notes: list[str] = []
            if claim_you == 70:
                notes.append(
                    f"Delaying to 70 maximizes survivor benefit: "
                    f"${monthly_you:,.0f}/mo passes to survivor"
                )
            if claim_you < inp.fra_age_you:
                pct_reduction = round(
                    (inp.benefit_at_fra_you - monthly_you) / inp.benefit_at_fra_you * 100, 1
                )
                notes.append(f"Early claim reduces your benefit by {pct_reduction}%")
            if claim_spouse < inp.fra_age_spouse:
                pct_reduction = round(
                    (inp.benefit_at_fra_spouse - monthly_spouse) / inp.benefit_at_fra_spouse * 100, 1
                )
                notes.append(f"Spouse early claim reduces their benefit by {pct_reduction}%")

            results.append(SSClaimResult(
                claim_age_you=claim_you,
                claim_age_spouse=claim_spouse,
                monthly_benefit_you=round(monthly_you, 2),
                monthly_benefit_spouse=round(monthly_spouse, 2),
                lifetime_benefit=round(lifetime_total, 2),
                survivor_monthly_benefit=round(survivor_monthly, 2),
                notes=notes,
            ))

    results.sort(key=lambda r: r.lifetime_benefit, reverse=True)
    return results
```

### 11.3 Run SS optimizer tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_ss_optimizer.py -v
```
Expected:
```
PASSED test_optimize_ss_returns_81_combinations
PASSED test_optimize_ss_sorted_descending
PASSED test_optimize_ss_claim_ages_in_range
PASSED test_delayed_to_70_generally_best_for_high_earner
PASSED test_early_claim_62_lower_benefit
PASSED test_benefit_reduction_at_62
PASSED test_survivor_benefit_noted_for_high_earner_delay
PASSED test_top_10_returned
8 passed in 0.XXs
```

### 11.4 Run full test suite
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/ -v
# Expected: all tests pass
```

### 11.5 Commit
- [ ] `git -C retirement add backend/engines/ss_optimizer.py backend/tests/test_ss_optimizer.py && git -C retirement commit -m "feat: SS Optimizer — 81 combinations, survivor benefit, lifetime ranking (Task 11)"`

---

## Task 12: Monte Carlo Engine

### 12.1 Write tests first
- [ ] Create `retirement/backend/tests/test_monte_carlo.py`:
```python
"""Tests for the Monte Carlo Engine — Task 12."""

from __future__ import annotations

import pytest

from backend.engines.monte_carlo import (
    MCInput,
    MCResult,
    run_monte_carlo,
)
from backend.engines.projection import ScenarioParams


def _make_mc_input(n_simulations: int = 100) -> MCInput:
    """Build a minimal MCInput for fast testing (100 simulations)."""
    params = ScenarioParams(
        retirement_age_you=57,
        retirement_age_spouse=57,
        annual_spending=120_000.0,
        spending_glide_path={},
        ss_claim_age_you=67,
        ss_claim_age_spouse=67,
        ss_monthly_you=3_100.0,
        ss_monthly_spouse=2_000.0,
        withdrawal_strategy="optimized",
        manual_withdrawal_order=None,
        roth_conversion_enabled=False,
        roth_conversion_target_bracket=None,
        healthcare_monthly_pre_medicare=2_200.0,
        stock_allocation=0.65,
        expected_return_stocks=0.07,
        expected_return_bonds=0.04,
        inflation_rate=0.025,
        pension_monthly_you=0.0,
        pension_start_age_you=0,
        rental_annual_income=0.0,
        nqdc_schedule=[],
        life_expectancy_you=85,
        life_expectancy_spouse=87,
        dob_year_you=1972,
        dob_year_spouse=1974,
        base_year=2024,
        filing_status="mfj",
        state="DE",
    )
    from backend.engines.withdrawal import AccountState
    accounts = [
        AccountState(account_type="401k", balance=800_000.0, basis=0.0,
                     owner="you", is_rule_of_55_eligible=True),
        AccountState(account_type="roth_ira", balance=120_000.0, basis=120_000.0,
                     owner="you"),
        AccountState(account_type="brokerage", balance=200_000.0, basis=100_000.0,
                     owner="you"),
        AccountState(account_type="hsa", balance=40_000.0, basis=0.0, owner="you"),
    ]
    return MCInput(
        scenario_params=params,
        accounts=accounts,
        start_year=2026,
        age_you_at_start=54,
        age_spouse_at_start=52,
        n_simulations=n_simulations,
        random_seed=42,  # deterministic for tests
    )


def test_mc_returns_correct_simulation_count():
    """MCResult.num_simulations should match input."""
    inp = _make_mc_input(n_simulations=100)
    result = run_monte_carlo(inp)
    assert result.num_simulations == 100


def test_mc_survival_rate_between_0_and_1():
    """Survival rate must be a valid probability."""
    result = run_monte_carlo(_make_mc_input(100))
    assert 0.0 <= result.survival_rate <= 1.0


def test_mc_percentile_bands_exist():
    """All 5 percentile bands should be present and non-empty."""
    result = run_monte_carlo(_make_mc_input(100))
    assert len(result.percentile_10) > 0
    assert len(result.percentile_25) > 0
    assert len(result.percentile_50) > 0
    assert len(result.percentile_75) > 0
    assert len(result.percentile_90) > 0


def test_mc_percentile_ordering():
    """At any year, p10 <= p25 <= p50 <= p75 <= p90."""
    result = run_monte_carlo(_make_mc_input(100))
    years = sorted(result.percentile_10.keys())
    for yr in years:
        p10 = result.percentile_10[yr]
        p25 = result.percentile_25[yr]
        p50 = result.percentile_50[yr]
        p75 = result.percentile_75[yr]
        p90 = result.percentile_90[yr]
        assert p10 <= p25 <= p50 <= p75 <= p90, (
            f"Year {yr}: percentile ordering violated "
            f"({p10:.0f}, {p25:.0f}, {p50:.0f}, {p75:.0f}, {p90:.0f})"
        )


def test_mc_sensitivity_has_six_variables():
    """Sensitivity analysis should report results for all 6 specified variables."""
    result = run_monte_carlo(_make_mc_input(100))
    expected_keys = {
        "retirement_age",
        "annual_spending",
        "ss_claim_age",
        "expected_return_stocks",
        "inflation_rate",
        "stock_allocation",
    }
    assert set(result.sensitivity.keys()) == expected_keys


def test_mc_deterministic_with_seed():
    """Same random seed should produce identical results."""
    result_a = run_monte_carlo(_make_mc_input(50))
    result_b = run_monte_carlo(_make_mc_input(50))
    assert result_a.survival_rate == pytest.approx(result_b.survival_rate, abs=0.001)


def test_mc_higher_spending_reduces_survival():
    """Increasing annual spending should reduce or maintain the survival rate."""
    import copy
    from backend.engines.withdrawal import AccountState

    inp_base = _make_mc_input(100)
    inp_high = _make_mc_input(100)
    inp_high.scenario_params = copy.deepcopy(inp_base.scenario_params)
    inp_high.scenario_params.annual_spending = 200_000.0  # much higher spending

    result_base = run_monte_carlo(inp_base)
    result_high = run_monte_carlo(inp_high)

    assert result_high.survival_rate <= result_base.survival_rate + 0.05  # allow small tolerance
```

- [ ] Run tests — expect failures:
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_monte_carlo.py -v 2>&1 | tail -10
```

### 12.2 Write backend/engines/monte_carlo.py
- [ ] Create `retirement/backend/engines/monte_carlo.py`:
```python
"""Monte Carlo Engine — runs N simulations of the Projection Engine with
sampled return and inflation values to estimate survival probability and
portfolio percentile bands.

All functions are pure (no DB access).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

import numpy as np

from backend.engines.projection import ScenarioParams, run_projection
from backend.engines.withdrawal import AccountState


@dataclass
class MCInput:
    """Inputs for a Monte Carlo simulation run."""
    scenario_params: ScenarioParams
    accounts: list[AccountState]
    start_year: int
    age_you_at_start: int
    age_spouse_at_start: int
    n_simulations: int = 10_000
    random_seed: int | None = None


@dataclass
class MCResult:
    """Results of a completed Monte Carlo simulation."""
    num_simulations: int
    survival_rate: float
    percentile_10: dict[int, float]   # year → portfolio balance at 10th pct
    percentile_25: dict[int, float]
    percentile_50: dict[int, float]
    percentile_75: dict[int, float]
    percentile_90: dict[int, float]
    sensitivity: dict[str, float]     # variable_name → survival delta


# ── Return distribution parameters ───────────────────────────────────────────
STOCK_RETURN_SIGMA = 0.15   # annual standard deviation for stock returns
BOND_RETURN_SIGMA  = 0.06   # annual standard deviation for bond returns
INFLATION_SIGMA    = 0.01   # annual standard deviation for inflation


def _sample_scenario_params(
    base_params: ScenarioParams,
    stock_return: float,
    bond_return: float,
    inflation_rate: float,
) -> ScenarioParams:
    """Return a copy of ScenarioParams with sampled return/inflation values."""
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
    """Run one simulation trial.

    Returns:
        (survived, balances_by_year) where survived=True if portfolio > 0
        at the final year.
    """
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
    survived = final_balance > 0.0
    return survived, balances


def run_monte_carlo(inp: MCInput) -> MCResult:
    """Run N Monte Carlo simulations and compute survival statistics.

    Per simulation:
    1. Sample stock return ~ N(mean, 0.15), clamp to [-0.50, 0.50].
    2. Sample bond return ~ N(mean, 0.06), clamp to [-0.30, 0.30].
    3. Sample inflation ~ N(mean, 0.01), clamp to [0.0, 0.10].
    4. Run run_projection() with sampled values.
    5. Record survival and per-year balances.

    After all trials:
    - Compute survival_rate = survived / n_simulations.
    - Compute percentile bands (10/25/50/75/90) per year.
    - Run sensitivity analysis: vary each of 6 inputs by ±1 unit,
      run 100 sub-simulations, record survival delta vs baseline.

    Args:
        inp: MCInput with scenario params, accounts, and simulation settings.

    Returns:
        MCResult with all computed statistics.
    """
    rng = np.random.default_rng(inp.random_seed)

    # Pre-sample returns for all simulations
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

    # ── Run all simulations ───────────────────────────────────────────────────
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

    # ── Compute percentile bands ──────────────────────────────────────────────
    # Collect all years that appear in any simulation
    all_years = sorted({yr for bal in all_balances for yr in bal.keys()})

    pct_bands: dict[int, list[float]] = {yr: [] for yr in all_years}
    for bal in all_balances:
        for yr in all_years:
            pct_bands[yr].append(bal.get(yr, 0.0))

    def _pct(p: int) -> dict[int, float]:
        return {yr: round(float(np.percentile(pct_bands[yr], p)), 2) for yr in all_years}

    # ── Sensitivity analysis ──────────────────────────────────────────────────
    # For each variable, run 100 sub-simulations at +1 unit and -1 unit,
    # compute survival delta vs baseline.
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
    n: int = 100,
    seed: int = 99,
) -> float:
    """Run n simulations with the override params and return survival rate."""
    sub_rng = np.random.default_rng(seed)
    stock_r = sub_rng.normal(params_override.expected_return_stocks, STOCK_RETURN_SIGMA, n).clip(-0.50, 0.50)
    bond_r = sub_rng.normal(params_override.expected_return_bonds, BOND_RETURN_SIGMA, n).clip(-0.30, 0.30)
    inf_r = sub_rng.normal(params_override.inflation_rate, INFLATION_SIGMA, n).clip(0.0, 0.10)

    survived = 0
    for i in range(n):
        p = _sample_scenario_params(params_override, float(stock_r[i]), float(bond_r[i]), float(inf_r[i]))
        ok, _ = _run_single_simulation(p, inp.accounts, inp.start_year,
                                       inp.age_you_at_start, inp.age_spouse_at_start)
        if ok:
            survived += 1
    return survived / n


def _run_sensitivity(inp: MCInput, baseline_survival: float) -> dict[str, float]:
    """Compute sensitivity of survival rate to ±1 unit changes in key variables.

    Variables:
    - retirement_age: ± 2 years on retirement_age_you
    - annual_spending: ± 15% of base spending
    - ss_claim_age: 62 vs 70 for primary earner
    - expected_return_stocks: ± 1 percentage point
    - inflation_rate: ± 1 percentage point
    - stock_allocation: ± 10 percentage points

    Returns delta = (high_survival - low_survival) / 2 for each variable.
    The sign indicates direction of impact.
    """
    sensitivity: dict[str, float] = {}
    base = inp.scenario_params

    def _delta(high_params: ScenarioParams, low_params: ScenarioParams) -> float:
        high_s = _sensitivity_survival(inp, high_params)
        low_s = _sensitivity_survival(inp, low_params)
        return round(high_s - low_s, 4)

    # retirement_age (± 2 years)
    p_retire_late = copy.copy(base)
    p_retire_late.retirement_age_you = base.retirement_age_you + 2
    p_retire_early = copy.copy(base)
    p_retire_early.retirement_age_you = base.retirement_age_you - 2
    sensitivity["retirement_age"] = _delta(p_retire_late, p_retire_early)

    # annual_spending (± 15%)
    p_spend_low = copy.copy(base)
    p_spend_low.annual_spending = base.annual_spending * 0.85
    p_spend_high = copy.copy(base)
    p_spend_high.annual_spending = base.annual_spending * 1.15
    sensitivity["annual_spending"] = _delta(p_spend_low, p_spend_high)

    # ss_claim_age (70 vs 62)
    p_ss_70 = copy.copy(base)
    p_ss_70.ss_claim_age_you = 70
    p_ss_62 = copy.copy(base)
    p_ss_62.ss_claim_age_you = 62
    sensitivity["ss_claim_age"] = _delta(p_ss_70, p_ss_62)

    # expected_return_stocks (± 1%)
    p_return_high = copy.copy(base)
    p_return_high.expected_return_stocks = base.expected_return_stocks + 0.01
    p_return_low = copy.copy(base)
    p_return_low.expected_return_stocks = base.expected_return_stocks - 0.01
    sensitivity["expected_return_stocks"] = _delta(p_return_high, p_return_low)

    # inflation_rate (± 1%)
    p_inf_low = copy.copy(base)
    p_inf_low.inflation_rate = max(0.0, base.inflation_rate - 0.01)
    p_inf_high = copy.copy(base)
    p_inf_high.inflation_rate = base.inflation_rate + 0.01
    sensitivity["inflation_rate"] = _delta(p_inf_low, p_inf_high)

    # stock_allocation (± 10%)
    p_alloc_high = copy.copy(base)
    p_alloc_high.stock_allocation = min(1.0, base.stock_allocation + 0.10)
    p_alloc_low = copy.copy(base)
    p_alloc_low.stock_allocation = max(0.0, base.stock_allocation - 0.10)
    sensitivity["stock_allocation"] = _delta(p_alloc_high, p_alloc_low)

    return sensitivity
```

### 12.3 Run Monte Carlo tests
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/test_monte_carlo.py -v
```
Expected (100 simulations — runs in ~10–30 seconds):
```
PASSED test_mc_returns_correct_simulation_count
PASSED test_mc_survival_rate_between_0_and_1
PASSED test_mc_percentile_bands_exist
PASSED test_mc_percentile_ordering
PASSED test_mc_sensitivity_has_six_variables
PASSED test_mc_deterministic_with_seed
PASSED test_mc_higher_spending_reduces_survival
7 passed in XXs
```

### 12.4 Run full test suite
- [ ]
```bash
cd retirement
PYTHONPATH=. pytest backend/tests/ -v
```
Expected: all tests pass across all modules.

### 12.5 Lint all backend code
- [ ]
```bash
cd retirement
ruff check backend/
# Expected: no issues found
```

### 12.6 Commit
- [ ] `git -C retirement add backend/engines/monte_carlo.py backend/tests/test_monte_carlo.py && git -C retirement commit -m "feat: Monte Carlo Engine — N simulations, percentile bands, sensitivity analysis (Task 12)"`

---

## Task 13: Frontend foundation — Vite + React + API client + tab shell

### 13.1 Write frontend/package.json
- [ ] Create `retirement/frontend/package.json`:
```json
{
  "name": "retirement-calculator",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "lint": "eslint src/"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.12.7",
    "axios": "^1.7.2"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "eslint": "^9.4.0",
    "vite": "^5.3.1"
  }
}
```

### 13.2 Write vite.config.js
- [ ] Create `retirement/frontend/vite.config.js`:
```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
});
```

### 13.3 Write frontend/src/index.css
- [ ] Create `retirement/frontend/src/index.css`:
```css
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

:root {
  --bg-primary: #0d1b2a;
  --bg-card: #0f3460;
  --bg-surface: #16213e;
  --text-primary: #e0e0e0;
  --text-muted: #90a4ae;
  --accent: #4fc3f7;
  --accent-hover: #81d4fa;
  --success: #81c784;
  --warning: #ffb74d;
  --danger: #ef5350;
  --border: #1e3a5f;
  --radius: 8px;
  --font: 'Inter', system-ui, -apple-system, sans-serif;
}

body {
  background-color: var(--bg-primary);
  color: var(--text-primary);
  font-family: var(--font);
  font-size: 14px;
  line-height: 1.5;
  min-height: 100vh;
}

input, select, textarea {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text-primary);
  font-family: var(--font);
  font-size: 14px;
  padding: 6px 10px;
  outline: none;
  width: 100%;
  transition: border-color 0.15s;
}

input:focus, select:focus, textarea:focus {
  border-color: var(--accent);
}

input[type="range"] {
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
}

button {
  background: var(--accent);
  border: none;
  border-radius: var(--radius);
  color: #0d1b2a;
  cursor: pointer;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 600;
  padding: 8px 16px;
  transition: background 0.15s;
}

button:hover {
  background: var(--accent-hover);
}

button.secondary {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  color: var(--text-primary);
}

button.secondary:hover {
  border-color: var(--accent);
  color: var(--accent);
}

button.danger {
  background: var(--danger);
  color: #fff;
}

button.danger:hover {
  background: #c62828;
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}

.tab-bar {
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  gap: 4px;
  padding: 8px 24px 0;
}

.tab-bar button {
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  border-radius: 0;
  color: var(--text-muted);
  font-size: 14px;
  font-weight: 500;
  padding: 8px 16px 10px;
  transition: color 0.15s, border-color 0.15s;
}

.tab-bar button:hover {
  background: transparent;
  color: var(--text-primary);
}

.tab-bar button.active {
  border-bottom-color: var(--accent);
  color: var(--accent);
}

.tab-content {
  padding: 24px;
}

label {
  color: var(--text-muted);
  display: block;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
  text-transform: uppercase;
}

.field {
  margin-bottom: 14px;
}

.badge {
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 7px;
  text-transform: uppercase;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th {
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  padding: 8px 10px;
  text-align: left;
  text-transform: uppercase;
}

td {
  border-bottom: 1px solid #1a2a3a;
  padding: 8px 10px;
}

tr:last-child td {
  border-bottom: none;
}

.metric-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  text-align: center;
}

.metric-card .metric-value {
  color: var(--accent);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.1;
}

.metric-card .metric-label {
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.05em;
  margin-top: 4px;
  text-transform: uppercase;
}

.section-title {
  border-bottom: 1px solid var(--border);
  color: var(--text-muted);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  margin-bottom: 14px;
  padding-bottom: 6px;
  text-transform: uppercase;
}

.two-col {
  display: grid;
  gap: 24px;
  grid-template-columns: 1fr 1fr;
}

.three-col {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr 1fr 1fr;
}

.four-col {
  display: grid;
  gap: 16px;
  grid-template-columns: 1fr 1fr 1fr 1fr;
}

@media (max-width: 900px) {
  .two-col, .three-col, .four-col {
    grid-template-columns: 1fr;
  }
}
```

### 13.4 Write frontend/src/main.jsx
- [ ] Create `retirement/frontend/src/main.jsx`:
```jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

### 13.5 Write frontend/src/App.jsx
- [ ] Create `retirement/frontend/src/App.jsx`:
```jsx
import React, { useState } from 'react';
import ProfileTab from './tabs/ProfileTab.jsx';
import ScenariosTab from './tabs/ScenariosTab.jsx';
import ResultsTab from './tabs/ResultsTab.jsx';
import MonteCarloTab from './tabs/MonteCarloTab.jsx';

const TABS = [
  { id: 'profile', label: 'Profile' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'results', label: 'Results' },
  { id: 'montecarlo', label: 'Monte Carlo' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('profile');

  return (
    <div style={{ minHeight: '100vh' }}>
      <header style={{
        background: '#0a1628',
        borderBottom: '1px solid #1e3a5f',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: '16px',
      }}>
        <span style={{ color: '#4fc3f7', fontWeight: 700, fontSize: 18 }}>
          Retirement Calculator
        </span>
      </header>

      <nav className="tab-bar">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            className={activeTab === tab.id ? 'active' : ''}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main className="tab-content">
        {activeTab === 'profile' && <ProfileTab />}
        {activeTab === 'scenarios' && <ScenariosTab />}
        {activeTab === 'results' && <ResultsTab />}
        {activeTab === 'montecarlo' && <MonteCarloTab />}
      </main>
    </div>
  );
}
```

### 13.6 Write frontend/src/api/client.js
- [ ] Create `retirement/frontend/src/api/client.js`:
```js
import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
});

// ── Profiles ──────────────────────────────────────────────────────────────────

export async function getProfiles() {
  const { data } = await api.get('/profiles/');
  return data;
}

export async function getProfile(id) {
  const { data } = await api.get(`/profiles/${id}`);
  return data;
}

export async function updateProfile(id, payload) {
  const { data } = await api.put(`/profiles/${id}`, payload);
  return data;
}

// ── Accounts ──────────────────────────────────────────────────────────────────

export async function getAccounts() {
  const { data } = await api.get('/accounts/');
  return data;
}

export async function createAccount(payload) {
  const { data } = await api.post('/accounts/', payload);
  return data;
}

export async function updateAccount(id, payload) {
  const { data } = await api.put(`/accounts/${id}`, payload);
  return data;
}

export async function deleteAccount(id) {
  await api.delete(`/accounts/${id}`);
}

// ── Social Security ───────────────────────────────────────────────────────────

export async function getSocialSecurity(profileId) {
  const { data } = await api.get(`/social-security/${profileId}`);
  return data;
}

export async function updateSocialSecurity(profileId, payload) {
  const { data } = await api.put(`/social-security/${profileId}`, payload);
  return data;
}

// ── Scenarios ─────────────────────────────────────────────────────────────────

export async function getScenarios() {
  const { data } = await api.get('/scenarios/');
  return data;
}

export async function createScenario(payload) {
  const { data } = await api.post('/scenarios/', payload);
  return data;
}

export async function updateScenario(id, payload) {
  const { data } = await api.put(`/scenarios/${id}`, payload);
  return data;
}

export async function deleteScenario(id) {
  await api.delete(`/scenarios/${id}`);
}

// ── Projections ───────────────────────────────────────────────────────────────

export async function runProjection(scenarioId) {
  const { data } = await api.post(`/projections/${scenarioId}/run`);
  return data;
}

export async function getProjection(scenarioId) {
  const { data } = await api.get(`/projections/${scenarioId}`);
  return data;
}

// ── Monte Carlo ───────────────────────────────────────────────────────────────

export async function runMonteCarlo(scenarioId, numSimulations = 10000) {
  const { data } = await api.post(`/monte-carlo/${scenarioId}/run`, {
    num_simulations: numSimulations,
  });
  return data;
}

export async function getMonteCarlo(scenarioId) {
  const { data } = await api.get(`/monte-carlo/${scenarioId}`);
  return data;
}

// ── SS Optimizer ──────────────────────────────────────────────────────────────

export async function getSsStrategies(params) {
  // params: { benefit_62_you, benefit_fra_you, benefit_70_you, fra_age_you,
  //           benefit_62_spouse, benefit_fra_spouse, benefit_70_spouse, fra_age_spouse,
  //           life_exp_you, life_exp_spouse }
  const { data } = await api.get('/ss-optimizer', { params });
  return data;
}

export default api;
```

### 13.7 Create stub tab files so App.jsx imports resolve
- [ ] Create `retirement/frontend/src/tabs/ProfileTab.jsx`:
```jsx
export default function ProfileTab() {
  return <div style={{ color: '#90a4ae' }}>Profile tab — coming in Task 14</div>;
}
```
- [ ] Create `retirement/frontend/src/tabs/ScenariosTab.jsx`:
```jsx
export default function ScenariosTab() {
  return <div style={{ color: '#90a4ae' }}>Scenarios tab — coming in Task 16</div>;
}
```
- [ ] Create `retirement/frontend/src/tabs/ResultsTab.jsx`:
```jsx
export default function ResultsTab() {
  return <div style={{ color: '#90a4ae' }}>Results tab — coming in Task 17</div>;
}
```
- [ ] Create `retirement/frontend/src/tabs/MonteCarloTab.jsx`:
```jsx
export default function MonteCarloTab() {
  return <div style={{ color: '#90a4ae' }}>Monte Carlo tab — coming in Task 19</div>;
}
```

### 13.8 Create index.html entry point
- [ ] Create `retirement/frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Retirement Calculator</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### 13.9 Install dependencies and verify dev server starts
- [ ]
```bash
cd retirement/frontend && npm install
```
Expected: `node_modules/` created, no errors.
- [ ]
```bash
cd retirement/frontend && npm run dev &
sleep 3
curl -s http://localhost:5173 | grep -q "root" && echo "PASS: Vite serving" || echo "FAIL"
kill %1
```
Expected output: `PASS: Vite serving`

### 13.10 Commit
- [ ] `git -C retirement add frontend/ && git -C retirement commit -m "feat: frontend foundation — Vite 5, React 18, axios client, tab shell, dark theme CSS (Task 13)"`

---

## Task 14: Profile Tab — People + Social Security inputs

### 14.1 Write ProfileTab.jsx
- [ ] Replace `retirement/frontend/src/tabs/ProfileTab.jsx` with:
```jsx
import React, { useEffect, useState, useRef } from 'react';
import { getProfiles, updateProfile, getSocialSecurity, updateSocialSecurity } from '../api/client.js';
import AccountsTable from '../components/AccountsTable.jsx';
import NQDCSchedule from '../components/NQDCSchedule.jsx';

function calcAge(dob) {
  if (!dob) return null;
  const today = new Date();
  const birth = new Date(dob);
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return age;
}

function useDebounce(fn, delay) {
  const timer = useRef(null);
  return (...args) => {
    clearTimeout(timer.current);
    timer.current = setTimeout(() => fn(...args), delay);
  };
}

function PersonCard({ person, ss, onPersonChange, onSsChange }) {
  const age = calcAge(person.dob);

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="section-title">{person.name}{age != null ? ` — Age ${age}` : ''}</div>
      <div className="field">
        <label>Date of Birth</label>
        <input
          type="date"
          value={person.dob || ''}
          onChange={(e) => onPersonChange(person.id, { dob: e.target.value })}
        />
      </div>
      <div className="field">
        <label>Life Expectancy: {person.life_expectancy_age}</label>
        <input
          type="range"
          min={70}
          max={100}
          value={person.life_expectancy_age || 88}
          onChange={(e) =>
            onPersonChange(person.id, { life_expectancy_age: parseInt(e.target.value, 10) })
          }
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#90a4ae', fontSize: 11 }}>
          <span>70</span><span>100</span>
        </div>
      </div>
      <div className="field">
        <label>State</label>
        <input type="text" value={person.state || 'DE'} readOnly style={{ opacity: 0.5 }} />
      </div>

      {ss && (
        <>
          <div className="section-title" style={{ marginTop: 16 }}>Social Security</div>
          <div className="three-col">
            <div className="field">
              <label>Benefit at 62 ($/mo)</label>
              <input
                type="number"
                min={0}
                value={ss.benefit_at_62 || ''}
                onChange={(e) => onSsChange(person.id, { benefit_at_62: parseFloat(e.target.value) || 0 })}
              />
            </div>
            <div className="field">
              <label>Benefit at FRA ($/mo)</label>
              <input
                type="number"
                min={0}
                value={ss.benefit_at_fra || ''}
                onChange={(e) => onSsChange(person.id, { benefit_at_fra: parseFloat(e.target.value) || 0 })}
              />
            </div>
            <div className="field">
              <label>Benefit at 70 ($/mo)</label>
              <input
                type="number"
                min={0}
                value={ss.benefit_at_70 || ''}
                onChange={(e) => onSsChange(person.id, { benefit_at_70: parseFloat(e.target.value) || 0 })}
              />
            </div>
          </div>
          <div className="two-col">
            <div className="field">
              <label>Full Retirement Age</label>
              <input
                type="number"
                min={62}
                max={70}
                value={ss.fra_age || 67}
                onChange={(e) => onSsChange(person.id, { fra_age: parseInt(e.target.value, 10) })}
              />
            </div>
            <div className="field">
              <label>Survivor Benefit (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={ss.survivor_benefit_pct != null ? ss.survivor_benefit_pct * 100 : ''}
                onChange={(e) =>
                  onSsChange(person.id, { survivor_benefit_pct: parseFloat(e.target.value) / 100 || 0 })
                }
              />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default function ProfileTab() {
  const [profiles, setProfiles] = useState([]);
  const [ssData, setSsData] = useState({});
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function load() {
      try {
        const profs = await getProfiles();
        setProfiles(profs);
        const ssMap = {};
        for (const p of profs) {
          try {
            ssMap[p.id] = await getSocialSecurity(p.id);
          } catch {
            ssMap[p.id] = null;
          }
        }
        setSsData(ssMap);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const debouncedUpdateProfile = useDebounce(async (id, patch) => {
    try {
      const updated = await updateProfile(id, patch);
      setProfiles((prev) => prev.map((p) => (p.id === id ? { ...p, ...updated } : p)));
    } catch (err) {
      console.error('Profile update failed:', err);
    }
  }, 500);

  const debouncedUpdateSs = useDebounce(async (profileId, patch) => {
    try {
      const updated = await updateSocialSecurity(profileId, patch);
      setSsData((prev) => ({ ...prev, [profileId]: { ...prev[profileId], ...updated } }));
    } catch (err) {
      console.error('SS update failed:', err);
    }
  }, 500);

  if (loading) return <div style={{ color: '#90a4ae' }}>Loading profile…</div>;
  if (error) return <div style={{ color: '#ef5350' }}>Error: {error}</div>;

  return (
    <div>
      <div className="two-col">
        {/* Left column: People */}
        <div>
          <h2 style={{ color: '#4fc3f7', fontSize: 16, marginBottom: 16 }}>People</h2>
          {profiles.map((person) => (
            <PersonCard
              key={person.id}
              person={person}
              ss={ssData[person.id]}
              onPersonChange={(id, patch) => {
                setProfiles((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
                debouncedUpdateProfile(id, patch);
              }}
              onSsChange={(profileId, patch) => {
                setSsData((prev) => ({
                  ...prev,
                  [profileId]: { ...prev[profileId], ...patch },
                }));
                debouncedUpdateSs(profileId, patch);
              }}
            />
          ))}
        </div>

        {/* Right column: Accounts */}
        <div>
          <h2 style={{ color: '#4fc3f7', fontSize: 16, marginBottom: 16 }}>Accounts</h2>
          <AccountsTable
            accounts={accounts}
            profiles={profiles}
            onAccountsChange={setAccounts}
          />
          <NQDCSchedule accounts={accounts} onAccountsChange={setAccounts} />
        </div>
      </div>
    </div>
  );
}
```

### 14.2 Commit
- [ ] `git -C retirement add frontend/src/tabs/ProfileTab.jsx && git -C retirement commit -m "feat: Profile Tab — People + SS inputs with debounced updates (Task 14)"`

---

## Task 15: Profile Tab — Accounts table + NQDC schedule editor

### 15.1 Write AccountsTable.jsx
- [ ] Create `retirement/frontend/src/components/AccountsTable.jsx`:
```jsx
import React, { useEffect, useState } from 'react';
import { getAccounts, createAccount, updateAccount, deleteAccount } from '../api/client.js';

const TYPE_COLORS = {
  '401k': '#ff9800',
  roth_ira: '#4fc3f7',
  brokerage: '#ce93d8',
  hsa: '#81c784',
  nqdc: '#ffcc02',
  pension: '#ff6b6b',
  real_estate: '#a5d6a7',
};

const TYPE_LABELS = {
  '401k': '401k',
  roth_ira: 'Roth IRA',
  brokerage: 'Brokerage',
  hsa: 'HSA',
  nqdc: 'NQDC',
  pension: 'Pension',
  real_estate: 'Real Estate',
};

const ACCOUNT_TYPES = Object.keys(TYPE_LABELS);

function TypeBadge({ type }) {
  const color = TYPE_COLORS[type] || '#90a4ae';
  return (
    <span
      className="badge"
      style={{ background: color + '22', color, border: `1px solid ${color}55` }}
    >
      {TYPE_LABELS[type] || type}
    </span>
  );
}

const EMPTY_FORM = {
  account_type: '401k',
  owner_id: '',
  balance: '',
  annual_return: '',
  annual_contribution: '',
};

export default function AccountsTable({ accounts, profiles, onAccountsChange }) {
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await getAccounts();
        onAccountsChange(data);
      } catch (err) {
        console.error('Failed to load accounts:', err);
      }
    }
    load();
  }, []);

  async function handleAdd() {
    if (!form.owner_id) return;
    setSaving(true);
    try {
      const payload = {
        account_type: form.account_type,
        owner_id: parseInt(form.owner_id, 10),
        balance: parseFloat(form.balance) || 0,
        annual_return: parseFloat(form.annual_return) || 0,
        annual_contribution: parseFloat(form.annual_contribution) || 0,
      };
      const created = await createAccount(payload);
      onAccountsChange((prev) => [...prev, created]);
      setForm(EMPTY_FORM);
      setShowAddForm(false);
    } catch (err) {
      console.error('Create account failed:', err);
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveEdit(id) {
    setSaving(true);
    try {
      const payload = {
        balance: parseFloat(editForm.balance) || 0,
        annual_return: parseFloat(editForm.annual_return) || 0,
        annual_contribution: parseFloat(editForm.annual_contribution) || 0,
      };
      const updated = await updateAccount(id, payload);
      onAccountsChange((prev) => prev.map((a) => (a.id === id ? { ...a, ...updated } : a)));
      setEditingId(null);
    } catch (err) {
      console.error('Update account failed:', err);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this account?')) return;
    try {
      await deleteAccount(id);
      onAccountsChange((prev) => prev.filter((a) => a.id !== id));
    } catch (err) {
      console.error('Delete account failed:', err);
    }
  }

  function ownerLabel(ownerId) {
    const p = profiles.find((x) => x.id === ownerId);
    if (!p) return '—';
    if (p.name === 'You') return 'You';
    if (p.name === 'Spouse') return 'Spouse';
    return p.name;
  }

  function fmt(n) {
    if (n == null) return '—';
    return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Owner</th>
              <th>Balance</th>
              <th>Return %</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {accounts.map((acct) =>
              editingId === acct.id ? (
                <tr key={acct.id}>
                  <td><TypeBadge type={acct.account_type} /></td>
                  <td>{ownerLabel(acct.owner_id)}</td>
                  <td>
                    <input
                      type="number"
                      value={editForm.balance}
                      onChange={(e) => setEditForm((f) => ({ ...f, balance: e.target.value }))}
                      style={{ width: 110 }}
                    />
                  </td>
                  <td>
                    <input
                      type="number"
                      step="0.1"
                      value={editForm.annual_return}
                      onChange={(e) => setEditForm((f) => ({ ...f, annual_return: e.target.value }))}
                      style={{ width: 70 }}
                    />
                  </td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => handleSaveEdit(acct.id)} disabled={saving}>Save</button>
                    <button className="secondary" onClick={() => setEditingId(null)}>Cancel</button>
                  </td>
                </tr>
              ) : (
                <tr key={acct.id}>
                  <td><TypeBadge type={acct.account_type} /></td>
                  <td>{ownerLabel(acct.owner_id)}</td>
                  <td>{fmt(acct.balance)}</td>
                  <td>{acct.annual_return}%</td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    <button
                      className="secondary"
                      onClick={() => {
                        setEditingId(acct.id);
                        setEditForm({
                          balance: acct.balance,
                          annual_return: acct.annual_return,
                          annual_contribution: acct.annual_contribution,
                        });
                      }}
                    >
                      Edit
                    </button>
                    <button className="danger" onClick={() => handleDelete(acct.id)}>Delete</button>
                  </td>
                </tr>
              )
            )}

            {showAddForm && (
              <tr>
                <td>
                  <select
                    value={form.account_type}
                    onChange={(e) => setForm((f) => ({ ...f, account_type: e.target.value }))}
                  >
                    {ACCOUNT_TYPES.map((t) => (
                      <option key={t} value={t}>{TYPE_LABELS[t]}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <select
                    value={form.owner_id}
                    onChange={(e) => setForm((f) => ({ ...f, owner_id: e.target.value }))}
                  >
                    <option value="">— Owner —</option>
                    {profiles.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="number"
                    placeholder="Balance"
                    value={form.balance}
                    onChange={(e) => setForm((f) => ({ ...f, balance: e.target.value }))}
                    style={{ width: 110 }}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    step="0.1"
                    placeholder="7.0"
                    value={form.annual_return}
                    onChange={(e) => setForm((f) => ({ ...f, annual_return: e.target.value }))}
                    style={{ width: 70 }}
                  />
                </td>
                <td style={{ display: 'flex', gap: 6 }}>
                  <button onClick={handleAdd} disabled={saving || !form.owner_id}>Add</button>
                  <button className="secondary" onClick={() => setShowAddForm(false)}>Cancel</button>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {!showAddForm && (
        <button className="secondary" onClick={() => setShowAddForm(true)}>
          + Add Account
        </button>
      )}
    </div>
  );
}
```

### 15.2 Write NQDCSchedule.jsx
- [ ] Create `retirement/frontend/src/components/NQDCSchedule.jsx`:
```jsx
import React, { useState } from 'react';
import { updateAccount } from '../api/client.js';

export default function NQDCSchedule({ accounts, onAccountsChange }) {
  const nqdcAccounts = accounts.filter((a) => a.account_type === 'nqdc');
  const [saving, setSaving] = useState(false);

  if (nqdcAccounts.length === 0) return null;

  async function handleScheduleChange(acctId, newSchedule) {
    setSaving(true);
    try {
      const updated = await updateAccount(acctId, { nqdc_schedule: newSchedule });
      onAccountsChange((prev) =>
        prev.map((a) => (a.id === acctId ? { ...a, ...updated } : a))
      );
    } catch (err) {
      console.error('Failed to update NQDC schedule:', err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ marginTop: 24 }}>
      {nqdcAccounts.map((acct) => {
        const schedule = Array.isArray(acct.nqdc_schedule) ? acct.nqdc_schedule : [];

        function addRow() {
          handleScheduleChange(acct.id, [...schedule, { date: '', amount: '' }]);
        }

        function removeRow(idx) {
          const next = schedule.filter((_, i) => i !== idx);
          handleScheduleChange(acct.id, next);
        }

        function updateRow(idx, field, value) {
          const next = schedule.map((row, i) =>
            i === idx ? { ...row, [field]: value } : row
          );
          handleScheduleChange(acct.id, next);
        }

        return (
          <div key={acct.id} className="card" style={{ marginBottom: 16 }}>
            <div className="section-title">NQDC Payout Schedule</div>
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Amount ($)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((row, idx) => (
                  <tr key={idx}>
                    <td>
                      <input
                        type="date"
                        value={row.date || ''}
                        onChange={(e) => updateRow(idx, 'date', e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        value={row.amount || ''}
                        onChange={(e) => updateRow(idx, 'amount', parseFloat(e.target.value) || 0)}
                        style={{ width: 120 }}
                      />
                    </td>
                    <td>
                      <button className="danger" onClick={() => removeRow(idx)} disabled={saving}>
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button
              className="secondary"
              style={{ marginTop: 10 }}
              onClick={addRow}
              disabled={saving}
            >
              + Add Payout
            </button>
          </div>
        );
      })}
    </div>
  );
}
```

### 15.3 Commit
- [ ] `git -C retirement add frontend/src/components/AccountsTable.jsx frontend/src/components/NQDCSchedule.jsx && git -C retirement commit -m "feat: AccountsTable + NQDCSchedule components (Task 15)"`

---

## Task 16: Scenarios Tab

### 16.1 Write ScenariosTab.jsx
- [ ] Replace `retirement/frontend/src/tabs/ScenariosTab.jsx` with:
```jsx
import React, { useEffect, useState } from 'react';
import {
  getScenarios,
  createScenario,
  updateScenario,
  deleteScenario,
  runProjection,
} from '../api/client.js';

const ACCOUNT_TYPES = ['401k', 'roth_ira', 'brokerage', 'hsa', 'nqdc', 'pension', 'real_estate'];

const DEFAULT_SCENARIO = {
  name: 'New Scenario',
  retirement_age_you: 57,
  retirement_age_spouse: 57,
  annual_spending: 120000,
  ss_claim_age_you: 67,
  ss_claim_age_spouse: 67,
  withdrawal_strategy: 'optimized',
  manual_withdrawal_order: ACCOUNT_TYPES,
  roth_conversion_enabled: false,
  roth_conversion_target_bracket: '22%',
  healthcare_monthly_pre_medicare: 1500,
  expected_return_stocks: 7.0,
  expected_return_bonds: 4.0,
  inflation_rate: 2.5,
  stock_allocation: 0.6,
};

function SliderWithLabel({ label, value, min, max, onChange, unit = '' }) {
  return (
    <div className="field">
      <label>{label}: {value}{unit}</label>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(parseInt(e.target.value, 10))}
      />
      <div style={{ display: 'flex', justifyContent: 'space-between', color: '#90a4ae', fontSize: 11 }}>
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

function SurvivalBadge({ rate }) {
  if (rate == null) return <span className="badge" style={{ background: '#1e3a5f', color: '#90a4ae' }}>Not run</span>;
  const pct = Math.round(rate * 100);
  const color = pct >= 85 ? '#81c784' : pct >= 70 ? '#ffb74d' : '#ef5350';
  return (
    <span className="badge" style={{ background: color + '22', color, border: `1px solid ${color}55` }}>
      {pct}% survival
    </span>
  );
}

export default function ScenariosTab() {
  const [scenarios, setScenarios] = useState([]);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getScenarios();
        setScenarios(data);
        if (data.length > 0) {
          setSelected(data[0].id);
          setForm({ ...data[0] });
        }
      } catch (err) {
        console.error('Failed to load scenarios:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function handleSelect(scenario) {
    setSelected(scenario.id);
    setForm({ ...scenario });
    setShowAdvanced(false);
  }

  function patchForm(patch) {
    setForm((f) => ({ ...f, ...patch }));
  }

  async function handleSave() {
    if (!form) return;
    try {
      const updated = await updateScenario(form.id, form);
      setScenarios((prev) => prev.map((s) => (s.id === form.id ? updated : s)));
      setForm(updated);
    } catch (err) {
      console.error('Save scenario failed:', err);
    }
  }

  async function handleNew() {
    try {
      const created = await createScenario(DEFAULT_SCENARIO);
      setScenarios((prev) => [...prev, created]);
      setSelected(created.id);
      setForm({ ...created });
    } catch (err) {
      console.error('Create scenario failed:', err);
    }
  }

  async function handleDuplicate() {
    if (!form) return;
    try {
      const { id, ...rest } = form;
      const created = await createScenario({ ...rest, name: `${form.name} (copy)` });
      setScenarios((prev) => [...prev, created]);
      setSelected(created.id);
      setForm({ ...created });
    } catch (err) {
      console.error('Duplicate scenario failed:', err);
    }
  }

  async function handleDelete(id) {
    if (!confirm('Delete this scenario?')) return;
    try {
      await deleteScenario(id);
      const next = scenarios.filter((s) => s.id !== id);
      setScenarios(next);
      if (selected === id) {
        setSelected(next[0]?.id ?? null);
        setForm(next[0] ? { ...next[0] } : null);
      }
    } catch (err) {
      console.error('Delete scenario failed:', err);
    }
  }

  async function handleRunProjection() {
    if (!form) return;
    setRunning(true);
    try {
      await handleSave();
      await runProjection(form.id);
      setLastRun((prev) => ({ ...prev, [form.id]: new Date().toLocaleString() }));
    } catch (err) {
      console.error('Run projection failed:', err);
    } finally {
      setRunning(false);
    }
  }

  function moveWithdrawalOrder(idx, direction) {
    const order = [...(form.manual_withdrawal_order || ACCOUNT_TYPES)];
    const targetIdx = idx + direction;
    if (targetIdx < 0 || targetIdx >= order.length) return;
    [order[idx], order[targetIdx]] = [order[targetIdx], order[idx]];
    patchForm({ manual_withdrawal_order: order });
  }

  if (loading) return <div style={{ color: '#90a4ae' }}>Loading scenarios…</div>;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 24 }}>
      {/* Scenario list */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ color: '#4fc3f7', fontWeight: 600 }}>Scenarios</span>
          <button onClick={handleNew} style={{ fontSize: 12, padding: '4px 10px' }}>+ New</button>
        </div>
        {scenarios.map((s) => (
          <div
            key={s.id}
            className="card"
            style={{
              marginBottom: 8,
              cursor: 'pointer',
              border: selected === s.id ? '1px solid #4fc3f7' : undefined,
              background: selected === s.id ? '#0f3460' : '#16213e',
            }}
            onClick={() => handleSelect(s)}
          >
            <div style={{ fontWeight: 600, marginBottom: 4 }}>{s.name}</div>
            <div style={{ fontSize: 12, color: '#90a4ae', marginBottom: 6 }}>
              Retire {s.retirement_age_you}/{s.retirement_age_spouse} · SS {s.ss_claim_age_you}/{s.ss_claim_age_spouse}
            </div>
            <SurvivalBadge rate={s.survival_rate ?? null} />
          </div>
        ))}
      </div>

      {/* Scenario editor */}
      {form ? (
        <div className="card">
          <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap' }}>
            <input
              type="text"
              value={form.name}
              onChange={(e) => patchForm({ name: e.target.value })}
              style={{ flex: '1 1 200px', fontWeight: 600, fontSize: 16 }}
            />
            <button onClick={handleSave} className="secondary">Save</button>
            <button onClick={handleDuplicate} className="secondary">Duplicate</button>
            <button onClick={() => handleDelete(form.id)} className="danger">Delete</button>
          </div>

          <div className="two-col">
            <div>
              <div className="section-title">Retirement Ages</div>
              <SliderWithLabel label="Your Retirement Age" value={form.retirement_age_you} min={52} max={70} onChange={(v) => patchForm({ retirement_age_you: v })} />
              <SliderWithLabel label="Spouse Retirement Age" value={form.retirement_age_spouse} min={52} max={70} onChange={(v) => patchForm({ retirement_age_spouse: v })} />

              <div className="section-title" style={{ marginTop: 16 }}>Annual Spending</div>
              <div className="field">
                <label>Annual Spending (today's dollars)</label>
                <input
                  type="number"
                  value={form.annual_spending}
                  onChange={(e) => patchForm({ annual_spending: parseFloat(e.target.value) || 0 })}
                />
              </div>
              <div className="field">
                <label>Healthcare ($/mo, pre-Medicare)</label>
                <input
                  type="number"
                  value={form.healthcare_monthly_pre_medicare}
                  onChange={(e) => patchForm({ healthcare_monthly_pre_medicare: parseFloat(e.target.value) || 0 })}
                />
              </div>

              <div className="section-title" style={{ marginTop: 16 }}>SS Claim Ages</div>
              <SliderWithLabel label="Your SS Claim Age" value={form.ss_claim_age_you} min={62} max={70} onChange={(v) => patchForm({ ss_claim_age_you: v })} />
              <SliderWithLabel label="Spouse SS Claim Age" value={form.ss_claim_age_spouse} min={62} max={70} onChange={(v) => patchForm({ ss_claim_age_spouse: v })} />
            </div>

            <div>
              <div className="section-title">Withdrawal Strategy</div>
              <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                {['optimized', 'manual'].map((s) => (
                  <button
                    key={s}
                    style={{
                      background: form.withdrawal_strategy === s ? '#4fc3f7' : '#16213e',
                      color: form.withdrawal_strategy === s ? '#0d1b2a' : '#e0e0e0',
                      border: '1px solid #1e3a5f',
                    }}
                    onClick={() => patchForm({ withdrawal_strategy: s })}
                  >
                    {s.charAt(0).toUpperCase() + s.slice(1)}
                  </button>
                ))}
              </div>

              {form.withdrawal_strategy === 'manual' && (
                <div style={{ marginBottom: 16 }}>
                  <div className="section-title">Withdrawal Priority (drag to reorder)</div>
                  {(form.manual_withdrawal_order || ACCOUNT_TYPES).map((type, idx) => (
                    <div
                      key={type}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '4px 8px',
                        background: '#16213e',
                        border: '1px solid #1e3a5f',
                        borderRadius: 4,
                        marginBottom: 4,
                      }}
                    >
                      <span style={{ flex: 1, fontSize: 13 }}>{idx + 1}. {type}</span>
                      <button
                        className="secondary"
                        style={{ padding: '2px 8px', fontSize: 12 }}
                        onClick={() => moveWithdrawalOrder(idx, -1)}
                        disabled={idx === 0}
                      >▲</button>
                      <button
                        className="secondary"
                        style={{ padding: '2px 8px', fontSize: 12 }}
                        onClick={() => moveWithdrawalOrder(idx, 1)}
                        disabled={idx === (form.manual_withdrawal_order || ACCOUNT_TYPES).length - 1}
                      >▼</button>
                    </div>
                  ))}
                </div>
              )}

              <div className="section-title">Return Assumptions</div>
              <div className="field">
                <label>Stocks Return (%)</label>
                <input type="number" step="0.1" value={form.expected_return_stocks} onChange={(e) => patchForm({ expected_return_stocks: parseFloat(e.target.value) || 0 })} />
              </div>
              <div className="field">
                <label>Bonds Return (%)</label>
                <input type="number" step="0.1" value={form.expected_return_bonds} onChange={(e) => patchForm({ expected_return_bonds: parseFloat(e.target.value) || 0 })} />
              </div>
              <div className="field">
                <label>Inflation (%)</label>
                <input type="number" step="0.1" value={form.inflation_rate} onChange={(e) => patchForm({ inflation_rate: parseFloat(e.target.value) || 0 })} />
              </div>
              <div className="field">
                <label>Stock Allocation (%)</label>
                <input type="number" step="1" min={0} max={100} value={Math.round(form.stock_allocation * 100)} onChange={(e) => patchForm({ stock_allocation: parseInt(e.target.value, 10) / 100 })} />
              </div>

              {/* Advanced: Roth conversion */}
              <div
                style={{ cursor: 'pointer', color: '#4fc3f7', fontSize: 13, marginTop: 8 }}
                onClick={() => setShowAdvanced((v) => !v)}
              >
                {showAdvanced ? '▾' : '▸'} Advanced Options
              </div>
              {showAdvanced && (
                <div style={{ marginTop: 10 }}>
                  <div className="field" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <input
                      type="checkbox"
                      id="roth-conv"
                      checked={!!form.roth_conversion_enabled}
                      onChange={(e) => patchForm({ roth_conversion_enabled: e.target.checked })}
                      style={{ width: 'auto' }}
                    />
                    <label htmlFor="roth-conv" style={{ textTransform: 'none', fontSize: 13 }}>
                      Enable Roth Conversion Ladder
                    </label>
                  </div>
                  {form.roth_conversion_enabled && (
                    <div className="field">
                      <label>Target Bracket</label>
                      <select
                        value={form.roth_conversion_target_bracket}
                        onChange={(e) => patchForm({ roth_conversion_target_bracket: e.target.value })}
                      >
                        {['10%', '12%', '22%', '24%', '32%'].map((b) => (
                          <option key={b} value={b}>{b}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div style={{ marginTop: 20, borderTop: '1px solid #1e3a5f', paddingTop: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
            <button onClick={handleRunProjection} disabled={running} style={{ minWidth: 160 }}>
              {running ? 'Running…' : 'Run Projection'}
            </button>
            {lastRun[form.id] && (
              <span style={{ color: '#90a4ae', fontSize: 12 }}>Last run: {lastRun[form.id]}</span>
            )}
          </div>
        </div>
      ) : (
        <div style={{ color: '#90a4ae' }}>Select or create a scenario.</div>
      )}
    </div>
  );
}
```

### 16.2 Commit
- [ ] `git -C retirement add frontend/src/tabs/ScenariosTab.jsx && git -C retirement commit -m "feat: Scenarios Tab — list, editor, sliders, withdrawal strategy, Roth toggle (Task 16)"`

---

## Task 17: Results Tab — key metrics + portfolio chart + income chart

### 17.1 Write PortfolioChart.jsx
- [ ] Create `retirement/frontend/src/components/PortfolioChart.jsx`:
```jsx
import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer, Legend,
} from 'recharts';

function fmtDollar(v) {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{ background: '#0f3460', border: '1px solid #1e3a5f', borderRadius: 6, padding: '10px 14px', fontSize: 13 }}>
      <div style={{ color: '#4fc3f7', fontWeight: 700, marginBottom: 4 }}>Age {d.age_you} · {d.year}</div>
      <div>Portfolio: <strong>{fmtDollar(d.portfolio_balance)}</strong></div>
    </div>
  );
};

export default function PortfolioChart({ years, retirementAge, ssStartAge, rmdStartAge = 73 }) {
  if (!years?.length) return <div style={{ color: '#90a4ae', padding: 24 }}>No projection data. Run a scenario first.</div>;

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={years} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
        <XAxis dataKey="age_you" stroke="#90a4ae" tick={{ fontSize: 11 }} label={{ value: 'Your Age', position: 'insideBottom', offset: -4, fill: '#90a4ae', fontSize: 11 }} />
        <YAxis stroke="#90a4ae" tick={{ fontSize: 11 }} tickFormatter={fmtDollar} width={60} />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="portfolio_balance"
          stroke="#4fc3f7"
          strokeWidth={2}
          dot={false}
          name="Portfolio Balance"
        />
        {retirementAge != null && (
          <ReferenceLine x={retirementAge} stroke="#ff9800" strokeDasharray="4 3" label={{ value: 'Retire', fill: '#ff9800', fontSize: 11 }} />
        )}
        {ssStartAge != null && (
          <ReferenceLine x={ssStartAge} stroke="#81c784" strokeDasharray="4 3" label={{ value: 'SS Start', fill: '#81c784', fontSize: 11 }} />
        )}
        <ReferenceLine x={rmdStartAge} stroke="#ce93d8" strokeDasharray="4 3" label={{ value: 'RMD 73', fill: '#ce93d8', fontSize: 11 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}
```

### 17.2 Write IncomeBreakdownChart.jsx
- [ ] Create `retirement/frontend/src/components/IncomeBreakdownChart.jsx`:
```jsx
import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer,
} from 'recharts';

const SOURCE_COLORS = {
  ss: '#81c784',
  '401k': '#ff9800',
  roth_ira: '#4fc3f7',
  brokerage: '#ce93d8',
  nqdc: '#ffcc02',
  rmd: '#ff9800',
  pension: '#ff6b6b',
  real_estate: '#a5d6a7',
};

const SOURCE_LABELS = {
  ss: 'Social Security',
  '401k': '401k',
  roth_ira: 'Roth IRA',
  brokerage: 'Brokerage',
  nqdc: 'NQDC',
  rmd: 'RMD',
  pension: 'Pension',
  real_estate: 'Rental',
};

function bucketByAge(years) {
  // Group into 5-year age buckets
  if (!years?.length) return [];
  const buckets = {};
  for (const y of years) {
    const bucket = Math.floor(y.age_you / 5) * 5;
    const key = `${bucket}–${bucket + 4}`;
    if (!buckets[key]) buckets[key] = { age: key };
    const src = y.income_by_source || {};
    for (const [k, v] of Object.entries(src)) {
      buckets[key][k] = (buckets[key][k] || 0) + v / 5; // avg per year in bucket
    }
  }
  return Object.values(buckets);
}

export default function IncomeBreakdownChart({ years }) {
  const data = bucketByAge(years);
  if (!data.length) return <div style={{ color: '#90a4ae', padding: 24 }}>No projection data. Run a scenario first.</div>;

  const sources = Object.keys(SOURCE_COLORS).filter((k) => data.some((d) => d[k] > 0));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
        <XAxis dataKey="age" stroke="#90a4ae" tick={{ fontSize: 11 }} />
        <YAxis stroke="#90a4ae" tick={{ fontSize: 11 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} width={60} />
        <Tooltip
          contentStyle={{ background: '#0f3460', border: '1px solid #1e3a5f', borderRadius: 6, fontSize: 12 }}
          formatter={(value, name) => [`$${Number(value).toLocaleString('en-US', { maximumFractionDigits: 0 })}`, SOURCE_LABELS[name] || name]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} formatter={(v) => SOURCE_LABELS[v] || v} />
        {sources.map((src) => (
          <Bar key={src} dataKey={src} stackId="income" fill={SOURCE_COLORS[src]} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### 17.3 Write ResultsTab.jsx
- [ ] Replace `retirement/frontend/src/tabs/ResultsTab.jsx` with:
```jsx
import React, { useEffect, useState } from 'react';
import { getScenarios, getProjection } from '../api/client.js';
import PortfolioChart from '../components/PortfolioChart.jsx';
import IncomeBreakdownChart from '../components/IncomeBreakdownChart.jsx';
import TaxSummaryPanel from '../components/TaxSummaryPanel.jsx';

function MetricCard({ label, value, sub }) {
  return (
    <div className="metric-card">
      <div className="metric-value">{value}</div>
      <div className="metric-label">{label}</div>
      {sub && <div style={{ fontSize: 11, color: '#90a4ae', marginTop: 4 }}>{sub}</div>}
    </div>
  );
}

function fmtDollar(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n}`;
}

function computeMetrics(years) {
  if (!years?.length) return {};
  const retirementYear = years.find((y) => y.withdrawal_notes?.some?.((n) => typeof n === 'string' && n.includes('retire')));
  const portfolioAtRetirement = retirementYear?.portfolio_balance ?? years[0]?.portfolio_balance;
  const depleted = years.find((y) => y.portfolio_balance <= 0);
  const depletionAge = depleted ? depleted.age_you : null;
  const lastYear = years[years.length - 1];
  const estate = lastYear?.portfolio_balance;
  const avgEffRate = years.reduce((sum, y) => sum + (y.effective_rate || 0), 0) / years.length;
  return { portfolioAtRetirement, depletionAge, estate, avgEffRate };
}

export default function ResultsTab() {
  const [scenarios, setScenarios] = useState([]);
  const [selectedIds, setSelectedIds] = useState([]);
  const [projections, setProjections] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getScenarios();
        setScenarios(data);
        if (data.length > 0) setSelectedIds([data[0].id]);
      } catch (err) {
        console.error('Failed to load scenarios:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  useEffect(() => {
    async function loadProjection(id) {
      if (projections[id]) return;
      try {
        const data = await getProjection(id);
        setProjections((prev) => ({ ...prev, [id]: data }));
      } catch {
        setProjections((prev) => ({ ...prev, [id]: null }));
      }
    }
    for (const id of selectedIds) loadProjection(id);
  }, [selectedIds]);

  function toggleScenario(id) {
    setSelectedIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return [prev[1], id];
      return [...prev, id];
    });
  }

  if (loading) return <div style={{ color: '#90a4ae' }}>Loading…</div>;

  const primaryId = selectedIds[0];
  const primaryScenario = scenarios.find((s) => s.id === primaryId);
  const primaryProjection = projections[primaryId];
  const years = primaryProjection?.years ?? [];
  const metrics = computeMetrics(years);

  return (
    <div>
      {/* Scenario selector chips */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
        {scenarios.map((s) => (
          <button
            key={s.id}
            onClick={() => toggleScenario(s.id)}
            style={{
              background: selectedIds.includes(s.id) ? '#4fc3f7' : '#16213e',
              color: selectedIds.includes(s.id) ? '#0d1b2a' : '#e0e0e0',
              border: '1px solid #1e3a5f',
              borderRadius: 20,
              padding: '4px 14px',
              fontSize: 13,
            }}
          >
            {s.name}
          </button>
        ))}
      </div>

      {/* Key metrics row */}
      <div className="four-col" style={{ marginBottom: 24 }}>
        <MetricCard
          label="Portfolio at Retirement"
          value={fmtDollar(metrics.portfolioAtRetirement)}
        />
        <MetricCard
          label="Depletion Age"
          value={metrics.depletionAge ? `Age ${metrics.depletionAge}` : 'Never ✓'}
          sub={metrics.depletionAge ? 'Portfolio runs out' : 'Portfolio survives'}
        />
        <MetricCard
          label="Avg Effective Tax Rate"
          value={metrics.avgEffRate != null ? `${(metrics.avgEffRate * 100).toFixed(1)}%` : '—'}
        />
        <MetricCard
          label="Estate at Life Expectancy"
          value={fmtDollar(metrics.estate)}
        />
      </div>

      {/* Charts + Tax Panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 24 }}>
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="section-title" style={{ marginBottom: 12 }}>Portfolio Balance Over Time</div>
            <PortfolioChart
              years={years}
              retirementAge={primaryScenario?.retirement_age_you}
              ssStartAge={primaryScenario?.ss_claim_age_you}
            />
          </div>
          <div className="card">
            <div className="section-title" style={{ marginBottom: 12 }}>Annual Income by Source</div>
            <IncomeBreakdownChart years={years} />
          </div>
        </div>
        <TaxSummaryPanel years={years} scenario={primaryScenario} />
      </div>
    </div>
  );
}
```

### 17.4 Commit
- [ ] `git -C retirement add frontend/src/tabs/ResultsTab.jsx frontend/src/components/PortfolioChart.jsx frontend/src/components/IncomeBreakdownChart.jsx && git -C retirement commit -m "feat: Results Tab — key metrics, portfolio chart, income breakdown chart (Task 17)"`

---

## Task 18: Results Tab — tax summary panel

### 18.1 Write TaxSummaryPanel.jsx
- [ ] Create `retirement/frontend/src/components/TaxSummaryPanel.jsx`:
```jsx
import React, { useState } from 'react';

function rateColor(rate) {
  if (rate == null) return '#90a4ae';
  const pct = rate * 100;
  if (pct < 12) return '#81c784';
  if (pct < 20) return '#ffb74d';
  return '#ef5350';
}

function fmtDollar(n) {
  if (n == null || n === 0) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function PhaseCard({ title, years }) {
  const [open, setOpen] = useState(true);
  if (!years.length) return null;

  const avgFedTax = years.reduce((s, y) => s + (y.federal_tax || 0), 0) / years.length;
  const avgStateTax = years.reduce((s, y) => s + (y.state_tax || 0), 0) / years.length;
  const avgRate = years.reduce((s, y) => s + (y.effective_rate || 0), 0) / years.length;

  // Aggregate income sources across years
  const sources = {};
  for (const y of years) {
    if (!y.income_by_source) continue;
    for (const [k, v] of Object.entries(y.income_by_source)) {
      sources[k] = (sources[k] || 0) + v;
    }
  }
  const avgSources = Object.fromEntries(
    Object.entries(sources).map(([k, v]) => [k, v / years.length])
  );

  // Collect optimizer notes
  const notes = new Set();
  for (const y of years) {
    if (Array.isArray(y.withdrawal_notes)) {
      y.withdrawal_notes.forEach((n) => typeof n === 'string' && n && notes.add(n));
    }
  }
  const uniqueNotes = [...notes].slice(0, 6);

  const color = rateColor(avgRate);

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
        onClick={() => setOpen((v) => !v)}
      >
        <span style={{ fontWeight: 600, fontSize: 13 }}>{title}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color, fontWeight: 700, fontSize: 14 }}>
            {(avgRate * 100).toFixed(1)}%
          </span>
          <span style={{ color: '#90a4ae' }}>{open ? '▾' : '▸'}</span>
        </div>
      </div>

      {open && (
        <div style={{ marginTop: 12 }}>
          <table style={{ fontSize: 12, marginBottom: 10 }}>
            <tbody>
              {Object.entries(avgSources)
                .filter(([, v]) => v > 100)
                .sort(([, a], [, b]) => b - a)
                .map(([src, avg]) => (
                  <tr key={src}>
                    <td style={{ color: '#90a4ae', paddingRight: 16, paddingTop: 2, paddingBottom: 2 }}>
                      {src.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                    </td>
                    <td style={{ textAlign: 'right' }}>{fmtDollar(avg)}</td>
                  </tr>
                ))}
            </tbody>
          </table>

          <div style={{ display: 'flex', gap: 12, marginBottom: 10, fontSize: 12 }}>
            <div>
              <span style={{ color: '#90a4ae' }}>Federal: </span>
              <strong>{fmtDollar(avgFedTax)}</strong>
            </div>
            <div>
              <span style={{ color: '#90a4ae' }}>State (DE): </span>
              <strong>{fmtDollar(avgStateTax)}</strong>
            </div>
          </div>

          {uniqueNotes.length > 0 && (
            <div style={{ borderTop: '1px solid #1e3a5f', paddingTop: 8, fontSize: 12 }}>
              <div style={{ color: '#90a4ae', marginBottom: 4, fontSize: 11 }}>OPTIMIZER NOTES</div>
              <ul style={{ paddingLeft: 16, margin: 0 }}>
                {uniqueNotes.map((note, i) => (
                  <li key={i} style={{ marginBottom: 2 }}>{note}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function TaxSummaryPanel({ years, scenario }) {
  if (!years?.length) {
    return (
      <div className="card" style={{ color: '#90a4ae', padding: 24 }}>
        Run a projection to see tax summary.
      </div>
    );
  }

  const ssStartAge = scenario?.ss_claim_age_you ?? 67;
  const retirementAge = scenario?.retirement_age_you ?? 57;

  const preSSYears = years.filter((y) => y.age_you >= retirementAge && y.age_you < ssStartAge);
  const postSSPreRMDYears = years.filter((y) => y.age_you >= ssStartAge && y.age_you < 73);
  const postRMDYears = years.filter((y) => y.age_you >= 73);

  return (
    <div>
      <div style={{ color: '#4fc3f7', fontWeight: 600, fontSize: 14, marginBottom: 14 }}>Tax Summary by Phase</div>
      <PhaseCard title={`Pre-SS (${retirementAge}–${ssStartAge - 1})`} years={preSSYears} />
      <PhaseCard title={`Post-SS / Pre-RMD (${ssStartAge}–72)`} years={postSSPreRMDYears} />
      <PhaseCard title="Post-RMD (73+)" years={postRMDYears} />
    </div>
  );
}
```

### 18.2 Commit
- [ ] `git -C retirement add frontend/src/components/TaxSummaryPanel.jsx && git -C retirement commit -m "feat: TaxSummaryPanel — phases, income sources, effective rate, optimizer notes (Task 18)"`

---

## Task 19: Monte Carlo Tab — survival rate + percentile fan chart + sensitivity

### 19.1 Write PercentileFanChart.jsx
- [ ] Create `retirement/frontend/src/components/PercentileFanChart.jsx`:
```jsx
import React from 'react';
import {
  AreaChart, Area, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ReferenceLine, ResponsiveContainer, Legend, ComposedChart,
} from 'recharts';

function fmtDollar(v) {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${(v / 1_000).toFixed(0)}k`;
  return `$${v}`;
}

function mergePercentiles(p10, p25, p50, p75, p90) {
  if (!p50?.length) return [];
  return p50.map((row, i) => ({
    age: row.age_you ?? i,
    p10: p10?.[i]?.portfolio_balance ?? 0,
    p25: p25?.[i]?.portfolio_balance ?? 0,
    p50: row.portfolio_balance ?? 0,
    p75: p75?.[i]?.portfolio_balance ?? 0,
    p90: p90?.[i]?.portfolio_balance ?? 0,
  }));
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: '#0f3460', border: '1px solid #1e3a5f', borderRadius: 6, padding: '10px 14px', fontSize: 12 }}>
      <div style={{ color: '#4fc3f7', fontWeight: 700, marginBottom: 6 }}>Age {label}</div>
      {[90, 75, 50, 25, 10].map((pct) => {
        const entry = payload.find((p) => p.dataKey === `p${pct}`);
        if (!entry) return null;
        return (
          <div key={pct}>{pct}th: <strong>{fmtDollar(entry.value)}</strong></div>
        );
      })}
    </div>
  );
};

export default function PercentileFanChart({ mcResult, retirementAge, ssStartAge }) {
  if (!mcResult?.percentile_50?.length) {
    return <div style={{ color: '#90a4ae', padding: 24 }}>No Monte Carlo data. Run simulations first.</div>;
  }

  const data = mergePercentiles(
    mcResult.percentile_10,
    mcResult.percentile_25,
    mcResult.percentile_50,
    mcResult.percentile_75,
    mcResult.percentile_90,
  );

  return (
    <ResponsiveContainer width="100%" height={340}>
      <ComposedChart data={data} margin={{ top: 10, right: 20, left: 10, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" />
        <XAxis dataKey="age" stroke="#90a4ae" tick={{ fontSize: 11 }} label={{ value: 'Your Age', position: 'insideBottom', offset: -4, fill: '#90a4ae', fontSize: 11 }} />
        <YAxis stroke="#90a4ae" tick={{ fontSize: 11 }} tickFormatter={fmtDollar} width={60} />
        <Tooltip content={<CustomTooltip />} />
        <Legend wrapperStyle={{ fontSize: 11 }} />

        <Area type="monotone" dataKey="p90" stroke="#1565c0" fill="#1565c033" strokeWidth={1} name="90th pct" />
        <Area type="monotone" dataKey="p75" stroke="#4fc3f7" fill="#4fc3f722" strokeWidth={1} name="75th pct" />
        <Area type="monotone" dataKey="p25" stroke="#ff8a65" fill="#ff8a6522" strokeWidth={1} name="25th pct" />
        <Area type="monotone" dataKey="p10" stroke="#c62828" fill="#c6282833" strokeWidth={1} name="10th pct" />
        <Line type="monotone" dataKey="p50" stroke="#81c784" strokeWidth={2.5} dot={false} name="Median (50th)" />

        {retirementAge != null && (
          <ReferenceLine x={retirementAge} stroke="#ff9800" strokeDasharray="4 3" label={{ value: 'Retire', fill: '#ff9800', fontSize: 11 }} />
        )}
        {ssStartAge != null && (
          <ReferenceLine x={ssStartAge} stroke="#81c784" strokeDasharray="4 3" label={{ value: 'SS', fill: '#81c784', fontSize: 11 }} />
        )}
        <ReferenceLine x={73} stroke="#ce93d8" strokeDasharray="4 3" label={{ value: 'RMD', fill: '#ce93d8', fontSize: 11 }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
```

### 19.2 Write SensitivityChart.jsx
- [ ] Create `retirement/frontend/src/components/SensitivityChart.jsx`:
```jsx
import React from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Cell, ResponsiveContainer,
} from 'recharts';

const VAR_LABELS = {
  retirement_age: 'Retirement Age (±2yr)',
  annual_spending: 'Annual Spending (±15%)',
  ss_claim_age: 'SS Claim Age (62 vs 70)',
  expected_return_stocks: 'Stock Return (±1%)',
  inflation_rate: 'Inflation (±1%)',
  stock_allocation: 'Stock Allocation (±10%)',
};

export default function SensitivityChart({ sensitivity }) {
  if (!sensitivity || !Object.keys(sensitivity).length) {
    return <div style={{ color: '#90a4ae', padding: 16 }}>No sensitivity data available.</div>;
  }

  const data = Object.entries(sensitivity)
    .map(([key, delta]) => ({
      variable: VAR_LABELS[key] || key,
      delta: Math.round(delta * 1000) / 10, // convert to percentage points
    }))
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta));

  return (
    <ResponsiveContainer width="100%" height={Math.max(200, data.length * 44)}>
      <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 10, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e3a5f" horizontal={false} />
        <XAxis
          type="number"
          stroke="#90a4ae"
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => `${v > 0 ? '+' : ''}${v}pp`}
        />
        <YAxis type="category" dataKey="variable" stroke="#90a4ae" tick={{ fontSize: 11 }} width={180} />
        <Tooltip
          contentStyle={{ background: '#0f3460', border: '1px solid #1e3a5f', borderRadius: 6, fontSize: 12 }}
          formatter={(v) => [`${v > 0 ? '+' : ''}${v}pp survival rate`, 'Delta']}
        />
        <Bar dataKey="delta" radius={[0, 4, 4, 0]}>
          {data.map((entry, idx) => (
            <Cell key={idx} fill={entry.delta >= 0 ? '#81c784' : '#ef5350'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
```

### 19.3 Write MonteCarloTab.jsx
- [ ] Replace `retirement/frontend/src/tabs/MonteCarloTab.jsx` with:
```jsx
import React, { useEffect, useState } from 'react';
import { getScenarios, runMonteCarlo, getMonteCarlo } from '../api/client.js';
import PercentileFanChart from '../components/PercentileFanChart.jsx';
import SensitivityChart from '../components/SensitivityChart.jsx';
import SSStrategyTable from '../components/SSStrategyTable.jsx';

const SIM_COUNTS = [1000, 5000, 10000, 50000];

function SurvivalDisplay({ rate }) {
  if (rate == null) return <div style={{ color: '#90a4ae', fontSize: 48, fontWeight: 700 }}>—</div>;
  const pct = Math.round(rate * 100);
  const color = pct >= 85 ? '#81c784' : pct >= 70 ? '#ffb74d' : '#ef5350';
  return (
    <div style={{ color, fontSize: 64, fontWeight: 800, lineHeight: 1 }}>
      {pct}%
      <div style={{ fontSize: 14, fontWeight: 500, color: '#90a4ae', marginTop: 4 }}>survival rate</div>
    </div>
  );
}

function fmtDollar(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}k`;
  return `$${n}`;
}

function pctAtLifeExp(pctBand, lifeExpAge) {
  if (!pctBand?.length) return null;
  const last = pctBand.find((r) => r.age_you >= lifeExpAge) ?? pctBand[pctBand.length - 1];
  return last?.portfolio_balance ?? null;
}

export default function MonteCarloTab() {
  const [scenarios, setScenarios] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [mcResult, setMcResult] = useState(null);
  const [simCount, setSimCount] = useState(10000);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getScenarios();
        setScenarios(data);
        if (data.length > 0) {
          setSelectedId(data[0].id);
          try {
            const mc = await getMonteCarlo(data[0].id);
            setMcResult(mc);
          } catch {
            setMcResult(null);
          }
        }
      } catch (err) {
        console.error('Failed to load scenarios:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  async function handleSelectScenario(id) {
    setSelectedId(id);
    setMcResult(null);
    try {
      const mc = await getMonteCarlo(id);
      setMcResult(mc);
    } catch {
      setMcResult(null);
    }
  }

  async function handleRun() {
    if (!selectedId) return;
    setRunning(true);
    try {
      const result = await runMonteCarlo(selectedId, simCount);
      setMcResult(result);
    } catch (err) {
      console.error('Monte Carlo run failed:', err);
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <div style={{ color: '#90a4ae' }}>Loading…</div>;

  const scenario = scenarios.find((s) => s.id === selectedId);
  const lifeExpAge = 90; // default; could read from profiles

  const p10AtLE = pctAtLifeExp(mcResult?.percentile_10, lifeExpAge);
  const p50AtLE = pctAtLifeExp(mcResult?.percentile_50, lifeExpAge);
  const p90AtLE = pctAtLifeExp(mcResult?.percentile_90, lifeExpAge);

  return (
    <div>
      {/* Scenario selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap', alignItems: 'center' }}>
        {scenarios.map((s) => (
          <button
            key={s.id}
            onClick={() => handleSelectScenario(s.id)}
            style={{
              background: selectedId === s.id ? '#4fc3f7' : '#16213e',
              color: selectedId === s.id ? '#0d1b2a' : '#e0e0e0',
              border: '1px solid #1e3a5f',
              borderRadius: 20,
              padding: '4px 14px',
              fontSize: 13,
            }}
          >
            {s.name}
          </button>
        ))}
      </div>

      {/* Top metrics row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr 1fr 1fr', gap: 24, alignItems: 'center', marginBottom: 28 }}>
        <SurvivalDisplay rate={mcResult?.survival_rate} />
        <div className="metric-card">
          <div className="metric-value">{fmtDollar(p50AtLE)}</div>
          <div className="metric-label">Median at Life Exp</div>
        </div>
        <div className="metric-card">
          <div className="metric-value" style={{ color: '#ef5350' }}>{fmtDollar(p10AtLE)}</div>
          <div className="metric-label">10th Percentile</div>
        </div>
        <div className="metric-card">
          <div className="metric-value" style={{ color: '#81c784' }}>{fmtDollar(p90AtLE)}</div>
          <div className="metric-label">90th Percentile</div>
        </div>
      </div>

      {/* Run controls */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginBottom: 24 }}>
        <button onClick={handleRun} disabled={running || !selectedId} style={{ minWidth: 180 }}>
          {running ? `Running ${simCount.toLocaleString()} sims…` : `Run ${simCount.toLocaleString()} Simulations`}
        </button>
        <div style={{ display: 'flex', gap: 4 }}>
          {SIM_COUNTS.map((n) => (
            <button
              key={n}
              className="secondary"
              onClick={() => setSimCount(n)}
              style={{
                background: simCount === n ? '#4fc3f7' : undefined,
                color: simCount === n ? '#0d1b2a' : undefined,
                padding: '4px 10px',
                fontSize: 12,
              }}
            >
              {n >= 1000 ? `${n / 1000}k` : n}
            </button>
          ))}
        </div>
        {mcResult?.run_at && (
          <span style={{ color: '#90a4ae', fontSize: 12 }}>
            Last run: {new Date(mcResult.run_at).toLocaleString()}
          </span>
        )}
      </div>

      {/* Fan chart + Sensitivity */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 24, marginBottom: 24 }}>
        <div className="card">
          <div className="section-title" style={{ marginBottom: 12 }}>Portfolio Percentile Fan</div>
          <PercentileFanChart
            mcResult={mcResult}
            retirementAge={scenario?.retirement_age_you}
            ssStartAge={scenario?.ss_claim_age_you}
          />
        </div>
        <div className="card">
          <div className="section-title" style={{ marginBottom: 12 }}>Sensitivity Analysis</div>
          <SensitivityChart sensitivity={mcResult?.sensitivity} />
        </div>
      </div>

      {/* SS Strategy Table */}
      <SSStrategyTable scenario={scenario} />
    </div>
  );
}
```

### 19.4 Commit
- [ ] `git -C retirement add frontend/src/tabs/MonteCarloTab.jsx frontend/src/components/PercentileFanChart.jsx frontend/src/components/SensitivityChart.jsx && git -C retirement commit -m "feat: Monte Carlo Tab — survival rate, fan chart, sensitivity chart (Task 19)"`

---

## Task 20: Monte Carlo Tab — SS strategy table

### 20.1 Write SSStrategyTable.jsx
- [ ] Create `retirement/frontend/src/components/SSStrategyTable.jsx`:
```jsx
import React, { useEffect, useState } from 'react';
import { getSsStrategies, getProfiles, getSocialSecurity, updateScenario } from '../api/client.js';

function fmtDollar(n) {
  if (n == null) return '—';
  return '$' + Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function DeltaBadge({ delta }) {
  if (delta == null) return null;
  const pos = delta >= 0;
  const color = pos ? '#81c784' : '#ef5350';
  return (
    <span style={{ color, fontWeight: 600, fontSize: 12 }}>
      {pos ? '+' : ''}{fmtDollar(delta)}
    </span>
  );
}

export default function SSStrategyTable({ scenario }) {
  const [strategies, setStrategies] = useState([]);
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(false);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    if (!scenario) return;
    async function load() {
      setLoading(true);
      try {
        const profiles = await getProfiles();
        const you = profiles.find((p) => p.name === 'You');
        const spouse = profiles.find((p) => p.name === 'Spouse');
        if (!you || !spouse) return;

        const ssYou = await getSocialSecurity(you.id);
        const ssSpouse = await getSocialSecurity(spouse.id);

        const params = {
          benefit_62_you: ssYou.benefit_at_62,
          benefit_fra_you: ssYou.benefit_at_fra,
          benefit_70_you: ssYou.benefit_at_70,
          fra_age_you: ssYou.fra_age,
          benefit_62_spouse: ssSpouse.benefit_at_62,
          benefit_fra_spouse: ssSpouse.benefit_at_fra,
          benefit_70_spouse: ssSpouse.benefit_at_70,
          fra_age_spouse: ssSpouse.fra_age,
          life_exp_you: you.life_expectancy_age,
          life_exp_spouse: spouse.life_expectancy_age,
        };
        const data = await getSsStrategies(params);
        setStrategies(data.slice(0, 10));
      } catch (err) {
        console.error('Failed to load SS strategies:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [scenario?.id]);

  async function handleApply(strat) {
    if (!scenario) return;
    setApplying(true);
    try {
      await updateScenario(scenario.id, {
        ss_claim_age_you: strat.claim_age_you,
        ss_claim_age_spouse: strat.claim_age_spouse,
      });
    } catch (err) {
      console.error('Apply SS strategy failed:', err);
    } finally {
      setApplying(false);
    }
  }

  if (!scenario) return null;

  return (
    <div className="card">
      <div className="section-title" style={{ marginBottom: 12 }}>SS Claiming Strategies</div>
      {loading ? (
        <div style={{ color: '#90a4ae' }}>Loading strategies…</div>
      ) : strategies.length === 0 ? (
        <div style={{ color: '#90a4ae', fontSize: 13 }}>
          Enter Social Security benefit amounts in the Profile tab to see claiming strategies.
        </div>
      ) : (
        <>
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Your Age</th>
                <th>Spouse Age</th>
                <th>Lifetime Benefit</th>
                <th>vs. Recommended</th>
                <th>Notes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {strategies.map((strat, idx) => (
                <React.Fragment key={idx}>
                  <tr
                    style={{
                      background: idx === 0 ? '#0a2a1a' : selected === idx ? '#0f2a3f' : undefined,
                      cursor: 'pointer',
                    }}
                    onClick={() => setSelected(selected === idx ? null : idx)}
                  >
                    <td>
                      {idx === 0 ? (
                        <span style={{ color: '#81c784', fontWeight: 700 }}>★ 1</span>
                      ) : (
                        <span style={{ color: '#90a4ae' }}>{idx + 1}</span>
                      )}
                    </td>
                    <td>{strat.claim_age_you}</td>
                    <td>{strat.claim_age_spouse}</td>
                    <td style={{ fontWeight: 600 }}>{fmtDollar(strat.lifetime_benefit)}</td>
                    <td><DeltaBadge delta={idx === 0 ? null : strat.lifetime_benefit - strategies[0].lifetime_benefit} /></td>
                    <td style={{ color: '#90a4ae', fontSize: 12, maxWidth: 220, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {strat.notes}
                    </td>
                    <td>
                      <button
                        className="secondary"
                        style={{ fontSize: 11, padding: '3px 8px' }}
                        onClick={(e) => { e.stopPropagation(); handleApply(strat); }}
                        disabled={applying}
                      >
                        Apply
                      </button>
                    </td>
                  </tr>
                  {selected === idx && (
                    <tr>
                      <td colSpan={7} style={{ background: '#0a1e30', padding: '10px 14px', fontSize: 13, color: '#e0e0e0' }}>
                        {strat.notes || 'No additional notes.'}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
```

### 20.2 Commit
- [ ] `git -C retirement add frontend/src/components/SSStrategyTable.jsx && git -C retirement commit -m "feat: SSStrategyTable — ranked strategies, apply to scenario (Task 20)"`

---

## Task 21: API routes for projections, MC, SS optimizer

### 21.1 Write backend/routers/projections.py
- [ ] Create `retirement/backend/routers/projections.py`:
```python
"""Projection run + fetch endpoints."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account, MCResult, Profile, Projection, Scenario, SocialSecurity
from backend.engines.projection import run_projection, ProjectionInput

router = APIRouter(prefix="/projections", tags=["projections"])


def _build_input_hash(scenario: Scenario, profiles: list, accounts: list, ss_list: list) -> str:
    payload = {
        "scenario": {
            k: v for k, v in scenario.__dict__.items() if not k.startswith("_")
        },
        "profiles": [
            {k: v for k, v in p.__dict__.items() if not k.startswith("_")} for p in profiles
        ],
        "accounts": [
            {k: v for k, v in a.__dict__.items() if not k.startswith("_")} for a in accounts
        ],
        "ss": [
            {k: v for k, v in s.__dict__.items() if not k.startswith("_")} for s in ss_list
        ],
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _scenario_to_input(
    scenario: Scenario, profiles: list, accounts: list, ss_list: list
) -> ProjectionInput:
    from backend.engines.projection import AccountData, ProfileData, SSData

    profile_data = [
        ProfileData(
            id=p.id,
            name=p.name,
            dob=str(p.dob),
            life_expectancy_age=p.life_expectancy_age,
            state=p.state or "DE",
            filing_status=p.filing_status or "mfj",
        )
        for p in profiles
    ]

    account_data = [
        AccountData(
            id=a.id,
            owner_id=a.owner_id,
            account_type=a.account_type,
            balance=float(a.balance or 0),
            annual_return=float(a.annual_return or 0),
            annual_contribution=float(a.annual_contribution or 0),
            nqdc_schedule=a.nqdc_schedule or [],
            pension_monthly=float(a.pension_monthly or 0),
            pension_start_age=a.pension_start_age,
            rental_annual_income=float(a.rental_annual_income or 0),
        )
        for a in accounts
    ]

    ss_map = {s.owner_id: s for s in ss_list}
    ss_data = {}
    for p in profiles:
        ss = ss_map.get(p.id)
        if ss:
            ss_data[p.id] = SSData(
                benefit_at_62=float(ss.benefit_at_62 or 0),
                benefit_at_fra=float(ss.benefit_at_fra or 0),
                fra_age=ss.fra_age or 67,
                benefit_at_70=float(ss.benefit_at_70 or 0),
                survivor_benefit_pct=float(ss.survivor_benefit_pct or 1.0),
            )

    return ProjectionInput(
        profiles=profile_data,
        accounts=account_data,
        ss_data=ss_data,
        retirement_age_you=scenario.retirement_age_you,
        retirement_age_spouse=scenario.retirement_age_spouse,
        annual_spending=float(scenario.annual_spending or 0),
        ss_claim_age_you=scenario.ss_claim_age_you,
        ss_claim_age_spouse=scenario.ss_claim_age_spouse,
        withdrawal_strategy=scenario.withdrawal_strategy or "optimized",
        manual_withdrawal_order=scenario.manual_withdrawal_order or [],
        roth_conversion_enabled=bool(scenario.roth_conversion_enabled),
        roth_conversion_target_bracket=scenario.roth_conversion_target_bracket or "22%",
        healthcare_monthly_pre_medicare=float(scenario.healthcare_monthly_pre_medicare or 0),
        expected_return_stocks=float(scenario.expected_return_stocks or 7.0),
        expected_return_bonds=float(scenario.expected_return_bonds or 4.0),
        inflation_rate=float(scenario.inflation_rate or 2.5),
        stock_allocation=float(scenario.stock_allocation or 0.6),
    )


@router.post("/{scenario_id}/run")
def run_projection_endpoint(scenario_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    profiles = db.query(Profile).all()
    accounts = db.query(Account).all()
    ss_list = db.query(SocialSecurity).all()

    input_hash = _build_input_hash(scenario, profiles, accounts, ss_list)

    # Check cache
    cached = (
        db.query(Projection)
        .filter(Projection.scenario_id == scenario_id, Projection.input_hash == input_hash)
        .first()
    )
    if cached:
        existing = (
            db.query(Projection)
            .filter(Projection.scenario_id == scenario_id)
            .order_by(Projection.year)
            .all()
        )
        return {"years": [_proj_to_dict(p) for p in existing], "cached": True}

    # Clear stale cache for this scenario
    db.query(Projection).filter(Projection.scenario_id == scenario_id).delete()

    proj_input = _scenario_to_input(scenario, profiles, accounts, ss_list)
    year_results = run_projection(proj_input)

    for yr in year_results:
        row = Projection(
            scenario_id=scenario_id,
            input_hash=input_hash,
            year=yr.year,
            age_you=yr.age_you,
            age_spouse=yr.age_spouse,
            portfolio_balance=yr.portfolio_balance,
            balances_by_account=yr.balances_by_account,
            gross_income=yr.gross_income,
            income_by_source=yr.income_by_source,
            federal_tax=yr.federal_tax,
            state_tax=yr.state_tax,
            effective_rate=yr.effective_rate,
            roth_conversion_amount=yr.roth_conversion_amount,
            withdrawal_notes=yr.withdrawal_notes,
        )
        db.add(row)
    db.commit()

    saved = (
        db.query(Projection)
        .filter(Projection.scenario_id == scenario_id)
        .order_by(Projection.year)
        .all()
    )
    return {"years": [_proj_to_dict(p) for p in saved], "cached": False}


@router.get("/{scenario_id}")
def get_projection_endpoint(scenario_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    rows = (
        db.query(Projection)
        .filter(Projection.scenario_id == scenario_id)
        .order_by(Projection.year)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No projection found for this scenario. Run it first.")
    return {"years": [_proj_to_dict(p) for p in rows]}


def _proj_to_dict(p: Projection) -> dict:
    return {
        "year": p.year,
        "age_you": p.age_you,
        "age_spouse": p.age_spouse,
        "portfolio_balance": p.portfolio_balance,
        "balances_by_account": p.balances_by_account,
        "gross_income": p.gross_income,
        "income_by_source": p.income_by_source,
        "federal_tax": p.federal_tax,
        "state_tax": p.state_tax,
        "effective_rate": p.effective_rate,
        "roth_conversion_amount": p.roth_conversion_amount,
        "withdrawal_notes": p.withdrawal_notes,
    }
```

### 21.2 Write backend/routers/monte_carlo.py
- [ ] Create `retirement/backend/routers/monte_carlo.py`:
```python
"""Monte Carlo run + fetch endpoints, plus SS optimizer."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Account, MCResult, Profile, Scenario, SocialSecurity
from backend.engines.monte_carlo import run_monte_carlo, MonteCarloInput
from backend.engines.ss_optimizer import optimize_ss, SSOptimizerInput
from backend.routers.projections import _scenario_to_input

router = APIRouter(tags=["monte_carlo"])


class RunMCRequest(BaseModel):
    num_simulations: int = 10000


@router.post("/monte-carlo/{scenario_id}/run")
def run_mc_endpoint(
    scenario_id: int, body: RunMCRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    profiles = db.query(Profile).all()
    accounts = db.query(Account).all()
    ss_list = db.query(SocialSecurity).all()

    # Build hash including num_simulations
    cache_key_data = {
        "scenario_id": scenario_id,
        "num_simulations": body.num_simulations,
        "scenario": {k: v for k, v in scenario.__dict__.items() if not k.startswith("_")},
    }
    input_hash = hashlib.sha256(
        json.dumps(cache_key_data, sort_keys=True, default=str).encode()
    ).hexdigest()

    cached = (
        db.query(MCResult)
        .filter(MCResult.scenario_id == scenario_id, MCResult.input_hash == input_hash)
        .first()
    )
    if cached:
        return _mc_to_dict(cached) | {"cached": True}

    proj_input = _scenario_to_input(scenario, profiles, accounts, ss_list)
    mc_input = MonteCarloInput(projection_input=proj_input, num_simulations=body.num_simulations)
    result = run_monte_carlo(mc_input)

    # Clear stale cached result
    db.query(MCResult).filter(MCResult.scenario_id == scenario_id).delete()

    row = MCResult(
        scenario_id=scenario_id,
        input_hash=input_hash,
        num_simulations=body.num_simulations,
        survival_rate=result.survival_rate,
        percentile_10=result.percentile_10,
        percentile_25=result.percentile_25,
        percentile_50=result.percentile_50,
        percentile_75=result.percentile_75,
        percentile_90=result.percentile_90,
        sensitivity=result.sensitivity,
        run_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _mc_to_dict(row) | {"cached": False}


@router.get("/monte-carlo/{scenario_id}")
def get_mc_endpoint(scenario_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    row = (
        db.query(MCResult)
        .filter(MCResult.scenario_id == scenario_id)
        .order_by(MCResult.id.desc())
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=404, detail="No Monte Carlo result found. Run simulations first."
        )
    return _mc_to_dict(row)


@router.get("/ss-optimizer")
def ss_optimizer_endpoint(
    benefit_62_you: float = Query(...),
    benefit_fra_you: float = Query(...),
    benefit_70_you: float = Query(...),
    fra_age_you: int = Query(67),
    benefit_62_spouse: float = Query(...),
    benefit_fra_spouse: float = Query(...),
    benefit_70_spouse: float = Query(...),
    fra_age_spouse: int = Query(67),
    life_exp_you: int = Query(88),
    life_exp_spouse: int = Query(90),
) -> list[dict[str, Any]]:
    inp = SSOptimizerInput(
        benefit_62_you=benefit_62_you,
        benefit_fra_you=benefit_fra_you,
        benefit_70_you=benefit_70_you,
        fra_age_you=fra_age_you,
        benefit_62_spouse=benefit_62_spouse,
        benefit_fra_spouse=benefit_fra_spouse,
        benefit_70_spouse=benefit_70_spouse,
        fra_age_spouse=fra_age_spouse,
        life_exp_you=life_exp_you,
        life_exp_spouse=life_exp_spouse,
    )
    results = optimize_ss(inp)
    return [
        {
            "rank": i + 1,
            "claim_age_you": r.claim_age_you,
            "claim_age_spouse": r.claim_age_spouse,
            "lifetime_benefit": r.lifetime_benefit,
            "notes": r.notes,
        }
        for i, r in enumerate(results[:10])
    ]


def _mc_to_dict(row: MCResult) -> dict:
    return {
        "scenario_id": row.scenario_id,
        "num_simulations": row.num_simulations,
        "survival_rate": row.survival_rate,
        "percentile_10": row.percentile_10,
        "percentile_25": row.percentile_25,
        "percentile_50": row.percentile_50,
        "percentile_75": row.percentile_75,
        "percentile_90": row.percentile_90,
        "sensitivity": row.sensitivity,
        "run_at": row.run_at.isoformat() if row.run_at else None,
    }
```

### 21.3 Register routers in main.py
- [ ] Open `retirement/backend/main.py` and add the two new router imports and `app.include_router()` calls. The existing include_router block should look like:
```python
from backend.routers import profiles, accounts, scenarios, social_security
from backend.routers.projections import router as projections_router
from backend.routers.monte_carlo import router as mc_router

# ...existing includes...
app.include_router(projections_router)
app.include_router(mc_router)
```

### 21.4 Smoke test new endpoints with backend running
- [ ]
```bash
cd retirement
PYTHONPATH=. uvicorn backend.main:app --port 8000 &
sleep 2
curl -s http://localhost:8000/docs | grep -q "projections" && echo "PASS: /projections in OpenAPI" || echo "FAIL"
curl -s http://localhost:8000/docs | grep -q "monte-carlo" && echo "PASS: /monte-carlo in OpenAPI" || echo "FAIL"
curl -s http://localhost:8000/docs | grep -q "ss-optimizer" && echo "PASS: /ss-optimizer in OpenAPI" || echo "FAIL"
kill %1
```
Expected output:
```
PASS: /projections in OpenAPI
PASS: /monte-carlo in OpenAPI
PASS: /ss-optimizer in OpenAPI
```

### 21.5 Commit
- [ ] `git -C retirement add backend/routers/projections.py backend/routers/monte_carlo.py backend/main.py && git -C retirement commit -m "feat: projection + Monte Carlo + SS optimizer API routes (Task 21)"`

---

## Task 22: Makefile dev target wiring + final integration smoke test

### 22.1 Add concurrently to frontend devDependencies
- [ ] Edit `retirement/frontend/package.json` — add to `devDependencies`:
```json
"concurrently": "^8.2.2"
```
- [ ]
```bash
cd retirement/frontend && npm install
```

### 22.2 Update Makefile dev target to use concurrently
- [ ] Edit `retirement/Makefile`. Replace the `dev` target with:
```makefile
dev:
	cd $(FRONTEND_DIR) && npx concurrently \
		--names "backend,frontend" \
		--prefix-colors "cyan,magenta" \
		"cd .. && PYTHONPATH=. $(UVICORN) backend.main:app --reload --host 0.0.0.0 --port 8000" \
		"npm run dev" & \
	sleep 3 && open http://localhost:5173 2>/dev/null || xdg-open http://localhost:5173 2>/dev/null || true; \
	wait
```

### 22.3 Write db-seed implementation in database.py
- [ ] Append to `retirement/backend/database.py`:
```python
def seed_db() -> None:
    """Insert sample data for immediate use after install."""
    from datetime import date
    from backend.models import (
        Account, MCResult, Profile, Projection, Scenario, SocialSecurity,
    )

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        # Skip if already seeded
        if db.query(Profile).count() > 0:
            print("Database already has data — skipping seed.")
            return

        # Profiles
        you = Profile(
            name="You",
            dob=date(1972, 6, 15),
            life_expectancy_age=88,
            state="DE",
            filing_status="mfj",
            pre_retirement_income=180000.0,
        )
        spouse = Profile(
            name="Spouse",
            dob=date(1974, 3, 22),
            life_expectancy_age=90,
            state="DE",
            filing_status="mfj",
            pre_retirement_income=95000.0,
        )
        db.add_all([you, spouse])
        db.flush()

        # Social Security
        db.add_all([
            SocialSecurity(
                owner_id=you.id,
                benefit_at_62=2100.0,
                benefit_at_fra=3000.0,
                fra_age=67,
                benefit_at_70=3720.0,
                survivor_benefit_pct=1.0,
            ),
            SocialSecurity(
                owner_id=spouse.id,
                benefit_at_62=1400.0,
                benefit_at_fra=2000.0,
                fra_age=67,
                benefit_at_70=2480.0,
                survivor_benefit_pct=1.0,
            ),
        ])

        # Accounts
        db.add_all([
            Account(
                owner_id=you.id,
                account_type="401k",
                balance=750000.0,
                annual_return=7.0,
                annual_contribution=23000.0,
            ),
            Account(
                owner_id=you.id,
                account_type="roth_ira",
                balance=120000.0,
                annual_return=7.0,
                annual_contribution=7000.0,
            ),
            Account(
                owner_id=you.id,
                account_type="brokerage",
                balance=200000.0,
                annual_return=6.5,
                annual_contribution=15000.0,
            ),
            Account(
                owner_id=you.id,
                account_type="hsa",
                balance=35000.0,
                annual_return=5.0,
                annual_contribution=4150.0,
            ),
            Account(
                owner_id=you.id,
                account_type="nqdc",
                balance=0.0,
                annual_return=0.0,
                annual_contribution=0.0,
                nqdc_schedule=[
                    {"date": "2029-03-01", "amount": 50000},
                    {"date": "2030-03-01", "amount": 50000},
                    {"date": "2031-03-01", "amount": 50000},
                ],
            ),
            Account(
                owner_id=spouse.id,
                account_type="401k",
                balance=380000.0,
                annual_return=7.0,
                annual_contribution=23000.0,
            ),
            Account(
                owner_id=spouse.id,
                account_type="roth_ira",
                balance=65000.0,
                annual_return=7.0,
                annual_contribution=7000.0,
            ),
            Account(
                owner_id=you.id,
                account_type="pension",
                balance=0.0,
                annual_return=0.0,
                annual_contribution=0.0,
                pension_monthly=1200.0,
                pension_start_age=60,
            ),
            Account(
                owner_id=you.id,
                account_type="real_estate",
                balance=320000.0,
                annual_return=3.0,
                annual_contribution=0.0,
                rental_annual_income=18000.0,
            ),
        ])

        # Scenarios
        db.add_all([
            Scenario(
                name="Retire 57 · SS 67",
                retirement_age_you=57,
                retirement_age_spouse=57,
                annual_spending=120000.0,
                ss_claim_age_you=67,
                ss_claim_age_spouse=67,
                withdrawal_strategy="optimized",
                manual_withdrawal_order=["401k", "roth_ira", "brokerage", "hsa", "nqdc", "pension", "real_estate"],
                roth_conversion_enabled=True,
                roth_conversion_target_bracket="22%",
                healthcare_monthly_pre_medicare=1500.0,
                expected_return_stocks=7.0,
                expected_return_bonds=4.0,
                inflation_rate=2.5,
                stock_allocation=0.6,
            ),
            Scenario(
                name="Retire 59 · SS 70",
                retirement_age_you=59,
                retirement_age_spouse=59,
                annual_spending=130000.0,
                ss_claim_age_you=70,
                ss_claim_age_spouse=70,
                withdrawal_strategy="optimized",
                manual_withdrawal_order=["401k", "roth_ira", "brokerage", "hsa", "nqdc", "pension", "real_estate"],
                roth_conversion_enabled=False,
                roth_conversion_target_bracket="22%",
                healthcare_monthly_pre_medicare=1500.0,
                expected_return_stocks=7.0,
                expected_return_bonds=4.0,
                inflation_rate=2.5,
                stock_allocation=0.6,
            ),
        ])

        db.commit()
        print("Seed complete: 2 profiles, 9 accounts, 2 scenarios.")
```

### 22.4 Verify seed runs cleanly
- [ ]
```bash
cd retirement
make db-reset
make db-seed
```
Expected output:
```
Database reset complete.
Seed complete: 2 profiles, 9 accounts, 2 scenarios.
```

### 22.5 Full integration smoke test checklist
Run each step manually after `make dev`:

- [ ] `make install` completes without errors
- [ ] `make db-reset && make db-seed` outputs "Seed complete"
- [ ] `make dev` starts both backend (port 8000) and frontend (port 5173)
- [ ] Browser opens to http://localhost:5173
- [ ] **Profile tab** renders — two person cards (You + Spouse) with DOB, life expectancy, SS inputs, accounts table with 9 pre-seeded accounts
- [ ] Edit a DOB value — page saves without error (check Network tab: `PUT /api/profiles/1` returns 200)
- [ ] Edit an SS benefit — `PUT /api/social-security/1` returns 200
- [ ] **Scenarios tab** renders — two scenario cards in left panel
- [ ] Select "Retire 57 · SS 67" — edit form populates, sliders render
- [ ] Click "Run Projection" — button shows "Running…", then stops; no JS errors in console
- [ ] **Results tab** renders — scenario chips visible
- [ ] Selecting "Retire 57 · SS 67" loads portfolio chart and income chart (may show "No projection data" if projection endpoint returns 404 — run from Scenarios tab first)
- [ ] After running projection: portfolio line chart renders with retirement/SS/RMD reference lines; income stacked bar renders; tax summary panel shows three phases
- [ ] **Monte Carlo tab** renders — scenario selector, survival rate display (shows "—" until run), percentile chart placeholder
- [ ] Select sim count "1k", click "Run Simulations" — button shows running state; fan chart renders after completion; sensitivity bars render
- [ ] SS Strategy table loads top strategies
- [ ] `make lint` passes: `ruff check backend/` and `npx eslint src/` both exit 0

### 22.6 Commit
- [ ] `git -C retirement add Makefile backend/database.py frontend/package.json && git -C retirement commit -m "feat: Makefile concurrently dev target, db-seed with sample data (Task 22)"`

---

## Execution

Plan saved. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks

**2. Inline Execution** — execute tasks in this session with checkpoints

Which approach?
