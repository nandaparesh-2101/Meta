"""Agents 49-54 — Funnel Economics, Marginal Performance, Scaling Risk,
Budget Simulation, Stop/Pause, and Recovery.

These agents reason about money, not just traffic metrics — consistent
with this system's BUSINESS RESULT -> REVENUE -> ... -> CPM performance
priority ordering.
"""

from __future__ import annotations

import statistics

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot, cost_per_appointment, pct_change
from app.models.leads import FunnelStage
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import (
    ActionType,
    AgentFinding,
    EvidenceSource,
    FindingStatus,
)
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency
from app.rules.kpi_rules import evaluate_cac, evaluate_cpl


class FunnelEconomicsAgent(BaseAgent):
    name = "funnel_economics"
    description = "Computes full-funnel economics and identifies the single highest economic bottleneck."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if not insights:
                continue
            snapshot = MetricSnapshot.aggregate(insights)
            campaign_leads = [lead for lead in context.leads if lead.campaign_id == campaign.campaign_id]
            appointments = sum(1 for lead in campaign_leads if lead.stage.order >= FunnelStage.APPOINTMENT.order)
            cpa = cost_per_appointment(snapshot.spend, appointments) if appointments else None
            revenue_per_customer = (snapshot.revenue / snapshot.sales) if snapshot.revenue and snapshot.sales else None

            stage_costs = {
                "cpl": snapshot.cpl, "qualified_cpl": snapshot.qualified_cpl,
                "cost_per_appointment": cpa, "cac": snapshot.cac,
            }
            calculable = {k: v for k, v in stage_costs.items() if v is not None}
            multipliers = {}
            ordered = ["cpl", "qualified_cpl", "cost_per_appointment", "cac"]
            for i in range(len(ordered) - 1):
                a, b = ordered[i], ordered[i + 1]
                if calculable.get(a) and calculable.get(b) and calculable[a] > 0:
                    multipliers[f"{a}->{b}"] = calculable[b] / calculable[a]
            bottleneck = max(multipliers, key=multipliers.get) if multipliers else None

            days = len({i.date for i in insights})
            sufficiency = assess_data_sufficiency(days_of_data=days, sample_size=snapshot.leads, minimum_days_required=7, minimum_sample_required=30)

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=(
                        f"Campaign '{campaign.name}' highest economic bottleneck: {bottleneck} "
                        f"({multipliers[bottleneck]:.1f}x cost jump)" if bottleneck
                        else f"Campaign '{campaign.name}': insufficient stage-cost data to identify a bottleneck."
                    ),
                    detail=f"Revenue per customer: {revenue_per_customer:.2f}" if revenue_per_customer else "Revenue per customer: N/A",
                    evidence=[f"{k}: {v:.2f}" for k, v in calculable.items()] + [f"revenue_per_lead: {snapshot.revenue_per_lead:.2f}" if snapshot.revenue_per_lead else "revenue_per_lead: N/A"],
                    data_sufficiency=sufficiency.level,
                    confidence=0.6 if sufficiency.allows_strong_recommendation else 0.35,
                    suggested_actions=[ActionType.DO_NOTHING],
                    tags=["funnel_economics"] + ([f"economic_bottleneck:{bottleneck}"] if bottleneck else []),
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                    payload={"stage_costs": calculable, "multipliers": multipliers, "revenue_per_customer": revenue_per_customer},
                )
            )
        return findings


