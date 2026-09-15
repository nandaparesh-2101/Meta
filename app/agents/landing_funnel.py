"""Agents 31-38 — Landing Page, Funnel, and Sales Intelligence.

This build has no dedicated landing-page-content model (no scraped page
copy, no form-field schema) — several agents here are honest about that
gap (reporting INSUFFICIENT_DATA for anything they cannot actually see)
while still computing everything that genuinely is available: landing
page conversion rate, lead response time, funnel stage drop-off, and
(when supplied) CRM records.
"""

from __future__ import annotations

from collections import defaultdict

from app.agents.base import BaseAgent
from app.metrics.engine import MetricSnapshot
from app.models.leads import FunnelStage
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding, EvidenceSource, FindingStatus
from app.orchestration.context import AgentContext
from app.rules.data_sufficiency import assess_data_sufficiency

LP_COPY_CHECKLIST = ["hero_section", "headline", "subheadline", "benefits", "proof", "objections", "cta", "faq", "form_copy"]


class LandingPageCopyAgent(BaseAgent):
    name = "landing_page_copy"
    description = "Checks ad-to-landing-page message match and provides a landing page copy checklist."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        offers = {c.offer_stated for c in context.creatives if c.offer_stated}
        mismatch_risk = len(offers) > 1

        findings = [
            AgentFinding(
                agent_name=self.name,
                headline=(
                    f"{len(offers)} distinct offer claim(s) across active creatives"
                    + (" — message-match risk if the landing page only reflects one of them." if mismatch_risk else " — consistent offer messaging.")
                ),
                detail=(
                    "This build has no landing-page-content model, so this agent cannot audit real hero/headline/"
                    "FAQ copy directly — it can only check AD-side offer consistency and provide the standard "
                    "landing-page copy checklist below for manual/future-automated review."
                ),
                evidence=[f"Distinct offers in ad copy: {sorted(offers)}"] if offers else ["No offer_stated data on file."],
                data_sufficiency=DataSufficiencyLevel.PROMISING if context.creatives else DataSufficiencyLevel.INSUFFICIENT_DATA,
                confidence=0.4,
                suggested_actions=[ActionType.ADJUST_LANDING_PAGE] if mismatch_risk else [ActionType.DO_NOTHING],
                tags=["landing_page_copy"] + (["message_match_risk"] if mismatch_risk else []),
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                questions=["No landing page content is connected to this system yet — a real page audit requires that data."],
                payload={"checklist": LP_COPY_CHECKLIST, "distinct_offers": sorted(offers)},
            )
        ]
        return findings


class LandingPageCROAgent(BaseAgent):
    name = "landing_page_cro"
    description = "Diagnoses landing-page conversion problems from click -> landing page -> lead data."

    LOW_CONVERSION_THRESHOLD = 0.10

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if not insights:
                continue
            snapshot = MetricSnapshot.aggregate(insights)
            if snapshot.landing_page_conversion_rate is None:
                continue

            days = len({i.date for i in insights})
            sufficiency = assess_data_sufficiency(
                days_of_data=days, sample_size=snapshot.landing_page_views, minimum_days_required=7, minimum_sample_required=200
            )

            low = snapshot.landing_page_conversion_rate < self.LOW_CONVERSION_THRESHOLD
            experiments = []
            if low:
                experiments = [
                    "Test a shorter, more focused above-the-fold section",
                    "Test a more prominent/repeated CTA",
                    "Test adding a trust signal (proof/guarantee) near the form",
                ]

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=(
                        f"Campaign '{campaign.name}' landing page conversion: {snapshot.landing_page_conversion_rate:.1%} "
                        f"({'below' if low else 'at/above'} the {self.LOW_CONVERSION_THRESHOLD:.0%} caution threshold)"
                    ),
                    detail=(
                        "Experiments recommended: " + "; ".join(experiments)
                        if experiments else "Conversion rate does not indicate a landing-page-level problem."
                    ),
                    evidence=[f"landing_page_views={snapshot.landing_page_views}, leads={snapshot.leads}"],
                    data_sufficiency=sufficiency.level,
                    confidence=0.5 if sufficiency.allows_strong_recommendation else 0.3,
                    suggested_actions=[ActionType.ADJUST_LANDING_PAGE, ActionType.LAUNCH_TEST] if low else [ActionType.DO_NOTHING],
                    tags=["landing_page_cro"] + (["low_lp_conversion"] if low else []),
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                    payload={"experiments": experiments},
                )
            )
        return findings


