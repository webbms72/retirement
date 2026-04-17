"""Monte Carlo router — full implementation in Task 21."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_mc_results() -> dict:
    return {"detail": "Not yet implemented — see Task 21"}
