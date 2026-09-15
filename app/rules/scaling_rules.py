"""Budget scaling guardrails.

Encodes "never scale aggressively without evidence" as executable rules
consumed by the Budget & Scaling agent and re-checked by Guardian.
"""

from __future__ import annotations

from app.models.business import BusinessConstraints
from app.models.metrics import DataSufficiencyLevel


def max_allowed_budget_change_pct(
    constraints: BusinessConstraints, data_sufficiency: DataSufficiencyLevel
) -> float:
    """Scale down the allowed budget change further when evidence is weak,
    on top of the business's own hard cap."""
    sufficiency_multiplier = {
        DataSufficiencyLevel.INSUFFICIENT_DATA: 0.0,
        DataSufficiencyLevel.EARLY_SIGNAL: 0.25,
        DataSufficiencyLevel.PROMISING: 0.6,
        DataSufficiencyLevel.CONFIDENT: 1.0,
    }[data_sufficiency]
    return constraints.max_budget_change_pct_per_change * sufficiency_multiplier


def is_scaling_change_safe(
    *,
    current_daily_budget: float,
    proposed_daily_budget: float,
    constraints: BusinessConstraints,
    data_sufficiency: DataSufficiencyLevel,
    days_running: int,
) -> tuple[bool, str]:
    """Returns (is_safe, reason)."""
    if days_running < constraints.min_data_days_before_scaling:
        return False, (
            f"Only {days_running} day(s) running; business requires "
            f"{constraints.min_data_days_before_scaling} days before any scaling change."
        )

    if current_daily_budget <= 0:
        return False, "Current budget is zero/invalid; cannot compute a safe scaling delta."

    change_pct = abs(proposed_daily_budget - current_daily_budget) / current_daily_budget
    allowed_pct = max_allowed_budget_change_pct(constraints, data_sufficiency)

    if allowed_pct <= 0:
        return False, (
            "Data sufficiency is INSUFFICIENT_DATA; no budget scaling is permitted yet."
        )

    if change_pct > allowed_pct:
        return False, (
            f"Proposed change of {change_pct:.0%} exceeds the "
            f"{allowed_pct:.0%} ceiling allowed at this evidence level."
        )

    if constraints.max_daily_budget is not None and proposed_daily_budget > constraints.max_daily_budget:
        return False, (
            f"Proposed budget {proposed_daily_budget:.2f} exceeds the business's hard cap "
            f"of {constraints.max_daily_budget:.2f}."
        )

    return True, "Within safe scaling bounds."
