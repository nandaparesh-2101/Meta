"""MOCK Meta Ads data generator.

Everything produced here is clearly labeled MOCK — it is deterministic
(seeded RNG per scenario, so repeated runs and tests are stable) synthetic
data, never a real advertiser's data and never a real Meta API response.

Ten scenarios are generated, one per campaign, matching the required test
coverage:

 1. strong_campaign            - efficient across the whole funnel, stable
 2. high_cpl_campaign          - CPL trending up and off target
 3. cheap_low_quality_leads    - cheap CPL but poor qualified rate/close rate
 4. creative_fatigue           - CTR decaying, frequency climbing
 5. audience_saturation        - very high frequency, rising CPL from overexposure
 6. high_ctr_poor_conversion   - strong CTR, weak landing-page/qualified conversion
 7. low_ctr_high_quality       - weak CTR, but high qualified rate + revenue/lead
 8. insufficient_data          - brand new campaign, only 3 days of history
 9. scaling_opportunity        - all efficiency metrics on target and improving
10. tracking_anomaly           - impossible/inconsistent data points present
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from app.models.ads import (
    Ad,
    AdSet,
    AudienceDefinition,
    AudienceType,
    Campaign,
    CampaignObjective,
    CampaignStatus,
    Creative,
    CreativeFormat,
    Gender,
    Placement,
)
from app.models.business import (
    BusinessConstraints,
    BusinessObjective,
    BusinessProfile,
    KPIConfiguration,
    SalesProcess,
)
from app.models.leads import FunnelStage, Lead, Sale
from app.models.metrics import DailyInsight, EntityLevel

AVG_DEAL_VALUE = 150.0
DEFAULT_WINDOW_DAYS = 21


@dataclass
class MockAccountData:
    business_objective: BusinessObjective
    campaigns: list[Campaign] = field(default_factory=list)
    ad_sets: list[AdSet] = field(default_factory=list)
    ads: list[Ad] = field(default_factory=list)
    creatives: list[Creative] = field(default_factory=list)
    insights: list[DailyInsight] = field(default_factory=list)
    leads: list[Lead] = field(default_factory=list)
    sales: list[Sale] = field(default_factory=list)


def _business_objective() -> BusinessObjective:
    profile = BusinessProfile(
        business_name="Apex Fitness Studio",
        business_type="local service (fitness membership)",
        product_or_service="Monthly group fitness membership",
        price=150.0,
        gross_margin_pct=0.55,
        target_customer="Adults 25-45 wanting accountability-based group fitness",
        geography="Austin, TX metro",
        sales_process=SalesProcess.SALES_ASSISTED,
        average_customer_lifetime_value=1800.0,
    )
    kpis = KPIConfiguration(
        revenue_goal_monthly=45000.0,
        lead_goal_monthly=300,
        target_cpl=25.0,
        target_qualified_cpl=60.0,
        target_cac=300.0,
        target_roas=3.0,
    )
    constraints = BusinessConstraints(
        max_daily_budget=500.0,
        max_budget_change_pct_per_change=0.20,
        min_data_days_before_scaling=7,
        protected_campaign_ids=[],
        brand_safety_notes="No competitor bashing; no unverifiable health claims.",
    )
    return BusinessObjective(
        profile=profile,
        kpis=kpis,
        constraints=constraints,
        summary=(
            "Apex Fitness Studio needs 300 leads/month at <=$25 CPL and <=$60 qualified CPL, "
            "converting at >=3x ROAS, to hit its $45k/month revenue goal."
        ),
    )


def _creative(ad_id: str, angle: str, hook: str, fmt: CreativeFormat, has_proof: bool, first_used: date) -> Creative:
    return Creative(
        creative_id=f"cr_{ad_id}",
        ad_id=ad_id,
        format=fmt,
        hook=hook,
        visual_description=f"{angle}-themed {fmt.value} showing a group class in progress",
        primary_text=f"{hook} Join Apex Fitness and get your first class free.",
        headline=f"{angle.title()} Starts Here",
        description="No contracts. Cancel anytime.",
        cta="Sign Up",
        emotional_angle=angle,
        problem_stated="Struggling to stay consistent with workouts alone" if "problem" in angle else None,
        desire_stated="Feel strong and confident in 90 days",
        proof_elements=["500+ 5-star reviews", "Featured in Austin Fit Magazine"] if has_proof else [],
        offer_stated="First class free",
        first_used_date=first_used,
    )


def _audience(audience_type: AudienceType, desc: str) -> AudienceDefinition:
    return AudienceDefinition(
        audience_type=audience_type,
        description=desc,
        age_min=25,
        age_max=45,
        genders=Gender.ALL,
        locations=["Austin, TX"],
        placements=[Placement.FEED, Placement.STORY, Placement.REELS],
        devices=[],
        interests=["fitness", "wellness"] if audience_type == AudienceType.INTEREST else [],
        lookalike_source="past_customers" if audience_type == AudienceType.LOOKALIKE else None,
        lookalike_pct=0.03 if audience_type == AudienceType.LOOKALIKE else None,
        estimated_audience_size=250_000,
    )


def _stage_for_roll(rng: random.Random, qualified_rate: float, close_rate: float) -> FunnelStage:
    roll = rng.random()
    if roll < close_rate:
        return FunnelStage.SALE
    if roll < qualified_rate:
        return FunnelStage.QUALIFIED
    if roll < qualified_rate + 0.25:
        return FunnelStage.CONTACTED
    return FunnelStage.LEAD


def _build_scenario(
    *,
    scenario_key: str,
    campaign_name: str,
    seed: int,
    days: int,
    daily_budget: float,
    cpm_base: float,
    ctr_base: float,
    lp_view_rate: float,
    lead_conv_rate: float,
    qualified_rate: float,
    close_rate: float,
    frequency_base: float,
    ctr_trend_per_day: float = 0.0,
    frequency_growth_per_day: float = 0.0,
    cpl_variance: float = 0.10,
    anomaly: str | None = None,
    angle: str = "aspiration",
    reference_date: date | None = None,
) -> MockAccountData:
    rng = random.Random(seed)
    reference_date = reference_date or date.today()
    start_date = reference_date - timedelta(days=days - 1)

    campaign_id = f"cmp_{scenario_key}"
    ad_set_id = f"adset_{scenario_key}"
    ad_id = f"ad_{scenario_key}"

    campaign = Campaign(
        campaign_id=campaign_id,
        name=campaign_name,
        objective=CampaignObjective.LEAD_GENERATION,
        status=CampaignStatus.ACTIVE,
        daily_budget=daily_budget,
        created_date=start_date,
    )
    audience_type = AudienceType.LOOKALIKE if "low_ctr" in scenario_key else AudienceType.BROAD
    ad_set = AdSet(
        ad_set_id=ad_set_id,
        campaign_id=campaign_id,
        name=f"{campaign_name} - Ad Set 1",
        daily_budget=daily_budget,
        audience=_audience(audience_type, f"{campaign_name} primary audience"),
        status=CampaignStatus.ACTIVE,
        created_date=start_date,
    )
    ad = Ad(
        ad_id=ad_id,
        ad_set_id=ad_set_id,
        name=f"{campaign_name} - Ad 1",
        creative_id=f"cr_{ad_id}",
        status=CampaignStatus.ACTIVE,
        created_date=start_date,
    )
    creative = _creative(
        ad_id,
        angle=angle,
        hook="Tired of gyms that don't hold you accountable?" if "problem" in angle else "Feel unstoppable.",
        fmt=CreativeFormat.SINGLE_VIDEO,
        has_proof="poor_conversion" not in scenario_key,
        first_used=start_date,
    )

    insights: list[DailyInsight] = []
    leads: list[Lead] = []
    sales: list[Sale] = []

    for day_index in range(days):
        current_date = start_date + timedelta(days=day_index)

        ctr = max(0.001, ctr_base + ctr_trend_per_day * day_index + rng.uniform(-0.001, 0.001))
        frequency = frequency_base + frequency_growth_per_day * day_index

        spend = daily_budget * rng.uniform(0.95, 1.0)
        impressions = int((spend / cpm_base) * 1000) if cpm_base else 0
        reach = int(impressions / max(frequency, 1.0))
        clicks = int(impressions * ctr)
        landing_page_views = int(clicks * lp_view_rate)
        leads_today = max(0, round(landing_page_views * lead_conv_rate * rng.uniform(1 - cpl_variance, 1 + cpl_variance)))

        qualified_today = 0
        sales_today = 0
        revenue_today = 0.0

        day_leads: list[Lead] = []
        for _ in range(leads_today):
            stage = _stage_for_roll(rng, qualified_rate, close_rate)
            lead_id = f"lead_{uuid.uuid4().hex[:10]}"
            created_at = datetime.combine(current_date, datetime.min.time(), tzinfo=UTC) + timedelta(
                hours=rng.uniform(6, 20)
            )
            lead = Lead(
                lead_id=lead_id,
                ad_id=ad_id,
                ad_set_id=ad_set_id,
                campaign_id=campaign_id,
                created_at=created_at,
                stage=stage,
                contacted_at=created_at + timedelta(hours=2) if stage.order >= FunnelStage.CONTACTED.order else None,
                qualified_at=created_at + timedelta(hours=6) if stage.order >= FunnelStage.QUALIFIED.order else None,
                appointment_at=created_at + timedelta(days=1) if stage.order >= FunnelStage.APPOINTMENT.order else None,
                response_time_minutes=rng.uniform(15, 240),
            )
            day_leads.append(lead)
            if stage.order >= FunnelStage.QUALIFIED.order:
                qualified_today += 1
            if stage == FunnelStage.SALE:
                sale_amount = AVG_DEAL_VALUE * rng.uniform(0.9, 1.3)
                sales.append(
                    Sale(
                        sale_id=f"sale_{uuid.uuid4().hex[:10]}",
                        lead_id=lead_id,
                        ad_id=ad_id,
                        ad_set_id=ad_set_id,
                        campaign_id=campaign_id,
                        sale_date=current_date,
                        amount=round(sale_amount, 2),
                    )
                )
                sales_today += 1
                revenue_today += sale_amount

        leads.extend(day_leads)

        insight = DailyInsight(
            entity_level=EntityLevel.AD,
            entity_id=ad_id,
            campaign_id=campaign_id,
            ad_set_id=ad_set_id,
            ad_id=ad_id,
            date=current_date,
            spend=round(spend, 2),
            impressions=impressions,
            reach=max(reach, 0),
            clicks=clicks,
            landing_page_views=landing_page_views,
            leads=leads_today,
            qualified_leads=qualified_today,
            sales=sales_today,
            revenue=round(revenue_today, 2),
        )
        insights.append(insight)

    if anomaly == "tracking_anomaly":
        insights = _inject_tracking_anomalies(insights)

    business_objective = _business_objective()
    return MockAccountData(
        business_objective=business_objective,
        campaigns=[campaign],
        ad_sets=[ad_set],
        ads=[ad],
        creatives=[creative],
        insights=insights,
        leads=leads,
        sales=sales,
    )


def _inject_tracking_anomalies(insights: list[DailyInsight]) -> list[DailyInsight]:
    """Corrupts two days in a realistic, detectable way — never silently."""
    if len(insights) < 4:
        return insights
    updated = list(insights)

    mid = len(updated) // 2
    anomaly_day = updated[mid]
    updated[mid] = anomaly_day.model_copy(update={"revenue": max(anomaly_day.revenue or 0.0, 500.0), "leads": 0, "qualified_leads": 0, "sales": 0})

    late = updated[-2]
    updated[-2] = late.model_copy(update={"spend": max(late.spend, 50.0), "impressions": 0, "clicks": 0, "landing_page_views": 0, "leads": 0})

    return updated


SCENARIO_BUILDERS = {
    "strong_campaign": lambda ref: _build_scenario(
        scenario_key="strong_campaign", campaign_name="Strong Performer - Group Classes", seed=1,
        days=DEFAULT_WINDOW_DAYS, daily_budget=200.0, cpm_base=14.0, ctr_base=0.018, lp_view_rate=0.75,
        lead_conv_rate=0.14, qualified_rate=0.55, close_rate=0.22, frequency_base=1.6, angle="aspiration",
        reference_date=ref,
    ),
    "high_cpl_campaign": lambda ref: _build_scenario(
        scenario_key="high_cpl_campaign", campaign_name="Rising CPL - Weekend Bootcamp", seed=2,
        days=DEFAULT_WINDOW_DAYS, daily_budget=250.0, cpm_base=22.0, ctr_base=0.012, lp_view_rate=0.65,
        lead_conv_rate=0.06, qualified_rate=0.35, close_rate=0.10, frequency_base=2.2,
        ctr_trend_per_day=-0.0004, angle="urgency", reference_date=ref,
    ),
    "cheap_low_quality_leads": lambda ref: _build_scenario(
        scenario_key="cheap_low_quality_leads", campaign_name="Cheap Volume - Free Trial Blast", seed=3,
        days=DEFAULT_WINDOW_DAYS, daily_budget=180.0, cpm_base=9.0, ctr_base=0.022, lp_view_rate=0.8,
        lead_conv_rate=0.22, qualified_rate=0.10, close_rate=0.02, frequency_base=1.8, angle="urgency",
        reference_date=ref,
    ),
    "creative_fatigue": lambda ref: _build_scenario(
        scenario_key="creative_fatigue", campaign_name="Fatigued Hook - 90 Day Challenge", seed=4,
        days=DEFAULT_WINDOW_DAYS, daily_budget=150.0, cpm_base=15.0, ctr_base=0.020, lp_view_rate=0.72,
        lead_conv_rate=0.12, qualified_rate=0.45, close_rate=0.15, frequency_base=2.0,
        ctr_trend_per_day=-0.0007, frequency_growth_per_day=0.12, angle="problem-first", reference_date=ref,
    ),
    "audience_saturation": lambda ref: _build_scenario(
        scenario_key="audience_saturation", campaign_name="Saturated Lookalike 1%", seed=5,
        days=DEFAULT_WINDOW_DAYS, daily_budget=220.0, cpm_base=18.0, ctr_base=0.016, lp_view_rate=0.7,
        lead_conv_rate=0.10, qualified_rate=0.40, close_rate=0.14, frequency_base=3.0,
        frequency_growth_per_day=0.18, angle="aspiration", reference_date=ref,
    ),
    "high_ctr_poor_conversion": lambda ref: _build_scenario(
        scenario_key="high_ctr_poor_conversion", campaign_name="Viral Hook - Poor Landing Page", seed=6,
        days=DEFAULT_WINDOW_DAYS, daily_budget=200.0, cpm_base=13.0, ctr_base=0.032, lp_view_rate=0.35,
        lead_conv_rate=0.05, qualified_rate=0.20, close_rate=0.05, frequency_base=1.9, angle="curiosity",
        reference_date=ref,
    ),
    "low_ctr_high_quality": lambda ref: _build_scenario(
        scenario_key="low_ctr_high_quality", campaign_name="Niche Lookalike - Serious Athletes", seed=7,
        days=DEFAULT_WINDOW_DAYS, daily_budget=160.0, cpm_base=20.0, ctr_base=0.008, lp_view_rate=0.78,
        lead_conv_rate=0.18, qualified_rate=0.65, close_rate=0.30, frequency_base=1.4, angle="problem-first",
        reference_date=ref,
    ),
    "insufficient_data": lambda ref: _build_scenario(
        scenario_key="insufficient_data", campaign_name="Brand New - Just Launched", seed=8,
        days=3, daily_budget=100.0, cpm_base=16.0, ctr_base=0.015, lp_view_rate=0.7,
        lead_conv_rate=0.10, qualified_rate=0.4, close_rate=0.15, frequency_base=1.1, angle="aspiration",
        reference_date=ref,
    ),
    "scaling_opportunity": lambda ref: _build_scenario(
        scenario_key="scaling_opportunity", campaign_name="Efficient & Stable - Ready to Scale", seed=9,
        days=DEFAULT_WINDOW_DAYS, daily_budget=180.0, cpm_base=12.0, ctr_base=0.021, lp_view_rate=0.77,
        lead_conv_rate=0.15, qualified_rate=0.58, close_rate=0.24, frequency_base=1.5,
        ctr_trend_per_day=0.0003, angle="aspiration", reference_date=ref,
    ),
    "tracking_anomaly": lambda ref: _build_scenario(
        scenario_key="tracking_anomaly", campaign_name="Anomalous Data - Pixel Issue Suspected", seed=10,
        days=DEFAULT_WINDOW_DAYS, daily_budget=150.0, cpm_base=15.0, ctr_base=0.017, lp_view_rate=0.7,
        lead_conv_rate=0.11, qualified_rate=0.4, close_rate=0.15, frequency_base=1.7, angle="aspiration",
        anomaly="tracking_anomaly", reference_date=ref,
    ),
}


def generate_full_mock_account(reference_date: date | None = None) -> MockAccountData:
    """Builds all 10 scenarios into a single combined mock account."""
    ref = reference_date or date.today()
    merged: MockAccountData | None = None
    for builder in SCENARIO_BUILDERS.values():
        scenario_data = builder(ref)
        if merged is None:
            merged = scenario_data
        else:
            merged.campaigns += scenario_data.campaigns
            merged.ad_sets += scenario_data.ad_sets
            merged.ads += scenario_data.ads
            merged.creatives += scenario_data.creatives
            merged.insights += scenario_data.insights
            merged.leads += scenario_data.leads
            merged.sales += scenario_data.sales
    assert merged is not None
    return merged


def generate_scenario(scenario_key: str, reference_date: date | None = None) -> MockAccountData:
    if scenario_key not in SCENARIO_BUILDERS:
        raise ValueError(f"Unknown mock scenario '{scenario_key}'. Available: {sorted(SCENARIO_BUILDERS)}")
    return SCENARIO_BUILDERS[scenario_key](reference_date or date.today())


def default_business_objective() -> BusinessObjective:
    """Public accessor for the shared mock business context."""
    return _business_objective()


def available_scenarios() -> list[str]:
    return sorted(SCENARIO_BUILDERS.keys())
