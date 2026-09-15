"""Agent 02 — Data Analyst.

Analyzes raw performance trends per campaign: winners, losers, outliers,
anomalies, and missing data. Never invents a value for a metric it cannot
compute — a `None` result is reported as "not calculable", not zero.
"""

from __future__ import annotations

from collections import defaultdict

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot, pct_change
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

TREND_SIGNIFICANCE_THRESHOLD = 0.15  # 15% move is worth flagging


class DataAnalystAgent(BaseAgent):
    name = "data_analyst"
    description = "Analyzes spend, funnel and efficiency metrics for trends, winners, losers and anomalies."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        by_campaign: dict[str, list] = defaultdict(list)
        for insight in context.insights:
            by_campaign[insight.campaign_id].append(insight)

        campaign_snapshots: dict[str, MetricSnapshot] = {}

        for campaign_id, insights in by_campaign.items():
            insights_sorted = sorted(insights, key=lambda i: i.date)
            days = len({i.date for i in insights_sorted})
            snapshot = MetricSnapshot.aggregate(insights_sorted)
            campaign_snapshots[campaign_id] = snapshot

            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.leads, minimum_days_required=7, minimum_sample_required=30
            )

            evidence = [
                f"{days} day(s) of data, spend={snapshot.spend:.2f}, leads={snapshot.leads}",
                f"CTR={self._fmt_pct(snapshot.ctr)}, CPL={self._fmt_money(snapshot.cpl)}, "
                f"ROAS={self._fmt_ratio(snapshot.roas)}",
            ]

            # Trend: compare first half vs second half of the window.
            half = len(insights_sorted) // 2
            trend_tags: list[str] = []
            trend_notes: list[str] = []
            if half >= 2:
                first_half = MetricSnapshot.aggregate(insights_sorted[:half])
                second_half = MetricSnapshot.aggregate(insights_sorted[half:])
                cpl_change = pct_change(first_half.cpl, second_half.cpl)
                ctr_change = pct_change(first_half.ctr, second_half.ctr)
                if cpl_change is not None and abs(cpl_change) >= TREND_SIGNIFICANCE_THRESHOLD:
                    direction = "increased" if cpl_change > 0 else "decreased"
                    trend_notes.append(f"CPL {direction} {abs(cpl_change):.0%} from first half to second half.")
                    trend_tags.append("cpl_increase" if cpl_change > 0 else "cpl_decrease")
                if ctr_change is not None and abs(ctr_change) >= TREND_SIGNIFICANCE_THRESHOLD:
                    direction = "increased" if ctr_change > 0 else "decreased"
                    trend_notes.append(f"CTR {direction} {abs(ctr_change):.0%} from first half to second half.")
                    trend_tags.append("ctr_increase" if ctr_change > 0 else "ctr_decrease")

            # Anomaly detection: values that shouldn't be possible / are suspicious.
            anomalies = self._detect_anomalies(insights_sorted, snapshot)

            missing_data_notes = self._detect_missing_data(insights_sorted)

            tags = trend_tags + (["tracking_anomaly"] if anomalies else []) + (["missing_data"] if missing_data_notes else [])
            confidence = 0.85 if sufficiency.allows_strong_recommendation else 0.4

            headline = f"Campaign {campaign_id}: " + (
                "; ".join(trend_notes) if trend_notes else "no significant trend detected"
            )

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign_id,
                    headline=headline,
                    detail=(
                        f"Aggregated over {days} day(s). "
                        + (" ".join(trend_notes) if trend_notes else "Metrics are stable within threshold.")
                        + (f" Anomalies: {'; '.join(anomalies)}." if anomalies else "")
                        + (f" Missing data: {'; '.join(missing_data_notes)}." if missing_data_notes else "")
                    ),
                    evidence=evidence + anomalies + missing_data_notes,
                    data_sufficiency=sufficiency.level,
                    confidence=confidence,
                    suggested_actions=[ActionType.DO_NOTHING] if not trend_tags and not anomalies else [],
                    tags=tags,
                )
            )

        if campaign_snapshots:
            findings.append(self._winners_losers_finding(campaign_snapshots, context))

        return findings

    def _winners_losers_finding(self, snapshots: dict[str, MetricSnapshot], context: AgentContext) -> AgentFinding:
        ranked = sorted(
            ((cid, s) for cid, s in snapshots.items() if s.cpl is not None),
            key=lambda pair: pair[1].cpl,
        )
        evidence = [f"{cid}: CPL={s.cpl:.2f}, ROAS={self._fmt_ratio(s.roas)}" for cid, s in ranked]
        winner = ranked[0][0] if ranked else None
        loser = ranked[-1][0] if ranked else None
        return AgentFinding(
            agent_name=self.name,
            entity_id=None,
            headline=(
                f"Best CPL efficiency: {winner}; worst CPL efficiency: {loser}"
                if winner and loser
                else "Not enough campaigns with calculable CPL to rank."
            ),
            detail="Ranked all campaigns by cost-per-lead where calculable.",
            evidence=evidence,
            data_sufficiency=DataSufficiencyLevel.PROMISING,
            confidence=0.7,
            suggested_actions=[],
            tags=["ranking"],
        )

    @staticmethod
    def _detect_anomalies(insights, snapshot: MetricSnapshot) -> list[str]:
        notes = []
        for i in insights:
            if i.revenue and i.revenue > 0 and i.leads == 0:
                notes.append(f"{i.date}: revenue reported ({i.revenue:.2f}) with zero leads — check attribution/tracking.")
            if i.qualified_leads is not None and i.qualified_leads > i.leads:
                notes.append(f"{i.date}: qualified_leads ({i.qualified_leads}) exceeds leads ({i.leads}).")
            if i.spend > 0 and i.impressions == 0:
                notes.append(f"{i.date}: spend recorded ({i.spend:.2f}) with zero impressions.")
        return notes

    @staticmethod
    def _detect_missing_data(insights) -> list[str]:
        notes = []
        missing_qualified = sum(1 for i in insights if i.qualified_leads is None)
        missing_revenue = sum(1 for i in insights if i.revenue is None)
        if 0 < missing_qualified < len(insights):
            notes.append(f"{missing_qualified}/{len(insights)} day(s) missing qualified_leads data")
        if 0 < missing_revenue < len(insights):
            notes.append(f"{missing_revenue}/{len(insights)} day(s) missing revenue data")
        return notes

    @staticmethod
    def _fmt_pct(v):
        return f"{v:.2%}" if v is not None else "N/A"

    @staticmethod
    def _fmt_money(v):
        return f"{v:.2f}" if v is not None else "N/A"

    @staticmethod
    def _fmt_ratio(v):
        return f"{v:.2f}x" if v is not None else "N/A"
