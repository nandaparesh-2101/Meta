"""Controlled-experiment models.

Every experiment is a falsifiable, pre-registered test — never an
uncontrolled "let's try changing this and see."
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class ExperimentStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETE_WIN = "complete_win"
    COMPLETE_LOSS = "complete_loss"
    COMPLETE_INCONCLUSIVE = "complete_inconclusive"
    ABANDONED = "abandoned"


class Experiment(BaseModel):
    experiment_id: str
    hypothesis: str = Field(..., description="If X, then Y, because Z")
    variable: str = Field(..., description="The single thing being changed")
    control_description: str
    test_description: str
    success_metric: str
    minimum_data_requirement: str = Field(
        ..., description="e.g. '50 leads per arm' or '14 days per arm'"
    )
    decision_rule: str = Field(..., description="Explicit rule for declaring a winner")
    review_window_days: int = Field(..., ge=1)
    related_entity_ids: list[str] = Field(default_factory=list)
    status: ExperimentStatus = ExperimentStatus.PLANNED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_date: date | None = None
    ended_date: date | None = None

    def fingerprint(self) -> str:
        """Normalized identity used for duplicate-experiment detection."""
        return f"{self.variable.strip().lower()}::{self.hypothesis.strip().lower()}"


class ExperimentResult(BaseModel):
    experiment_id: str
    control_metric_value: float
    test_metric_value: float
    relative_lift_pct: float
    sample_size_control: int
    sample_size_test: int
    is_statistically_meaningful: bool
    winner: str = Field(..., description="'control' | 'test' | 'inconclusive'")
    learning: str
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
