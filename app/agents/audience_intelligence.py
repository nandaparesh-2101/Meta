"""Agent 04 — Audience Intelligence.

Analyzes audience definitions (broad/interest/lookalike/custom/retargeting)
plus frequency as a saturation/fatigue proxy. Explicitly does NOT assume
narrow targeting outperforms broad — it lets the data decide.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

FREQUENCY_SATURATION_THRESHOLD = 4.0


class AudienceIntelligenceAgent(BaseAgent):
    name = "audience_intelligence"
    description = "Analyzes audience type, saturation, overlap and fatigue signals."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        performance_by_type: dict[str, list[MetricSnapshot]] = {}

        for ad_set in context.ad_sets:
            insights = context.insights_for_ad_set(ad_set.ad_set_id)
            if not insights:
                continue
            days = len({i.date for i in insights})
            snapshot = MetricSnapshot.aggregate(insights)
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.leads, minimum_days_required=7, minimum_sample_required=30
            )

            performance_by_type.setdefault(ad_set.audience.audience_type.value, []).append(snapshot)

            tags: list[str] = []
            notes: list[str] = []
            actions: list[ActionType] = []

            if snapshot.frequency is not None and snapshot.frequency >= FREQUENCY_SATURATION_THRESHOLD:
                notes.append(
                    f"Frequency is {snapshot.frequency:.1f} — audience is likely saturated/fatigued; "
                    "the same people are seeing this ad repeatedly."
                )
                tags.append("audience_saturation")
                actions.append(ActionType.ADJUST_AUDIENCE)

            evidence = [
                f"Ad set '{ad_set.name}' ({ad_set.audience.audience_type.value}): "
                f"frequency={self._fmt(snapshot.frequency)}, CPL={self._fmt(snapshot.cpl)}, "
                f"CTR={self._fmt_pct(snapshot.ctr)}",
            ]

            if not notes:
                notes.append(f"Audience '{ad_set.name}' ({ad_set.audience.audience_type.value}) shows no saturation signal.")
                actions = [ActionType.DO_NOTHING]

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=ad_set.ad_set_id,
                    headline=notes[0],
                    detail=" ".join(notes),
                    evidence=evidence,
                    data_sufficiency=sufficiency.level,
                    confidence=0.7 if tags else 0.5,
                    suggested_actions=actions,
                    tags=tags,
                )
            )

        if performance_by_type:
            findings.append(self._audience_type_comparison(performance_by_type))

        return findings

    def _audience_type_comparison(self, performance_by_type: dict[str, list[MetricSnapshot]]) -> AgentFinding:
        from app.models.metrics import DataSufficiencyLevel

        rows = []
        for audience_type, snapshots in performance_by_type.items():
            combined_leads = sum(s.leads for s in snapshots)
            combined_spend = sum(s.spend for s in snapshots)
            cpl = combined_spend / combined_leads if combined_leads else None
            rows.append((audience_type, cpl, combined_leads))
        rows.sort(key=lambda r: (r[1] is None, r[1]))

        evidence = [
            f"{audience_type}: CPL={self._fmt(cpl)} across {leads} lead(s)"
            for audience_type, cpl, leads in rows
        ]
        best = rows[0][0] if rows and rows[0][1] is not None else None

        return AgentFinding(
            agent_name=self.name,
            entity_id=None,
            headline=(
                f"'{best}' audiences currently show the strongest CPL efficiency."
                if best
                else "Insufficient calculable CPL data across audience types to compare."
            ),
            detail=(
                "Comparison is descriptive, not prescriptive — narrow targeting is not assumed superior; "
                "broad audiences with strong CPL should not be narrowed just because they are broad."
            ),
            evidence=evidence,
            data_sufficiency=DataSufficiencyLevel.PROMISING,
            confidence=0.6,
            suggested_actions=[],
            tags=["audience_comparison"],
        )

    @staticmethod
    def _fmt(v):
        return f"{v:.2f}" if v is not None else "N/A"

    @staticmethod
    def _fmt_pct(v):
        return f"{v:.2%}" if v is not None else "N/A"
