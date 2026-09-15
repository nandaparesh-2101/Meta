"""Data Sufficiency Engine.

Decides whether the evidence behind a finding is strong enough to support a
confident recommendation. Every specialist agent must consult this before
elevating a suggestion to P0/P1, and Guardian re-checks it independently.
"""

from __future__ import annotations

from app.models.metrics import DataSufficiencyLevel, DataSufficiencyResult

# Defaults — override per-agent when a specific analysis needs a stricter bar
# (e.g. lead-quality conclusions need more leads than a CTR observation does).
DEFAULT_MIN_DAYS = 7
DEFAULT_MIN_SAMPLE = 50


def assess_data_sufficiency(
    *,
    days_of_data: int,
    sample_size: int,
    minimum_days_required: int = DEFAULT_MIN_DAYS,
    minimum_sample_required: int = DEFAULT_MIN_SAMPLE,
) -> DataSufficiencyResult:
    """Classify evidence strength.

    - INSUFFICIENT_DATA: below half the minimum threshold on either axis.
    - EARLY_SIGNAL: below the minimum threshold, but not by much.
    - PROMISING: meets both minimums, but not comfortably beyond them.
    - CONFIDENT: comfortably (>=2x) beyond both minimums.
    """
    days_ratio = days_of_data / minimum_days_required if minimum_days_required else 1.0
    sample_ratio = sample_size / minimum_sample_required if minimum_sample_required else 1.0
    worst_ratio = min(days_ratio, sample_ratio)

    if worst_ratio < 0.5:
        level = DataSufficiencyLevel.INSUFFICIENT_DATA
        reason = (
            f"Only {days_of_data} day(s) and {sample_size} sample(s) observed; "
            f"need at least {minimum_days_required} days and {minimum_sample_required} "
            "samples before any pattern can be trusted."
        )
    elif worst_ratio < 1.0:
        level = DataSufficiencyLevel.EARLY_SIGNAL
        reason = (
            f"{days_of_data} day(s) / {sample_size} sample(s) is below the "
            f"{minimum_days_required}-day / {minimum_sample_required}-sample bar; "
            "treat as a hint worth watching, not a basis for action."
        )
    elif worst_ratio < 2.0:
        level = DataSufficiencyLevel.PROMISING
        reason = (
            f"{days_of_data} day(s) / {sample_size} sample(s) clears the minimum "
            "bar. Directionally trustworthy; a bit more data would raise confidence further."
        )
    else:
        level = DataSufficiencyLevel.CONFIDENT
        reason = (
            f"{days_of_data} day(s) / {sample_size} sample(s) is comfortably beyond "
            "the minimum bar. Safe to treat this evidence as solid."
        )

    return DataSufficiencyResult(
        level=level,
        reason=reason,
        days_of_data=days_of_data,
        sample_size=sample_size,
        minimum_days_required=minimum_days_required,
        minimum_sample_required=minimum_sample_required,
    )


def confidence_ceiling(level: DataSufficiencyLevel) -> float:
    """Hard cap on the confidence score an agent may report for a given
    sufficiency level — prevents an agent from claiming 0.95 confidence off
    two days of data."""
    return {
        DataSufficiencyLevel.INSUFFICIENT_DATA: 0.25,
        DataSufficiencyLevel.EARLY_SIGNAL: 0.5,
        DataSufficiencyLevel.PROMISING: 0.75,
        DataSufficiencyLevel.CONFIDENT: 0.95,
    }[level]
