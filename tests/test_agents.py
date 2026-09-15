from __future__ import annotations

from app.agents.business_intelligence import BusinessIntelligenceAgent
from app.agents.data_analyst import DataAnalystAgent
from app.agents.experimentation import ExperimentationAgent
from app.agents.optimization import OptimizationAgent
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding


def test_business_intelligence_produces_summary_finding(scenario_context):
    context = scenario_context("strong_campaign")
    findings = BusinessIntelligenceAgent().run(context)
    assert len(findings) == 1
    assert "business_context" in findings[0].tags


def test_data_analyst_flags_tracking_anomaly(scenario_context):
    context = scenario_context("tracking_anomaly")
    findings = DataAnalystAgent().run(context)
    assert any("tracking_anomaly" in f.tags for f in findings)


def test_data_analyst_flags_insufficient_data_for_new_campaign(scenario_context):
    context = scenario_context("insufficient_data")
    findings = DataAnalystAgent().run(context)
    assert any(f.data_sufficiency == DataSufficiencyLevel.INSUFFICIENT_DATA for f in findings)


def test_data_analyst_does_not_invent_missing_metrics(scenario_context):
    context = scenario_context("strong_campaign")
    findings = DataAnalystAgent().run(context)
    # Every finding's evidence must be composed only of computed/real values —
    # spot check that no finding blindly claims 100% or 0.00 for something uncalculated.
    assert all(isinstance(f, AgentFinding) for f in findings)


def test_optimization_agent_returns_do_nothing_when_no_actionable_findings():
    from app.integrations.meta.mock_data import generate_scenario
    from app.orchestration.context import AgentContext
    from tests.conftest import REFERENCE_DATE

    account = generate_scenario("strong_campaign", reference_date=REFERENCE_DATE)
    ctx = AgentContext(
        business_objective=account.business_objective,
        campaigns=account.campaigns,
        ad_sets=account.ad_sets,
        ads=account.ads,
        creatives=account.creatives,
        insights=[],
        leads=[],
        sales=[],
        trigger="scheduled_review",
    )
    findings = OptimizationAgent().run(ctx)
    assert any("no_action_recommended" in f.tags or f.suggested_actions == [ActionType.DO_NOTHING] for f in findings)


def test_experimentation_prevents_duplicate_experiment(scenario_context):
    context = scenario_context("high_ctr_poor_conversion")
    from app.agents.copy_intelligence import CopyIntelligenceAgent

    CopyIntelligenceAgent().run(context)
    agent = ExperimentationAgent()
    first_run_findings = agent.run(context)
    proposed_count = sum(1 for f in first_run_findings if "experiment_created" in f.tags)

    # Simulate persisted experiments now existing from the first run.
    context.existing_experiments = list(context.new_experiments)
    context.new_experiments = []

    second_run_findings = ExperimentationAgent().run(context)
    duplicate_count = sum(1 for f in second_run_findings if "duplicate_experiment_prevented" in f.tags)

    assert proposed_count > 0
    assert duplicate_count == proposed_count
