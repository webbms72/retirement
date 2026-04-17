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
def create_account(
    body: AccountCreate, db: Session = Depends(get_db)
) -> models.Account:
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
