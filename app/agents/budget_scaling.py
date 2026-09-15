"""Agent 11 — Budget & Scaling.

Recommends INCREASE / DECREASE / REALLOCATE / MAINTAIN / TEST based on
efficiency versus business KPI targets, data sufficiency, and marginal
performance trend — never on raw enthusiasm about "a good day."
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot, pct_change
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency
from app.rules.kpi_rules import KPIStatus, evaluate_cpl, evaluate_qualified_cpl, evaluate_roas
from app.rules.scaling_rules import is_scaling_change_safe


class BudgetScalingAgent(BaseAgent):
    name = "budget_scaling"
    description = "Recommends budget actions based on efficiency, stability, and evidence strength."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        kpis = context.business_objective.kpis
        constraints = context.business_objective.constraints

        for campaign in context.campaigns:
            insights = sorted(context.insights_for_campaign(campaign.campaign_id), key=lambda i: i.date)
            if not insights:
                continue
            days = len({i.date for i in insights})
            snapshot = MetricSnapshot.aggregate(insights)
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.leads, minimum_days_required=7, minimum_sample_required=30
            )

            cpl_status = evaluate_cpl(snapshot.cpl, kpis)
            qcpl_status = evaluate_qualified_cpl(snapshot.qualified_cpl, kpis)
            roas_status = evaluate_roas(snapshot.roas, kpis)

            half = len(insights) // 2
            cpl_trend = None
            if half >= 2:
                cpl_trend = pct_change(
                    MetricSnapshot.aggregate(insights[:half]).cpl,
                    MetricSnapshot.aggregate(insights[half:]).cpl,
                )
            stable = cpl_trend is None or abs(cpl_trend) < 0.15

            action = ActionType.MAINTAIN
            proposed_budget = campaign.daily_budget
            reason = "Default: maintain current budget."

            statuses_on_target = [
                s == KPIStatus.ON_TARGET for s in (cpl_status, qcpl_status, roas_status) if s != KPIStatus.NOT_CALCULABLE
            ]
            statuses_off_target = [
                s == KPIStatus.OFF_TARGET for s in (cpl_status, qcpl_status, roas_status) if s != KPIStatus.NOT_CALCULABLE
            ]

            if statuses_on_target and all(statuses_on_target) and stable:
                action = ActionType.INCREASE_BUDGET
                proposed_budget = campaign.daily_budget * 1.20
                reason = (
                    "CPL, qualified CPL and ROAS are all on target and stable — evidence supports "
                    "a measured scale-up."
                )
            elif any(statuses_off_target):
                action = ActionType.DECREASE_BUDGET
                proposed_budget = campaign.daily_budget * 0.80
                reason = "One or more efficiency metrics are off target — reduce spend while root cause is addressed."
            elif not stable:
                action = ActionType.MAINTAIN
                reason = "Efficiency metrics are trending but not yet stable — hold budget and keep watching."

            is_safe, safety_reason = is_scaling_change_safe(
                current_daily_budget=campaign.daily_budget,
                proposed_daily_budget=proposed_budget,
                constraints=constraints,
                data_sufficiency=sufficiency.level,
                days_running=days,
            )
            if action in (ActionType.INCREASE_BUDGET, ActionType.DECREASE_BUDGET) and not is_safe:
                action = ActionType.MAINTAIN
                proposed_budget = campaign.daily_budget
                reason = f"Scaling signal present but blocked by safety rule: {safety_reason}"

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=f"Campaign '{campaign.name}': {action.value} (budget {campaign.daily_budget:.2f} -> {proposed_budget:.2f})",
                    detail=reason,
                    evidence=[
                        f"CPL status={cpl_status.value}, qualified CPL status={qcpl_status.value}, ROAS status={roas_status.value}",
                        f"CPL trend={self._fmt_pct(cpl_trend)}, days_running={days}",
                    ],
                    data_sufficiency=sufficiency.level,
                    confidence=0.7 if sufficiency.allows_strong_recommendation else 0.4,
                    suggested_actions=[action],
                    tags=["budget_scaling"],
                )
            )

        return findings

    @staticmethod
    def _fmt_pct(v):
        return f"{v:.0%}" if v is not None else "N/A"
