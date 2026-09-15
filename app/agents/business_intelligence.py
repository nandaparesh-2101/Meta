"""Agent 01 — Business Intelligence.

Establishes the business-economics frame every other agent must reason
within. This agent does not analyze ad performance; it sanity-checks the
business objective/KPI/constraint configuration itself and produces the
summary finding that anchors the rest of the run.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext


class BusinessIntelligenceAgent(BaseAgent):
    name = "business_intelligence"
    description = "Establishes business economics and KPI targets before any ad optimization."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        obj = context.business_objective
        profile, kpis, constraints = obj.profile, obj.kpis, obj.constraints

        evidence = [
            f"Business type: {profile.business_type} ({profile.sales_process.value})",
            f"Price: {profile.price:.2f}, gross margin: {profile.gross_margin_pct:.0%}",
            f"Target CPL: {kpis.target_cpl:.2f}, target qualified CPL: {kpis.target_qualified_cpl:.2f}",
            f"Target CAC: {kpis.target_cac:.2f}, target ROAS: {kpis.target_roas:.2f}",
            f"Revenue goal: {kpis.revenue_goal_monthly:.2f}/mo, lead goal: {kpis.lead_goal_monthly}/mo",
        ]

        concerns: list[str] = []
        if kpis.target_cac > profile.average_customer_lifetime_value:
            concerns.append(
                "Target CAC exceeds average customer lifetime value — even hitting "
                "target CAC would be unprofitable per customer."
            )
        max_affordable_cac = profile.gross_profit_per_unit
        if kpis.target_roas > 0 and (1 / kpis.target_roas) * profile.price > max_affordable_cac * 3:
            # Loose heuristic: implied spend-per-sale at target ROAS vastly exceeds gross profit.
            pass

        if constraints.max_daily_budget is not None and constraints.max_daily_budget <= 0:
            concerns.append("max_daily_budget constraint is zero — no scaling will ever be permitted.")

        headline = "Business objective established: " + obj.summary
        detail = (
            "Downstream agents will evaluate all performance against these targets. "
            + (f"Concerns flagged: {'; '.join(concerns)}" if concerns else "No configuration concerns found.")
        )

        return [
            AgentFinding(
                agent_name=self.name,
                entity_id=None,
                headline=headline,
                detail=detail,
                evidence=evidence,
                data_sufficiency=DataSufficiencyLevel.CONFIDENT,
                confidence=0.95 if not concerns else 0.6,
                suggested_actions=[ActionType.DO_NOTHING] if not concerns else [ActionType.INVESTIGATE_OFFER],
                tags=["business_context"] + (["kpi_configuration_risk"] if concerns else []),
            )
        ]
