"""Rich agent catalog: tier, capabilities, inputs, outputs, dependencies,
priority, and enabled status for all 70 agents (16 core + 54 V2 specialists
+ Guardian).

`app.agents.AGENT_REGISTRY` (name -> class) is what the orchestrator uses
to instantiate agents. This module is the documentation/observability
layer on top of it — routing decisions still live in
`app.orchestration.router`; this catalog explains *why* an agent exists,
what tier it belongs to, and what it expects to have run before it, so a
human (or future Claude Code session) can reason about the whole system
without reading 70 files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.agents import AGENT_REGISTRY


class Tier(str, Enum):
    TIER_0_CONTROL = "T0_control"
    TIER_1_BUSINESS_INTELLIGENCE = "T1_business_intelligence"
    TIER_2_PERFORMANCE = "T2_performance"
    TIER_3_CREATIVE = "T3_creative"
    TIER_4_CONTENT = "T4_content"
    TIER_5_FUNNEL = "T5_funnel"
    TIER_6_EXPERIMENTATION = "T6_experimentation"
    TIER_7_INTELLIGENCE = "T7_intelligence"


@dataclass(frozen=True)
class AgentMetadata:
    agent_id: str
    name: str
    purpose: str
    tier: Tier
    capabilities: list[str] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list, metadata={"doc": "Agent names expected to have run first"})
    priority: int = 5
    enabled: bool = True


AGENT_CATALOG: dict[str, AgentMetadata] = {
    # -- Tier 0: control --------------------------------------------------
    "guardian": AgentMetadata(
        "16", "guardian", "Reviews every recommendation for safety; has veto power.", Tier.TIER_0_CONTROL,
        capabilities=["safety_review", "veto"], inputs=["recommendations"], outputs=["guardian_decisions"],
        dependencies=["optimization"], priority=0,
    ),
    # -- Tier 1: business intelligence -------------------------------------
    "business_intelligence": AgentMetadata(
        "01", "business_intelligence", "Establishes business economics and KPI targets.", Tier.TIER_1_BUSINESS_INTELLIGENCE,
        capabilities=["kpi_configuration"], outputs=["business_objective_summary"], priority=0,
    ),
    "attribution": AgentMetadata(
        "13", "attribution", "Connects ads to leads/sales/revenue; flags broken attribution.", Tier.TIER_1_BUSINESS_INTELLIGENCE,
        capabilities=["attribution"], inputs=["leads", "sales"], outputs=["attribution_findings"], priority=2,
    ),
    "lead_quality": AgentMetadata(
        "08", "lead_quality", "Walks the full lead-to-revenue funnel; prioritizes business value over cheap leads.", Tier.TIER_1_BUSINESS_INTELLIGENCE,
        capabilities=["funnel_analysis"], inputs=["leads"], outputs=["lead_quality_findings"], priority=2,
    ),
    "funnel_economics": AgentMetadata(
        "49", "funnel_economics", "Computes full-funnel $ economics; identifies the highest-cost bottleneck.", Tier.TIER_1_BUSINESS_INTELLIGENCE,
        capabilities=["economics"], inputs=["insights", "leads"], outputs=["stage_costs", "bottleneck"], priority=2,
    ),
    "sales_conversion": AgentMetadata(
        "35", "sales_conversion", "Diagnoses Contact->Qualified->Appointment->Sale bottlenecks.", Tier.TIER_1_BUSINESS_INTELLIGENCE,
        capabilities=["sales_funnel_analysis"], inputs=["leads"], outputs=["sales_bottleneck"], priority=3,
    ),
    # -- Tier 2: performance ------------------------------------------------
    "data_analyst": AgentMetadata(
        "02", "data_analyst", "Trends, winners/losers, anomalies, missing data.", Tier.TIER_2_PERFORMANCE,
        capabilities=["trend_analysis"], inputs=["insights"], outputs=["performance_findings"], priority=1,
    ),
    "campaign_strategist": AgentMetadata(
        "03", "campaign_strategist", "Budget distribution, fragmentation, consolidation.", Tier.TIER_2_PERFORMANCE,
        capabilities=["structure_analysis"], inputs=["campaigns", "ad_sets"], priority=3,
    ),
    "audience_intelligence": AgentMetadata(
        "04", "audience_intelligence", "Saturation/fatigue and audience-type comparison.", Tier.TIER_2_PERFORMANCE,
        capabilities=["audience_analysis"], inputs=["ad_sets", "insights"], priority=2,
    ),
    "budget_scaling": AgentMetadata(
        "11", "budget_scaling", "INCREASE/DECREASE/REALLOCATE/MAINTAIN decisions.", Tier.TIER_2_PERFORMANCE,
        capabilities=["scaling_decision"], inputs=["insights"], dependencies=["data_analyst"], priority=2,
    ),
    "forecasting": AgentMetadata(
        "12", "forecasting", "Transparent trend-projection forecasting.", Tier.TIER_2_PERFORMANCE,
        capabilities=["forecasting"], inputs=["insights"], priority=4,
    ),
    "anomaly_detection": AgentMetadata(
        "42", "anomaly_detection", "z-score pass across spend/leads/CPL/CTR/CPM/CPC.", Tier.TIER_2_PERFORMANCE,
        capabilities=["statistics", "anomaly_detection"], inputs=["insights"], priority=1,
    ),
    "statistical_analysis": AgentMetadata(
        "40", "statistical_analysis", "Sample-size caution pass over trend findings.", Tier.TIER_2_PERFORMANCE,
        capabilities=["statistics"], dependencies=["data_analyst"], priority=3,
    ),
    "time_series_trend": AgentMetadata(
        "41", "time_series_trend", "Gradual deterioration vs. sudden-change detection.", Tier.TIER_2_PERFORMANCE,
        capabilities=["trend_analysis"], inputs=["insights"], priority=3,
    ),
    "tracking_data_quality": AgentMetadata(
        "39", "tracking_data_quality", "Duplicate leads, out-of-order timestamps, missing data.", Tier.TIER_2_PERFORMANCE,
        capabilities=["data_quality"], inputs=["leads"], priority=0,
    ),
    "market_condition": AgentMetadata(
        "43", "market_condition", "External market/seasonality context, only when supplied.", Tier.TIER_2_PERFORMANCE,
        capabilities=["external_context"], inputs=["competitor_research"], priority=4,
    ),
    "marginal_performance": AgentMetadata(
        "50", "marginal_performance", "High vs low spend day comparison as a marginal-cost proxy.", Tier.TIER_2_PERFORMANCE,
        capabilities=["economics"], inputs=["insights"], priority=3,
    ),
    "scaling_risk": AgentMetadata(
        "51", "scaling_risk", "SAFE/CAUTION/HIGH_RISK verdict before scaling.", Tier.TIER_2_PERFORMANCE,
        capabilities=["risk_assessment"], dependencies=["creative_fatigue_prediction", "sales_conversion"], priority=1,
    ),
    "budget_allocation_simulator": AgentMetadata(
        "52", "budget_allocation_simulator", "Simulates budget-reallocation scenarios (forecast, not fact).", Tier.TIER_2_PERFORMANCE,
        capabilities=["simulation"], inputs=["campaigns", "insights"], priority=4,
    ),
    "stop_pause_decision": AgentMetadata(
        "53", "stop_pause_decision", "Determines whether pausing is defensible; avoids premature pausing.", Tier.TIER_2_PERFORMANCE,
        capabilities=["decision"], inputs=["insights"], priority=2,
    ),
    "recovery": AgentMetadata(
        "54", "recovery", "WHAT/WHEN/WHERE/WHY diagnosis + recovery plan after deterioration.", Tier.TIER_2_PERFORMANCE,
        capabilities=["diagnosis"], dependencies=["data_analyst"], priority=1,
    ),
    "post_change_verification": AgentMetadata(
        "55", "post_change_verification", "Before vs. after comparison: IMPROVED/UNCHANGED/WORSE/INCONCLUSIVE.", Tier.TIER_2_PERFORMANCE,
        capabilities=["verification"], inputs=["baseline_insights"], priority=2, enabled=True,
    ),
    "rollback_decision": AgentMetadata(
        "56", "rollback_decision", "Determines whether rollback should be considered.", Tier.TIER_2_PERFORMANCE,
        capabilities=["decision"], dependencies=["post_change_verification"], priority=1,
    ),
    # -- Tier 3: creative ---------------------------------------------------
    "creative_intelligence": AgentMetadata(
        "05", "creative_intelligence", "Creative fatigue signal + winning-pattern detection.", Tier.TIER_3_CREATIVE,
        capabilities=["creative_analysis"], inputs=["creatives", "insights"], priority=2,
    ),
    "hook_engine": AgentMetadata(
        "21", "hook_engine", "Generates/evaluates hooks across 11 angle categories.", Tier.TIER_3_CREATIVE,
        capabilities=["generation"], dependencies=["customer_avatar", "customer_language_mining"], priority=3,
    ),
    "content_angle": AgentMetadata(
        "22", "content_angle", "Structured creative angle library; tracks tested angles.", Tier.TIER_3_CREATIVE,
        capabilities=["angle_tracking"], inputs=["creatives"], priority=3,
    ),
    "ugc_strategist": AgentMetadata(
        "23", "ugc_strategist", "UGC concepts (HOOK->PROBLEM->EXPERIENCE->SOLUTION->PROOF->CTA).", Tier.TIER_3_CREATIVE,
        capabilities=["generation"], dependencies=["customer_avatar"], priority=4,
    ),
    "video_script": AgentMetadata(
        "24", "video_script", "Duration-scaled video scripts (15-90s).", Tier.TIER_3_CREATIVE,
        capabilities=["generation"], priority=4,
    ),
    "static_creative_concept": AgentMetadata(
        "25", "static_creative_concept", "Static/carousel/infographic/comparison concepts.", Tier.TIER_3_CREATIVE,
        capabilities=["generation"], priority=4,
    ),
    "creative_scoring": AgentMetadata(
        "28", "creative_scoring", "10-dimension prioritization scoring (not a performance guarantee).", Tier.TIER_3_CREATIVE,
        capabilities=["scoring"], inputs=["creatives"], priority=3,
    ),
    "creative_fatigue_prediction": AgentMetadata(
        "26", "creative_fatigue_prediction", "Multi-signal LOW/MEDIUM/HIGH/CRITICAL fatigue classification.", Tier.TIER_3_CREATIVE,
        capabilities=["fatigue_prediction"], inputs=["insights", "creatives"], priority=1,
    ),
    "creative_refresh": AgentMetadata(
        "27", "creative_refresh", "Controlled refresh preserving the winning pattern.", Tier.TIER_3_CREATIVE,
        capabilities=["generation"], dependencies=["creative_fatigue_prediction", "creative_intelligence"], priority=2,
    ),
    "creative_diversity": AgentMetadata(
        "29", "creative_diversity", "Flags overused hook/angle/format patterns.", Tier.TIER_3_CREATIVE,
        capabilities=["diversity_tracking"], inputs=["creatives"], priority=3,
    ),
    "content_calendar": AgentMetadata(
        "30", "content_calendar", "Structured weekly creative production plan; tracks lifecycle status.", Tier.TIER_3_CREATIVE,
        capabilities=["production_planning"], dependencies=["creative_fatigue_prediction", "content_angle"], priority=3,
    ),
    # -- Tier 4: content ------------------------------------------------------
    "copy_intelligence": AgentMetadata(
        "06", "copy_intelligence", "Hypothesis-driven copy variation for weak-CTR ads.", Tier.TIER_4_CONTENT,
        capabilities=["generation"], inputs=["ads", "insights"], priority=3,
    ),
    "customer_language_mining": AgentMetadata(
        "18", "customer_language_mining", "Extracts real objection/desire/emotion language from supplied text.", Tier.TIER_4_CONTENT,
        capabilities=["language_mining"], inputs=["customer_language_sources"], priority=2,
    ),
    "brand_voice": AgentMetadata(
        "62", "brand_voice", "Maintains the reusable brand voice profile.", Tier.TIER_4_CONTENT,
        capabilities=["brand_governance"], outputs=["context.brand_voice"], priority=2,
    ),
    "content_quality": AgentMetadata(
        "63", "content_quality", "Rejects hype/generic generated content.", Tier.TIER_4_CONTENT,
        capabilities=["quality_review"], dependencies=["hook_engine", "ugc_strategist", "video_script", "static_creative_concept"], priority=1,
    ),
    "human_like_copy_editor": AgentMetadata(
        "64", "human_like_copy_editor", "Deterministic hype-word cleanup (not an LLM rewrite).", Tier.TIER_4_CONTENT,
        capabilities=["editing"], dependencies=["content_quality"], priority=2,
    ),
    "creative_brief": AgentMetadata(
        "65", "creative_brief", "Assembles a complete production-ready creative brief.", Tier.TIER_4_CONTENT,
        capabilities=["synthesis"], dependencies=["customer_avatar", "hook_engine", "content_angle"], priority=2,
    ),
    "creative_production_prioritizer": AgentMetadata(
        "66", "creative_production_prioritizer", "Ranks generated concepts into a production queue.", Tier.TIER_4_CONTENT,
        capabilities=["prioritization"], dependencies=["opportunity_discovery"], priority=3,
    ),
    # -- Tier 5: funnel ---------------------------------------------------------
    "funnel_diagnostics": AgentMetadata(
        "09", "funnel_diagnostics", "Weakest ad-to-lead funnel step + root-cause categories.", Tier.TIER_5_FUNNEL,
        capabilities=["funnel_diagnosis"], inputs=["insights"], priority=1,
    ),
    "landing_page_copy": AgentMetadata(
        "31", "landing_page_copy", "Ad-to-landing-page message-match check + copy checklist.", Tier.TIER_5_FUNNEL,
        capabilities=["message_match"], inputs=["creatives"], priority=3,
    ),
    "landing_page_cro": AgentMetadata(
        "32", "landing_page_cro", "Diagnoses landing page conversion problems from real funnel data.", Tier.TIER_5_FUNNEL,
        capabilities=["cro"], inputs=["insights"], priority=2,
    ),
    "form_optimization": AgentMetadata(
        "33", "form_optimization", "Balances form conversion rate vs. lead quality.", Tier.TIER_5_FUNNEL,
        capabilities=["form_analysis"], inputs=["insights"], priority=3,
    ),
    "lead_response": AgentMetadata(
        "34", "lead_response", "Response time / contact rate — sales bottleneck check.", Tier.TIER_5_FUNNEL,
        capabilities=["response_analysis"], inputs=["leads"], priority=2,
    ),
    "crm_intelligence": AgentMetadata(
        "36", "crm_intelligence", "Connects ad source to CRM lead/sale/revenue status.", Tier.TIER_5_FUNNEL,
        capabilities=["crm_analysis"], inputs=["crm_records"], priority=3, enabled=True,
    ),
    "lead_scoring": AgentMetadata(
        "37", "lead_scoring", "Explainable per-campaign lead quality score.", Tier.TIER_5_FUNNEL,
        capabilities=["scoring"], inputs=["leads"], priority=3,
    ),
    "sales_feedback_loop": AgentMetadata(
        "38", "sales_feedback_loop", "Feeds sale revenue back to the originating creative angle.", Tier.TIER_5_FUNNEL,
        capabilities=["feedback_loop"], inputs=["sales"], priority=2,
    ),
    # -- Tier 6: experimentation -------------------------------------------------
    "experimentation": AgentMetadata(
        "10", "experimentation", "Builds pre-registered experiments; blocks duplicates.", Tier.TIER_6_EXPERIMENTATION,
        capabilities=["experiment_design"], priority=1,
    ),
    "experiment_portfolio": AgentMetadata(
        "67", "experiment_portfolio", "Prevents too many simultaneous tests running at once.", Tier.TIER_6_EXPERIMENTATION,
        capabilities=["portfolio_management"], inputs=["existing_experiments", "new_experiments"], priority=1,
    ),
    "exploration_exploitation": AgentMetadata(
        "68", "exploration_exploitation", "Balances exploit (scale winners) vs. explore (test new).", Tier.TIER_6_EXPERIMENTATION,
        capabilities=["portfolio_balance"], inputs=["recommendations", "creatives"], priority=2,
    ),
    "offer_psychology": AgentMetadata(
        "07", "offer_psychology", "Detects when the offer, not the ad, is the root cause of a performance gap.", Tier.TIER_6_EXPERIMENTATION,
        capabilities=["root_cause_analysis"], inputs=["insights"], priority=2,
    ),
    "offer_testing": AgentMetadata(
        "45", "offer_testing", "Designs price/bundle/bonus/guarantee/trial experiments.", Tier.TIER_6_EXPERIMENTATION,
        capabilities=["experiment_design"], inputs=["business_objective"], priority=3,
    ),
    # -- Tier 7: intelligence -----------------------------------------------------
    "competitor_intelligence": AgentMetadata(
        "14", "competitor_intelligence", "Positioning/messaging patterns, only with supplied research.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["market_research"], inputs=["competitor_research"], priority=4,
    ),
    "optimization": AgentMetadata(
        "15", "optimization", "Converts findings into prioritized, structured recommendations.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["decision_synthesis"], dependencies=["experimentation"], priority=0,
    ),
    "customer_avatar": AgentMetadata(
        "17", "customer_avatar", "Observed/inferred/hypothesized customer avatar profile.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["avatar_building"], inputs=["business_objective", "creatives"], priority=2,
    ),
    "buyer_awareness": AgentMetadata(
        "19", "buyer_awareness", "Classifies audience awareness level; recommends message structure.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["awareness_classification"], dependencies=["customer_avatar"], priority=2,
    ),
    "customer_journey": AgentMetadata(
        "20", "customer_journey", "Maps journey-stage messaging coverage/gaps.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["journey_mapping"], inputs=["ad_sets"], priority=3,
    ),
    "positioning": AgentMetadata(
        "44", "positioning", "UVP/differentiation analysis.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["positioning_analysis"], priority=3,
    ),
    "objection_mining": AgentMetadata(
        "46", "objection_mining", "Mines real objections into FAQ/ad/landing-page content.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["objection_mining"], inputs=["customer_language_sources"], priority=3,
    ),
    "social_proof": AgentMetadata(
        "47", "social_proof", "Catalogs legitimate proof; never fabricates it.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["proof_cataloging"], inputs=["creatives"], priority=3,
    ),
    "offer_creative_matching": AgentMetadata(
        "48", "offer_creative_matching", "Maps offer -> audience -> angle -> hook -> format -> CTA.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["matching"], inputs=["creatives", "ad_sets"], priority=4,
    ),
    "learning_synthesis": AgentMetadata(
        "57", "learning_synthesis", "Combines cross-agent findings into strategic patterns.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["synthesis"], dependencies=["sales_feedback_loop", "audience_intelligence", "creative_intelligence"], priority=2,
    ),
    "knowledge_graph": AgentMetadata(
        "58", "knowledge_graph", "Audience->creative->hook->offer->campaign->sales relationship graph.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["graph_building"], priority=4,
    ),
    "creative_library_manager": AgentMetadata(
        "59", "creative_library_manager", "Catalogs library with performance/fatigue status; flags duplicates.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["library_management"], dependencies=["creative_fatigue_prediction"], priority=3,
    ),
    "opportunity_discovery": AgentMetadata(
        "69", "opportunity_discovery", "Underfunded winners, untested audiences/angles, funnel gaps.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["opportunity_scan"], dependencies=["content_angle", "funnel_economics"], priority=2,
    ),
    "ad_policy_compliance": AgentMetadata(
        "60", "ad_policy_compliance", "Flags policy-risk language. Risk detector, not an approval guarantee.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["policy_check"], inputs=["creatives"], priority=1,
    ),
    "brand_safety": AgentMetadata(
        "61", "brand_safety", "Checks creative against brand voice words-to-avoid; flags contradictions.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["brand_check"], dependencies=["brand_voice"], priority=2,
    ),
    "executive_strategy": AgentMetadata(
        "70", "executive_strategy", "NOW/NEXT/LATER synthesis of Guardian-cleared recommendations.", Tier.TIER_7_INTELLIGENCE,
        capabilities=["strategic_synthesis"], dependencies=["optimization", "guardian"], priority=0,
    ),
}


def get_metadata(agent_name: str) -> AgentMetadata | None:
    return AGENT_CATALOG.get(agent_name)


def agents_by_tier(tier: Tier) -> list[str]:
    return sorted(name for name, meta in AGENT_CATALOG.items() if meta.tier == tier)


def enabled_agents() -> list[str]:
    return sorted(name for name, meta in AGENT_CATALOG.items() if meta.enabled)


def validate_catalog_matches_registry() -> list[str]:
    """Returns a list of discrepancies between the catalog and the actual
    instantiable registry — empty means every registered agent (+ Guardian)
    has metadata, and every catalog entry corresponds to a real agent."""
    registry_names = set(AGENT_REGISTRY) | {"guardian"}
    catalog_names = set(AGENT_CATALOG)
    missing_from_catalog = registry_names - catalog_names
    missing_from_registry = catalog_names - registry_names
    problems = []
    if missing_from_catalog:
        problems.append(f"In AGENT_REGISTRY but not AGENT_CATALOG: {sorted(missing_from_catalog)}")
    if missing_from_registry:
        problems.append(f"In AGENT_CATALOG but not AGENT_REGISTRY: {sorted(missing_from_registry)}")
    return problems
