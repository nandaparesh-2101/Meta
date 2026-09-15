"""Intelligent agent routing.

The orchestrator must NOT blindly call every agent for every problem. This
module maps a `trigger` (the type of problem/request) to the ordered list of
specialist agents actually relevant to diagnosing it. `business_intelligence`
always runs first (outside this routing table) and `experimentation` +
`optimization` + `guardian` + `executive_strategy` always run last (also
outside this table) — this table only covers the diagnostic middle of the
pipeline.

V2 note: adding 54 new specialist agents (see `app.agents.registry` for the
full catalog) did not change this principle. Every route below is still a
deliberately curated sequence; `scheduled_review` is intentionally the
broadest one (a full periodic health check), not a stand-in for "run
everything" on every trigger.
"""

from __future__ import annotations

# Ordered: each list is a diagnostic sequence, not an unordered set — later
# agents in a route can use earlier agents' findings (e.g. Experimentation
# consumes tags set by Creative/Copy Intelligence; content_quality consumes
# tags set by the creative-generation agents that ran earlier in the same
# route).
ROUTES: dict[str, list[str]] = {
    # -- Core V1 routes ------------------------------------------------------
    # CPL increased: is it creative fatigue, audience saturation, or a funnel/lead-quality issue?
    "cpl_increase": [
        "data_analyst",
        "creative_intelligence",
        "audience_intelligence",
        "funnel_diagnostics",
        "lead_quality",
    ],
    # Cheap leads but poor sales: quality/funnel/offer/attribution, not the ad itself.
    "cheap_leads_poor_sales": [
        "lead_quality",
        "funnel_diagnostics",
        "offer_psychology",
        "attribution",
    ],
    # CTR decreased: creative/copy/audience — the top-of-funnel levers.
    "ctr_decrease": [
        "data_analyst",
        "creative_intelligence",
        "copy_intelligence",
        "audience_intelligence",
    ],
    # Explicit ask: "should we scale this?"
    "scaling_review": [
        "data_analyst",
        "campaign_strategist",
        "budget_scaling",
        "forecasting",
    ],
    # Explicit ask: "is this creative fatigued?"
    "creative_fatigue_check": [
        "data_analyst",
        "creative_intelligence",
        "copy_intelligence",
    ],
    # Explicit ask: "why aren't leads converting to sales?"
    "funnel_investigation": [
        "funnel_diagnostics",
        "lead_quality",
        "offer_psychology",
        "attribution",
    ],

    # -- V2 expansion routes (spec section 3 examples) ------------------------
    # Creative performance problem.
    "creative_performance_problem": [
        "data_analyst",
        "creative_intelligence",
        "creative_fatigue_prediction",
        "creative_scoring",
        "content_quality",
        "creative_refresh",
    ],
    # Lead quality problem.
    "lead_quality_problem": [
        "lead_quality",
        "crm_intelligence",
        "sales_conversion",
        "sales_feedback_loop",
        "funnel_economics",
        "attribution",
    ],
    # Content creation request — the full generative pipeline from spec section 9:
    # Business Objective (always-first) -> Avatar -> Language -> Awareness ->
    # Pain/Desire (in avatar) -> Offer -> Winning Patterns -> Angle -> Hook ->
    # Brief -> Copy/Video/Static -> Quality -> Editor -> Policy -> Final.
    "content_creation_request": [
        "customer_avatar",
        "customer_language_mining",
        "buyer_awareness",
        "customer_journey",
        "offer_psychology",
        "creative_intelligence",
        "content_angle",
        "hook_engine",
        "creative_brief",
        "ugc_strategist",
        "video_script",
        "static_creative_concept",
        "copy_intelligence",
        "brand_voice",
        "content_quality",
        "human_like_copy_editor",
        "ad_policy_compliance",
        "brand_safety",
    ],
    # Scaling request.
    "scaling_request": [
        "data_analyst",
        "marginal_performance",
        "budget_scaling",
        "scaling_risk",
        "funnel_economics",
        "forecasting",
    ],
    # Sales-process-specific review (advertising looks fine — is sales converting it?).
    "sales_process_review": [
        "lead_response",
        "sales_conversion",
        "crm_intelligence",
        "lead_scoring",
        "sales_feedback_loop",
    ],
    # Offer/positioning experiment design request.
    "offer_experiment_request": [
        "offer_psychology",
        "positioning",
        "objection_mining",
        "social_proof",
        "offer_testing",
        "offer_creative_matching",
    ],
    # After a (future, approved) change: verify impact and decide on rollback.
    "post_change_review": [
        "post_change_verification",
        "rollback_decision",
    ],
    # Portfolio-level check: are we testing too much/too little, and what's overlooked?
    "portfolio_review": [
        "experiment_portfolio",
        "exploration_exploitation",
        "opportunity_discovery",
        "creative_production_prioritizer",
        "learning_synthesis",
        "knowledge_graph",
    ],

    # Periodic/manual full review with no specific symptom reported — the
    # broadest route by design, covering data quality/trend/anomaly checks
    # plus every operational area. Still not literally every agent (the
    # content-generation, offer-experiment, and portfolio-management agents
    # above are request-driven, not periodic-review concerns).
    "scheduled_review": [
        "data_analyst",
        "statistical_analysis",
        "time_series_trend",
        "campaign_strategist",
        "audience_intelligence",
        "creative_intelligence",
        "creative_fatigue_prediction",
        "creative_scoring",
        "creative_diversity",
        "content_calendar",
        "creative_library_manager",
        "lead_quality",
        "funnel_diagnostics",
        "landing_page_copy",
        "landing_page_cro",
        "form_optimization",
        "funnel_economics",
        "budget_scaling",
        "scaling_risk",
        "budget_allocation_simulator",
        "stop_pause_decision",
        "recovery",
        "forecasting",
        "attribution",
        "market_condition",
    ],
}

DEFAULT_ROUTE = "scheduled_review"

# Agents that always run in this fixed order, regardless of route, per
# `Orchestrator.run()`. Listed here (not executed here) purely so this
# module remains the single place documenting the full agent-selection
# policy for the whole system.
ALWAYS_FIRST = "business_intelligence"
ALWAYS_PREFLIGHT = ["tracking_data_quality", "anomaly_detection"]
ALWAYS_LAST = ["experimentation", "optimization", "guardian", "executive_strategy"]


def route_for_trigger(trigger: str) -> list[str]:
    """Returns the ordered diagnostic agent sequence for a given trigger.

    Falls back to the general scheduled-review sequence for an unrecognized
    trigger rather than either crashing or running literally every agent —
    competitor_intelligence is deliberately excluded from every route here
    because it only runs when external research was actually supplied (see
    `workflow.py`).
    """
    return list(ROUTES.get(trigger, ROUTES[DEFAULT_ROUTE]))


def available_triggers() -> list[str]:
    return sorted(ROUTES.keys())
