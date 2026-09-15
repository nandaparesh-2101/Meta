"""Agent 06 — Copy Intelligence.

Analyzes on-ad copy elements (primary text, headline, CTA) and generates
testable copy variations. Every variation this agent proposes carries an
explicit hypothesis — no "just try a different headline" without a reason.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

WEAK_CTR_PERCENTILE_CUTOFF = 0.34  # bottom third


class CopyIntelligenceAgent(BaseAgent):
    name = "copy_intelligence"
    description = "Analyzes ad copy elements and proposes hypothesis-driven copy test variations."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        ad_ctrs: list[tuple[str, float]] = []

        for ad in context.ads:
            insights = context.insights_for_ad(ad.ad_id)
            if not insights:
                continue
            snapshot = MetricSnapshot.aggregate(insights)
            if snapshot.ctr is not None:
                ad_ctrs.append((ad.ad_id, snapshot.ctr))

        if not ad_ctrs:
            return findings

        ad_ctrs.sort(key=lambda t: t[1])
        cutoff_index = max(1, int(len(ad_ctrs) * WEAK_CTR_PERCENTILE_CUTOFF))
        weak_ad_ids = {ad_id for ad_id, _ in ad_ctrs[:cutoff_index]}

        for ad in context.ads:
            if ad.ad_id not in weak_ad_ids:
                continue
            creative = context.creative_for_ad(ad.ad_id)
            if creative is None:
                continue
            insights = context.insights_for_ad(ad.ad_id)
            days = len({i.date for i in insights})
            snapshot = MetricSnapshot.aggregate(insights)
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.impressions, minimum_days_required=5, minimum_sample_required=2000
            )

            variations = self._propose_variations(creative)

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=ad.ad_id,
                    headline=f"Ad '{ad.name}' has bottom-tier CTR ({snapshot.ctr:.2%}) — copy variation test proposed.",
                    detail=(
                        "Current headline/primary text may not be the driver of low CTR (creative/audience "
                        "could also be responsible), but copy is the cheapest lever to test first. "
                        f"Proposed variations: {'; '.join(v['hypothesis'] for v in variations)}"
                    ),
                    evidence=[
                        f"Current headline: '{creative.headline}'",
                        f"Current primary text: '{creative.primary_text[:120]}'",
                        f"CTR={snapshot.ctr:.2%} (bottom {WEAK_CTR_PERCENTILE_CUTOFF:.0%} of ads in this run)",
                    ],
                    data_sufficiency=sufficiency.level,
                    confidence=0.55,
                    suggested_actions=[ActionType.ADJUST_COPY, ActionType.LAUNCH_TEST],
                    tags=["copy_test_candidate"],
                )
            )

        return findings

    @staticmethod
    def _propose_variations(creative) -> list[dict]:
        variations = []
        if creative.problem_stated is None:
            variations.append(
                {
                    "hypothesis": "Leading with a stated problem before the offer will improve relevance and CTR",
                    "headline": f"Struggling with {creative.emotional_angle}?",
                }
            )
        if "?" not in creative.headline:
            variations.append(
                {
                    "hypothesis": "A question-format headline increases pattern interrupt and CTR",
                    "headline": creative.headline.rstrip(".") + "?",
                }
            )
        if not creative.proof_elements:
            variations.append(
                {
                    "hypothesis": "Adding a proof element (stat/testimonial) to primary text improves trust and CTR",
                    "primary_text_addition": "Add a customer result or stat in the first two lines.",
                }
            )
        if not variations:
            variations.append(
                {
                    "hypothesis": "Shortening the primary text to lead with the strongest benefit improves CTR",
                }
            )
        return variations
