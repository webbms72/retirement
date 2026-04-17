"""Database session setup and lifecycle utilities."""

from __future__ import annotations

import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./retirement.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
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
            m.Account(
                owner_id=you.id,
                account_type="401k",
                balance=800000.0,
                annual_return=0.07,
                annual_contribution=23000.0,
            ),
            m.Account(
                owner_id=you.id,
                account_type="roth_ira",
                balance=120000.0,
                annual_return=0.07,
                annual_contribution=7000.0,
            ),
            m.Account(
                owner_id=you.id,
                account_type="brokerage",
                balance=250000.0,
                annual_return=0.06,
                annual_contribution=20000.0,
            ),
            m.Account(
                owner_id=you.id,
                account_type="hsa",
                balance=45000.0,
                annual_return=0.06,
                annual_contribution=8300.0,
            ),
            m.Account(
                owner_id=you.id,
                account_type="nqdc",
                balance=0.0,
                annual_return=0.0,
                annual_contribution=0.0,
                nqdc_schedule=[
                    {"date": "2030-01-15", "amount": 50000},
                    {"date": "2031-01-15", "amount": 50000},
                    {"date": "2032-01-15", "amount": 50000},
                ],
            ),
            m.Account(
                owner_id=you.id,
                account_type="pension",
                balance=0.0,
                annual_return=0.0,
                annual_contribution=0.0,
                pension_monthly=2500.0,
                pension_start_age=60,
            ),
            m.Account(
                owner_id=spouse.id,
                account_type="401k",
                balance=320000.0,
                annual_return=0.07,
                annual_contribution=23000.0,
            ),
            m.Account(
                owner_id=spouse.id,
                account_type="roth_ira",
                balance=80000.0,
                annual_return=0.07,
                annual_contribution=7000.0,
            ),
            m.Account(
                owner_id=spouse.id,
                account_type="real_estate",
                balance=0.0,
                annual_return=0.0,
                annual_contribution=0.0,
                rental_annual_income=24000.0,
            ),
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
