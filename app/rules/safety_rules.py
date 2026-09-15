"""Safety checks consumed by the Guardian agent.

Each function returns a list of concern strings (empty = no concern). These
are intentionally simple, explicit, and independently testable — Guardian
should never rely on "AI judgment" for hard safety limits.
"""

from __future__ import annotations

from app.models.business import BusinessConstraints
from app.models.experiments import Experiment
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, Recommendation, RiskLevel


def check_data_sufficiency(recommendation: Recommendation) -> list[str]:
    concerns: list[str] = []
    if recommendation.data_sufficiency == DataSufficiencyLevel.INSUFFICIENT_DATA:
        concerns.append(
            "Recommendation is based on INSUFFICIENT_DATA — evidence does not "
            "clear the minimum bar for action."
        )
    elif (
        recommendation.data_sufficiency == DataSufficiencyLevel.EARLY_SIGNAL
        and recommendation.priority.value in ("P0", "P1")
    ):
        concerns.append(
            "High priority assigned despite only EARLY_SIGNAL data sufficiency."
        )
    return concerns


def check_budget_risk(
    recommendation: Recommendation, constraints: BusinessConstraints, current_budget: float | None
) -> list[str]:
    concerns: list[str] = []
    if recommendation.action not in (
        ActionType.INCREASE_BUDGET,
        ActionType.DECREASE_BUDGET,
        ActionType.REALLOCATE_BUDGET,
    ):
        return concerns
    if current_budget is None:
        concerns.append("Budget change proposed without a known current budget baseline.")
        return concerns
    if constraints.max_daily_budget is not None and current_budget > constraints.max_daily_budget:
        concerns.append("Entity's current budget already exceeds the configured hard cap.")
    if recommendation.entity_id in constraints.protected_campaign_ids:
        concerns.append("Entity is on the protected-campaign list; budget changes require explicit human review.")
    return concerns


def check_excessive_scaling(recommendation: Recommendation, proposed_change_pct: float | None) -> list[str]:
    concerns: list[str] = []
    if proposed_change_pct is not None and abs(proposed_change_pct) > 0.5:
        concerns.append(
            f"Proposed change of {proposed_change_pct:.0%} is aggressive; "
            "large single-step changes carry outsized risk."
        )
    return concerns


def check_confidence_vs_risk(recommendation: Recommendation) -> list[str]:
    concerns: list[str] = []
    if recommendation.risk == RiskLevel.HIGH and recommendation.confidence < 0.6:
        concerns.append("High risk action proposed with confidence below 0.6.")
    return concerns


def check_duplicate_experiment(new_experiment: Experiment, existing_experiments: list[Experiment]) -> list[str]:
    concerns: list[str] = []
    new_fp = new_experiment.fingerprint()
    for existing in existing_experiments:
        if existing.fingerprint() == new_fp:
            concerns.append(
                f"An experiment with the same variable/hypothesis already exists "
                f"(experiment_id={existing.experiment_id}, status={existing.status.value})."
            )
    return concerns


def check_missing_measurement_plan(recommendation: Recommendation) -> list[str]:
    concerns: list[str] = []
    if not recommendation.measurement or not recommendation.measurement.strip():
        concerns.append("Recommendation has no measurement plan defined.")
    return concerns


def check_tracking_anomaly(tags: list[str]) -> list[str]:
    concerns: list[str] = []
    if "tracking_anomaly" in tags:
        concerns.append(
            "Underlying data carries a tracking_anomaly tag; recommendation may be "
            "based on corrupted or mis-attributed data."
        )
    return concerns
