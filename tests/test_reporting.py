from __future__ import annotations

from app.orchestration.workflow import Orchestrator
from app.reports.command_center import SECTION_TITLES, generate_report
from tests.conftest import build_context


def test_report_contains_all_eighteen_sections(memory_store, full_mock_account):
    context = build_context(full_mock_account)
    result = Orchestrator(memory=memory_store).run(context)
    report = generate_report(context, result.guardian_decisions)
    for title in SECTION_TITLES:
        assert title in report.sections


def test_report_markdown_renders_without_error(memory_store, full_mock_account):
    context = build_context(full_mock_account)
    result = Orchestrator(memory=memory_store).run(context)
    report = generate_report(context, result.guardian_decisions)
    markdown = report.to_markdown()
    assert "META ADS AI COMMAND CENTER" in markdown
    assert "## 1. Business Objective" in markdown


def test_report_says_do_nothing_yet_when_no_actionable_recs(memory_store):
    from app.integrations.meta.mock_data import generate_scenario
    from app.orchestration.context import AgentContext
    from tests.conftest import REFERENCE_DATE

    account = generate_scenario("insufficient_data", reference_date=REFERENCE_DATE)
    context = AgentContext(
        business_objective=account.business_objective,
        campaigns=account.campaigns,
        ad_sets=[],
        ads=[],
        creatives=[],
        insights=[],
        leads=[],
        sales=[],
        trigger="scheduled_review",
    )
    result = Orchestrator(memory=memory_store).run(context)
    report = generate_report(context, result.guardian_decisions)
    actions_section = report.sections["13. Recommended Actions"]
    assert any("DO NOTHING" in line for line in actions_section)
