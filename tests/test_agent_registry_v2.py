from __future__ import annotations

from app.agents import AGENT_REGISTRY, GuardianAgent
from app.agents.registry import (
    AGENT_CATALOG,
    Tier,
    agents_by_tier,
    enabled_agents,
    validate_catalog_matches_registry,
)
from app.orchestration.router import ALWAYS_LAST, ALWAYS_PREFLIGHT, ROUTES


def test_registry_has_70_agents_total():
    # 69 instantiable via AGENT_REGISTRY + Guardian (different contract).
    assert len(AGENT_REGISTRY) == 69
    assert GuardianAgent.name == "guardian"
    assert len(AGENT_REGISTRY) + 1 == 70


def test_no_duplicate_agent_names():
    names = list(AGENT_REGISTRY.keys())
    assert len(names) == len(set(names)), "Agent names must be unique across the registry"


def test_catalog_matches_registry_exactly():
    problems = validate_catalog_matches_registry()
    assert problems == [], f"Catalog/registry mismatch: {problems}"


def test_every_tier_is_represented():
    for tier in Tier:
        assert agents_by_tier(tier), f"Tier {tier.value} has no agents assigned"


def test_all_catalog_entries_enabled_by_default():
    # Nothing should be silently disabled without a documented reason.
    assert set(enabled_agents()) == set(AGENT_CATALOG.keys())


def test_every_registered_agent_is_reachable_by_routing():
    """Every agent in AGENT_REGISTRY must appear in at least one route, the
    always-first/preflight/always-last lists, or be explicitly conditional
    (competitor_intelligence). No agent should be dead code."""
    covered = set()
    for route in ROUTES.values():
        covered.update(route)
    covered.update(ALWAYS_PREFLIGHT)
    covered.update(ALWAYS_LAST)
    covered.add("business_intelligence")
    covered.add("competitor_intelligence")  # conditional on supplied research

    unreachable = set(AGENT_REGISTRY.keys()) - covered
    assert unreachable == set(), f"Agents not reachable via any route: {unreachable}"


def test_v2_expansion_agent_count():
    """Confirms exactly 54 new agents were added on top of the 15 core
    specialists (business_intelligence through optimization)."""
    core_v1_names = {
        "business_intelligence", "data_analyst", "campaign_strategist", "audience_intelligence",
        "creative_intelligence", "copy_intelligence", "offer_psychology", "lead_quality",
        "funnel_diagnostics", "experimentation", "budget_scaling", "forecasting", "attribution",
        "competitor_intelligence", "optimization",
    }
    assert core_v1_names <= set(AGENT_REGISTRY.keys())
    v2_agents = set(AGENT_REGISTRY.keys()) - core_v1_names
    assert len(v2_agents) == 54, f"Expected 54 V2 agents, found {len(v2_agents)}"
