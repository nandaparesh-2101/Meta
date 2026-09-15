"""Agents 39-43 — Data Quality, Statistics, Trends, Anomalies, Market Conditions.

`TrackingDataQualityAgent` checks lead-record-level integrity (duplicates,
out-of-order timestamps) that `DataAnalystAgent` (agent 02, which only
inspects `DailyInsight` rows) does not cover — deliberately non-duplicated
coverage. `AnomalyDetectionAgent` adds a real statistical (z-score) pass on
top of `DataAnalystAgent`'s rule-based anomaly checks.
"""

from __future__ import annotations

import statistics
from collections import Counter

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot, pct_change
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext


class TrackingDataQualityAgent(BaseAgent):
    name = "tracking_data_quality"
    description = "Checks lead-record integrity: duplicate IDs, out-of-order timestamps, missing downstream data."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        issues: list[str] = []

        id_counts = Counter(lead.lead_id for lead in context.leads)
        duplicates = [lead_id for lead_id, count in id_counts.items() if count > 1]
        if duplicates:
            issues.append(f"{len(duplicates)} duplicate lead_id(s) found: {duplicates[:5]}")

        out_of_order = 0
        for lead in context.leads:
            if lead.contacted_at and lead.contacted_at < lead.created_at:
                out_of_order += 1
            if lead.qualified_at and lead.contacted_at and lead.qualified_at < lead.contacted_at:
                out_of_order += 1
            if lead.appointment_at and lead.qualified_at and lead.appointment_at < lead.qualified_at:
                out_of_order += 1
        if out_of_order:
            issues.append(f"{out_of_order} lead record(s) have out-of-order stage timestamps")

        missing_response_time = sum(1 for lead in context.leads if lead.response_time_minutes is None)
        if 0 < missing_response_time < len(context.leads):
            issues.append(f"{missing_response_time}/{len(context.leads)} lead(s) missing response_time_minutes")

        severity = "CRITICAL" if duplicates or out_of_order else ("WATCH" if missing_response_time else "NORMAL")

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Lead data quality: {severity} ({len(issues)} issue category(ies))",
                detail="; ".join(issues) if issues else "No lead-record integrity issues detected.",
                evidence=issues,
                data_sufficiency=DataSufficiencyLevel.CONFIDENT if context.leads else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.7 if context.leads else 0.0,
                suggested_actions=[ActionType.INVESTIGATE_TRACKING] if severity == "CRITICAL" else [ActionType.DO_NOTHING],
                tags=["tracking_data_quality"] + (["tracking_anomaly"] if severity == "CRITICAL" else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"severity": severity, "duplicate_count": len(duplicates), "out_of_order_count": out_of_order},
            )
        ]


class StatisticalAnalysisAgent(BaseAgent):
    name = "statistical_analysis"
    description = "Applies a sample-size-aware rule of thumb to trend findings so small-sample noise isn't over-read."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        trend_findings = [f for f in context.findings_by_agent("data_analyst") if any(t.startswith(("cpl_", "ctr_")) for t in f.tags)]

        for f in trend_findings:
            insights = context.insights_for_campaign(f.entity_id) if f.entity_id else []
            n = sum(i.leads for i in insights) or sum(i.clicks for i in insights)
            if n <= 0:
                continue
            # Rough rule of thumb: relative standard error of a rate estimate ~ 1/sqrt(n).
            min_meaningful_relative_change = 1 / (n ** 0.5)
            likely_noise = min_meaningful_relative_change > 0.30  # sample too small to trust any % move

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=f.entity_id,
                    headline=(
                        f"Statistical read on '{f.headline}': "
                        + ("sample size is too small to distinguish this move from random noise" if likely_noise
                           else "sample size is large enough that this move is directionally trustworthy (not a formal significance test)")
                    ),
                    detail=(
                        f"n={n}, rough minimum-meaningful-relative-change ≈ {min_meaningful_relative_change:.0%} "
                        "(1/sqrt(n) rule of thumb — a real statistical test would require raw per-observation variance, "
                        "not just aggregate counts, so this is a caution signal, not a p-value)."
                    ),
                    evidence=[f"n={n}"],
                    data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL if likely_noise else DataSufficiencyLevel.PROMISING,
                    confidence=0.3 if likely_noise else 0.55,
                    suggested_actions=[ActionType.DO_NOTHING] if likely_noise else [],
                    tags=["statistical_analysis"] + (["likely_noise"] if likely_noise else []),
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
                    assumptions=["Uses a 1/sqrt(n) rule-of-thumb, not a formal hypothesis test — treat as a caution signal."],
                )
            )
        return findings


