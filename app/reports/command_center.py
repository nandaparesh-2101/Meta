"""Command Center report generator.

Produces the 18-section META ADS AI COMMAND CENTER report from a completed
orchestration run. Pure presentation layer — it never computes a metric or
makes a decision itself, it only organizes what agents/Guardian already
produced.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.metrics.engine import MetricSnapshot
from app.models.execution import GuardianDecision
from app.models.recommendations import ActionType, Priority, Recommendation
from app.orchestration.context import AgentContext

SECTION_TITLES = [
    "1. Business Objective",
    "2. Overall Performance",
    "3. What Changed",
    "4. Root Cause",
    "5. Winners",
    "6. Losers",
    "7. Lead Quality",
    "8. Creative Intelligence",
    "9. Audience Intelligence",
    "10. Funnel Health",
    "11. Budget & Scaling",
    "12. Experiments",
    "13. Recommended Actions",
    "14. What NOT to Change",
    "15. Risks",
    "16. Confidence",
    "17. Data Required",
    "18. Next Review",
]


@dataclass
class CommandCenterReport:
    sections: dict[str, list[str]] = field(default_factory=dict)

    def to_markdown(self) -> str:
        lines = ["# META ADS AI COMMAND CENTER", ""]
        for title in SECTION_TITLES:
            lines.append(f"## {title}")
            content = self.sections.get(title, ["No data."])
            for item in content:
                lines.append(f"- {item}")
            lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, list[str]]:
        return dict(self.sections)


def generate_report(context: AgentContext, guardian_decisions: list[GuardianDecision]) -> CommandCenterReport:
    report = CommandCenterReport()
    decisions_by_rec = {d.recommendation_id: d for d in guardian_decisions}

    report.sections["1. Business Objective"] = [context.business_objective.summary]

    overall = MetricSnapshot.aggregate(context.insights)
    report.sections["2. Overall Performance"] = [
        f"Spend: {overall.spend:.2f}",
        f"Leads: {overall.leads} (CPL: {_fmt(overall.cpl)})",
        f"Qualified leads: {overall.qualified_leads if overall.qualified_leads is not None else 'N/A'} "
        f"(qualified CPL: {_fmt(overall.qualified_cpl)})",
        f"Sales: {overall.sales if overall.sales is not None else 'N/A'}, "
        f"Revenue: {overall.revenue if overall.revenue is not None else 'N/A'}",
        f"CTR: {_fmt_pct(overall.ctr)}, ROAS: {_fmt(overall.roas)}",
    ]

    report.sections["3. What Changed"] = _findings_by_tag_prefix(context, prefixes=("cpl_", "ctr_")) or [
        "No significant metric-level change detected this run."
    ]

    report.sections["4. Root Cause"] = _findings_by_tag_prefix(
        context, prefixes=("bottleneck:", "offer_risk", "audience_saturation", "creative_fatigue", "tracking_anomaly")
    ) or ["No single dominant root cause identified this run."]

    ranking = context.findings_by_agent("data_analyst")
    ranking_note = next((f for f in ranking if "ranking" in f.tags), None)
    report.sections["5. Winners"] = (
        [ranking_note.headline] + ranking_note.evidence[:1] if ranking_note else ["Not enough campaigns to rank."]
    )
    report.sections["6. Losers"] = (
        [ranking_note.headline] + ranking_note.evidence[-1:] if ranking_note else ["Not enough campaigns to rank."]
    )

    report.sections["7. Lead Quality"] = _headlines(context, "lead_quality")
    report.sections["8. Creative Intelligence"] = _headlines(context, "creative_intelligence")
    report.sections["9. Audience Intelligence"] = _headlines(context, "audience_intelligence")
    report.sections["10. Funnel Health"] = _headlines(context, "funnel_diagnostics")
    report.sections["11. Budget & Scaling"] = _headlines(context, "budget_scaling")

    experiment_lines = [
        f"[{e.status.value}] {e.hypothesis} (variable={e.variable})" for e in context.new_experiments
    ]
    if not experiment_lines:
        experiment_lines = ["No new experiments proposed this run."]
    report.sections["12. Experiments"] = experiment_lines

    actionable_recs = [r for r in context.recommendations if r.action != ActionType.DO_NOTHING]
    actionable_recs.sort(key=lambda r: list(Priority).index(r.priority))
    report.sections["13. Recommended Actions"] = [
        f"[{r.priority.value}] {r.action.value} on {r.entity_id} — {r.reason} "
        f"(confidence={r.confidence:.0%}, risk={r.risk.value}, guardian={_verdict(decisions_by_rec, r)})"
        for r in actionable_recs
    ] or ["DO NOTHING YET — no recommendation cleared the evidence bar this run."]

    do_nothing = [r for r in context.recommendations if r.action in (ActionType.DO_NOTHING, ActionType.MAINTAIN)]
    report.sections["14. What NOT to Change"] = [
        f"{r.entity_id}: {r.reason}" for r in do_nothing
    ] or ["No explicit 'hold steady' findings this run."]

    all_concerns = [c for d in guardian_decisions for c in d.concerns]
    report.sections["15. Risks"] = sorted(set(all_concerns)) or ["No safety concerns raised by Guardian this run."]

    report.sections["16. Confidence"] = _confidence_summary(context.recommendations)

    insufficient = [f for f in context.findings if f.data_sufficiency.value == "insufficient_data"]
    report.sections["17. Data Required"] = [
        f"{f.entity_id or 'account'}: {f.headline}" for f in insufficient[:10]
    ] or ["No blocking data gaps identified this run."]

    review_windows = [r.review_window_days for r in actionable_recs]
    next_review = min(review_windows) if review_windows else 14
    report.sections["18. Next Review"] = [f"Recommended next review in {next_review} day(s)."]

    return report


def _headlines(context: AgentContext, agent_name: str, limit: int = 10) -> list[str]:
    findings = context.findings_by_agent(agent_name)
    return [f.headline for f in findings[:limit]] or [f"No findings from {agent_name} this run."]


def _findings_by_tag_prefix(context: AgentContext, prefixes: tuple[str, ...]) -> list[str]:
    out = []
    for f in context.findings:
        if any(tag.startswith(prefix) for tag in f.tags for prefix in prefixes):
            out.append(f"{f.entity_id or 'account'}: {f.headline}")
    return out


def _confidence_summary(recommendations: list[Recommendation]) -> list[str]:
    if not recommendations:
        return ["No recommendations produced this run."]
    avg_confidence = sum(r.confidence for r in recommendations) / len(recommendations)
    by_level: dict[str, int] = {}
    for r in recommendations:
        by_level[r.data_sufficiency.value] = by_level.get(r.data_sufficiency.value, 0) + 1
    return [f"Average recommendation confidence: {avg_confidence:.0%}"] + [
        f"{count} recommendation(s) at {level} data sufficiency" for level, count in by_level.items()
    ]


def _verdict(decisions_by_rec: dict[str, GuardianDecision], rec: Recommendation) -> str:
    decision = decisions_by_rec.get(rec.recommendation_id)
    return decision.verdict.value if decision else "not_reviewed"


def _fmt(v: float | None) -> str:
    return f"{v:.2f}" if v is not None else "N/A"


def _fmt_pct(v: float | None) -> str:
    return f"{v:.2%}" if v is not None else "N/A"
