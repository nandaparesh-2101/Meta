"""Agent 05 — Creative Intelligence.

Analyzes creative-level performance and the qualitative attributes behind
it (hook, visual, format, emotional angle, proof, offer, CTA) to identify
patterns behind winners and losers, and to detect creative fatigue.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot, pct_change
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

FATIGUE_FREQUENCY_THRESHOLD = 3.5
FATIGUE_CTR_DECLINE_THRESHOLD = -0.20


class CreativeIntelligenceAgent(BaseAgent):
    name = "creative_intelligence"
    description = "Analyzes creative performance, patterns behind winners, and fatigue signals."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        ad_performance: list[tuple] = []

        for ad in context.ads:
            insights = sorted(context.insights_for_ad(ad.ad_id), key=lambda i: i.date)
            if not insights:
                continue
            creative = context.creative_for_ad(ad.ad_id)
            days = len({i.date for i in insights})
            snapshot = MetricSnapshot.aggregate(insights)
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.impressions, minimum_days_required=5, minimum_sample_required=2000
            )

            tags: list[str] = []
            notes: list[str] = []
            actions: list[ActionType] = []

            half = len(insights) // 2
            ctr_change = None
            if half >= 2:
                first_half = MetricSnapshot.aggregate(insights[:half])
                second_half = MetricSnapshot.aggregate(insights[half:])
                ctr_change = pct_change(first_half.ctr, second_half.ctr)

            is_fatigued = (
                snapshot.frequency is not None and snapshot.frequency >= FATIGUE_FREQUENCY_THRESHOLD
            ) or (ctr_change is not None and ctr_change <= FATIGUE_CTR_DECLINE_THRESHOLD)

            if is_fatigued:
                tags.append("creative_fatigue")
                actions.append(ActionType.REFRESH_CREATIVE)
                notes.append(
                    f"Ad '{ad.name}' shows fatigue signals (frequency={self._fmt(snapshot.frequency)}, "
                    f"CTR trend={self._fmt_pct(ctr_change)}); refresh the creative before scaling further."
                )

            evidence = [
                f"Ad '{ad.name}': CTR={self._fmt_pct(snapshot.ctr)}, frequency={self._fmt(snapshot.frequency)}, "
                f"CPL={self._fmt(snapshot.cpl)}",
            ]
            if creative:
                evidence.append(
                    f"Creative: format={creative.format.value}, hook='{creative.hook}', "
                    f"angle='{creative.emotional_angle}'"
                )
                ad_performance.append((ad, creative, snapshot))

            if not notes:
                notes.append(f"Ad '{ad.name}' shows no fatigue signal at current frequency/CTR trend.")
                actions = [ActionType.DO_NOTHING]

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=ad.ad_id,
                    headline=notes[0],
                    detail=" ".join(notes),
                    evidence=evidence,
                    data_sufficiency=sufficiency.level,
                    confidence=0.75 if tags else 0.5,
                    suggested_actions=actions,
                    tags=tags,
                )
            )

        if len(ad_performance) >= 2:
            findings.append(self._winning_pattern_finding(ad_performance))

        return findings

    def _winning_pattern_finding(self, ad_performance: list[tuple]) -> AgentFinding:
        from app.models.metrics import DataSufficiencyLevel

        ranked = sorted(
            (t for t in ad_performance if t[2].cpl is not None), key=lambda t: t[2].cpl
        )
        if not ranked:
            return AgentFinding(
                agent_name=self.name,
                entity_id=None,
                headline="No ads with calculable CPL to compare creative patterns.",
                detail="Insufficient lead data across ads.",
                evidence=[],
                data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.2,
                suggested_actions=[],
                tags=[],
            )
        top = ranked[: max(1, len(ranked) // 3)]
        angles = [c.emotional_angle for _, c, _ in top]
        formats = [c.format.value for _, c, _ in top]
        common_angle = max(set(angles), key=angles.count) if angles else None
        common_format = max(set(formats), key=formats.count) if formats else None

        evidence = [f"{ad.name}: CPL={s.cpl:.2f}, angle='{c.emotional_angle}', format={c.format.value}" for ad, c, s in top]

        return AgentFinding(
            agent_name=self.name,
            entity_id=None,
            headline=(
                f"Top-performing creatives skew toward '{common_angle}' angle and '{common_format}' format."
                if common_angle
                else "No consistent pattern found among top-performing creatives yet."
            ),
            detail=(
                "Pattern derived from the top third of ads ranked by CPL. Treat as a hypothesis for "
                "the Experimentation agent, not a proven rule."
            ),
            evidence=evidence,
            data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL if len(ranked) < 6 else DataSufficiencyLevel.PROMISING,
            confidence=0.55,
            suggested_actions=[],
            tags=["creative_pattern"],
        )

    @staticmethod
    def _fmt(v):
        return f"{v:.2f}" if v is not None else "N/A"

    @staticmethod
    def _fmt_pct(v):
        return f"{v:.2%}" if v is not None else "N/A"
