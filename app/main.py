"""FastAPI application entry point.

Run locally with: uvicorn app.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router
from app.config import settings

app = FastAPI(
    title="Meta Ads AI Growth & Optimization OS",
    description=(
        "Multi-agent Meta Ads analysis and optimization system. "
        "Currently running in MOCK DATA MODE — no live Meta Ads account is connected."
    ),
    version="0.1.0",
)

app.include_router(router)


@app.get("/")
def root() -> dict:
    return {
        "name": "Meta Ads AI Growth & Optimization OS",
        "data_mode": settings.data_mode.value,
        "execution_mode": settings.execution_mode.value,
        "docs": "/docs",
    }
