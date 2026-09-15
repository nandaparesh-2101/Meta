"""Agents 26-30 — Creative Operations.

Fatigue prediction, controlled refresh, scoring, diversity tracking, and
production planning for the creative library. These build on top of
`CreativeIntelligenceAgent` (agent 05)'s single-ad fatigue signal rather
than duplicating it — `CreativeFatiguePredictionAgent` combines multiple
independent signals into a graded classification, which is the piece
agent 05 deliberately does not attempt.
"""

from __future__ import annotations

from collections import Counter

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot, pct_change
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

FATIGUE_SIGNAL_THRESHOLDS = {
    "frequency": 3.5,
    "ctr_decline": -0.15,
    "cpc_increase": 0.15,
    "cpm_increase": 0.15,
    "conversion_decline": -0.15,
    "creative_age_days": 21,
}
FATIGUE_LEVELS = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class CreativeFatiguePredictionAgent(BaseAgent):
    name = "creative_fatigue_prediction"
    description = "Combines frequency, CTR/CPC/CPM trend, conversion trend, age and spend into a graded fatigue classification."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        for ad in context.ads:
            insights = sorted(context.insights_for_ad(ad.ad_id), key=lambda i: i.date)
            if len(insights) < 4:
                continue
            creative = context.creative_for_ad(ad.ad_id)
            half = len(insights) // 2
            first, second = MetricSnapshot.aggregate(insights[:half]), MetricSnapshot.aggregate(insights[half:])
            full = MetricSnapshot.aggregate(insights)

            ctr_change = pct_change(first.ctr, second.ctr)
            cpc_change = pct_change(first.cpc, second.cpc)
            cpm_change = pct_change(first.cpm, second.cpm)
            conv_change = pct_change(first.landing_page_conversion_rate, second.landing_page_conversion_rate)
            age_days = (insights[-1].date - creative.first_used_date).days if creative else None

            signals = []
            if full.frequency is not None and full.frequency >= FATIGUE_SIGNAL_THRESHOLDS["frequency"]:
                signals.append(f"frequency={full.frequency:.1f}")
            if ctr_change is not None and ctr_change <= FATIGUE_SIGNAL_THRESHOLDS["ctr_decline"]:
                signals.append(f"CTR declined {ctr_change:.0%}")
            if cpc_change is not None and cpc_change >= FATIGUE_SIGNAL_THRESHOLDS["cpc_increase"]:
                signals.append(f"CPC rose {cpc_change:.0%}")
            if cpm_change is not None and cpm_change >= FATIGUE_SIGNAL_THRESHOLDS["cpm_increase"]:
                signals.append(f"CPM rose {cpm_change:.0%}")
            if conv_change is not None and conv_change <= FATIGUE_SIGNAL_THRESHOLDS["conversion_decline"]:
                signals.append(f"Landing page conversion declined {conv_change:.0%}")
            if age_days is not None and age_days >= FATIGUE_SIGNAL_THRESHOLDS["creative_age_days"]:
                signals.append(f"creative age={age_days}d")

            # Do not declare fatigue from one metric alone.
            if not signals:
                level = "LOW"
            elif len(signals) == 1:
                level = "LOW"
            elif len(signals) == 2:
                level = "MEDIUM"
            elif len(signals) == 3:
                level = "HIGH"
            else:
                level = "CRITICAL"

            days = len({i.date for i in insights})
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=full.impressions, minimum_days_required=5, minimum_sample_required=2000
            )

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=ad.ad_id,
                    headline=f"Ad '{ad.name}' fatigue level: {level} ({len(signals)} signal(s))",
                    detail=(
                        f"Signals observed: {'; '.join(signals) if signals else 'none'}. Classification requires "
                        "at least two independent signals to reach MEDIUM or above — a single moved metric never "
                        "triggers a fatigue call on its own."
                    ),
                    evidence=signals,
                    data_sufficiency=sufficiency.level,
                    confidence=0.65 if len(signals) >= 2 else 0.35,
                    suggested_actions=[ActionType.REFRESH_CREATIVE] if level in ("HIGH", "CRITICAL") else [ActionType.DO_NOTHING],
                    tags=["creative_fatigue"] + ([f"fatigue_level:{level}"]),
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                    payload={"fatigue_level": level, "signal_count": len(signals)},
                )
            )
        return findings


