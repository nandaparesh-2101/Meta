"""SQLite-backed memory store.

Single source of persistence for findings, recommendations, guardian
decisions, experiments, experiment results, learnings, and the audit log.
Every important system event flows through here — nothing about a
decision the system made is allowed to be invisible.

Rows are stored as validated Pydantic JSON so a read always reconstructs a
proper typed model, never a raw dict passed further up the stack.
"""

from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from app.config import settings
from app.models.execution import (
    ApprovalRequest,
    AuditEvent,
    AuditEventType,
    ExecutionResult,
    GuardianDecision,
)
from app.models.experiments import Experiment, ExperimentResult, ExperimentStatus
from app.models.learning import Learning
from app.models.recommendations import AgentFinding, Recommendation

SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    entity_id TEXT,
    timestamp TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_id);

CREATE TABLE IF NOT EXISTS findings (
    finding_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    entity_id TEXT,
    generated_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_entity ON findings(entity_id);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guardian_decisions (
    recommendation_id TEXT PRIMARY KEY,
    verdict TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiments (
    experiment_id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_experiments_fingerprint ON experiments(fingerprint);

CREATE TABLE IF NOT EXISTS experiment_results (
    experiment_id TEXT PRIMARY KEY,
    recorded_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learnings (
    learning_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    tags TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    recommendation_id TEXT NOT NULL,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS execution_results (
    execution_id TEXT PRIMARY KEY,
    recommendation_id TEXT,
    status TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    payload TEXT NOT NULL
);
"""


class MemoryStore:
    """Implements the `AuditRecorder` protocol (`.record(...)`) plus the
    full read/write surface for findings, recommendations, guardian
    decisions, experiments and learnings."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path else Path(settings.sqlite_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # -- Audit log -----------------------------------------------------

    def record(
        self,
        event_type: AuditEventType,
        actor: str,
        summary: str,
        details: dict | None = None,
        entity_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=f"audit_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            actor=actor,
            summary=summary,
            details=details or {},
            entity_id=entity_id,
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.event_type.value,
                    event.actor,
                    event.entity_id,
                    event.timestamp.isoformat(),
                    event.model_dump_json(),
                ),
            )
        return event

    def get_audit_events(self, limit: int = 200, entity_id: str | None = None) -> list[AuditEvent]:
        query = "SELECT payload FROM audit_events"
        params: tuple = ()
        if entity_id:
            query += " WHERE entity_id = ?"
            params = (entity_id,)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params = params + (limit,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [AuditEvent.model_validate_json(row[0]) for row in rows]

    # -- Findings --------------------------------------------------------

    def save_finding(self, finding: AgentFinding) -> None:
        finding_id = f"finding_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO findings VALUES (?, ?, ?, ?, ?)",
                (finding_id, finding.agent_name, finding.entity_id, finding.generated_at.isoformat(), finding.model_dump_json()),
            )

    def get_findings(self, entity_id: str | None = None, limit: int = 500) -> list[AgentFinding]:
        query = "SELECT payload FROM findings"
        params: tuple = ()
        if entity_id:
            query += " WHERE entity_id = ?"
            params = (entity_id,)
        query += " ORDER BY generated_at DESC LIMIT ?"
        params = params + (limit,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [AgentFinding.model_validate_json(row[0]) for row in rows]

    # -- Recommendations ---------------------------------------------------

    def save_recommendation(self, recommendation: Recommendation) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO recommendations VALUES (?, ?, ?, ?)",
                (
                    recommendation.recommendation_id,
                    recommendation.entity_id,
                    recommendation.created_at.isoformat(),
                    recommendation.model_dump_json(),
                ),
            )
        self.record(
            AuditEventType.RECOMMENDATION_CREATED,
            actor="optimization",
            summary=f"Recommendation {recommendation.recommendation_id} created: {recommendation.action.value}",
            details=recommendation.to_summary_dict(),
            entity_id=recommendation.entity_id,
        )

    def get_recommendations(self, limit: int = 200) -> list[Recommendation]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM recommendations ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Recommendation.model_validate_json(row[0]) for row in rows]

    # -- Guardian decisions --------------------------------------------------

    def save_guardian_decision(self, decision: GuardianDecision) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO guardian_decisions VALUES (?, ?, ?, ?)",
                (
                    decision.recommendation_id,
                    decision.verdict.value,
                    decision.decided_at.isoformat(),
                    decision.model_dump_json(),
                ),
            )

    def get_guardian_decision(self, recommendation_id: str) -> GuardianDecision | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM guardian_decisions WHERE recommendation_id = ?", (recommendation_id,)
            ).fetchone()
        return GuardianDecision.model_validate_json(row[0]) if row else None

    # -- Experiments ----------------------------------------------------------

    def save_experiment(self, experiment: Experiment) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO experiments VALUES (?, ?, ?, ?, ?)",
                (
                    experiment.experiment_id,
                    experiment.fingerprint(),
                    experiment.status.value,
                    experiment.created_at.isoformat(),
                    experiment.model_dump_json(),
                ),
            )
        self.record(
            AuditEventType.EXPERIMENT_CREATED,
            actor="experimentation",
            summary=f"Experiment {experiment.experiment_id} created: {experiment.hypothesis}",
            details={"variable": experiment.variable},
        )

    def get_all_experiments(self) -> list[Experiment]:
        with self._connect() as conn:
            rows = conn.execute("SELECT payload FROM experiments ORDER BY created_at DESC").fetchall()
        return [Experiment.model_validate_json(row[0]) for row in rows]

    def get_active_experiments(self) -> list[Experiment]:
        active_statuses = (ExperimentStatus.PLANNED.value, ExperimentStatus.RUNNING.value)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT payload FROM experiments WHERE status IN "
                f"({','.join('?' for _ in active_statuses)})",
                active_statuses,
            ).fetchall()
        return [Experiment.model_validate_json(row[0]) for row in rows]

    def find_experiment_by_fingerprint(self, fingerprint: str) -> Experiment | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM experiments WHERE fingerprint = ? ORDER BY created_at DESC LIMIT 1",
                (fingerprint,),
            ).fetchone()
        return Experiment.model_validate_json(row[0]) if row else None

    def save_experiment_result(self, result: ExperimentResult) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO experiment_results VALUES (?, ?, ?)",
                (result.experiment_id, result.recorded_at.isoformat(), result.model_dump_json()),
            )

    def get_experiment_result(self, experiment_id: str) -> ExperimentResult | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM experiment_results WHERE experiment_id = ?", (experiment_id,)
            ).fetchone()
        return ExperimentResult.model_validate_json(row[0]) if row else None

    # -- Learnings --------------------------------------------------------

    def save_learning(self, learning: Learning) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO learnings VALUES (?, ?, ?, ?)",
                (
                    learning.learning_id,
                    learning.created_at.isoformat(),
                    ",".join(learning.tags),
                    learning.model_dump_json(),
                ),
            )
        self.record(
            AuditEventType.LEARNING_RECORDED,
            actor="memory",
            summary=f"Learning recorded: {learning.learning}",
            details={"confidence": learning.confidence, "sample_size": learning.sample_size},
        )

    def get_learnings(self, tag: str | None = None, limit: int = 200) -> list[Learning]:
        query = "SELECT payload FROM learnings"
        params: tuple = ()
        if tag:
            query += " WHERE ',' || tags || ',' LIKE ?"
            params = (f"%,{tag},%",)
        query += " ORDER BY created_at DESC LIMIT ?"
        params = params + (limit,)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [Learning.model_validate_json(row[0]) for row in rows]

    # -- Approvals --------------------------------------------------------

    def save_approval(self, approval: ApprovalRequest) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO approvals VALUES (?, ?, ?, ?, ?)",
                (
                    approval.approval_id,
                    approval.recommendation_id,
                    approval.status.value,
                    approval.requested_at.isoformat(),
                    approval.model_dump_json(),
                ),
            )

    def get_approval(self, approval_id: str) -> ApprovalRequest | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
        return ApprovalRequest.model_validate_json(row[0]) if row else None

    def get_pending_approvals(self) -> list[ApprovalRequest]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM approvals WHERE status = 'pending' ORDER BY requested_at DESC"
            ).fetchall()
        return [ApprovalRequest.model_validate_json(row[0]) for row in rows]

    # -- Execution results --------------------------------------------------

    def get_execution_result(self, execution_id: str) -> ExecutionResult | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM execution_results WHERE execution_id = ?", (execution_id,)
            ).fetchone()
        return ExecutionResult.model_validate_json(row[0]) if row else None

    def save_execution_result(self, result: ExecutionResult, recommendation_id: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO execution_results VALUES (?, ?, ?, ?, ?)",
                (
                    result.execution_id,
                    recommendation_id,
                    result.status.value,
                    result.executed_at.isoformat(),
                    result.model_dump_json(),
                ),
            )
