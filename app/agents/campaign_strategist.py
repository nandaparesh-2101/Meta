"""Agent 03 — Campaign Strategist.

Analyzes campaign/ad-set structure: budget distribution, fragmentation, and
consolidation vs. testing-structure opportunities. Recommendations are
structural, not creative or audience-level (those belong to other agents).
"""

from __future__ import annotations

from collections import defaultdict

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

MIN_VIABLE_DAILY_BUDGET_PER_ADSET = 20.0
FRAGMENTATION_ADSET_COUNT_THRESHOLD = 5


class CampaignStrategistAgent(BaseAgent):
    name = "campaign_strategist"
    description = "Analyzes campaign/ad-set structure, budget distribution and fragmentation."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []

        ad_sets_by_campaign: dict[str, list] = defaultdict(list)
        for ad_set in context.ad_sets:
            ad_sets_by_campaign[ad_set.campaign_id].append(ad_set)

        for campaign in context.campaigns:
            ad_sets = ad_sets_by_campaign.get(campaign.campaign_id, [])
            if not ad_sets:
                continue

            total_budget = sum(a.daily_budget for a in ad_sets)
            underfunded = [a for a in ad_sets if a.daily_budget < MIN_VIABLE_DAILY_BUDGET_PER_ADSET]
            evidence = [
                f"Campaign '{campaign.name}' has {len(ad_sets)} ad set(s), total daily budget={total_budget:.2f}",
            ]
            tags: list[str] = []
            actions: list[ActionType] = []
            notes: list[str] = []

            if len(ad_sets) >= FRAGMENTATION_ADSET_COUNT_THRESHOLD and underfunded:
                notes.append(
                    f"{len(underfunded)}/{len(ad_sets)} ad set(s) are below the "
                    f"{MIN_VIABLE_DAILY_BUDGET_PER_ADSET:.0f}/day viability floor — budget is fragmented "
                    "thin enough that Meta's delivery system cannot exit learning phase efficiently."
                )
                tags.append("fragmentation")
                actions.append(ActionType.REALLOCATE_BUDGET)
                evidence.append(
                    "Underfunded ad sets: " + ", ".join(f"{a.name} ({a.daily_budget:.2f}/day)" for a in underfunded)
                )

            campaign_insights = context.insights_for_campaign(campaign.campaign_id)
            days = len({i.date for i in campaign_insights})
            snapshot = MetricSnapshot.aggregate(campaign_insights)
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.leads, minimum_days_required=7, minimum_sample_required=30
            )

            # Consolidation signal: many ad sets targeting overlapping broad
            # audiences with similar performance suggest testing structure
            # has run its course and consolidation would reduce overhead.
            if len(ad_sets) >= FRAGMENTATION_ADSET_COUNT_THRESHOLD and not underfunded:
                notes.append(
                    f"{len(ad_sets)} ad sets are each adequately funded; if performance is "
                    "converging across them, consider consolidating for delivery efficiency "
                    "rather than adding more variants."
                )
                actions.append(ActionType.MAINTAIN)

            if not notes:
                notes.append("Campaign structure looks reasonable for its current spend level.")
                actions = [ActionType.DO_NOTHING]

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=f"Campaign '{campaign.name}' structure: " + notes[0],
                    detail=" ".join(notes),
                    evidence=evidence,
                    data_sufficiency=sufficiency.level,
                    confidence=0.65 if tags else 0.5,
                    suggested_actions=actions or [ActionType.DO_NOTHING],
                    tags=tags,
                )
            )

        return findings
