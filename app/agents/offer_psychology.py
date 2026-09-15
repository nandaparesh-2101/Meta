"""Agent 07 — Offer & Psychology.

Determines whether poor performance likely originates from the offer
itself (pricing, risk, trust, differentiation) rather than the ad creative
or targeting. Key signal: good top-of-funnel metrics (CTR, CPL) combined
with poor bottom-of-funnel metrics (qualified rate, close rate) — that
divergence points at the offer, not the ad.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency
from app.rules.kpi_rules import KPIStatus, evaluate_cpl, evaluate_qualified_cpl

GOOD_CTR_THRESHOLD = 0.015


class OfferPsychologyAgent(BaseAgent):
    name = "offer_psychology"
    description = "Determines whether poor performance originates from the offer rather than the ad."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        kpis = context.business_objective.kpis

        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if not insights:
                continue
            days = len({i.date for i in insights})
            snapshot = MetricSnapshot.aggregate(insights)
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.leads, minimum_days_required=7, minimum_sample_required=30
            )

            cpl_status = evaluate_cpl(snapshot.cpl, kpis)
            qcpl_status = evaluate_qualified_cpl(snapshot.qualified_cpl, kpis)

            good_top_funnel = (
                snapshot.ctr is not None and snapshot.ctr >= GOOD_CTR_THRESHOLD
                and cpl_status in (KPIStatus.ON_TARGET, KPIStatus.BORDERLINE)
            )
            poor_bottom_funnel = qcpl_status == KPIStatus.OFF_TARGET or (
                snapshot.qualified_rate is not None and snapshot.qualified_rate < 0.2
            )

            tags: list[str] = []
            actions: list[ActionType] = []
            if good_top_funnel and poor_bottom_funnel and snapshot.qualified_leads is not None:
                notes = (
                    f"Campaign '{campaign.name}' has strong CTR ({self._fmt_pct(snapshot.ctr)}) and CPL "
                    f"({cpl_status.value}), but qualified rate is only {self._fmt_pct(snapshot.qualified_rate)} "
                    "and qualified CPL is off target. This divergence points at the offer/pricing/trust, "
                    "not the ad — cheap attention is being generated but it isn't converting into qualified interest."
                )
                tags.append("offer_risk")
                actions.append(ActionType.INVESTIGATE_OFFER)
            else:
                notes = f"Campaign '{campaign.name}' shows no clear top-vs-bottom-funnel divergence suggesting an offer problem."
                actions = [ActionType.DO_NOTHING]

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=notes.split(".")[0] + ".",
                    detail=notes,
                    evidence=[
                        f"CTR={self._fmt_pct(snapshot.ctr)}, CPL status={cpl_status.value}, "
                        f"qualified rate={self._fmt_pct(snapshot.qualified_rate)}, qualified CPL status={qcpl_status.value}"
                    ],
                    data_sufficiency=sufficiency.level,
                    confidence=0.6 if tags else 0.4,
                    suggested_actions=actions,
                    tags=tags,
                )
            )

        return findings

    @staticmethod
    def _fmt_pct(v):
        return f"{v:.2%}" if v is not None else "N/A"
