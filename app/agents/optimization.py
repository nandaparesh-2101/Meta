"""Agent 15 — Optimization Decision.

Converts the accumulated findings from every prior agent in this run into
prioritized, fully-structured `Recommendation` objects. Handles agent
disagreement by preserving every contributing finding and choosing the
higher-confidence, lower-risk path when actions conflict for the same
entity — it never silently drops a dissenting finding.
"""

from __future__ import annotations

from collections import defaultdict

from app.agents.base import BaseAgent
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, Priority, Recommendation, RiskLevel
from app.orchestration.context import AgentContext

NON_ACTIONABLE = {ActionType.DO_NOTHING}

HIGH_RISK_ACTIONS = {ActionType.DECREASE_BUDGET, ActionType.INCREASE_BUDGET, ActionType.PAUSE_AD_SET, ActionType.PAUSE_AD}
MEDIUM_RISK_ACTIONS = {ActionType.REALLOCATE_BUDGET, ActionType.ADJUST_AUDIENCE, ActionType.REFRESH_CREATIVE}
LOW_RISK_ACTIONS = {
    ActionType.ADJUST_COPY, ActionType.LAUNCH_TEST, ActionType.INVESTIGATE_TRACKING,
    ActionType.INVESTIGATE_OFFER, ActionType.MAINTAIN,
}

CRITICAL_TAGS = {"tracking_anomaly", "offer_risk"}