class TimeSeriesTrendAgent(BaseAgent):
    name = "time_series_trend"
    description = "Detects gradual deterioration vs. sudden change in daily CPL/CTR series."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        for campaign in context.campaigns:
            insights = sorted(context.insights_for_campaign(campaign.campaign_id), key=lambda i: i.date)
            if len(insights) < 5:
                continue
            daily_cpl = [MetricSnapshot.from_insight(i).cpl for i in insights]
            daily_cpl_valid = [(idx, v) for idx, v in enumerate(daily_cpl) if v is not None]
            if len(daily_cpl_valid) < 5:
                continue

            jumps = [
                (idx, pct_change(daily_cpl_valid[i][1], daily_cpl_valid[i + 1][1]))
                for i, idx in enumerate(range(len(daily_cpl_valid) - 1))
            ]
            biggest_jump = max(jumps, key=lambda t: abs(t[1]) if t[1] is not None else 0, default=(None, None))

            third = len(daily_cpl_valid) // 3 or 1
            early_avg = statistics.mean(v for _, v in daily_cpl_valid[:third])
            late_avg = statistics.mean(v for _, v in daily_cpl_valid[-third:])
            gradual_change = pct_change(early_avg, late_avg)

            pattern = "stable"
            if biggest_jump[1] is not None and abs(biggest_jump[1]) >= 0.40:
                pattern = "sudden_change"
            elif gradual_change is not None and abs(gradual_change) >= 0.20:
                pattern = "gradual_deterioration" if gradual_change > 0 else "gradual_improvement"

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=f"Campaign '{campaign.name}' CPL pattern: {pattern.replace('_', ' ')}",
                    detail=(
                        f"Largest single day-to-day CPL jump: {biggest_jump[1]:.0%}. "
                        f"Early-vs-late window average change: {gradual_change:.0%}."
                        if biggest_jump[1] is not None and gradual_change is not None
                        else "Insufficient valid daily CPL points to characterize the pattern."
                    ),
                    evidence=[f"daily_cpl={[round(v, 2) if v else None for v in daily_cpl]}"],
                    data_sufficiency=DataSufficiencyLevel.PROMISING if len(insights) >= 14 else DataSufficiencyLevel.EARLY_SIGNAL,
                    confidence=0.5,
                    suggested_actions=[ActionType.INVESTIGATE_TRACKING] if pattern == "sudden_change" else [ActionType.DO_NOTHING],
                    tags=["time_series_trend", f"pattern:{pattern}"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                )
            )
        return findings


ANOMALY_METRICS = ["spend", "leads", "cpl", "ctr", "cpm", "cpc"]


class AnomalyDetectionAgent(BaseAgent):
    name = "anomaly_detection"
    description = "Applies a z-score pass across spend/leads/CPL/CTR/CPM/CPC to flag NORMAL/WATCH/ANOMALY/CRITICAL days."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        for campaign in context.campaigns:
            insights = sorted(context.insights_for_campaign(campaign.campaign_id), key=lambda i: i.date)
            if len(insights) < 5:
                continue
            snapshots = [MetricSnapshot.from_insight(i) for i in insights]

            worst_metric, worst_z, worst_date = None, 0.0, None
            for metric in ANOMALY_METRICS:
                series = [getattr(s, metric) for s in snapshots]
                values = [v for v in series if v is not None]
                if len(values) < 5:
                    continue
                mean, stdev = statistics.mean(values), statistics.pstdev(values)
                if stdev == 0:
                    continue
                for idx, v in enumerate(series):
                    if v is None:
                        continue
                    z = abs(v - mean) / stdev
                    if z > worst_z:
                        worst_z, worst_metric, worst_date = z, metric, insights[idx].date

            if worst_metric is None:
                level = "NORMAL"
            elif worst_z > 4:
                level = "CRITICAL"
            elif worst_z > 2.5:
                level = "ANOMALY"
            elif worst_z > 1.5:
                level = "WATCH"
            else:
                level = "NORMAL"

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=f"Campaign '{campaign.name}': {level}" + (f" (worst signal: {worst_metric} on {worst_date}, z={worst_z:.1f})" if worst_metric else ""),
                    detail="z-score computed against this campaign's own mean/stdev across the observed window (population stdev, no external benchmark assumed).",
                    evidence=[f"worst_metric={worst_metric}, z={worst_z:.2f}"] if worst_metric else [],
                    data_sufficiency=DataSufficiencyLevel.PROMISING if len(insights) >= 14 else DataSufficiencyLevel.EARLY_SIGNAL,
                    confidence=0.6 if level in ("ANOMALY", "CRITICAL") else 0.4,
                    suggested_actions=[ActionType.INVESTIGATE_TRACKING] if level in ("ANOMALY", "CRITICAL") else [ActionType.DO_NOTHING],
                    tags=["anomaly_detection", f"anomaly_level:{level}"] + (["tracking_anomaly"] if level == "CRITICAL" else []),
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                )
            )
        return findings


MARKET_KEYWORDS = ["season", "seasonal", "demand", "recession", "growth", "holiday", "downturn", "competitor pricing", "market"]


class MarketConditionAgent(BaseAgent):
    name = "market_condition"
    description = "Considers external market/seasonality signals only when external research was actually supplied."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        relevant = [s for s in context.competitor_research if any(k in s.lower() for k in MARKET_KEYWORDS)]
        if not relevant:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No external market-condition evidence supplied — not using market conditions as an explanation.",
                    detail="This agent never assumes seasonality/demand shifts without supplied evidence, per policy.",
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0,
                    suggested_actions=[],
                    tags=["no_market_data"],
                    status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"{len(relevant)} supplied research item(s) reference market/seasonality conditions.",
                detail="These are considered as context for performance changes, not used to override data-driven findings.",
                evidence=relevant[:5],
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.35,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["market_condition"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.EXTERNAL_RESEARCH],
            )
        ]
