"""Brand voice profile (agent 62).

Consumed by content-quality/copy-editing agents so generated copy respects
a consistent voice rather than each agent inventing its own tone.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BrandVoiceProfile(BaseModel):
    tone: str = Field(..., description="e.g. 'direct, encouraging, no-nonsense'")
    vocabulary_notes: str = ""
    personality: str = ""
    formality: str = Field(default="conversational", description="'formal' | 'conversational' | 'casual'")
    emotional_style: str = ""
    words_to_use: list[str] = Field(default_factory=list)
    words_to_avoid: list[str] = Field(default_factory=list)
