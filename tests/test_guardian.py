from __future__ import annotations

from app.agents.guardian import GuardianAgent
from app.models.execution import GuardianVerdict
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, Priority, Recommendation, RiskLevel
from tests.conftest import build_context


def _recommendation(**overrides) -> Recommendation:
    base = dict(
        recommendation_id="rec_1",
        entity_id="cmp_strong_campaign",
        entity_level="campaign",
        action=ActionType.INCREASE_BUDGET,
        priority=Priority.P2_MEDIUM,
        reason="CPL and ROAS on target",
        evidence=["CPL=20", "ROAS=4.0"],
        expected_impact="More leads at maintained efficiency",
        confidence=0.8,
        risk=RiskLevel.LOW,
        measurement="Track CPL weekly",
        review_window_days=14,
        requires_approval=True,
        data_sufficiency=DataSufficiencyLevel.CONFIDENT,
    )
    base.update(overrides)
    return Recommendation(**base)


def test_guardian_approves_clean_low_risk_recommendation(full_mock_account):
    context = build_context(full_mock_account)
    guardian = GuardianAgent()
    rec = _recommendation()
    decisions = guardian.review(context, [rec])
    assert decisions[0].verdict in (GuardianVerdict.APPROVE, GuardianVerdict.APPROVE_WITH_CAUTION)


def test_guardian_rejects_insufficient_data_recommendation(full_mock_account):
    context = build_context(full_mock_account)
    guardian = GuardianAgent()
    rec = _recommendation(data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA, confidence=0.2)
    decisions = guardian.review(context, [rec])
    assert decisions[0].verdict == GuardianVerdict.REJECT
    assert any("INSUFFICIENT_DATA" in c for c in decisions[0].concerns)


def test_guardian_requires_human_approval_for_high_risk_low_confidence(full_mock_account):
    context = build_context(full_mock_account)
    guardian = GuardianAgent()
    rec = _recommendation(risk=RiskLevel.HIGH, confidence=0.4, priority=Priority.P1_HIGH)
    decisions = guardian.review(context, [rec])
    assert decisions[0].verdict in (GuardianVerdict.REQUIRE_HUMAN_APPROVAL, GuardianVerdict.REJECT)


def test_guardian_flags_missing_measurement_plan(full_mock_account):
    context = build_context(full_mock_account)
    guardian = GuardianAgent()
    rec = _recommendation(measurement="")
    decisions = guardian.review(context, [rec])
    assert any("measurement" in c.lower() for c in decisions[0].concerns)


def test_guardian_flags_protected_campaign(full_mock_account):
    context = build_context(full_mock_account)
    context.business_objective.constraints.protected_campaign_ids.append("cmp_strong_campaign")
    guardian = GuardianAgent()
    rec = _recommendation(entity_id="cmp_strong_campaign")
    decisions = guardian.review(context, [rec])
    assert any("protected" in c.lower() for c in decisions[0].concerns)
