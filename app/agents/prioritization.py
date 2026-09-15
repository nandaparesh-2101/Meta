"""Agents 66-68 and 70 — Production Prioritization, Experiment Portfolio,
Exploration/Exploitation, and Executive Strategy.

`ExecutiveStrategyAgent` is the capstone: it reads `context.recommendations`
and `context.guardian_decisions` (populated by the orchestrator after
Guardian runs) and turns them into a NOW/NEXT/LATER plan — it performs no
analysis of its own, only synthesis of what every other agent already
produced and Guardian already cleared.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.execution import GuardianVerdict
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import (
    ActionType,
    AgentFinding,
    EvidenceSource,
    FindingStatus,
    Priority,
)
from app.orchestration.context import AgentContext

MAX_CONCURRENT_EXPERIMENTS = 5


class CreativeProductionPrioritizerAgent(BaseAgent):
    name = "creative_production_prioritizer"
    description = "Ranks generated creative concepts by expected impact, evidence, novelty, and ease of testing."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        generated = [f for f in context.findings if "generated_content" in f.tags]
        if not generated:
            return [
                AgentFinding(
                    agent_name=self.name, headline="No generated concepts to prioritize this run.", detail="",
                    evidence=[], data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA, confidence=0.0,
                    suggested_actions=[], tags=["no_content_to_prioritize"], status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        opportunity_findings = context.findings_by_agent("opportunity_discovery")
        business_importance_boost = bool(opportunity_findings and opportunity_findings[0].payload.get("opportunities"))

        scored = []
        for f in generated:
            evidence_score = min(len(f.evidence), 5)
            novelty_score = 3 if "hook_engine" in f.agent_name or "content_angle" in f.tags else 2
            importance_score = 2 if business_importance_boost else 1
            total = evidence_score + novelty_score + importance_score + round(f.confidence * 3)
            scored.append({"agent": f.agent_name, "score": total, "headline": f.headline})

        scored.sort(key=lambda s: s["score"], reverse=True)

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Ranked {len(scored)} creative concept batch(es) into a production queue.",
                detail="Score = evidence volume + novelty + business-relevance + agent confidence. A prioritization tool, not a performance guarantee.",
                evidence=[f"#{i + 1} {s['agent']} (score={s['score']}): {s['headline']}" for i, s in enumerate(scored)],
                data_sufficiency=DataSufficiencyLevel.PROMISING,
                confidence=0.4,
                suggested_actions=[ActionType.GENERATE_CREATIVE_CONCEPT],
                tags=["production_priority_queue"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.MODEL_INFERENCE],
                payload={"ranked_queue": scored},
            )
        ]


class ExperimentPortfolioAgent(BaseAgent):
    name = "experiment_portfolio"
    description = "Manages experiments as a portfolio — prevents too many simultaneous tests running at once."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        active = [e for e in context.existing_experiments if e.status.value in ("planned", "running")]
        total_after_this_run = len(active) + len(context.new_experiments)
        overloaded = total_after_this_run > MAX_CONCURRENT_EXPERIMENTS

        by_variable: dict[str, int] = {}
        for e in active + context.new_experiments:
            by_variable[e.variable] = by_variable.get(e.variable, 0) + 1

        return [
            AgentFinding(
                agent_name=self.name,
                headline=(
                    f"Experiment portfolio: {total_after_this_run} active/proposed experiment(s) "
                    f"({'OVER the concurrency limit' if overloaded else 'within concurrency limit'} of {MAX_CONCURRENT_EXPERIMENTS})"
                ),
                detail=(
                    f"Distribution by variable: {by_variable}. "
                    + ("Recommend deferring lower-priority new experiments until some active ones conclude."
                       if overloaded else "Portfolio has room for additional controlled tests.")
                ),
                evidence=[f"{len(active)} active + {len(context.new_experiments)} proposed this run"],
                data_sufficiency=DataSufficiencyLevel.CONFIDENT,
                confidence=0.6,
                suggested_actions=[ActionType.MAINTAIN] if overloaded else [ActionType.DO_NOTHING],
                tags=["experiment_portfolio"] + (["portfolio_overloaded"] if overloaded else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.EXPERIMENT_HISTORY],
                payload={"active_count": len(active), "proposed_count": len(context.new_experiments), "by_variable": by_variable},
            )
        ]


class ExplorationExploitationAgent(BaseAgent):
    name = "exploration_exploitation"
    description = "Balances scaling proven winners (exploit) against testing new possibilities (explore); flags over-dependence on few creatives."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        exploit_actions = {ActionType.INCREASE_BUDGET, ActionType.MAINTAIN}
        explore_actions = {ActionType.LAUNCH_TEST, ActionType.GENERATE_CREATIVE_CONCEPT}

        exploit_count = sum(1 for r in context.recommendations if r.action in exploit_actions)
        explore_count = sum(1 for r in context.recommendations if r.action in explore_actions)

        active_creatives = [c for c in context.creatives if c.is_active]
        total_budget = sum(c.daily_budget for c in context.campaigns) or 1
        max_campaign_budget = max((c.daily_budget for c in context.campaigns), default=0)
        concentration = max_campaign_budget / total_budget if total_budget else 0

        over_dependent = len(active_creatives) <= 2 or concentration > 0.6

        return [
            AgentFinding(
                agent_name=self.name,
                headline=(
                    f"Exploit/explore split: {exploit_count} exploit-leaning, {explore_count} explore-leaning recommendation(s). "
                    + ("Concentration risk detected." if over_dependent else "Healthy balance.")
                ),
                detail=(
                    f"{len(active_creatives)} active creative(s); largest single campaign holds {concentration:.0%} of total budget. "
                    + ("The account risks depending on a small number of creatives/campaigns — recommend allocating "
                       "at least some budget to exploration even while winners are being scaled." if over_dependent else "")
                ),
                evidence=[f"active_creatives={len(active_creatives)}, budget_concentration={concentration:.0%}"],
                data_sufficiency=DataSufficiencyLevel.PROMISING if context.creatives else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.45,
                suggested_actions=[ActionType.LAUNCH_TEST, ActionType.DIVERSIFY_CREATIVE] if over_dependent else [ActionType.DO_NOTHING],
                tags=["exploration_exploitation"] + (["creative_concentration_risk"] if over_dependent else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
            )
        ]


class ExecutiveStrategyAgent(BaseAgent):
    name = "executive_strategy"
    description = "Synthesizes cleared recommendations into a NOW / NEXT / LATER strategic plan. Performs no new analysis."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        decisions_by_rec = {d.recommendation_id: d for d in context.guardian_decisions}
        cleared = [
            r for r in context.recommendations
            if decisions_by_rec.get(r.recommendation_id) is None
            or decisions_by_rec[r.recommendation_id].verdict != GuardianVerdict.REJECT
        ]

        now = [r for r in cleared if r.priority in (Priority.P0_CRITICAL, Priority.P1_HIGH)]
        next_ = [r for r in cleared if r.priority == Priority.P2_MEDIUM]
        later = [r for r in cleared if r.priority == Priority.P3_EXPERIMENTAL]

        if not cleared:
            headline = "DO NOTHING YET — no Guardian-cleared recommendation exists to build a strategic plan from."
        else:
            headline = f"Strategic plan: {len(now)} NOW, {len(next_)} NEXT, {len(later)} LATER item(s)."

        return [
            AgentFinding(
                agent_name=self.name,
                headline=headline,
                detail=(
                    "NOW = highest-impact, Guardian-cleared actions. NEXT = important experiments/medium-confidence "
                    "moves. LATER = longer-term/exploratory opportunities. Guardian-rejected recommendations are "
                    "excluded entirely, never silently included."
                ),
                evidence=[f"NOW: {[r.action.value + '@' + r.entity_id for r in now]}",
                          f"NEXT: {[r.action.value + '@' + r.entity_id for r in next_]}",
                          f"LATER: {[r.action.value + '@' + r.entity_id for r in later]}"],
                data_sufficiency=DataSufficiencyLevel.PROMISING if cleared else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.5 if cleared else 0.2,
                suggested_actions=[ActionType.DO_NOTHING] if not cleared else [],
                tags=["executive_strategy"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={
                    "now": [r.recommendation_id for r in now],
                    "next": [r.recommendation_id for r in next_],
                    "later": [r.recommendation_id for r in later],
                },
            )
        ]
