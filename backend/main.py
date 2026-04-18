"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import Base, engine
from backend.routers import accounts, profiles, scenarios
from backend.routers import projections
from backend.routers import monte_carlo

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
app.include_router(monte_carlo.router, prefix="/api", tags=["monte_carlo"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
