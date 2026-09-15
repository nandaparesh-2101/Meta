from __future__ import annotations

from app.models.execution import AuditEventType
from app.models.experiments import Experiment, ExperimentStatus
from app.models.learning import Learning


def _experiment(hypothesis="If we lead with a problem, CTR improves", variable="copy") -> Experiment:
    return Experiment(
        experiment_id="exp_test1",
        hypothesis=hypothesis,
        variable=variable,
        control_description="current copy",
        test_description="problem-first copy",
        success_metric="CTR",
        minimum_data_requirement="50 leads per arm",
        decision_rule="10% lift wins",
        review_window_days=14,
    )


def test_audit_log_records_and_reads_back(memory_store):
    memory_store.record(AuditEventType.AGENT_STARTED, actor="test_agent", summary="started")
    events = memory_store.get_audit_events()
    assert len(events) == 1
    assert events[0].actor == "test_agent"


def test_experiment_dedup_by_fingerprint(memory_store):
    exp1 = _experiment()
    memory_store.save_experiment(exp1)

    duplicate = _experiment()  # same hypothesis + variable
    duplicate = duplicate.model_copy(update={"experiment_id": "exp_test2"})
    assert exp1.fingerprint() == duplicate.fingerprint()

    found = memory_store.find_experiment_by_fingerprint(duplicate.fingerprint())
    assert found is not None
    assert found.experiment_id == exp1.experiment_id


def test_experiment_materially_different_hypothesis_is_not_a_duplicate(memory_store):
    exp1 = _experiment()
    memory_store.save_experiment(exp1)
    different = _experiment(hypothesis="A shorter headline will improve CTR", variable="headline_length")
    assert memory_store.find_experiment_by_fingerprint(different.fingerprint()) is None


def test_active_experiments_excludes_completed(memory_store):
    running = _experiment().model_copy(update={"experiment_id": "exp_running", "status": ExperimentStatus.RUNNING})
    done = _experiment().model_copy(
        update={"experiment_id": "exp_done", "status": ExperimentStatus.COMPLETE_WIN, "variable": "other"}
    )
    memory_store.save_experiment(running)
    memory_store.save_experiment(done)
    active_ids = {e.experiment_id for e in memory_store.get_active_experiments()}
    assert "exp_running" in active_ids
    assert "exp_done" not in active_ids


def test_learning_round_trip_and_tag_filter(memory_store):
    learning = Learning(
        learning_id="learn_1",
        observation="obs",
        action="action",
        result="result",
        learning="problem-first messaging looks promising",
        future_implication="test further",
        tags=["copy"],
        confidence=0.4,
        sample_size=40,
    )
    memory_store.save_learning(learning)
    all_learnings = memory_store.get_learnings()
    assert len(all_learnings) == 1
    tagged = memory_store.get_learnings(tag="copy")
    assert len(tagged) == 1
    not_generalizable = all_learnings[0]
    assert not_generalizable.is_generalizable is False  # sample_size < 100
