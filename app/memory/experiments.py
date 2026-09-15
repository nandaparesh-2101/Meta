"""Experiment-memory helpers: duplicate prevention and lifecycle queries.

Thin convenience layer over `MemoryStore` so callers don't have to know the
storage details — only "search previous experiments before creating a new
one" semantics.
"""

from __future__ import annotations

from app.memory.store import MemoryStore
from app.models.experiments import Experiment, ExperimentResult, ExperimentStatus


class ExperimentMemory:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store

    def find_duplicate(self, candidate: Experiment) -> Experiment | None:
        """Search previous experiments for the same hypothesis/variable
        fingerprint before a new one is created. Returns the most recent
        matching experiment, or None if this is a materially new hypothesis."""
        return self.store.find_experiment_by_fingerprint(candidate.fingerprint())

    def register(self, experiment: Experiment) -> Experiment | None:
        """Registers a new experiment unless a duplicate already exists.
        Returns the newly stored experiment, or None if it was a duplicate
        (caller should surface the existing experiment instead)."""
        existing = self.find_duplicate(experiment)
        if existing is not None:
            return None
        self.store.save_experiment(experiment)
        return experiment

    def mark_running(self, experiment_id: str, experiment: Experiment) -> None:
        updated = experiment.model_copy(update={"status": ExperimentStatus.RUNNING})
        self.store.save_experiment(updated)

    def record_result(self, experiment: Experiment, result: ExperimentResult) -> None:
        status = {
            "test": ExperimentStatus.COMPLETE_WIN,
            "control": ExperimentStatus.COMPLETE_LOSS,
            "inconclusive": ExperimentStatus.COMPLETE_INCONCLUSIVE,
        }.get(result.winner, ExperimentStatus.COMPLETE_INCONCLUSIVE)
        updated = experiment.model_copy(update={"status": status})
        self.store.save_experiment(updated)
        self.store.save_experiment_result(result)

    def active(self) -> list[Experiment]:
        return self.store.get_active_experiments()

    def all(self) -> list[Experiment]:
        return self.store.get_all_experiments()
