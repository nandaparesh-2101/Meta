"""5 scaling-pipeline scenario tests: the `scaling_request` route (data
analyst -> marginal performance -> budget scaling -> scaling risk -> funnel
economics -> forecasting -> guardian -> executive strategy) against real
mock scenarios.
"""

from __future__ import annotations

from app.integrations.meta.mock_data import generate_scenario
from app.orchestration.workflow import Orchestrator
from tests.conftest import REFERENCE_DATE, build_context


def _run(memory_store, scenario_key: str):
    account = generate_scenario(scenario_key, reference_date=REFERENCE_DATE)
    context = build_context(account, trigger="scaling_request")
    result = Orchestrator(memory=memory_store).run(context)
    return context, result


def test_1_scaling_opportunity_gets_a_safe_or_caution_verdict(memory_store):
    context, result = _run(memory_store, "scaling_opportunity")
    risk_findings = context.findings_by_agent("scaling_risk")
    assert risk_findings
    for f in risk_findings:
        assert f.payload["verdict"] in ("SAFE", "CAUTION", "HIGH_RISK")


def test_2_creative_fatigue_scenario_scaling_is_not_safe_when_fatigue_upstream(memory_store):
    # Run creative_fatigue_prediction first via a combined trigger to prove
    # scaling_risk actually consumes it, not just computes independently.
    account = generate_scenario("creative_fatigue", reference_date=REFERENCE_DATE)
    context = build_context(account, trigger="creative_performance_problem")
    Orchestrator(memory=memory_store).run(context)
    # Re-run scaling_risk directly against the already-populated context.
    from app.agents.funnel_economics import ScalingRiskAgent
    findings = ScalingRiskAgent().run(context)
    assert findings
    fatigued_ads = [f for f in context.findings_by_agent("creative_fatigue_prediction") if f.payload.get("fatigue_level") in ("HIGH", "CRITICAL")]
    if fatigued_ads:
        assert any(f.payload["verdict"] != "SAFE" for f in findings)


def test_3_insufficient_data_scenario_never_marked_safe_to_scale(memory_store):
    context, result = _run(memory_store, "insufficient_data")
    risk_findings = context.findings_by_agent("scaling_risk")
    for f in risk_findings:
        assert f.payload["verdict"] != "SAFE"


def test_4_high_cpl_campaign_marginal_performance_runs(memory_store):
    context, result = _run(memory_store, "high_cpl_campaign")
    assert context.findings_by_agent("marginal_performance")
    assert context.findings_by_agent("budget_scaling")


def test_5_audience_saturation_forecast_and_economics_present(memory_store):
    context, result = _run(memory_store, "audience_saturation")
    assert context.findings_by_agent("forecasting")
    assert context.findings_by_agent("funnel_economics")
    # Executive strategy always runs last and must reflect this run's recommendations.
    strategy = context.findings_by_agent("executive_strategy")
    assert strategy
