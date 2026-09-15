from __future__ import annotations

from app.execution.approval import create_approval_request, decide_approval
from app.execution.executor import Executor
from app.execution.rollback import RollbackManager
from app.integrations.meta.adapter import MockMetaAdsProvider
from app.models.execution import (
    ApprovalStatus,
    ExecutionResultStatus,
    GuardianDecision,
    GuardianVerdict,
)
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, Priority, Recommendation, RiskLevel


def _recommendation(**overrides) -> Recommendation:
    base = dict(
        recommendation_id="rec_exec_1",
        entity_id="ad_123",
        entity_level="ad",
        action=ActionType.PAUSE_AD,
        priority=Priority.P1_HIGH,
        reason="test",
        expected_impact="test",
        confidence=0.8,
        risk=RiskLevel.HIGH,
        measurement="test",
        review_window_days=14,
        requires_approval=True,
        data_sufficiency=DataSufficiencyLevel.CONFIDENT,
    )
    base.update(overrides)
    return Recommendation(**base)


def _decision(verdict: GuardianVerdict, rec_id: str = "rec_exec_1") -> GuardianDecision:
    return GuardianDecision(recommendation_id=rec_id, verdict=verdict, reasoning="test")


def test_rejected_recommendation_never_gets_approval_request():
    rec = _recommendation()
    decision = _decision(GuardianVerdict.REJECT)
    approval = create_approval_request(rec, decision)
    assert approval is None


def test_approved_verdict_creates_pending_approval():
    rec = _recommendation()
    decision = _decision(GuardianVerdict.REQUIRE_HUMAN_APPROVAL)
    approval = create_approval_request(rec, decision)
    assert approval is not None
    assert approval.status == ApprovalStatus.PENDING


def test_decide_approval_transitions_status():
    rec = _recommendation()
    decision = _decision(GuardianVerdict.APPROVE)
    approval = create_approval_request(rec, decision)
    approved = decide_approval(approval, approved=True, decided_by="human:test@example.com")
    assert approved.status == ApprovalStatus.APPROVED
    assert approved.decided_by == "human:test@example.com"


def test_executor_blocks_when_execution_mode_disabled(memory_store):
    rec = _recommendation()
    decision = _decision(GuardianVerdict.APPROVE)
    executor = Executor(provider=MockMetaAdsProvider(), memory=memory_store)
    result = executor.execute(rec, decision, approval=None)
    assert result.status == ExecutionResultStatus.BLOCKED_EXECUTION_DISABLED


def test_executor_blocks_on_guardian_rejection(memory_store, monkeypatch):
    from app.config import ExecutionMode
    from app.execution import executor as executor_module

    monkeypatch.setattr(executor_module.settings, "execution_mode", ExecutionMode.RECOMMENDATION_ONLY)
    rec = _recommendation()
    decision = _decision(GuardianVerdict.REJECT)
    executor = Executor(provider=MockMetaAdsProvider(), memory=memory_store)
    result = executor.execute(rec, decision, approval=None)
    assert result.status == ExecutionResultStatus.BLOCKED_GUARDIAN_REJECTED


def test_executor_blocks_without_approval_when_required(memory_store, monkeypatch):
    from app.config import ExecutionMode
    from app.execution import executor as executor_module

    monkeypatch.setattr(executor_module.settings, "execution_mode", ExecutionMode.APPROVAL_REQUIRED)
    rec = _recommendation(requires_approval=True)
    decision = _decision(GuardianVerdict.APPROVE)
    executor = Executor(provider=MockMetaAdsProvider(), memory=memory_store)
    result = executor.execute(rec, decision, approval=None)
    assert result.status == ExecutionResultStatus.BLOCKED_NO_APPROVAL


def test_rollback_reports_nothing_to_roll_back_for_unknown_execution(memory_store):
    manager = RollbackManager(memory=memory_store)
    result = manager.rollback("exec_does_not_exist")
    assert result.status == ExecutionResultStatus.FAILED
