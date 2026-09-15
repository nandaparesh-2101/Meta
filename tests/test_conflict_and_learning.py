"""Conflict resolution (agent disagreement preserved, never silently
resolved) and cross-agent learning synthesis.
"""

from __future__ import annotations

from app.agents.learning_intelligence import LearningSynthesisAgent
from app.agents.optimization import OptimizationAgent
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding
from tests.conftest import build_context


def test_conflicting_actions_for_same_entity_both_preserved(full_mock_account):
    context = build_context(full_mock_account)
    entity_id = full_mock_account.campaigns[0].campaign_id

    # Two agents disagree on the same entity: one says increase, one says decrease.
    context.findings.append(
        AgentFinding(
            agent_name="budget_scaling", entity_id=entity_id, headline="Scale up — efficiency on target",
            detail="", evidence=[], data_sufficiency=DataSufficiencyLevel.CONFIDENT, confidence=0.8,
            suggested_actions=[ActionType.INCREASE_BUDGET], tags=[],
        )
    )
    context.findings.append(
        AgentFinding(
            agent_name="scaling_risk", entity_id=entity_id, headline="Scaling risk is HIGH",
            detail="", evidence=[], data_sufficiency=DataSufficiencyLevel.PROMISING, confidence=0.6,
            suggested_actions=[ActionType.DECREASE_BUDGET], tags=[],
        )
    )

    OptimizationAgent().run(context)

    entity_recs = [r for r in context.recommendations if r.entity_id == entity_id]
    actions = {r.action for r in entity_recs}
    assert ActionType.INCREASE_BUDGET in actions
    assert ActionType.DECREASE_BUDGET in actions, "Both conflicting recommendations must be preserved, not silently resolved"

    summary = [f for f in context.findings if f.agent_name == "optimization" and f.entity_id == entity_id]
    assert any("agent_disagreement" in f.tags for f in summary)


def test_learning_synthesis_requires_independent_supporting_signals(full_mock_account):
    context = build_context(full_mock_account)
    findings = LearningSynthesisAgent().run(context)
    # With no sales_feedback_loop/audience_comparison/creative_pattern findings yet, nothing to synthesize.
    assert findings[0].status.value == "insufficient_data"


def test_learning_synthesis_confidence_scales_with_evidence_count(full_mock_account):
    context = build_context(full_mock_account)
    context.findings.append(
        AgentFinding(
            agent_name="sales_feedback_loop", entity_id=None, headline="'problem-first' angle produced most revenue",
            detail="", evidence=[], data_sufficiency=DataSufficiencyLevel.PROMISING, confidence=0.6,
            suggested_actions=[], tags=[], payload={"revenue_by_angle": {"problem-first": 500.0, "aspiration": 200.0}},
        )
    )
    single_signal = LearningSynthesisAgent().run(context)[0].confidence

    context.findings.append(
        AgentFinding(
            agent_name="audience_intelligence", entity_id=None, headline="'broad' audiences show strongest CPL",
            detail="", evidence=[], data_sufficiency=DataSufficiencyLevel.PROMISING, confidence=0.5,
            suggested_actions=[], tags=["audience_comparison"],
        )
    )
    two_signals = LearningSynthesisAgent().run(context)[0].confidence

    assert two_signals > single_signal, "Repeated/independent evidence must increase confidence, not just isolated results"
