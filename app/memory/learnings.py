"""Learning-memory helpers.

Formats and persists learnings in the required
OBSERVATION -> ACTION -> RESULT -> LEARNING -> FUTURE_IMPLICATION shape, and
guards against overgeneralizing from a single small experiment.
"""

from __future__ import annotations

import uuid

from app.memory.store import MemoryStore
from app.models.experiments import Experiment, ExperimentResult
from app.models.learning import Learning


class LearningMemory:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def record_from_experiment(self, experiment: Experiment, result: ExperimentResult) -> Learning:
        sample_size = result.sample_size_control + result.sample_size_test
        confidence = 0.75 if result.is_statistically_meaningful else 0.35

        future_implication = (
            "Promising — consider testing a related hypothesis with a larger sample before "
            "generalizing further."
            if sample_size < 100
            else "Sample size supports treating this as a reasonably reliable pattern for similar audiences/offers."
        )

        learning = Learning(
            learning_id=f"learn_{uuid.uuid4().hex[:12]}",
            observation=f"Experiment tested: {experiment.hypothesis}",
            action=f"Ran controlled test — control: {experiment.control_description}; test: {experiment.test_description}",
            result=(
                f"{result.winner} won with {result.relative_lift_pct:+.1%} relative lift on "
                f"{experiment.success_metric} (statistically meaningful={result.is_statistically_meaningful})"
            ),
            learning=result.learning,
            future_implication=future_implication,
            source_experiment_id=experiment.experiment_id,
            related_entity_ids=experiment.related_entity_ids,
            tags=[experiment.variable],
            confidence=confidence,
            sample_size=sample_size,
        )
        self.store.save_learning(learning)
        return learning

    def relevant_to(self, tag: str) -> list[Learning]:
        return self.store.get_learnings(tag=tag)

    def generalizable_only(self, tag: str | None = None) -> list[Learning]:
        return [l for l in self.store.get_learnings(tag=tag) if l.is_generalizable]