class FormOptimizationAgent(BaseAgent):
    name = "form_optimization"
    description = "Balances form conversion rate against downstream lead quality — never optimizes completion blindly."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        for campaign in context.campaigns:
            insights = context.insights_for_campaign(campaign.campaign_id)
            if not insights:
                continue
            snapshot = MetricSnapshot.aggregate(insights)
            if snapshot.landing_page_conversion_rate is None or snapshot.qualified_rate is None:
                continue

            high_conv_low_quality = snapshot.landing_page_conversion_rate > 0.15 and snapshot.qualified_rate < 0.25
            low_conv = snapshot.landing_page_conversion_rate < 0.08

            if high_conv_low_quality:
                recommendation = "Form converts easily but qualified rate is low — consider adding one qualifying field, not removing friction further."
                action = ActionType.ADJUST_FORM
            elif low_conv:
                recommendation = "Form conversion is low — consider reducing field count/friction before assuming the offer itself is the problem."
                action = ActionType.ADJUST_FORM
            else:
                recommendation = "Form conversion and qualified rate appear balanced — no blind optimization warranted."
                action = ActionType.DO_NOTHING

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign.campaign_id,
                    headline=f"Campaign '{campaign.name}': {recommendation}",
                    detail=(
                        "This system has no direct field-count/field-quality data (no form schema is connected) — "
                        "this recommendation is based purely on the conversion-rate-vs-lead-quality trade-off, "
                        "which is a real, computed signal even without field-level detail."
                    ),
                    evidence=[
                        f"landing_page_conversion_rate={snapshot.landing_page_conversion_rate:.1%}, "
                        f"qualified_rate={snapshot.qualified_rate:.1%}"
                    ],
                    data_sufficiency=DataSufficiencyLevel.PROMISING,
                    confidence=0.45,
                    suggested_actions=[action],
                    tags=["form_optimization"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                    questions=["No form field schema is connected — recommendation is metric-driven, not field-level."],
                )
            )
        return findings


class LeadResponseAgent(BaseAgent):
    name = "lead_response"
    description = "Analyzes lead response time and contact rate to check whether sales, not ads, is the bottleneck."

    SLOW_RESPONSE_MINUTES = 60

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        leads_by_campaign: dict[str, list] = defaultdict(list)
        for lead in context.leads:
            leads_by_campaign[lead.campaign_id].append(lead)

        for campaign_id, leads in leads_by_campaign.items():
            response_times = [lead.response_time_minutes for lead in leads if lead.response_time_minutes is not None]
            if not response_times:
                continue
            avg_response = sum(response_times) / len(response_times)
            contacted = sum(1 for lead in leads if lead.stage.order >= FunnelStage.CONTACTED.order)
            contact_rate = contacted / len(leads) if leads else None
            qualified = sum(1 for lead in leads if lead.stage.order >= FunnelStage.QUALIFIED.order)
            qualified_rate = qualified / len(leads) if leads else None

            slow = avg_response > self.SLOW_RESPONSE_MINUTES
            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign_id,
                    headline=(
                        f"Avg lead response time: {avg_response:.0f} min, contact rate {contact_rate:.0%}, "
                        f"qualified rate {qualified_rate:.0%}"
                    ),
                    detail=(
                        f"Response time exceeds the {self.SLOW_RESPONSE_MINUTES}-minute caution threshold — "
                        "advertising may be producing usable leads that the sales process is failing to capture in time."
                        if slow else "Response time is within a reasonable window; advertising and sales response appear aligned."
                    ),
                    evidence=[f"n={len(leads)} leads, avg_response={avg_response:.0f}min, contact_rate={contact_rate:.0%}"],
                    data_sufficiency=DataSufficiencyLevel.PROMISING if len(leads) >= 20 else DataSufficiencyLevel.EARLY_SIGNAL,
                    confidence=0.55 if slow else 0.4,
                    suggested_actions=[ActionType.ESCALATE_TO_SALES] if slow else [ActionType.DO_NOTHING],
                    tags=["lead_response"] + (["slow_lead_response"] if slow else []),
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                )
            )
        return findings


