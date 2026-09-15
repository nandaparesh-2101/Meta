"""Customer avatar + buyer awareness models (agents 17 and 19).

`CustomerAvatarProfile` explicitly separates OBSERVED (directly present in
the data), INFERRED (a reasonable read of observed data), and HYPOTHESIZED
(a plausible guess with no direct support) facts about the customer — the
system must never blur these into a single undifferentiated "profile."
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

AVATAR_DIMENSIONS = (
    "demographics",
    "behaviors",
    "needs",
    "pain_points",
    "desired_outcomes",
    "objections",
    "buying_triggers",
    "fears",
    "motivations",
    "decision_factors",
    "price_sensitivity",
)


class BuyerAwarenessLevel(str, Enum):
    UNAWARE = "unaware"
    PROBLEM_AWARE = "problem_aware"
    SOLUTION_AWARE = "solution_aware"
    PRODUCT_AWARE = "product_aware"
    MOST_AWARE = "most_aware"


AWARENESS_MESSAGING_STRUCTURE: dict[BuyerAwarenessLevel, list[str]] = {
    BuyerAwarenessLevel.UNAWARE: ["Pattern interrupt", "Relatable scenario", "Problem introduction", "Curiosity CTA"],
    BuyerAwarenessLevel.PROBLEM_AWARE: ["Problem", "Consequence", "Solution", "Proof", "CTA"],
    BuyerAwarenessLevel.SOLUTION_AWARE: ["Solution category", "Why this approach", "Differentiation", "Proof", "CTA"],
    BuyerAwarenessLevel.PRODUCT_AWARE: ["Product", "Differentiation vs. alternatives", "Proof", "Offer", "CTA"],
    BuyerAwarenessLevel.MOST_AWARE: ["Offer", "Proof", "Urgency", "CTA"],
}


class CustomerAvatarProfile(BaseModel):
    """Every dimension is a dict of `AVATAR_DIMENSIONS -> list[str]`, kept
    separate across the three certainty buckets. A dimension absent from a
    bucket simply has no entries there — it is never backfilled with a
    plausible-sounding guess."""

    observed: dict[str, list[str]] = Field(default_factory=dict)
    inferred: dict[str, list[str]] = Field(default_factory=dict)
    hypothesized: dict[str, list[str]] = Field(default_factory=dict)
    awareness_level: BuyerAwarenessLevel | None = None
    confidence: float = Field(..., ge=0.0, le=1.0)

    def all_for_dimension(self, dimension: str) -> dict[str, list[str]]:
        return {
            "observed": self.observed.get(dimension, []),
            "inferred": self.inferred.get(dimension, []),
            "hypothesized": self.hypothesized.get(dimension, []),
        }

    def has_any_observed_data(self) -> bool:
        return any(self.observed.values())
