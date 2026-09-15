"""Agent output models: findings and recommendations.

Every agent returns an `AgentFinding`. Findings that imply an action are
converted into `Recommendation` objects by Agent 15 (Optimization) and then
must pass through Guardian before they can ever be approved or executed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.metrics import DataSufficiencyLevel


class Priority(str, Enum):
    P0_CRITICAL = "P0"
    P1_HIGH = "P1"
    P2_MEDIUM = "P2"
    P3_EXPERIMENTAL = "P3"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionType(str, Enum):
    INCREASE_BUDGET = "increase_budget"
    DECREASE_BUDGET = "decrease_budget"
    REALLOCATE_BUDGET = "reallocate_budget"
    MAINTAIN = "maintain"
    PAUSE_AD = "pause_ad"
    PAUSE_AD_SET = "pause_ad_set"
    LAUNCH_TEST = "launch_test"
    REFRESH_CREATIVE = "refresh_creative"
    ADJUST_AUDIENCE = "adjust_audience"
    ADJUST_COPY = "adjust_copy"
    INVESTIGATE_TRACKING = "investigate_tracking"
    INVESTIGATE_OFFER = "investigate_offer"
    DO_NOTHING = "do_nothing"
    # -- Added for the V2 specialist agent expansion (agents 17-70) --
    ADJUST_LANDING_PAGE = "adjust_landing_page"
    ADJUST_FORM = "adjust_form"
    ESCALATE_TO_SALES = "escalate_to_sales"
    ROLLBACK_CHANGE = "rollback_change"
    FLAG_POLICY_RISK = "flag_policy_risk"
    FLAG_BRAND_RISK = "flag_brand_risk"
    GENERATE_CREATIVE_CONCEPT = "generate_creative_concept"
    DIVERSIFY_CREATIVE = "diversify_creative"
    INVESTIGATE_SALES_PROCESS = "investigate_sales_process"


class EvidenceSource(str, Enum):
    """Where a finding's evidence actually came from — required so nothing
    is ever presented as fact without a traceable origin (see AGENTS V2
    spec section 6, the Evidence Rule)."""

    META_DATA = "META_DATA"
    CRM_DATA = "CRM_DATA"
    USER_INPUT = "USER_INPUT"
    EXPERIMENT_HISTORY = "EXPERIMENT_HISTORY"
    EXTERNAL_RESEARCH = "EXTERNAL_RESEARCH"
    MODEL_INFERENCE = "MODEL_INFERENCE"


class FindingStatus(str, Enum):
    """Per-agent-call completion status (spec section 5's output contract).
    Distinct from `DataSufficiencyLevel`, which grades evidence *strength*
    for findings that were produced — `status` records whether the agent
    could produce a meaningful finding at all."""

    COMPLETE = "complete"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


class AgentFinding(BaseModel):
    """The structured output every specialist agent must produce."""

    agent_name: str
    entity_id: str | None = Field(default=None, description="Campaign/AdSet/Ad this finding is about")
    headline: str = Field(..., description="One-sentence summary of the finding")
    detail: str = Field(..., description="Full explanation of the observation and reasoning")
    evidence: list[str] = Field(default_factory=list)
    data_sufficiency: DataSufficiencyLevel
    confidence: float = Field(..., ge=0.0, le=1.0)
    suggested_actions: list[ActionType] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list, description="e.g. 'creative_fatigue', 'tracking_anomaly'")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # -- V2 output-contract fields (spec sections 5-7) --
    status: FindingStatus = FindingStatus.COMPLETE
    evidence_sources: list[EvidenceSource] = Field(default_factory=list)
    assumptions: list[str] = Field(
        default_factory=list, description="Explicitly labeled inferences, not observed fact"
    )
    questions: list[str] = Field(
        default_factory=list, description="Open questions this finding could not resolve"
    )
    payload: dict = Field(
        default_factory=dict,
        description=(
            "Optional structured sub-output that doesn't fit the string-based evidence/tags "
            "scheme (e.g. a serialized CustomerAvatarProfile, a list of generated hooks). "
            "Downstream agents read this via context.findings_by_agent(...) rather than "
            "dedicated context fields, keeping the existing finding-passing pattern uniform."
        ),
    )

    def is_actionable(self) -> bool:
        return bool(self.suggested_actions) and self.suggested_actions != [ActionType.DO_NOTHING]


class Recommendation(BaseModel):
    """A single proposed change, fully justified and ready for Guardian review."""

    recommendation_id: str
    entity_id: str
    entity_level: str = Field(..., description="campaign | ad_set | ad")
    action: ActionType
    priority: Priority
    reason: str
    evidence: list[str] = Field(default_factory=list)
    contributing_agents: list[str] = Field(default_factory=list)
    expected_impact: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk: RiskLevel
    measurement: str = Field(..., description="How success/failure will be measured")
    review_window_days: int = Field(..., ge=1)
    requires_approval: bool = True
    data_sufficiency: DataSufficiencyLevel
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_summary_dict(self) -> dict:
        return {
            "action": self.action.value,
            "priority": self.priority.value,
            "reason": self.reason,
            "evidence": self.evidence,
            "expected_impact": self.expected_impact,
            "confidence": self.confidence,
            "risk": self.risk.value,
            "measurement": self.measurement,
            "review_window": f"{self.review_window_days} days",
            "requires_approval": self.requires_approval,
        }
