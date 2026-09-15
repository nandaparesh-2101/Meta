"""Agent 12 — Forecasting.

Simple, transparent trend-projection forecasting (linear extrapolation of
recent daily averages). Every forecast states its confidence, its
assumptions, and its data basis explicitly, and is never presented as fact.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

FORECAST_HORIZON_DAYS = 14


class ForecastingAgent(BaseAgent):
    name = "forecasting"
    description = "Projects leads, CPL, spend and revenue forward using recent trend, with explicit confidence."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []

        for campaign in context.campaigns:
            insights = sorted(context.insights_for_campaign(campaign.campaign_id), key=lambda i: i.date)
            days = len({i.date for i in insights})
            if days < 3:
                findings.append(
                    AgentFinding(
                        agent_name=self.name,
                        entity_id=campaign.campaign_id,
                        headline=f"Campaign '{campaign.name}': not enough history to forecast.",
                        detail="At least 3 days of data are required before any forecast is produced.",
                        evidence=[f"{days} day(s) available"],
                        data_sufficiency=assess_data_sufficiency(
                            days_of_data=days, sample_size=0, minimum_days_required=7, minimum_sample_required=30
                        ).level,
                        confidence=0.1,
                        suggested_actions=[],
                        tags=["forecast_unavailable"],
                    )
                )
                continue

            sufficiency = assess_data_sufficiency(
                days_of_data=days,
                sample_size=sum(i.leads for i in insights),
                minimum_days_required=14,
                minimum_sample_required=50,
            )

            daily_avg = MetricSnapshot.aggregate(insights)
            per_day_leads = daily_avg.leads / days
            per_day_spend = daily_avg.spend / days
            per_day_revenue = (daily_avg.revenue / days) if daily_avg.revenue is not None else None

            forecast_leads = round(per_day_leads * FORECAST_HORIZON_DAYS)
            forecast_spend = round(per_day_spend * FORECAST_HORIZON_DAYS, 2)
            forecast_revenue = round(per_day_revenue * FORECAST_HORIZON_DAYS, 2) if per_day_revenue is not None else None
            forecast_cpl = round(forecast_spend / forecast_leads, 2) if forecast_leads else None
            forecast_roas = round(forecast_revenue / forecast_spend, 2) if forecast_revenue and forecast_spend else None

            confidence = 0.65 if sufficiency.allows_strong_recommendation else 0.35

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=(
                        f"Campaign '{campaign.name}' {FORECAST_HORIZON_DAYS}-day forecast: "
                        f"~{forecast_leads} leads at ~{forecast_cpl if forecast_cpl else 'N/A'} CPL"
                    ),
                    detail=(
                        f"Assumption: the last {days} day(s) of daily average performance continues unchanged "
                        f"(linear extrapolation, no seasonality adjustment). Data basis: {days} day(s), "
                        f"{daily_avg.leads} lead(s) observed. This is a projection, not a guarantee."
                    ),
                    evidence=[
                        f"Forecast spend: {forecast_spend}",
                        f"Forecast revenue: {forecast_revenue if forecast_revenue is not None else 'N/A'}",
                        f"Forecast ROAS: {forecast_roas if forecast_roas is not None else 'N/A'}",
                        f"Confidence basis: {sufficiency.reason}",
                    ],
                    data_sufficiency=sufficiency.level,
                    confidence=confidence,
                    suggested_actions=[ActionType.DO_NOTHING],
                    tags=["forecast"],
                )
            )

        return findings