class CreativeRefreshAgent(BaseAgent):
    name = "creative_refresh"
    description = "For HIGH/CRITICAL fatigue, preserves the winning pattern while generating controlled variation."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        fatigued = [f for f in context.findings_by_agent("creative_fatigue_prediction") if f.payload.get("fatigue_level") in ("HIGH", "CRITICAL")]
        if not fatigued:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No HIGH/CRITICAL fatigue detected this run — nothing to refresh.",
                    detail="Creative refresh only activates once CreativeFatiguePredictionAgent flags HIGH or CRITICAL fatigue.",
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.CONFIDENT,
                    confidence=0.6,
                    suggested_actions=[ActionType.DO_NOTHING],
                    tags=["no_refresh_needed"],
                    status=FindingStatus.COMPLETE,
                )
            ]

        pattern_findings = context.findings_by_agent("creative_intelligence")
        pattern = next((f for f in pattern_findings if "creative_pattern" in f.tags), None)

        findings = []
        for f in fatigued:
            ad = next((a for a in context.ads if a.ad_id == f.entity_id), None)
            creative = context.creative_for_ad(f.entity_id) if ad else None
            preserved = {
                "angle": creative.emotional_angle if creative else "unknown",
                "format": creative.format.value if creative else "unknown",
            }
            variations = {
                "new_hook": f"Reframed opening line for the same '{preserved['angle']}' angle — test a question or contrarian framing.",
                "new_opening": "New first 3 seconds; same core message and proof.",
                "new_proof": "Rotate in a different proof element if more than one is available.",
                "new_cta": "Test a lower-friction CTA phrase.",
            }

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=f.entity_id,
                    headline=f"Refresh plan for {f.entity_id}: preserve '{preserved['angle']}' angle/{preserved['format']} format, vary execution.",
                    detail=(
                        "Per policy, fatigue is never treated as a reason to abandon a working underlying pattern — "
                        "only the execution (hook/opening/proof/CTA) is varied. "
                        + (f"Winning pattern reference: {pattern.headline}" if pattern else "No confirmed winning-pattern finding available yet; preserving this creative's own current angle/format as the baseline.")
                    ),
                    evidence=[f"Preserved: {preserved}"],
                    data_sufficiency=f.data_sufficiency,
                    confidence=0.5,
                    suggested_actions=[ActionType.REFRESH_CREATIVE, ActionType.GENERATE_CREATIVE_CONCEPT],
                    tags=["creative_refresh_plan"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
                    payload={"preserved": preserved, "variations": variations},
                )
            )
        return findings


SCORE_DIMENSIONS = [
    "hook_strength", "relevance", "clarity", "differentiation", "emotional_impact",
    "proof", "offer_clarity", "cta", "audience_fit", "testability",
]


class CreativeScoringAgent(BaseAgent):
    name = "creative_scoring"
    description = "Scores creative concepts across 10 dimensions as a prioritization tool — never a performance guarantee."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        for creative in context.creatives:
            scores = {
                "hook_strength": 8 if "?" in creative.hook or len(creative.hook) < 60 else 5,
                "relevance": 7 if creative.problem_stated else 4,
                "clarity": 8 if len(creative.headline) < 40 else 5,
                "differentiation": 6 if creative.proof_elements else 4,
                "emotional_impact": 7 if creative.emotional_angle else 5,
                "proof": 8 if creative.proof_elements else 2,
                "offer_clarity": 8 if creative.offer_stated else 4,
                "cta": 7 if creative.cta else 3,
                "audience_fit": 6,
                "testability": 7,
            }
            total = sum(scores.values())
            max_total = len(SCORE_DIMENSIONS) * 10

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=creative.ad_id,
                    headline=f"Creative score for ad {creative.ad_id}: {total}/{max_total}",
                    detail=(
                        "Scores are a structured prioritization heuristic (presence/absence of proof, offer, CTA, "
                        "hook brevity), not a performance prediction — a high score does not guarantee results."
                    ),
                    evidence=[f"{dim}: {score}/10" for dim, score in scores.items()],
                    data_sufficiency=DataSufficiencyLevel.PROMISING,
                    confidence=0.4,
                    suggested_actions=[ActionType.DO_NOTHING],
                    tags=["creative_score"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
                    payload={"scores": scores, "total": total, "max_total": max_total},
                )
            )
        return findings


