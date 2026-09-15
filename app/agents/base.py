"""Base agent framework.

Every specialist agent subclasses `BaseAgent` and implements `analyze()`.
`run()` wraps that with timing, defensive error handling, confidence capping
against data sufficiency, and audit logging — so individual agents stay
focused on their domain logic and never have to re-implement plumbing.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from typing import Protocol

from app.llm.provider import LLMProvider, get_llm_provider
from app.models.execution import AuditEventType
from app.models.recommendations import AgentFinding, FindingStatus
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import confidence_ceiling


class AuditRecorder(Protocol):
    def record(
        self, event_type: AuditEventType, actor: str, summary: str,
        details: dict | None = None, entity_id: str | None = None,
    ) -> None: ...


class NullAuditRecorder:
    """Used when an agent runs standalone (e.g. in a unit test) with no
    orchestrator/memory wired up."""

    def record(self, event_type, actor, summary, details=None, entity_id=None) -> None:  # noqa: D401
        return None


class BaseAgent(ABC):
    name: str = "base_agent"
    description: str = ""

    def __init__(self, llm_provider: LLMProvider | None = None, audit: AuditRecorder | None = None) -> None:
        self.llm = llm_provider or get_llm_provider()
        self.audit = audit or NullAuditRecorder()

    @abstractmethod
    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        """Perform this agent's domain analysis and return findings.

        Must not mutate `context.findings` directly — `run()` does that so
        every finding is uniformly audited.
        """
        ...

    def run(self, context: AgentContext) -> list[AgentFinding]:
        self.audit.record(
            AuditEventType.AGENT_STARTED, actor=self.name,
            summary=f"{self.name} started analysis (trigger={context.trigger})",
        )
        started = time.perf_counter()
        try:
            findings = self.analyze(context)
        except Exception as exc:  # defensive: one failing agent must not crash a run
            findings = [
                self._error_finding(context, exc),
            ]

        findings = [self._cap_confidence(f) for f in findings]
        for f in findings:
            context.add_finding(f)

        elapsed_ms = (time.perf_counter() - started) * 1000
        self.audit.record(
            AuditEventType.AGENT_COMPLETED, actor=self.name,
            summary=f"{self.name} completed in {elapsed_ms:.0f}ms with {len(findings)} finding(s)",
            details={"elapsed_ms": round(elapsed_ms, 1), "finding_count": len(findings)},
        )
        return findings

    def _cap_confidence(self, finding: AgentFinding) -> AgentFinding:
        ceiling = confidence_ceiling(finding.data_sufficiency)
        if finding.confidence > ceiling:
            return finding.model_copy(update={"confidence": ceiling})
        return finding

    def _error_finding(self, context: AgentContext, exc: Exception) -> AgentFinding:
        from app.models.metrics import DataSufficiencyLevel

        return AgentFinding(
            agent_name=self.name,
            entity_id=None,
            headline=f"{self.name} failed to complete analysis",
            detail=f"An internal error occurred and was contained: {exc!r}",
            evidence=[],
            data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
            confidence=0.0,
            suggested_actions=[],
            tags=["agent_error"],
            status=FindingStatus.ERROR,
        )

    def structured_output(self, context: AgentContext) -> dict:
        """The machine-readable per-call contract from the V2 agent spec:

            {agent, status, findings, evidence, assumptions,
             confidence, recommendations, questions}

        Aggregates every finding this agent produced on `run()` into one
        object. `run()` remains the primary interface other agents/the
        orchestrator use (a `list[AgentFinding]`) — this method exists for
        callers (API consumers, external tooling) that need the flatter
        contract instead.
        """
        findings = self.run(context)
        if not findings:
            return {
                "agent": self.name, "status": FindingStatus.COMPLETE.value,
                "findings": [], "evidence": [], "assumptions": [], "confidence": 0.0,
                "recommendations": [], "questions": [],
            }
        status = FindingStatus.ERROR if any(f.status == FindingStatus.ERROR for f in findings) else (
            FindingStatus.INSUFFICIENT_DATA
            if all(f.status == FindingStatus.INSUFFICIENT_DATA for f in findings)
            else FindingStatus.COMPLETE
        )
        return {
            "agent": self.name,
            "status": status.value,
            "findings": [f.headline for f in findings],
            "evidence": [e for f in findings for e in f.evidence],
            "assumptions": [a for f in findings for a in f.assumptions],
            "confidence": round(sum(f.confidence for f in findings) / len(findings), 2),
            "recommendations": sorted({a.value for f in findings for a in f.suggested_actions}),
            "questions": [q for f in findings for q in f.questions],
        }

    @staticmethod
    def new_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:10]}"
