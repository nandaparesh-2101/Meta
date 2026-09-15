"""Scenario tests: run the full orchestrator against each of the 10 mock
scenarios and assert the system reaches the expected diagnostic conclusion.
"""

from __future__ import annotations

import pytest

from app.integrations.meta.mock_data import available_scenarios, generate_scenario
from app.orchestration.workflow import Orchestrator
from tests.conftest import REFERENCE_DATE, build_context


def _run(memory_store, scenario_key: str, trigger: str = "scheduled_review"):
    account = generate_scenario(scenario_key, reference_date=REFERENCE_DATE)
    context = build_context(account, trigger=trigger)
    orchestrator = Orchestrator(memory=memory_store)
    result = orchestrator.run(context)
    return context, result


def test_all_ten_scenarios_are_registered():
    assert len(available_scenarios()) == 10


def test_strong_campaign_produces_few_critical_recommendations(memory_store):
    context, result = _run(memory_store, "strong_campaign")
    critical = [r for r in context.recommendations if r.priority.value == "P0"]
    assert len(critical) == 0


def test_high_cpl_campaign_flags_cpl_increase(memory_store):
    context, result = _run(memory_store, "high_cpl_campaign", trigger="cpl_increase")
    tags = {t for f in context.findings for t in f.tags}
    assert "cpl_increase" in tags


def test_cheap_low_quality_leads_flags_pattern(memory_store):
    context, result = _run(memory_store, "cheap_low_quality_leads", trigger="cheap_leads_poor_sales")
    tags = {t for f in context.findings for t in f.tags}
    assert "cheap_low_quality_leads" in tags


def test_creative_fatigue_detected(memory_store):
    context, result = _run(memory_store, "creative_fatigue", trigger="ctr_decrease")
    tags = {t for f in context.findings for t in f.tags}
    assert "creative_fatigue" in tags


def test_audience_saturation_detected(memory_store):
    context, result = _run(memory_store, "audience_saturation")
    tags = {t for f in context.findings for t in f.tags}
    assert "audience_saturation" in tags


def test_high_ctr_poor_conversion_flags_offer_or_bottleneck(memory_store):
    context, result = _run(memory_store, "high_ctr_poor_conversion", trigger="funnel_investigation")
    tags = {t for f in context.findings for t in f.tags}
    assert "offer_risk" in tags or any(t.startswith("bottleneck:") for t in tags)


def test_insufficient_data_scenario_never_produces_high_priority_recs(memory_store):
    context, result = _run(memory_store, "insufficient_data")
    high_priority = [r for r in context.recommendations if r.priority.value in ("P0", "P1")]
    assert len(high_priority) == 0


def test_scaling_opportunity_produces_scale_recommendation(memory_store):
    context, result = _run(memory_store, "scaling_opportunity", trigger="scaling_review")
    actions = {r.action.value for r in context.recommendations}
    assert "increase_budget" in actions or "maintain" in actions


def test_tracking_anomaly_flags_investigate_tracking(memory_store):
    context, result = _run(memory_store, "tracking_anomaly")
    tags = {t for f in context.findings for t in f.tags}
    assert "tracking_anomaly" in tags


def test_low_ctr_high_quality_does_not_recommend_pausing_for_low_ctr_alone(memory_store):
    context, result = _run(memory_store, "low_ctr_high_quality", trigger="ctr_decrease")
    # Low CTR alone with strong downstream quality should not trigger a pause action.
    pause_recs = [r for r in context.recommendations if r.action.value.startswith("pause")]
    assert len(pause_recs) == 0


@pytest.mark.parametrize("scenario_key", available_scenarios())
def test_every_scenario_runs_without_error_and_every_recommendation_has_evidence(memory_store, scenario_key):
    context, result = _run(memory_store, scenario_key)
    assert len(context.findings) > 0
    for rec in context.recommendations:
        assert rec.reason
        assert rec.measurement
        assert 0.0 <= rec.confidence <= 1.0
    assert len(result.guardian_decisions) == len(context.recommendations)
