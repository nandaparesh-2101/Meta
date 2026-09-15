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
