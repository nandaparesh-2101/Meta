"""Agent 13 — Attribution.

Connects Ads -> Leads -> Qualified Leads -> Sales -> Revenue and reports the
actual business contribution of each campaign where data exists. Flags
entities where the attribution chain is broken (e.g. sales exist with no
traceable lead, or leads have no downstream outcome recorded at all).
"""

from __future__ import annotations

from collections import defaultdict

from app.agents.base import BaseAgent
from app.models.leads import FunnelStage
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext


class AttributionAgent(BaseAgent):
    name = "attribution"
    description = "Connects ads to leads, qualified leads, sales and revenue where data exists."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        leads_by_campaign: dict[str, list] = defaultdict(list)
        for lead in context.leads:
            leads_by_campaign[lead.campaign_id].append(lead)
        sales_by_campaign: dict[str, list] = defaultdict(list)
        for sale in context.sales:
            sales_by_campaign[sale.campaign_id].append(sale)

        known_lead_ids = {lead.lead_id for lead in context.leads}

        for campaign in context.campaigns:
            leads = leads_by_campaign.get(campaign.campaign_id, [])
            sales = sales_by_campaign.get(campaign.campaign_id, [])

            orphan_sales = [s for s in sales if s.lead_id not in known_lead_ids]
            revenue_total = sum(s.amount for s in sales)
            sale_lead_ids = {s.lead_id for s in sales}
            leads_never_advanced = [
                l for l in leads if l.stage == FunnelStage.LEAD and l.lead_id not in sale_lead_ids
            ]

            concerns: list[str] = []
            tags: list[str] = []
            if orphan_sales:
                concerns.append(
                    f"{len(orphan_sales)} sale(s) reference a lead_id not present in lead data — "
                    "attribution chain is broken for these sales."
                )
                tags.append("tracking_anomaly")

            if not leads and sales:
                concerns.append("Sales recorded with zero leads tracked for this campaign — attribution gap.")
                tags.append("tracking_anomaly")

            evidence = [
                f"{len(leads)} lead(s), {len(sales)} sale(s), revenue={revenue_total:.2f}",
            ]
            if leads:
                stalled_pct = len(leads_never_advanced) / len(leads)
                evidence.append(f"{stalled_pct:.0%} of leads never advanced past initial stage")

            headline = (
                f"Campaign '{campaign.name}': {len(sales)} sale(s) attributed, revenue={revenue_total:.2f}"
                if not concerns
                else f"Campaign '{campaign.name}': attribution chain has gaps"
            )

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=headline,
                    detail=" ".join(concerns) if concerns else "Attribution chain from lead to revenue is intact for all traceable sales.",
                    evidence=evidence,
                    data_sufficiency=DataSufficiencyLevel.CONFIDENT if (leads or sales) else DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.8 if not concerns else 0.5,
                    suggested_actions=[ActionType.INVESTIGATE_TRACKING] if concerns else [ActionType.DO_NOTHING],
                    tags=tags,
                )
            )

        return findings
