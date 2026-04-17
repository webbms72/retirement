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
def create_profile(
    body: ProfileCreate, db: Session = Depends(get_db)
) -> models.Profile:
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
