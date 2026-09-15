from __future__ import annotations

from app.orchestration.router import DEFAULT_ROUTE, ROUTES, available_triggers, route_for_trigger


def test_cpl_increase_route_matches_spec_example():
    route = route_for_trigger("cpl_increase")
    assert route == [
        "data_analyst",
        "creative_intelligence",
        "audience_intelligence",
        "funnel_diagnostics",
        "lead_quality",
    ]


def test_cheap_leads_poor_sales_route():
    route = route_for_trigger("cheap_leads_poor_sales")
    assert route[0] == "lead_quality"
    assert "offer_psychology" in route
    assert "attribution" in route


def test_ctr_decrease_route():
    route = route_for_trigger("ctr_decrease")
    assert "creative_intelligence" in route
    assert "copy_intelligence" in route


def test_unknown_trigger_falls_back_to_default_not_everything():
    route = route_for_trigger("some_unrecognized_trigger")
    assert route == ROUTES[DEFAULT_ROUTE]
    # The router must NOT blindly include every possible agent.
    assert "competitor_intelligence" not in route
    assert "experimentation" not in route
    assert "optimization" not in route


def test_available_triggers_nonempty():
    assert "cpl_increase" in available_triggers()