class MarginalPerformanceAgent(BaseAgent):
    name = "marginal_performance"
    description = "Compares high-spend vs. low-spend days as a proxy for diminishing marginal returns."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if len(insights) < 10:
                continue
            median_spend = statistics.median(i.spend for i in insights)
            high_spend_days = [i for i in insights if i.spend > median_spend]
            low_spend_days = [i for i in insights if i.spend <= median_spend]
            high_snap, low_snap = MetricSnapshot.aggregate(high_spend_days), MetricSnapshot.aggregate(low_spend_days)

            marginal_cpl_change = pct_change(low_snap.cpl, high_snap.cpl)
            marginal_qcpl_change = pct_change(low_snap.qualified_cpl, high_snap.qualified_cpl)
            diminishing = marginal_cpl_change is not None and marginal_cpl_change > 0.10

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=(
                        f"Campaign '{campaign.name}': {'evidence of diminishing returns' if diminishing else 'no strong diminishing-returns signal'} "
                        "at current spend levels"
                    ),
                    detail=(
                        f"CPL on above-median-spend days vs below-median-spend days: {marginal_cpl_change:+.0%}. "
                        "This is a same-account proxy for marginal cost, not a controlled spend experiment — "
                        "treat directionally, not as a precise marginal-CPL estimate."
                        if marginal_cpl_change is not None else "Insufficient variance in daily spend to estimate a marginal effect."
                    ),
                    evidence=[f"median_spend={median_spend:.2f}, high_days_cpl={self._fmt(high_snap.cpl)}, low_days_cpl={self._fmt(low_snap.cpl)}"],
                    data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                    confidence=0.3,
                    suggested_actions=[ActionType.DO_NOTHING] if not diminishing else [],
                    tags=["marginal_performance"] + (["diminishing_returns"] if diminishing else []),
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
                    assumptions=["High/low-spend-day comparison is a proxy for marginal cost, not a true holdout experiment."],
                    payload={"marginal_cpl_change": marginal_cpl_change, "marginal_qualified_cpl_change": marginal_qcpl_change},
                )
            )
        return findings

    @staticmethod
    def _fmt(v):
        return f"{v:.2f}" if v is not None else "N/A"


class ScalingRiskAgent(BaseAgent):
    name = "scaling_risk"
    description = "Combines audience/creative/funnel/sales-capacity signals into a SAFE/CAUTION/HIGH_RISK scaling verdict."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        fatigue_by_ad = {f.entity_id: f.payload.get("fatigue_level") for f in context.findings_by_agent("creative_fatigue_prediction")}
        sales_bottlenecks = {f.entity_id for f in context.findings_by_agent("sales_conversion")}

        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if not insights:
                continue
            days = len({i.date for i in insights})

            campaign_ad_ids = [a.ad_id for a in context.ads if any(s.ad_set_id == a.ad_set_id for s in context.ad_sets if s.campaign_id == campaign.campaign_id)]
            fatigued_ads = [aid for aid in campaign_ad_ids if fatigue_by_ad.get(aid) in ("HIGH", "CRITICAL")]

            audience_estimates = [
                s.audience.estimated_audience_size for s in context.ad_sets
                if s.campaign_id == campaign.campaign_id and s.audience.estimated_audience_size
            ]
            reach_total = sum(i.reach for i in insights)
            audience_saturation_risk = bool(audience_estimates) and reach_total >= min(audience_estimates) * 0.5

            risks = []
            if fatigued_ads:
                risks.append(f"{len(fatigued_ads)} fatigued creative(s)")
            if audience_saturation_risk:
                risks.append("reach approaching estimated audience size")
            if campaign.campaign_id in sales_bottlenecks:
                risks.append("sales-side bottleneck already identified downstream")
            if days < context.business_objective.constraints.min_data_days_before_scaling:
                risks.append(f"only {days} day(s) of data (business requires {context.business_objective.constraints.min_data_days_before_scaling})")

            verdict = "SAFE" if not risks else ("HIGH_RISK" if len(risks) >= 3 else "CAUTION")

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=f"Scaling risk for '{campaign.name}': {verdict}",
                    detail="; ".join(risks) if risks else "No audience/creative/funnel/sales capacity risk signals detected.",
                    evidence=risks,
                    data_sufficiency=DataSufficiencyLevel.PROMISING if days >= 7 else DataSufficiencyLevel.EARLY_SIGNAL,
                    confidence=0.55,
                    suggested_actions=[ActionType.MAINTAIN] if verdict != "SAFE" else [ActionType.DO_NOTHING],
                    tags=["scaling_risk", f"scaling_risk:{verdict}"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                    payload={"verdict": verdict, "risk_count": len(risks)},
                )
            )
        return findings


