"""Approval layer.

Turns a Guardian decision into a human-facing `ApprovalRequest`. Approval
objects exist and are fully functional now even though the execution step
downstream of them is disabled in this build — the safety pipeline is
representable end-to-end: READ -> ANALYZE -> RECOMMEND -> GUARDIAN ->
APPROVAL -> EXECUTE -> VERIFY -> LOG -> LEARN.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.models.execution import ApprovalRequest, ApprovalStatus, GuardianDecision, GuardianVerdict
from app.models.recommendations import Recommendation


def requires_approval_request(recommendation: Recommendation, guardian_decision: GuardianDecision) -> bool:
    """A REJECTed recommendation never gets an approval request — Guardian's
    veto is final at this stage; a human would have to override it through
    an explicit separate review process, not through this pipeline."""
    if guardian_decision.verdict == GuardianVerdict.REJECT:
        return False
    return recommendation.requires_approval


def create_approval_request(
    recommendation: Recommendation, guardian_decision: GuardianDecision
) -> ApprovalRequest | None:
    if not requires_approval_request(recommendation, guardian_decision):
        return None
    return ApprovalRequest(
        approval_id=f"approval_{uuid.uuid4().hex[:12]}",
        recommendation_id=recommendation.recommendation_id,
        guardian_decision=guardian_decision,
        status=ApprovalStatus.PENDING,
    )


def decide_approval(
    approval: ApprovalRequest, approved: bool, decided_by: str, notes: str | None = None
) -> ApprovalRequest:
    return approval.model_copy(
        update={
            "status": ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
            "decided_at": datetime.now(UTC),
            "decided_by": decided_by,
            "notes": notes,
        }
    )


def is_expired(approval: ApprovalRequest, max_age_days: int = 14) -> bool:
    if approval.status != ApprovalStatus.PENDING:
        return False
    age = datetime.now(UTC) - approval.requested_at
    return age.days > max_age_days