class CreativeDiversityAgent(BaseAgent):
    name = "creative_diversity"
    description = "Tracks hook/angle/format/offer patterns across the creative library and flags overused ones."

    OVERUSE_SHARE_THRESHOLD = 0.5

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        if not context.creatives:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No creatives in the library to assess diversity.",
                    detail="",
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0,
                    suggested_actions=[],
                    tags=["no_creative_data"],
                    status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        total = len(context.creatives)
        angle_counts = Counter(c.emotional_angle for c in context.creatives)
        format_counts = Counter(c.format.value for c in context.creatives)

        overused = [
            f"angle '{angle}' is {count / total:.0%} of the library"
            for angle, count in angle_counts.items() if count / total >= self.OVERUSE_SHARE_THRESHOLD
        ] + [
            f"format '{fmt}' is {count / total:.0%} of the library"
            for fmt, count in format_counts.items() if count / total >= self.OVERUSE_SHARE_THRESHOLD
        ]

        return [
            AgentFinding(
                agent_name=self.name,
                headline=(
                    f"Creative library shows {'concentration risk' if overused else 'reasonable diversity'} "
                    f"across {total} creative(s)."
                ),
                detail=(
                    ("Overused patterns: " + "; ".join(overused) + ". Recommend diversifying angle/format mix.")
                    if overused else "No single angle or format dominates the library."
                ),
                evidence=[f"Angle distribution: {dict(angle_counts)}", f"Format distribution: {dict(format_counts)}"],
                data_sufficiency=DataSufficiencyLevel.CONFIDENT,
                confidence=0.6,
                suggested_actions=[ActionType.DIVERSIFY_CREATIVE] if overused else [ActionType.DO_NOTHING],
                tags=["creative_diversity"] + (["concentration_risk"] if overused else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"angle_counts": dict(angle_counts), "format_counts": dict(format_counts)},
            )
        ]


class ContentCalendarAgent(BaseAgent):
    name = "content_calendar"
    description = "Builds a structured weekly creative production plan and tracks each item's lifecycle status."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        needs_refresh = [
            f.entity_id for f in context.findings_by_agent("creative_fatigue_prediction")
            if f.payload.get("fatigue_level") in ("HIGH", "CRITICAL")
        ]
        untested_angles = []
        angle_findings = context.findings_by_agent("content_angle")
        if angle_findings:
            untested_angles = angle_findings[0].payload.get("untested_angles", [])

        plan = {
            "refresh_needed": needs_refresh,
            "new_angle_tests": untested_angles[:4],
            "suggested_week": {
                "problem_ads": 3,
                "testimonial_ads": 2,
                "educational_ads": 2,
                "offer_ads": 2,
            },
        }
        active_count = sum(1 for c in context.creatives if c.is_active)
        inactive_count = len(context.creatives) - active_count

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"Production plan: {len(needs_refresh)} refresh item(s), {len(untested_angles[:4])} new angle test(s) suggested.",
                detail=f"Library status: {active_count} active, {inactive_count} inactive creative(s).",
                evidence=[f"Refresh needed: {needs_refresh}", f"Angle tests suggested: {untested_angles[:4]}"],
                data_sufficiency=DataSufficiencyLevel.PROMISING if context.creatives else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.5,
                suggested_actions=[ActionType.GENERATE_CREATIVE_CONCEPT] if (needs_refresh or untested_angles) else [ActionType.DO_NOTHING],
                tags=["content_calendar"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload=plan,
            )
        ]
