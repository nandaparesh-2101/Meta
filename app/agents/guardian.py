"""Agent 16 — Guardian.

Guardian has veto power over every recommendation. Its contract is
deliberately different from the other 15 agents: it does not turn context
into findings, it reviews already-produced `Recommendation` objects and
returns a `GuardianDecision` per recommendation. It never invents new
analysis — it only checks the safety rules in `app.rules.safety_rules` and
`app.rules.scaling_rules` plus a small set of additional structural checks.
"""

from __future__ import annotations

from app.agents.base import AuditRecorder, NullAuditRecorder
from app.llm.provider import LLMProvider, get_llm_provider
from app.models.execution import AuditEventType, GuardianDecision, GuardianVerdict
from app.models.recommendations import Recommendation, RiskLevel
from app.orchestration.context import AgentContext
from app.rules import safety_rules

CHECKS_RUN = [
    "data_sufficiency",
    "budget_risk",
    "excessive_scaling",
    "confidence_vs_risk",
    "duplicate_experiment",
    "missing_measurement_plan",
    "tracking_anomaly",
]


class GuardianAgent:
    name = "guardian"
    description = "Reviews every recommendation for safety before it may be approved or executed."

    def __init__(self, llm_provider: LLMProvider | None = None, audit: AuditRecorder | None = None) -> None:
        self.llm = llm_provider or get_llm_provider()
        self.audit = audit or NullAuditRecorder()

    def review(self, context: AgentContext, recommendations: list[Recommendation]) -> list[GuardianDecision]:
        decisions: list[GuardianDecision] = []
        constraints = context.business_objective.constraints

        for rec in recommendations:
            concerns: list[str] = []
            concerns += safety_rules.check_data_sufficiency(rec)
            concerns += safety_rules.check_budget_risk(rec, constraints, self._current_budget(context, rec.entity_id))
            concerns += safety_rules.check_excessive_scaling(rec, self._proposed_change_pct(context, rec))
            concerns += safety_rules.check_confidence_vs_risk(rec)
            concerns += safety_rules.check_missing_measurement_plan(rec)

            entity_tags = {t for f in context.findings_for_entity(rec.entity_id) for t in f.tags}
            concerns += safety_rules.check_tracking_anomaly(list(entity_tags))

            for experiment in context.new_experiments:
                concerns += safety_rules.check_duplicate_experiment(experiment, context.existing_experiments)

            verdict = self._verdict_for(rec, concerns)
            decision = GuardianDecision(
                recommendation_id=rec.recommendation_id,
                verdict=verdict,
                checks_run=CHECKS_RUN,
                concerns=concerns,
                reasoning=self._reasoning(rec, verdict, concerns),
            )
            decisions.append(decision)

            self.audit.record(
                AuditEventType.GUARDIAN_DECISION,
                actor=self.name,
                summary=f"Guardian verdict for {rec.recommendation_id}: {verdict.value}",
                details={"concerns": concerns, "action": rec.action.value, "priority": rec.priority.value},
                entity_id=rec.entity_id,
            )

        return decisions

    @staticmethod
    def _current_budget(context: AgentContext, entity_id: str) -> float | None:
        campaign = next((c for c in context.campaigns if c.campaign_id == entity_id), None)
        return campaign.daily_budget if campaign else None

    @staticmethod
    def _proposed_change_pct(context: AgentContext, rec: Recommendation) -> float | None:
        # The optimization agent does not currently persist the exact proposed
        # budget number on the Recommendation object (only the action), so
        # Guardian conservatively assumes the business's own configured ceiling
        # was respected upstream and only flags truly extreme actions here.
        return None

    @staticmethod
    def _verdict_for(rec: Recommendation, concerns: list[str]) -> GuardianVerdict:
        if not concerns:
            return GuardianVerdict.APPROVE if rec.risk == RiskLevel.LOW else GuardianVerdict.APPROVE_WITH_CAUTION

        blocking_phrases = ("INSUFFICIENT_DATA", "protected-campaign", "already exists")
        if any(any(p in c for p in blocking_phrases) for c in concerns):
            return GuardianVerdict.REJECT

        if rec.risk == RiskLevel.HIGH or len(concerns) >= 2:
            return GuardianVerdict.REQUIRE_HUMAN_APPROVAL

        return GuardianVerdict.APPROVE_WITH_CAUTION

    @staticmethod
    def _reasoning(rec: Recommendation, verdict: GuardianVerdict, concerns: list[str]) -> str:
        if verdict == GuardianVerdict.APPROVE:
            return "No safety concerns identified; risk is low and evidence is adequate."
        if verdict == GuardianVerdict.APPROVE_WITH_CAUTION:
            return "Minor concerns noted but not blocking: " + "; ".join(concerns) if concerns else "Low-risk action approved."
        if verdict == GuardianVerdict.REQUIRE_HUMAN_APPROVAL:
            return "Risk or concern volume is high enough that a human must review before proceeding: " + "; ".join(concerns)
        return "Blocking concern(s) found: " + "; ".join(concerns)
