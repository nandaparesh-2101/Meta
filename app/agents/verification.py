"""Agents 55-56 — Post-Change Verification and Rollback Decision.

Both agents reason about `context.baseline_insights` ("before") vs.
`context.insights` ("after") a change. Since execution is disabled in this
build, these only ever run against real historical data supplied for the
comparison — never a hypothetical, and never immediately after a change
with no real "after" data yet.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot, pct_change
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

VERDICT_IMPROVE_THRESHOLD = -0.10  # CPL improving by >=10%
VERDICT_WORSEN_THRESHOLD = 0.10


class PostChangeVerificationAgent(BaseAgent):
    name = "post_change_verification"
    description = "Compares before vs. after a change and classifies IMPROVED / UNCHANGED / WORSE / INCONCLUSIVE."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        if not context.baseline_insights:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No baseline ('before') data supplied — nothing to verify yet.",
                    detail=(
                        "This agent only runs a real before/after comparison. Execution is disabled in this build, "
                        "so no change has actually been made through this system — this activates once "
                        "AgentContext.baseline_insights is supplied for a real comparison."
                    ),
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0,
                    suggested_actions=[],
                    tags=["no_baseline_data"],
                    status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        before = MetricSnapshot.aggregate(context.baseline_insights)
        after = MetricSnapshot.aggregate(context.insights)
        cpl_change = pct_change(before.cpl, after.cpl)
        qcpl_change = pct_change(before.qualified_cpl, after.qualified_cpl)
        revenue_change = pct_change(before.revenue, after.revenue)

        days_after = len({i.date for i in context.insights})
        sufficiency = assess_data_sufficiency(days_of_data=days_after, sample_size=after.leads, minimum_days_required=7, minimum_sample_required=30)

        if cpl_change is None:
            verdict = "INCONCLUSIVE"
        elif cpl_change <= VERDICT_IMPROVE_THRESHOLD:
            verdict = "IMPROVED"
        elif cpl_change >= VERDICT_WORSEN_THRESHOLD:
            verdict = "WORSE"
        else:
            verdict = "UNCHANGED"

        if verdict != "INCONCLUSIVE" and not sufficiency.allows_strong_recommendation:
            verdict = "INCONCLUSIVE"

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Post-change verdict: {verdict}",
                detail=(
                    f"CPL change: {cpl_change:+.0%}" if cpl_change is not None else "CPL change: N/A"
                ) + (f", qualified CPL change: {qcpl_change:+.0%}" if qcpl_change is not None else "")
                + (f", revenue change: {revenue_change:+.0%}" if revenue_change is not None else ""),
                evidence=[f"before: spend={before.spend:.2f} leads={before.leads} cpl={self._fmt(before.cpl)}",
                          f"after: spend={after.spend:.2f} leads={after.leads} cpl={self._fmt(after.cpl)}"],
                data_sufficiency=sufficiency.level,
                confidence=0.6 if sufficiency.allows_strong_recommendation else 0.3,
                suggested_actions=[ActionType.DO_NOTHING] if verdict != "WORSE" else [],
                tags=["post_change_verification", f"verdict:{verdict}"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"verdict": verdict, "cpl_change": cpl_change, "qualified_cpl_change": qcpl_change, "revenue_change": revenue_change},
            )
        ]

    @staticmethod
    def _fmt(v):
        return f"{v:.2f}" if v is not None else "N/A"


class RollbackDecisionAgent(BaseAgent):
    name = "rollback_decision"
    description = "Determines whether rollback should be considered — never auto-rolls-back without criteria and approval."

    HARM_THRESHOLD = 0.25  # CPL worsening by >=25%

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        verification = context.findings_by_agent("post_change_verification")
        if not verification:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No post-change verification available — rollback cannot be evaluated.",
                    detail="Run PostChangeVerificationAgent first.",
                    evidence=[], data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA, confidence=0.0,
                    suggested_actions=[], tags=["no_verification_data"], status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        v = verification[0]
        if v.status == FindingStatus.INSUFFICIENT_DATA:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No baseline verification data — rollback cannot be evaluated.",
                    detail="PostChangeVerificationAgent had no baseline to compare against this run.",
                    evidence=[], data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA, confidence=0.0,
                    suggested_actions=[], tags=["no_verification_data"], status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        cpl_change = v.payload.get("cpl_change")
        material_harm = (
            v.payload.get("verdict") == "WORSE"
            and cpl_change is not None
            and cpl_change >= self.HARM_THRESHOLD
            and v.data_sufficiency.value in ("promising", "confident")
        )

        return [
            AgentFinding(
                agent_name=self.name,
                headline=(
                    "Rollback should be considered — material, well-evidenced harm detected"
                    if material_harm else "Rollback not indicated by current evidence"
                ),
                detail=(
                    f"CPL worsened {cpl_change:+.0%}, exceeding the {self.HARM_THRESHOLD:.0%} material-harm threshold "
                    "with adequate data sufficiency. Per policy, this is a RECOMMENDATION only — rollback is never "
                    "automatic and requires human approval through the standard approval pipeline."
                    if material_harm else "Either the change did not verify as materially worse, or evidence is not yet strong enough to act on."
                ),
                evidence=[f"cpl_change={cpl_change}", f"verification_data_sufficiency={v.data_sufficiency.value}"],
                data_sufficiency=v.data_sufficiency,
                confidence=0.6 if material_harm else 0.3,
                suggested_actions=[ActionType.ROLLBACK_CHANGE] if material_harm else [ActionType.DO_NOTHING],
                tags=["rollback_decision"] + (["rollback_candidate"] if material_harm else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
            )
        ]
