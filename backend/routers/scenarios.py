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
def create_scenario(
    body: ScenarioCreate, db: Session = Depends(get_db)
) -> models.Scenario:
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


@router.post(
    "/{scenario_id}/duplicate",
    response_model=ScenarioOut,
    status_code=status.HTTP_201_CREATED,
)
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
