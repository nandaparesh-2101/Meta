"""FastAPI routes.

Minimal, real endpoints for the current mock-data-mode system. Execution
endpoints are intentionally NOT exposed for actual use — `POST /execute`
exists only to make the safety gate visible and always reports that
execution is disabled.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.integrations.meta.mock_data import (
    available_scenarios,
    generate_full_mock_account,
    generate_scenario,
)
from app.memory.store import MemoryStore
from app.orchestration.context import AgentContext
from app.orchestration.router import available_triggers
from app.orchestration.workflow import Orchestrator
from app.reports.command_center import generate_report

router = APIRouter()

_memory = MemoryStore()
_orchestrator = Orchestrator(memory=_memory)


class AnalyzeRequest(BaseModel):
    trigger: str = Field(default="scheduled_review", description="See GET /status for available triggers")
    scenario: str | None = Field(
        default=None, description="Restrict to one mock scenario (see GET /status); default uses all scenarios"
    )
    competitor_research: list[str] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    trigger: str
    executed_agents: list[str]
    finding_count: int
    recommendation_count: int
    guardian_decision_count: int
    approval_request_count: int
    report: dict[str, list[str]]


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/status")
def status() -> dict:
    return {
        "app_env": settings.app_env,
        "data_mode": settings.data_mode.value,
        "execution_mode": settings.execution_mode.value,
        "llm_provider": settings.llm_provider.value,
        "has_meta_credentials": settings.has_meta_credentials,
        "meta_api_connected": False,
        "available_triggers": available_triggers(),
        "available_mock_scenarios": available_scenarios(),
        "note": (
            "System runs in MOCK DATA MODE. No real Meta Ads account is connected; "
            "no real advertising change can be executed in this build."
        ),
    }


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    if request.scenario:
        try:
            account = generate_scenario(request.scenario, reference_date=date.today())
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        account = generate_full_mock_account(reference_date=date.today())

    context = AgentContext(
        business_objective=account.business_objective,
        campaigns=account.campaigns,
        ad_sets=account.ad_sets,
        ads=account.ads,
        creatives=account.creatives,
        insights=account.insights,
        leads=account.leads,
        sales=account.sales,
        trigger=request.trigger,
        competitor_research=request.competitor_research,
    )
    result = _orchestrator.run(context)
    report = generate_report(context, result.guardian_decisions)

    return AnalyzeResponse(
        trigger=request.trigger,
        executed_agents=result.executed_agents,
        finding_count=len(context.findings),
        recommendation_count=len(context.recommendations),
        guardian_decision_count=len(result.guardian_decisions),
        approval_request_count=len(result.approval_requests),
        report=report.to_dict(),
    )


@router.post("/recommend")
def recommend(limit: int = 50) -> list[dict]:
    """Returns the most recently persisted recommendations (from the last
    `/analyze` run or any prior one) — recommendation-only, per current
    system mode."""
    return [r.to_summary_dict() | {"recommendation_id": r.recommendation_id, "entity_id": r.entity_id} for r in _memory.get_recommendations(limit=limit)]


@router.get("/experiments")
def experiments() -> list[dict]:
    return [e.model_dump(mode="json") for e in _memory.get_all_experiments()]


@router.get("/learnings")
def learnings(tag: str | None = None) -> list[dict]:
    return [l.model_dump(mode="json") for l in _memory.get_learnings(tag=tag)]


@router.get("/audit")
def audit(limit: int = 200, entity_id: str | None = None) -> list[dict]:
    return [e.model_dump(mode="json") for e in _memory.get_audit_events(limit=limit, entity_id=entity_id)]


@router.post("/execute")
def execute() -> dict:
    """Execution is intentionally disabled in this build. This endpoint
    exists to make that explicit rather than returning a 404 that could be
    mistaken for "not built yet"."""
    return {
        "executed": False,
        "execution_mode": settings.execution_mode.value,
        "message": (
            "Execution is disabled in this build. This system produces recommendations only; "
            "no real Meta Ads account modification is possible."
        ),
    }
