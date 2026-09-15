"""Rollback layer.

Reserved for the VERIFY step's failure path: if a future live execution
degrades performance, this module is where the compensating action (revert
budget, re-enable a paused ad, etc.) would be issued. In this build no
execution ever actually succeeds against a real account, so `rollback()`
can only ever find "nothing was executed" — it is implemented for real
(not a stub) against that constraint so the interface is proven out.
"""

from __future__ import annotations

import uuid

from app.memory.store import MemoryStore
from app.models.execution import AuditEventType, ExecutionResult, ExecutionResultStatus


class RollbackManager:
    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or MemoryStore()

    def rollback(self, execution_id: str) -> ExecutionResult:
        """Attempts to roll back a prior execution. Only meaningful for an
        execution that actually succeeded (`ExecutionResultStatus.SUCCESS`);
        anything else means there is nothing to compensate for."""
        original = self._find_execution(execution_id)
        rollback_id = f"rollback_{uuid.uuid4().hex[:12]}"

        if original is None:
            result = ExecutionResult(
                execution_id=rollback_id,
                status=ExecutionResultStatus.FAILED,
                message=f"No execution record found for execution_id={execution_id}; cannot roll back.",
            )
        elif original.status != ExecutionResultStatus.SUCCESS:
            result = ExecutionResult(
                execution_id=rollback_id,
                status=ExecutionResultStatus.FAILED,
                message=(
                    f"Execution {execution_id} never succeeded (status={original.status.value}); "
                    "there is nothing to roll back."
                ),
            )
        else:
            # In this build no provider write ever succeeds, so this branch
            # is unreachable today — it exists so a future live provider has
            # a defined rollback contract to implement against.
            result = ExecutionResult(
                execution_id=rollback_id,
                status=ExecutionResultStatus.FAILED,
                message="Rollback of a live Meta Ads change is not implemented in this build.",
            )

        self.memory.record(
            AuditEventType.EXECUTION_ATTEMPTED,
            actor="rollback_manager",
            summary=f"Rollback attempted for execution_id={execution_id}: {result.message}",
        )
        return result

    def _find_execution(self, execution_id: str) -> ExecutionResult | None:
        return self.memory.get_execution_result(execution_id)