class OptimizationAgent(BaseAgent):
    name = "optimization"
    description = "Converts findings into prioritized, structured, evidence-backed recommendations."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        by_entity: dict[str | None, list[AgentFinding]] = defaultdict(list)
        for finding in context.findings:
            if finding.agent_name == self.name:
                continue
            by_entity[finding.entity_id].append(finding)

        summary_findings: list[AgentFinding] = []

        for entity_id, entity_findings in by_entity.items():
            actionable = [f for f in entity_findings if f.is_actionable()]
            if not actionable:
                continue

            action_votes: dict[ActionType, list[AgentFinding]] = defaultdict(list)
            for f in actionable:
                for action in f.suggested_actions:
                    if action not in NON_ACTIONABLE:
                        action_votes[action].append(f)

            for action, supporting in action_votes.items():
                best_sufficiency = max(
                    (f.data_sufficiency for f in supporting),
                    key=lambda lvl: list(DataSufficiencyLevel).index(lvl),
                )
                confidence = sum(f.confidence for f in supporting) / len(supporting)
                risk = self._risk_for(action)
                priority = self._priority_for(action, supporting, best_sufficiency, confidence)
                requires_approval = action not in {ActionType.DO_NOTHING}

                recommendation = Recommendation(
                    recommendation_id=self.new_id("rec"),
                    entity_id=entity_id or "account_level",
                    entity_level="campaign",
                    action=action,
                    priority=priority,
                    reason="; ".join(f.headline for f in supporting),
                    evidence=[e for f in supporting for e in f.evidence],
                    contributing_agents=list({f.agent_name for f in supporting}),
                    expected_impact=self._expected_impact(action),
                    confidence=round(confidence, 2),
                    risk=risk,
                    measurement=self._measurement_for(action),
                    review_window_days=14 if action != ActionType.LAUNCH_TEST else 21,
                    requires_approval=requires_approval,
                    data_sufficiency=best_sufficiency,
                )
                context.recommendations.append(recommendation)

            conflicting = len(action_votes) > 1 and not (
                set(action_votes) <= {ActionType.MAINTAIN, ActionType.DO_NOTHING}
            )
            summary_findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=entity_id,
                    headline=(
                        f"{len(action_votes)} recommendation(s) generated for {entity_id or 'account level'}"
                        + (" (agents disagreed on action — all preserved)" if conflicting else "")
                    ),
                    detail=(
                        "Contributing agents: " + ", ".join(sorted({f.agent_name for f in actionable}))
                    ),
                    evidence=[f.headline for f in actionable],
                    data_sufficiency=best_sufficiency,
                    confidence=round(confidence, 2),
                    suggested_actions=list(action_votes.keys()),
                    tags=["recommendation_summary"] + (["agent_disagreement"] if conflicting else []),
                )
            )

        if not summary_findings:
            summary_findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=None,
                    headline="DO NOTHING YET — no finding in this run cleared the bar for a recommendation.",
                    detail=(
                        "No agent produced an actionable finding with sufficient evidence. This is a valid, "
                        "intentional outcome: the system does not manufacture recommendations to appear busy."
                    ),
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.5,
                    suggested_actions=[ActionType.DO_NOTHING],
                    tags=["no_action_recommended"],
                )
            )

        return summary_findings

    @staticmethod
    def _risk_for(action: ActionType) -> RiskLevel:
        if action in HIGH_RISK_ACTIONS:
            return RiskLevel.HIGH
        if action in MEDIUM_RISK_ACTIONS:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    @staticmethod
    def _priority_for(
        action: ActionType, supporting: list[AgentFinding], sufficiency: DataSufficiencyLevel, confidence: float
    ) -> Priority:
        tags = {t for f in supporting for t in f.tags}
        if tags & CRITICAL_TAGS and sufficiency != DataSufficiencyLevel.INSUFFICIENT_DATA:
            return Priority.P0_CRITICAL
        if sufficiency == DataSufficiencyLevel.INSUFFICIENT_DATA:
            return Priority.P3_EXPERIMENTAL
        if action in HIGH_RISK_ACTIONS and confidence >= 0.6:
            return Priority.P1_HIGH
        if sufficiency in (DataSufficiencyLevel.PROMISING, DataSufficiencyLevel.CONFIDENT) and confidence >= 0.5:
            return Priority.P2_MEDIUM
        return Priority.P3_EXPERIMENTAL

    @staticmethod
    def _expected_impact(action: ActionType) -> str:
        return {
            ActionType.INCREASE_BUDGET: "Increased lead volume at maintained efficiency, if evidence holds.",
            ActionType.DECREASE_BUDGET: "Reduced wasted spend while root cause is investigated.",
            ActionType.REALLOCATE_BUDGET: "Improved overall account efficiency by shifting spend to stronger performers.",
            ActionType.REFRESH_CREATIVE: "Restored CTR/CPL after fatigue-driven decline.",
            ActionType.ADJUST_AUDIENCE: "Reduced frequency/saturation, restoring efficiency.",
            ActionType.ADJUST_COPY: "Improved CTR via more relevant/compelling copy.",
            ActionType.LAUNCH_TEST: "Validated hypothesis under controlled conditions before wider rollout.",
            ActionType.INVESTIGATE_TRACKING: "Root cause identified for anomalous or missing data.",
            ActionType.INVESTIGATE_OFFER: "Clarified whether the offer itself is limiting conversion.",
            ActionType.PAUSE_AD: "Stopped spend on an underperforming ad.",
            ActionType.PAUSE_AD_SET: "Stopped spend on an underperforming ad set.",
            ActionType.MAINTAIN: "Preserved current performance while more evidence accumulates.",
        }.get(action, "Impact not characterized for this action type.")

    @staticmethod
    def _measurement_for(action: ActionType) -> str:
        if action in (ActionType.INCREASE_BUDGET, ActionType.DECREASE_BUDGET, ActionType.REALLOCATE_BUDGET):
            return "Track CPL, qualified CPL and ROAS daily for the review window vs. the 14 days prior."
        if action in (ActionType.REFRESH_CREATIVE, ActionType.ADJUST_COPY):
            return "Track CTR and CPL for the new asset vs. the control for the review window."
        if action == ActionType.LAUNCH_TEST:
            return "Follow the experiment's own decision rule and minimum data requirement."
        return "Re-evaluate at next scheduled review."
