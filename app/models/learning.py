"""Persisted institutional memory.

Format: OBSERVATION -> ACTION -> RESULT -> LEARNING -> FUTURE_IMPLICATION.
A single learning is a data point, not a law — `confidence` and
`sample_size` exist so the memory layer can refuse to overgeneralize from
one experiment.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Learning(BaseModel):
    learning_id: str
    observation: str
    action: str
    result: str
    learning: str
    future_implication: str
    source_experiment_id: str | None = None
    related_entity_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    sample_size: int = Field(..., ge=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_generalizable(self) -> bool:
        """A single small experiment should not be treated as an established
        rule. This is a soft guard used by the memory layer/UI, not a hard
        block — agents still see low-confidence learnings, just labeled."""
        return self.sample_size >= 100 and self.confidence >= 0.7
