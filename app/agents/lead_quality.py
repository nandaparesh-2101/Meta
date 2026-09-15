"""Agent 08 — Lead Quality.

Walks the funnel: Lead -> Contacted -> Qualified -> Appointment -> Opportunity
-> Sale -> Revenue. Prioritizes business value (revenue per lead, cost per
qualified lead) over raw lead volume/cheap CPL.
"""

from __future__ import annotations

from collections import defaultdict

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.leads import FunnelStage
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

CHEAP_BUT_LOW_QUALITY_RATE = 0.15


class LeadQualityAgent(BaseAgent):
    name = "lead_quality"
    description = "Analyzes the lead-to-revenue funnel and prioritizes business value over cheap leads."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        leads_by_campaign: dict[str, list] = defaultdict(list)
        for lead in context.leads:
            leads_by_campaign[lead.campaign_id].append(lead)

        for campaign in context.campaigns:
            leads = leads_by_campaign.get(campaign.campaign_id, [])
            insights = context.insights_for_campaign(campaign.campaign_id)
            if not leads and not insights:
                continue

            snapshot = MetricSnapshot.aggregate(insights)
            days = len({i.date for i in insights})
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=len(leads), minimum_days_required=7, minimum_sample_required=30
            )

            stage_counts = {stage: 0 for stage in FunnelStage}
            for lead in leads:
                stage_counts[lead.stage] += 1
            total_leads = len(leads) or snapshot.leads
            qualified_count = sum(stage_counts[s] for s in FunnelStage if s.order >= FunnelStage.QUALIFIED.order)
            qualified_rate = (qualified_count / total_leads) if total_leads else None

            tags: list[str] = []
            actions: list[ActionType] = []
            notes: list[str] = []

            cheap_cpl = snapshot.cpl is not None and snapshot.cpl < context.business_objective.kpis.target_cpl * 0.7
            if cheap_cpl and qualified_rate is not None and qualified_rate < CHEAP_BUT_LOW_QUALITY_RATE:
                notes.append(
                    f"CPL is cheap ({snapshot.cpl:.2f}) but only {qualified_rate:.0%} of leads qualify — "
                    "this campaign is generating volume, not business value. Do not scale on CPL alone."
                )
                tags.append("cheap_low_quality_leads")
                actions.append(ActionType.INVESTIGATE_OFFER)

            if snapshot.revenue_per_lead is not None:
                notes.append(f"Revenue per lead: {snapshot.revenue_per_lead:.2f}.")

            if not notes:
                notes.append("No cheap-but-low-quality-lead pattern detected for this campaign.")
                actions = [ActionType.DO_NOTHING]

            evidence = [
                f"Total leads={total_leads}, qualified={qualified_count} ({self._fmt_pct(qualified_rate)})",
                f"CPL={self._fmt(snapshot.cpl)}, qualified CPL={self._fmt(snapshot.qualified_cpl)}, "
                f"CAC={self._fmt(snapshot.cac)}, revenue/lead={self._fmt(snapshot.revenue_per_lead)}",
            ]

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=notes[0],
                    detail=" ".join(notes),
                    evidence=evidence,
                    data_sufficiency=sufficiency.level,
                    confidence=0.7 if tags else 0.5,
                    suggested_actions=actions,
                    tags=tags,
                )
            )

        return findings

    @staticmethod
    def _fmt(v):
        return f"{v:.2f}" if v is not None else "N/A"

    @staticmethod
    def _fmt_pct(v):
        return f"{v:.0%}" if v is not None else "N/A"
