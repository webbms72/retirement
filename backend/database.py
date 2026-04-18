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
    """Insert sample data for immediate use after install. Skips if data already exists."""
    import backend.models as m

    reset_db()
    db = SessionLocal()
    try:
        you = m.Profile(
            name="You",
            dob="1972-06-15",
            life_expectancy_age=88,
            state="DE",
            filing_status="mfj",
            pre_retirement_income=180000.0,
        )
        spouse = m.Profile(
            name="Spouse",
            dob="1974-03-22",
            life_expectancy_age=90,
            state="DE",
            filing_status="mfj",
            pre_retirement_income=95000.0,
        )
        db.add_all([you, spouse])
        db.flush()

        db.add_all(
            [
                m.SocialSecurity(
                    owner_id=you.id,
                    benefit_at_62=2100.0,
                    benefit_at_fra=3000.0,
                    fra_age=67,
                    benefit_at_70=3720.0,
                    survivor_benefit_pct=1.0,
                ),
                m.SocialSecurity(
                    owner_id=spouse.id,
                    benefit_at_62=1400.0,
                    benefit_at_fra=2000.0,
                    fra_age=67,
                    benefit_at_70=2480.0,
                    survivor_benefit_pct=1.0,
                ),
            ]
        )

        acct = m.Account(
            owner_id=you.id,
            account_type="nqdc",
            balance=0.0,
            annual_return=0.0,
            annual_contribution=0.0,
        )
        acct.nqdc_schedule = [
            {"date": "2029-03-01", "amount": 50000},
            {"date": "2030-03-01", "amount": 50000},
            {"date": "2031-03-01", "amount": 50000},
        ]

        pension = m.Account(
            owner_id=you.id,
            account_type="pension",
            balance=0.0,
            annual_return=0.0,
            annual_contribution=0.0,
            pension_monthly=1200.0,
            pension_start_age=60,
        )

        rental = m.Account(
            owner_id=you.id,
            account_type="real_estate",
            balance=320000.0,
            annual_return=0.03,
            annual_contribution=0.0,
            rental_annual_income=18000.0,
        )

        db.add_all(
            [
                m.Account(
                    owner_id=you.id,
                    account_type="401k",
                    balance=750000.0,
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
                    balance=200000.0,
                    annual_return=0.065,
                    annual_contribution=15000.0,
                ),
                m.Account(
                    owner_id=you.id,
                    account_type="hsa",
                    balance=35000.0,
                    annual_return=0.05,
                    annual_contribution=4150.0,
                ),
                acct,
                pension,
                rental,
                m.Account(
                    owner_id=spouse.id,
                    account_type="401k",
                    balance=380000.0,
                    annual_return=0.07,
                    annual_contribution=23000.0,
                ),
                m.Account(
                    owner_id=spouse.id,
                    account_type="roth_ira",
                    balance=65000.0,
                    annual_return=0.07,
                    annual_contribution=7000.0,
                ),
            ]
        )

        scenario1 = m.Scenario(
            name="Retire 57 · SS 67",
            retirement_age_you=57,
            retirement_age_spouse=57,
            annual_spending=120000.0,
            ss_claim_age_you=67,
            ss_claim_age_spouse=67,
            withdrawal_strategy="optimized",
            roth_conversion_enabled=True,
            roth_conversion_target_bracket="22%",
            healthcare_monthly_pre_medicare=1500.0,
            expected_return_stocks=0.07,
            expected_return_bonds=0.04,
            inflation_rate=0.025,
            stock_allocation=0.6,
        )
        scenario1.manual_withdrawal_order = [
            "401k",
            "roth_ira",
            "brokerage",
            "hsa",
            "nqdc",
            "pension",
            "real_estate",
        ]

        scenario2 = m.Scenario(
            name="Retire 59 · SS 70",
            retirement_age_you=59,
            retirement_age_spouse=59,
            annual_spending=130000.0,
            ss_claim_age_you=70,
            ss_claim_age_spouse=70,
            withdrawal_strategy="optimized",
            roth_conversion_enabled=False,
            roth_conversion_target_bracket="22%",
            healthcare_monthly_pre_medicare=1500.0,
            expected_return_stocks=0.07,
            expected_return_bonds=0.04,
            inflation_rate=0.025,
            stock_allocation=0.6,
        )
        scenario2.manual_withdrawal_order = [
            "401k",
            "roth_ira",
            "brokerage",
            "hsa",
            "nqdc",
            "pension",
            "real_estate",
        ]

        db.add_all([scenario1, scenario2])
        db.commit()
        print("Seed complete: 2 profiles, 9 accounts, 2 scenarios, 2 SS records.")
    finally:
        db.close()
