"""5 insufficient-data scenario tests for the V2 expansion — confirms the
system says "INSUFFICIENT DATA" rather than fabricating a finding, across
five genuinely different missing-data situations (not five copies of the
same case).
"""

from __future__ import annotations

from app.integrations.meta.mock_data import generate_scenario
from app.orchestration.workflow import Orchestrator
from tests.conftest import REFERENCE_DATE, build_context


def test_1_brand_new_campaign_scaling_never_marked_safe(memory_store):
    account = generate_scenario("insufficient_data", reference_date=REFERENCE_DATE)
    context = build_context(account, trigger="scaling_request")
    Orchestrator(memory=memory_store).run(context)
    for f in context.findings_by_agent("scaling_risk"):
        assert f.payload["verdict"] != "SAFE"


def test_2_content_creation_without_customer_language_flags_the_gap(memory_store):
    account = generate_scenario("strong_campaign", reference_date=REFERENCE_DATE)
    context = build_context(account, trigger="content_creation_request")
    assert context.customer_language_sources == []
    Orchestrator(memory=memory_store).run(context)
    lang_findings = context.findings_by_agent("customer_language_mining")
    assert lang_findings
    assert lang_findings[0].status.value == "insufficient_data"
    assert lang_findings[0].confidence == 0.0


def test_3_lead_quality_problem_without_crm_data_is_explicit(memory_store):
    account = generate_scenario("cheap_low_quality_leads", reference_date=REFERENCE_DATE)
    context = build_context(account, trigger="lead_quality_problem")
    assert context.crm_records == []
    Orchestrator(memory=memory_store).run(context)
    crm_findings = context.findings_by_agent("crm_intelligence")
    assert crm_findings
    assert crm_findings[0].status.value == "insufficient_data"
    assert "no_crm_data" in crm_findings[0].tags


def test_4_scheduled_review_without_external_research_market_condition_inactive(memory_store):
    account = generate_scenario("high_cpl_campaign", reference_date=REFERENCE_DATE)
    context = build_context(account, trigger="scheduled_review")
    assert context.competitor_research == []
    Orchestrator(memory=memory_store).run(context)
    market_findings = context.findings_by_agent("market_condition")
    assert market_findings
    assert market_findings[0].status.value == "insufficient_data"


def test_5_post_change_review_without_baseline_produces_no_rollback_call(memory_store):
    account = generate_scenario("strong_campaign", reference_date=REFERENCE_DATE)
    context = build_context(account, trigger="post_change_review")
    assert context.baseline_insights == []
    Orchestrator(memory=memory_store).run(context)
    verification = context.findings_by_agent("post_change_verification")
    rollback = context.findings_by_agent("rollback_decision")
    assert verification and verification[0].status.value == "insufficient_data"
    assert rollback and rollback[0].status.value == "insufficient_data"
