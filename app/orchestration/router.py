"""Intelligent agent routing.

The orchestrator must NOT blindly call every agent for every problem. This
module maps a `trigger` (the type of problem/request) to the ordered list of
specialist agents actually relevant to diagnosing it. `business_intelligence`
always runs first (outside this routing table) and `optimization` +
`guardian` always run last (also outside this table) — this table only
covers the diagnostic middle of the pipeline.
"""

from __future__ import annotations

# Ordered: each list is a diagnostic sequence, not an unordered set — later
# agents in a route can use earlier agents' findings (e.g. Experimentation
# consumes tags set by Creative/Copy Intelligence).
ROUTES: dict[str, list[str]] = {
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
    # Periodic/manual full review with no specific symptom reported.
    "scheduled_review": [
        "data_analyst",
        "campaign_strategist",
        "audience_intelligence",
        "creative_intelligence",
        "lead_quality",
        "funnel_diagnostics",
        "budget_scaling",
        "forecasting",
        "attribution",
    ],
}

DEFAULT_ROUTE = "scheduled_review"


def route_for_trigger(trigger: str) -> list[str]:
    """Returns the ordered diagnostic agent sequence for a given trigger.

    Falls back to the general scheduled-review sequence for an unrecognized
    trigger rather than either crashing or running literally every agent —
    competitor_intelligence and experimentation are deliberately excluded
    from every route here because they are conditionally triggered (see
    `workflow.py`): experimentation only runs when a prior agent raised a
    testable hypothesis, and competitor_intelligence only runs when external
    research was actually supplied.
    """
    return list(ROUTES.get(trigger, ROUTES[DEFAULT_ROUTE]))


def available_triggers() -> list[str]:
    return sorted(ROUTES.keys())