class SalesConversionAgent(BaseAgent):
    name = "sales_conversion"
    description = "Analyzes Contact -> Qualified -> Appointment -> Sale bottlenecks — never blames Meta for sales-side problems."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings = []
        leads_by_campaign: dict[str, list] = defaultdict(list)
        for lead in context.leads:
            leads_by_campaign[lead.campaign_id].append(lead)

        for campaign_id, leads in leads_by_campaign.items():
            if len(leads) < 10:
                continue
            stage_counts = {stage: sum(1 for lead in leads if lead.stage.order >= stage.order) for stage in FunnelStage}
            steps = {
                "contact_rate": stage_counts[FunnelStage.CONTACTED] / stage_counts[FunnelStage.LEAD],
                "qualify_rate": (stage_counts[FunnelStage.QUALIFIED] / stage_counts[FunnelStage.CONTACTED]) if stage_counts[FunnelStage.CONTACTED] else 0,
                "appointment_rate": (stage_counts[FunnelStage.APPOINTMENT] / stage_counts[FunnelStage.QUALIFIED]) if stage_counts[FunnelStage.QUALIFIED] else 0,
                "close_rate": (stage_counts[FunnelStage.SALE] / stage_counts[FunnelStage.APPOINTMENT]) if stage_counts[FunnelStage.APPOINTMENT] else 0,
            }
            weakest_step = min(steps, key=steps.get)

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign_id,
                    headline=f"Sales-side bottleneck: {weakest_step.replace('_', ' ')} ({steps[weakest_step]:.0%})",
                    detail=(
                        "This is a sales-process bottleneck (contact -> qualified -> appointment -> sale), downstream "
                        "of ad delivery — it is not evidence of an advertising problem and should not drive a "
                        "budget or creative change."
                    ),
                    evidence=[f"{k}: {v:.0%}" for k, v in steps.items()],
                    data_sufficiency=DataSufficiencyLevel.PROMISING,
                    confidence=0.55,
                    suggested_actions=[ActionType.INVESTIGATE_SALES_PROCESS],
                    tags=["sales_bottleneck", f"sales_bottleneck:{weakest_step}"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                )
            )
        return findings


class CRMIntelligenceAgent(BaseAgent):
    name = "crm_intelligence"
    description = "Connects ad source data to CRM lead/sales/revenue status, when CRM data is supplied."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        if not context.crm_records:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No CRM data connected — CRM Intelligence is inactive this run.",
                    detail="CRM is not connected in this build. Supply AgentContext.crm_records to activate this agent.",
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0,
                    suggested_actions=[],
                    tags=["no_crm_data"],
                    status=FindingStatus.INSUFFICIENT_DATA,
                    questions=["Connect a CRM data source to identify which campaigns produce actual paying customers."],
                )
            ]

        by_campaign: dict[str, list] = defaultdict(list)
        for record in context.crm_records:
            if record.campaign_id:
                by_campaign[record.campaign_id].append(record)

        findings = []
        for campaign_id, records in by_campaign.items():
            won = [r for r in records if r.crm_status.lower() == "won"]
            revenue = sum(r.deal_value or 0 for r in won)
            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign_id,
                    headline=f"CRM: {len(won)}/{len(records)} record(s) won, revenue={revenue:.2f}",
                    detail="Revenue and win counts sourced directly from connected CRM records.",
                    evidence=[f"{len(records)} CRM record(s), {len(won)} won"],
                    data_sufficiency=DataSufficiencyLevel.PROMISING if len(records) >= 10 else DataSufficiencyLevel.EARLY_SIGNAL,
                    confidence=0.6,
                    suggested_actions=[ActionType.DO_NOTHING],
                    tags=["crm_intelligence"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.CRM_DATA],
                    payload={"won": len(won), "total": len(records), "revenue": revenue},
                )
            )
        return findings


