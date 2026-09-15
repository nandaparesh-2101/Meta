"""5 lead-quality-pipeline scenario tests: the `lead_quality_problem` and
`sales_process_review` routes running against real mock scenarios.
"""

from __future__ import annotations

from app.integrations.meta.mock_data import generate_scenario
from app.orchestration.workflow import Orchestrator
from tests.conftest import REFERENCE_DATE, build_context


def _run(memory_store, scenario_key: str, trigger: str):
    account = generate_scenario(scenario_key, reference_date=REFERENCE_DATE)
    context = build_context(account, trigger=trigger)
    result = Orchestrator(memory=memory_store).run(context)
    return context, result


def test_1_cheap_low_quality_leads_flagged_by_lead_quality_and_sales_feedback(memory_store):
    context, result = _run(memory_store, "cheap_low_quality_leads", "lead_quality_problem")
    tags = {t for f in context.findings for t in f.tags}
    assert "cheap_low_quality_leads" in tags
    assert context.findings_by_agent("sales_feedback_loop")
    assert context.findings_by_agent("funnel_economics")


def test_2_low_ctr_high_quality_scores_well_on_sales_conversion(memory_store):
    context, result = _run(memory_store, "low_ctr_high_quality", "lead_quality_problem")
    sales_conv = context.findings_by_agent("sales_conversion")
    assert sales_conv, "sales_conversion should run with enough leads for this scenario"


def test_3_high_ctr_poor_conversion_shows_funnel_economics_bottleneck(memory_store):
    context, result = _run(memory_store, "high_ctr_poor_conversion", "lead_quality_problem")
    economics = context.findings_by_agent("funnel_economics")
    assert economics


def test_4_crm_intelligence_gracefully_inactive_without_crm_data(memory_store):
    context, result = _run(memory_store, "strong_campaign", "lead_quality_problem")
    assert context.crm_records == []
    crm_findings = context.findings_by_agent("crm_intelligence")
    assert crm_findings
    assert crm_findings[0].status.value == "insufficient_data"


def test_5_sales_process_review_route_checks_response_time_and_scoring(memory_store):
    context, result = _run(memory_store, "scaling_opportunity", "sales_process_review")
    assert context.findings_by_agent("lead_response")
    assert context.findings_by_agent("lead_scoring")
