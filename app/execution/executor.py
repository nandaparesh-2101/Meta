"""Execution layer.

READ -> ANALYZE -> RECOMMEND -> GUARDIAN -> APPROVAL -> EXECUTE -> VERIFY ->
LOG -> LEARN.

This module is the EXECUTE step. It is fully wired but safety-gated:
`settings.execution_mode` defaults to `disabled`, and even in any other
mode, the only `MetaAdsProvider` implementation available in this build is
`MockMetaAdsProvider`, whose write methods always refuse to act (see
`app/integrations/meta/adapter.py`). No combination of settings in this
codebase can cause a real Meta Ads account to be modified.
"""

from __future__ import annotations

import uuid

from app.config import ExecutionMode, settings
from app.integrations.base import MetaAdsProvider
from app.integrations.meta.adapter import get_meta_provider
from app.memory.store import MemoryStore
from app.models.execution import (
    ApprovalRequest,
    ApprovalStatus,
    AuditEventType,
    ExecutionResult,
    ExecutionResultStatus,
    GuardianDecision,
)
from app.models.recommendations import ActionType, Recommendation


class Executor:
    def __init__(self, provider: MetaAdsProvider | None = None, memory: MemoryStore | None = None) -> None:
        self.provider = provider or get_meta_provider()
        self.memory = memory or MemoryStore()

    def execute(
        self,
        recommendation: Recommendation,
        guardian_decision: GuardianDecision,
        approval: ApprovalRequest | None,
    ) -> ExecutionResult:
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        self.memory.record(
            AuditEventType.EXECUTION_ATTEMPTED,
            actor="executor",
            summary=f"Execution attempted for {recommendation.recommendation_id} ({recommendation.action.value})",
            entity_id=recommendation.entity_id,
        )

        result = self._guarded_execute(execution_id, recommendation, guardian_decision, approval)

        self.memory.save_execution_result(result, recommendation_id=recommendation.recommendation_id)
        self.memory.record(
            AuditEventType.EXECUTION_COMPLETED,
            actor="executor",
            summary=f"Execution {execution_id} finished with status={result.status.value}",
            details={"message": result.message},
            entity_id=recommendation.entity_id,
        )
        return result

    def _guarded_execute(
        self,
        execution_id: str,
        recommendation: Recommendation,
        guardian_decision: GuardianDecision,
        approval: ApprovalRequest | None,
    ) -> ExecutionResult:
        if settings.execution_mode == ExecutionMode.DISABLED:
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionResultStatus.BLOCKED_EXECUTION_DISABLED,
                message=(
                    "EXECUTION_MODE=disabled. This build performs analysis and recommendation only; "
                    "no advertising change was made."
                ),
            )

        if guardian_decision.blocks_execution:
            return ExecutionResult(
                execution_id=execution_id,
                status=ExecutionResultStatus.BLOCKED_GUARDIAN_REJECTED,
                message=f"Guardian rejected this recommendation: {guardian_decision.reasoning}",
            )

        if recommendation.requires_approval:
            if approval is None or approval.status != ApprovalStatus.APPROVED:
                return ExecutionResult(
                    execution_id=execution_id,
                    status=ExecutionResultStatus.BLOCKED_NO_APPROVAL,
                    message="Recommendation requires human approval and none has been granted yet.",
                )

        provider_result = self._dispatch_to_provider(recommendation)
        return ExecutionResult(
            execution_id=execution_id,
            status=ExecutionResultStatus.SUCCESS if provider_result.success else ExecutionResultStatus.FAILED,
            message=provider_result.message,
            provider_response={"is_mock": provider_result.is_mock},
        )

    def _dispatch_to_provider(self, recommendation: Recommendation):
        action_map = {
            ActionType.PAUSE_AD: lambda: self.provider.pause_ad(recommendation.entity_id),
            ActionType.INCREASE_BUDGET: lambda: self.provider.update_budget(recommendation.entity_id, 0.0),
            ActionType.DECREASE_BUDGET: lambda: self.provider.update_budget(recommendation.entity_id, 0.0),
            ActionType.REALLOCATE_BUDGET: lambda: self.provider.update_budget(recommendation.entity_id, 0.0),
        }
        dispatch = action_map.get(recommendation.action)
        if dispatch is None:
            from app.integrations.base import ProviderActionResult

            return ProviderActionResult(
                success=False, message=f"Action '{recommendation.action.value}' has no provider mapping to execute."
            )
        return dispatch()