class BudgetAllocationSimulatorAgent(BaseAgent):
    name = "budget_allocation_simulator"
    description = "Simulates budget allocation scenarios (labeled as forecasts, never fact)."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        snapshots = {}
        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if insights:
                snapshots[campaign.campaign_id] = (campaign, MetricSnapshot.aggregate(insights))
        eligible = {cid: (c, s) for cid, (c, s) in snapshots.items() if s.cpl}
        if len(eligible) < 2:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="Fewer than 2 campaigns with calculable CPL — nothing to simulate a reallocation between.",
                    detail="", evidence=[], data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0, suggested_actions=[], tags=["insufficient_campaigns_for_simulation"],
                    status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        ranked = sorted(eligible.items(), key=lambda kv: kv[1][1].cpl)
        best_id, (best_c, best_s) = ranked[0]
        worst_id, (worst_c, worst_s) = ranked[-1]
        total_budget = sum(c.daily_budget for c, _ in eligible.values())

        def project(campaign_id: str, new_budget: float) -> dict:
            c, s = eligible[campaign_id]
            leads = (new_budget / s.cpl) if s.cpl else None
            revenue = (leads * s.revenue_per_lead) if leads and s.revenue_per_lead else None
            return {"budget": round(new_budget, 2), "projected_leads": round(leads) if leads else None, "projected_revenue": round(revenue, 2) if revenue else None}

        scenarios = {
            "scenario_a_current": {cid: project(cid, c.daily_budget) for cid, (c, _) in eligible.items()},
            "scenario_b_shift_to_best_cpl": {
                **{cid: project(cid, c.daily_budget) for cid, (c, _) in eligible.items() if cid not in (best_id, worst_id)},
                best_id: project(best_id, best_c.daily_budget * 1.3),
                worst_id: project(worst_id, max(worst_c.daily_budget * 0.7, 0)),
            },
            "scenario_c_flat_increase_20pct": {cid: project(cid, c.daily_budget * 1.2) for cid, (c, _) in eligible.items()},
        }

        return [
            AgentFinding(
                agent_name=self.name,
                headline=f"3 budget allocation scenarios simulated across {len(eligible)} campaign(s), total budget {total_budget:.2f}/day.",
                detail=(
                    "FORECAST, NOT FACT: projections linearly extrapolate each campaign's current CPL/revenue-per-lead "
                    "onto a new budget level — they do not model diminishing returns, audience saturation, or "
                    "creative fatigue. Use MarginalPerformanceAgent and ScalingRiskAgent findings alongside this."
                ),
                evidence=[f"Best CPL: {best_id} ({best_s.cpl:.2f}); Worst CPL: {worst_id} ({worst_s.cpl:.2f})"],
                data_sufficiency=DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.3,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["budget_simulation"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA, EvidenceSource.MODEL_INFERENCE],
                assumptions=["Linear extrapolation of current CPL/revenue-per-lead — does not model diminishing returns."],
                payload={"scenarios": scenarios},
            )
        ]


