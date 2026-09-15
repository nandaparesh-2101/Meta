"""Guardian, approval, execution and audit models.

These exist NOW even though execution is disabled in this build, so the
full safety pipeline (READ -> ANALYZE -> RECOMMEND -> GUARDIAN -> APPROVAL ->
EXECUTE -> VERIFY -> LOG -> LEARN) is representable end-to-end.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class GuardianVerdict(str, Enum):
    APPROVE = "approve"
    APPROVE_WITH_CAUTION = "approve_with_caution"
    REQUIRE_HUMAN_APPROVAL = "require_human_approval"
    REJECT = "reject"


class GuardianDecision(BaseModel):
    recommendation_id: str
    verdict: GuardianVerdict
    checks_run: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    reasoning: str
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def blocks_execution(self) -> bool:
        return self.verdict == GuardianVerdict.REJECT


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    approval_id: str
    recommendation_id: str
    guardian_decision: GuardianDecision
    requested_by: str = "system"
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
    decided_by: str | None = None
    notes: str | None = None


class ExecutionMode(str, Enum):
    DISABLED = "disabled"
    RECOMMENDATION_ONLY = "recommendation_only"
    APPROVAL_REQUIRED = "approval_required"
    CONTROLLED_AUTOMATION = "controlled_automation"


class ExecutionRequest(BaseModel):
    execution_id: str
    recommendation_id: str
    approval_id: str | None = None
    action: str
    entity_id: str
    payload: dict = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ExecutionResultStatus(str, Enum):
    BLOCKED_EXECUTION_DISABLED = "blocked_execution_disabled"
    BLOCKED_NO_APPROVAL = "blocked_no_approval"
    BLOCKED_GUARDIAN_REJECTED = "blocked_guardian_rejected"
    SUCCESS = "success"
    FAILED = "failed"


class ExecutionResult(BaseModel):
    execution_id: str
    status: ExecutionResultStatus
    message: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider_response: dict | None = None


class AuditEventType(str, Enum):
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    RECOMMENDATION_CREATED = "recommendation_created"
    GUARDIAN_DECISION = "guardian_decision"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"
    EXECUTION_ATTEMPTED = "execution_attempted"
    EXECUTION_COMPLETED = "execution_completed"
    EXPERIMENT_CREATED = "experiment_created"
    LEARNING_RECORDED = "learning_recorded"
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"


class AuditEvent(BaseModel):
    event_id: str
    event_type: AuditEventType
    actor: str = Field(..., description="e.g. agent name, 'guardian', 'human:<email>', 'system'")
    summary: str
    details: dict = Field(default_factory=dict)
    entity_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
