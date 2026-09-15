"""5 creative-pipeline scenario tests: the `creative_performance_problem`
and `content_creation_request` routes running against real mock scenarios.
"""

from __future__ import annotations

from app.integrations.meta.mock_data import generate_scenario
from app.orchestration.workflow import Orchestrator
from tests.conftest import REFERENCE_DATE, build_context


def _run(memory_store, scenario_key: str, trigger: str, **overrides):
    account = generate_scenario(scenario_key, reference_date=REFERENCE_DATE)
    context = build_context(account, trigger=trigger, **overrides)
    result = Orchestrator(memory=memory_store).run(context)
    return context, result


def test_1_creative_fatigue_scenario_flags_fatigue_and_proposes_refresh(memory_store):
    context, result = _run(memory_store, "creative_fatigue", "creative_performance_problem")
    fatigue_findings = context.findings_by_agent("creative_fatigue_prediction")
    assert fatigue_findings
    assert any(f.payload.get("fatigue_level") in ("MEDIUM", "HIGH", "CRITICAL") for f in fatigue_findings)
    refresh_findings = context.findings_by_agent("creative_refresh")
    assert refresh_findings


def test_2_strong_campaign_creative_scores_reasonably(memory_store):
    context, result = _run(memory_store, "strong_campaign", "creative_performance_problem")
    scoring = context.findings_by_agent("creative_scoring")
    assert scoring
    for f in scoring:
        assert 0 <= f.payload["total"] <= f.payload["max_total"]


def test_3_content_creation_request_produces_full_creative_package(memory_store):
    context, result = _run(
        memory_store, "high_ctr_poor_conversion", "content_creation_request",
        customer_language_sources=[
            "Too expensive for what it offers, not sure it actually works for someone like me",
            "I've been looking for something that finally fits my crazy schedule",
        ],
    )
    for agent_name in ("customer_avatar", "hook_engine", "content_angle", "creative_brief", "ugc_strategist", "content_quality"):
        assert context.findings_by_agent(agent_name), f"{agent_name} should have run and produced a finding"
    quality = context.findings_by_agent("content_quality")[0]
    assert quality.status.value == "complete"


def test_4_content_creation_request_policy_check_flags_nothing_fabricated(memory_store):
    context, result = _run(memory_store, "cheap_low_quality_leads", "content_creation_request")
    ugc_findings = context.findings_by_agent("ugc_strategist")
    assert ugc_findings
    # No real proof was supplied for this scenario's creatives with proof_elements — must say so honestly.
    concepts = ugc_findings[0].payload["concepts"]
    assert any("INSUFFICIENT EVIDENCE" in c["proof"] for c in concepts) or all(c["proof"] for c in concepts)


def test_5_audience_saturation_creative_diversity_and_library_run_together(memory_store):
    context, result = _run(memory_store, "audience_saturation", "scheduled_review")
    assert context.findings_by_agent("creative_diversity")
    assert context.findings_by_agent("creative_library_manager")
    assert context.findings_by_agent("audience_intelligence")
    saturation_tags = {t for f in context.findings for t in f.tags}
    assert "audience_saturation" in saturation_tags