class StopPauseDecisionAgent(BaseAgent):
    name = "stop_pause_decision"
    description = "Determines whether an ad/campaign deserves pausing — avoids premature pausing on thin evidence."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        kpis = context.business_objective.kpis
        account_snapshot = MetricSnapshot.aggregate(context.insights)

        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if not insights:
                continue
            snapshot = MetricSnapshot.aggregate(insights)
            days = len({i.date for i in insights})
            sufficiency = assess_data_sufficiency(days_of_data=days, sample_size=snapshot.leads, minimum_days_required=10, minimum_sample_required=40)

            cpl_status = evaluate_cpl(snapshot.cpl, kpis, tolerance=0.5)
            cac_status = evaluate_cac(snapshot.cac, kpis, tolerance=0.5)
            below_account_quality = (
                snapshot.qualified_rate is not None and account_snapshot.qualified_rate is not None
                and snapshot.qualified_rate < account_snapshot.qualified_rate * 0.5
            )

            evidence_for_pause = sum([
                cpl_status.value == "off_target",
                cac_status.value == "off_target",
                below_account_quality,
            ])
            should_pause = evidence_for_pause >= 2 and sufficiency.allows_strong_recommendation

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=(
                        f"Campaign '{campaign.name}': {'pause is defensible' if should_pause else 'pausing not yet warranted'}"
                    ),
                    detail=(
                        f"{evidence_for_pause}/3 pause signals present, data sufficiency={sufficiency.level.value}. "
                        + ("Multiple independent signals plus adequate data support pausing." if should_pause
                           else "Either evidence is too thin or data sufficiency doesn't yet clear the bar — avoiding a premature pause.")
                    ),
                    evidence=[f"cpl_status={cpl_status.value}, cac_status={cac_status.value}, below_account_quality={below_account_quality}"],
                    data_sufficiency=sufficiency.level,
                    confidence=0.6 if should_pause else 0.4,
                    suggested_actions=[ActionType.PAUSE_AD_SET] if should_pause else [ActionType.DO_NOTHING],
                    tags=["stop_pause_decision"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                )
            )
        return findings


class RecoveryAgent(BaseAgent):
    name = "recovery"
    description = "For significant deterioration, diagnoses WHAT/WHEN/WHERE/WHY and proposes what to test."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        severe_tags = {"cpl_increase", "ctr_decrease", "audience_saturation", "creative_fatigue", "tracking_anomaly"}
        deterioration_findings = [f for f in context.findings if severe_tags & set(f.tags)]
        if not deterioration_findings:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No significant deterioration detected this run — recovery planning not triggered.",
                    detail="", evidence=[], data_sufficiency=DataSufficiencyLevel.CONFIDENT, confidence=0.5,
                    suggested_actions=[ActionType.DO_NOTHING], tags=["no_recovery_needed"], status=FindingStatus.COMPLETE,
                )
            ]

        by_entity: dict[str | None, list] = {}
        for f in deterioration_findings:
            by_entity.setdefault(f.entity_id, []).append(f)

        findings = []
        for entity_id, entity_findings in by_entity.items():
            causes = sorted({t for f in entity_findings for t in f.tags if t in severe_tags})
            what_to_test = []
            if "creative_fatigue" in causes:
                what_to_test.append("Refresh creative (see CreativeRefreshAgent plan)")
            if "audience_saturation" in causes:
                what_to_test.append("Test a new/expanded audience")
            if "cpl_increase" in causes:
                what_to_test.append("Test copy/offer variation to rebuild efficiency")
            if "tracking_anomaly" in causes:
                what_to_test.append("Fix tracking before drawing further conclusions")

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=entity_id,
                    headline=f"Recovery plan for {entity_id or 'account'}: {len(causes)} contributing cause(s) identified.",
                    detail=(
                        f"WHAT CHANGED: {causes}. WHY (candidate causes): {', '.join(causes) if causes else 'undetermined'}. "
                        f"WHAT SHOULD BE TESTED: {'; '.join(what_to_test) if what_to_test else 'insufficient signal to propose a specific test yet'}."
                    ),
                    evidence=[f.headline for f in entity_findings],
                    data_sufficiency=max((f.data_sufficiency for f in entity_findings), key=lambda lvl: list(DataSufficiencyLevel).index(lvl)),
                    confidence=0.5,
                    suggested_actions=[ActionType.LAUNCH_TEST] if what_to_test else [ActionType.INVESTIGATE_TRACKING],
                    tags=["recovery_plan"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                    payload={"causes": causes, "what_to_test": what_to_test},
                )
            )
        return findings