class LeadScoringAgent(BaseAgent):
    name = "lead_scoring"
    description = "Scores lead quality per campaign based on intent, engagement, and (when available) sales outcome."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        leads_by_campaign: dict[str, list] = defaultdict(list)
        for lead in context.leads:
            leads_by_campaign[lead.campaign_id].append(lead)

        findings = []
        for campaign_id, leads in leads_by_campaign.items():
            if not leads:
                continue
            intent_score = sum(lead.stage.order for lead in leads) / (len(leads) * (len(FunnelStage) - 1))
            engagement_score = 1.0 - min(
                (sum(lead.response_time_minutes or 0 for lead in leads) / len(leads)) / 240, 1.0
            )
            composite = round((intent_score * 0.6 + engagement_score * 0.4) * 100)

            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=campaign_id,
                    headline=f"Lead score for campaign {campaign_id}: {composite}/100",
                    detail=(
                        "Score basis: 60% funnel-stage-reached (intent proxy) + 40% response-time-derived engagement. "
                        "This is an explainable heuristic, not an arbitrary number — every factor is shown in evidence."
                    ),
                    evidence=[f"intent_component={intent_score:.2f}", f"engagement_component={engagement_score:.2f}"],
                    data_sufficiency=DataSufficiencyLevel.PROMISING if len(leads) >= 20 else DataSufficiencyLevel.EARLY_SIGNAL,
                    confidence=0.45,
                    suggested_actions=[ActionType.DO_NOTHING],
                    tags=["lead_scoring"],
                    status=FindingStatus.COMPLETE,
                    evidence_sources=[EvidenceSource.META_DATA],
                    payload={"score": composite, "intent_component": intent_score, "engagement_component": engagement_score},
                )
            )
        return findings


class SalesFeedbackLoopAgent(BaseAgent):
    name = "sales_feedback_loop"
    description = "Feeds sales outcomes backward to identify which creative angle actually produced revenue."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        if not context.sales:
            return [
                AgentFinding(
                    agent_name=self.name,
                    headline="No sales data available to close the feedback loop this run.",
                    detail="",
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0,
                    suggested_actions=[],
                    tags=["no_sales_data"],
                    status=FindingStatus.INSUFFICIENT_DATA,
                )
            ]

        revenue_by_angle: dict[str, float] = defaultdict(float)
        count_by_angle: dict[str, int] = defaultdict(int)
        for sale in context.sales:
            creative = context.creative_for_ad(sale.ad_id)
            angle = creative.emotional_angle if creative else "unknown"
            revenue_by_angle[angle] += sale.amount
            count_by_angle[angle] += 1

        best_angle = max(revenue_by_angle, key=revenue_by_angle.get) if revenue_by_angle else None

        return [
            AgentFinding(
                agent_name=self.name,
                headline=(
                    f"'{best_angle}' angle produced the most actual sale revenue ({revenue_by_angle[best_angle]:.2f})"
                    if best_angle else "No angle-attributable sales this run."
                ),
                detail=(
                    "This closes SALES -> creative angle -> (feed forward to) audience/copy/offer decisions. "
                    "Revenue, not lead volume, is the basis — consistent with this system's business-result-first priority."
                ),
                evidence=[f"{angle}: revenue={rev:.2f} across {count_by_angle[angle]} sale(s)" for angle, rev in revenue_by_angle.items()],
                data_sufficiency=DataSufficiencyLevel.PROMISING if len(context.sales) >= 20 else DataSufficiencyLevel.EARLY_SIGNAL,
                confidence=0.5,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["sales_feedback_loop"],
                status=FindingStatus.COMPLETE,
                evidence_sources=[EvidenceSource.META_DATA],
                payload={"revenue_by_angle": dict(revenue_by_angle)},
            )
        ]
