"""Agent 09 — Funnel Diagnostics.

Walks Ad -> Click -> Landing Page -> Form -> Lead -> Contact -> Qualified ->
Sale and identifies the single weakest conversion step (the bottleneck),
then maps that step to plausible root-cause categories.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

# Each step: (label, rate_attr_on_snapshot, plausible root causes)
STEP_CAUSES = {
    "click_to_landing_page": ["landing page load speed", "tracking/pixel issue", "ad-to-page mismatch"],
    "landing_page_to_lead": ["landing page", "form friction", "offer clarity", "trust signals"],
    "lead_to_qualified": ["lead response time", "sales process", "offer/audience mismatch", "lead quality"],
}


class FunnelDiagnosticsAgent(BaseAgent):
    name = "funnel_diagnostics"
    description = "Identifies the weakest funnel step and maps it to plausible root causes."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []

        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if not insights:
                continue
            days = len({i.date for i in insights})
            snapshot = MetricSnapshot.aggregate(insights)
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.clicks, minimum_days_required=7, minimum_sample_required=200
            )

            steps = {
                "click_to_landing_page": snapshot.landing_page_views / snapshot.clicks if snapshot.clicks else None,
                "landing_page_to_lead": snapshot.landing_page_conversion_rate,
                "lead_to_qualified": snapshot.qualified_rate,
            }
            calculable = {k: v for k, v in steps.items() if v is not None}

            if not calculable:
                findings.append(
                    AgentFinding(
                        agent_name=self.name,
                        entity_id=campaign.campaign_id,
                        headline=f"Campaign '{campaign.name}': not enough funnel data to diagnose a bottleneck.",
                        detail="Missing landing page, lead, or qualification data prevents step-by-step analysis.",
                        evidence=[],
                        data_sufficiency=sufficiency.level,
                        confidence=0.2,
                        suggested_actions=[ActionType.INVESTIGATE_TRACKING],
                        tags=["missing_funnel_data"],
                    )
                )
                continue

            weakest_step = min(calculable, key=calculable.get)
            weakest_rate = calculable[weakest_step]
            causes = STEP_CAUSES[weakest_step]

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=(
                        f"Campaign '{campaign.name}' bottleneck: {weakest_step.replace('_', ' ')} "
                        f"({weakest_rate:.1%})"
                    ),
                    detail=(
                        f"Of the measurable funnel steps, '{weakest_step.replace('_', ' ')}' converts worst "
                        f"at {weakest_rate:.1%}. Plausible root causes to investigate: {', '.join(causes)}."
                    ),
                    evidence=[f"{k.replace('_', ' ')}: {v:.1%}" for k, v in calculable.items()],
                    data_sufficiency=sufficiency.level,
                    confidence=0.6,
                    suggested_actions=[ActionType.INVESTIGATE_TRACKING] if weakest_rate < 0.05 else [],
                    tags=[f"bottleneck:{weakest_step}"],
                )
            )

        return findings
