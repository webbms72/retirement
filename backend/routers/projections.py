"""Projection router — full implementation in Task 21."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_projections() -> dict:
    return {"detail": "Not yet implemented — see Task 21"}
