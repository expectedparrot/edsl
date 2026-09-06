"""SQLite persistence for workflow instances, work items, events, and outbox."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping
from uuid import uuid4

from edsl._data_contracts import canonical_data, definition_fingerprint


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteWorkflowStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS workflow_instances (
                    id TEXT PRIMARY KEY, definition TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL, completed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS workflow_participants (
                    instance_id TEXT NOT NULL, participant_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    PRIMARY KEY (instance_id, participant_id)
                );
                CREATE TABLE IF NOT EXISTS workflow_items (
                    id TEXT PRIMARY KEY, instance_id TEXT NOT NULL,
                    step_name TEXT NOT NULL, participant_id TEXT NOT NULL,
                    status TEXT NOT NULL, created_at TEXT NOT NULL,
                    opened_at TEXT, completed_at TEXT,
                    UNIQUE(instance_id, step_name, participant_id)
                );
                CREATE TABLE IF NOT EXISTS workflow_submissions (
                    id TEXT PRIMARY KEY, work_item_id TEXT NOT NULL UNIQUE,
                    idempotency_key TEXT NOT NULL UNIQUE, answers TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    instance_id TEXT NOT NULL, kind TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_outbox (
                    id TEXT PRIMARY KEY, work_item_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_external_tasks (
                    provider TEXT NOT NULL, work_item_id TEXT NOT NULL,
                    resource_id TEXT NOT NULL UNIQUE, delivery_id TEXT,
                    status TEXT NOT NULL, created_at TEXT NOT NULL,
                    completed_at TEXT,
                    PRIMARY KEY(provider, work_item_id)
                );
                CREATE TABLE IF NOT EXISTS workflow_item_renders (
                    work_item_id TEXT PRIMARY KEY, survey TEXT NOT NULL,
                    shared_state TEXT NOT NULL, state_versions TEXT NOT NULL,
                    rendered_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_attempts (
                    id TEXT PRIMARY KEY, work_item_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL, status TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL, error_kind TEXT,
                    error_message TEXT, started_at TEXT NOT NULL, finished_at TEXT,
                    UNIQUE(work_item_id, attempt_number)
                );
                CREATE TABLE IF NOT EXISTS workflow_executor_resolutions (
                    work_item_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                    options TEXT NOT NULL, resolved_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_model_resolutions (
                    work_item_id TEXT PRIMARY KEY, definition TEXT NOT NULL,
                    definition_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_instance_contracts (
                    instance_id TEXT PRIMARY KEY, definition_hash TEXT NOT NULL,
                    random_seed TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_submission_intents (
                    work_item_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                    answers TEXT NOT NULL, attempt_id TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workflow_effects (
                    work_item_id TEXT NOT NULL, position INTEGER NOT NULL,
                    operation TEXT NOT NULL, applied INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(work_item_id, position)
                );
                """
            )

    def create_instance(
        self,
        instance_id: str,
        definition: Mapping[str, Any],
        participants: Iterable[tuple[str, Mapping[str, Any]]],
        *,
        random_seed: str | int | None = None,
        assignments: Iterable[tuple[str, str]] = (),
    ) -> None:
        now = _now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO workflow_instances VALUES (?, ?, 'running', ?, NULL)",
                (instance_id, canonical_data(dict(definition)), now),
            )
            for participant_id, agent in participants:
                db.execute(
                    "INSERT INTO workflow_participants VALUES (?, ?, ?)",
                    (instance_id, participant_id, canonical_data(dict(agent))),
                )
            for step_name, participant_id in assignments:
                db.execute(
                    "INSERT INTO workflow_items VALUES (?, ?, ?, ?, 'blocked', ?, NULL, NULL)",
                    (str(uuid4()), instance_id, step_name, participant_id, _now()),
                )
            db.execute(
                "INSERT INTO workflow_instance_contracts VALUES (?, ?, ?)",
                (
                    instance_id,
                    definition_fingerprint(definition),
                    canonical_data(instance_id if random_seed is None else random_seed),
                ),
            )
            self._event(db, instance_id, "workflow.started", {})
            db.commit()

    def assert_definition(
        self, instance_id: str, definition: Mapping[str, Any]
    ) -> None:
        stored_definition = self.definition(instance_id)
        stored = definition_fingerprint(stored_definition)
        if stored != definition_fingerprint(definition):
            raise ValueError(
                "workflow definition changed; start a new instance or explicitly migrate the stored definition"
            )

    def definition(self, instance_id: str) -> dict[str, Any]:
        """Return the pinned workflow definition after verifying its fingerprint."""
        rows = self.rows(
            "SELECT definition FROM workflow_instances WHERE id = ?", (instance_id,)
        )
        if not rows:
            raise KeyError(f"unknown workflow instance {instance_id!r}")
        definition = json.loads(rows[0]["definition"])
        stored = definition_fingerprint(definition)
        contracts = self.rows(
            "SELECT definition_hash FROM workflow_instance_contracts WHERE instance_id = ?",
            (instance_id,),
        )
        if contracts and contracts[0]["definition_hash"] != stored:
            raise ValueError(
                "persisted workflow definition does not match its fingerprint"
            )
        return definition

    def random_seed(self, instance_id: str) -> str | int:
        rows = self.rows(
            "SELECT random_seed FROM workflow_instance_contracts WHERE instance_id = ?",
            (instance_id,),
        )
        return json.loads(rows[0]["random_seed"]) if rows else instance_id

    def create_item(self, instance_id: str, step_name: str, participant_id: str) -> str:
        item_id = str(uuid4())
        with self.connect() as db:
            db.execute(
                "INSERT INTO workflow_items VALUES (?, ?, ?, ?, 'blocked', ?, NULL, NULL)",
                (item_id, instance_id, step_name, participant_id, _now()),
            )
        return item_id

    def rows(self, query: str, parameters: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self.connect() as db:
            return db.execute(query, parameters).fetchall()

    def items(
        self, instance_id: str, *, step_name: str | None = None
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM workflow_items WHERE instance_id = ?"
        params: tuple[Any, ...] = (instance_id,)
        if step_name is not None:
            query += " AND step_name = ?"
            params += (step_name,)
        return self.rows(query + " ORDER BY created_at, id", params)

    def item(self, item_id: str) -> sqlite3.Row:
        rows = self.rows("SELECT * FROM workflow_items WHERE id = ?", (item_id,))
        if not rows:
            raise KeyError(f"unknown work item {item_id!r}")
        return rows[0]

    def participant(self, instance_id: str, participant_id: str) -> dict[str, Any]:
        rows = self.rows(
            "SELECT agent FROM workflow_participants WHERE instance_id = ? AND participant_id = ?",
            (instance_id, participant_id),
        )
        if not rows:
            raise KeyError(f"unknown participant {participant_id!r}")
        return json.loads(rows[0]["agent"])

    def record_executor(
        self, work_item_id: str, kind: str, options: Mapping[str, Any]
    ) -> None:
        encoded = canonical_data(dict(options))
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO workflow_executor_resolutions VALUES (?, ?, ?, ?) "
                "ON CONFLICT(work_item_id) DO NOTHING",
                (work_item_id, kind, encoded, _now()),
            )
            saved = db.execute(
                "SELECT kind, options FROM workflow_executor_resolutions WHERE work_item_id = ?",
                (work_item_id,),
            ).fetchone()
            if (
                saved["kind"] != kind
                or canonical_data(json.loads(saved["options"])) != encoded
            ):
                raise ValueError(
                    "work item executor changed after its first resolution"
                )
            db.commit()

    def executor(self, work_item_id: str) -> dict[str, Any] | None:
        rows = self.rows(
            "SELECT * FROM workflow_executor_resolutions WHERE work_item_id = ?",
            (work_item_id,),
        )
        return (
            None
            if not rows
            else {"kind": rows[0]["kind"], "options": json.loads(rows[0]["options"])}
        )

    def record_model(self, work_item_id: str, definition: Mapping[str, Any]) -> None:
        """Pin the concrete EDSL model, independently of executor routing policy."""
        fingerprint = definition_fingerprint(definition)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO workflow_model_resolutions VALUES (?, ?, ?) ON CONFLICT(work_item_id) DO NOTHING",
                (work_item_id, canonical_data(dict(definition)), fingerprint),
            )
            saved = db.execute(
                "SELECT definition_hash FROM workflow_model_resolutions WHERE work_item_id = ?",
                (work_item_id,),
            ).fetchone()
            if saved["definition_hash"] != fingerprint:
                raise ValueError("work item model changed after its first resolution")
            db.commit()

    def model(self, work_item_id: str) -> dict[str, Any] | None:
        rows = self.rows(
            "SELECT definition FROM workflow_model_resolutions WHERE work_item_id = ?",
            (work_item_id,),
        )
        return json.loads(rows[0]["definition"]) if rows else None

    def make_ready(self, item_id: str) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = db.execute(
                "SELECT * FROM workflow_items WHERE id = ?", (item_id,)
            ).fetchone()
            if item is None or item["status"] not in (
                "blocked",
                "ready",
                "in_progress",
            ):
                db.rollback()
                return False
            db.execute(
                "UPDATE workflow_items SET status = 'ready' WHERE id = ?", (item_id,)
            )
            payload = {
                "instance_id": item["instance_id"],
                "step_name": item["step_name"],
                "participant_id": item["participant_id"],
            }
            db.execute(
                """
                INSERT INTO workflow_outbox VALUES (?, ?, 'pending', ?, ?)
                ON CONFLICT(work_item_id) DO UPDATE SET
                    status = 'pending', payload = excluded.payload,
                    created_at = excluded.created_at
                """,
                (str(uuid4()), item_id, json.dumps(payload), _now()),
            )
            self._event(
                db,
                item["instance_id"],
                "work_item.ready",
                {"work_item_id": item_id, **payload},
            )
            db.commit()
            return True

    def skip(self, item_id: str, *, reason: str, superseded: bool = False) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = db.execute(
                "SELECT * FROM workflow_items WHERE id = ?", (item_id,)
            ).fetchone()
            if item is None or item["status"] not in (
                "blocked",
                "ready",
                "in_progress",
            ):
                db.rollback()
                return False
            db.execute(
                "UPDATE workflow_items SET status = ?, completed_at = ? WHERE id = ?",
                ("superseded" if superseded else "skipped", _now(), item_id),
            )
            db.execute(
                "UPDATE workflow_outbox SET status = 'cancelled' WHERE work_item_id = ? AND status = 'pending'",
                (item_id,),
            )
            self._event(
                db,
                item["instance_id"],
                "work_item.superseded" if superseded else "work_item.skipped",
                {
                    "work_item_id": item_id,
                    "step_name": item["step_name"],
                    "participant_id": item["participant_id"],
                    "reason": reason,
                },
            )
            db.commit()
            return True

    def step_answers(self, instance_id: str, step_name: str) -> list[dict[str, Any]]:
        return [
            json.loads(row["answers"])
            for row in self.rows(
                """
                SELECT submissions.answers
                FROM workflow_submissions AS submissions
                JOIN workflow_items AS items ON items.id = submissions.work_item_id
                WHERE items.instance_id = ? AND items.step_name = ?
                ORDER BY submissions.created_at
                """,
                (instance_id, step_name),
            )
        ]

    def pending_outbox(self, instance_id: str | None = None) -> list[sqlite3.Row]:
        if instance_id is None:
            return self.rows(
                "SELECT * FROM workflow_outbox WHERE status = 'pending' ORDER BY created_at, id"
            )
        return self.rows(
            "SELECT outbox.* FROM workflow_outbox AS outbox JOIN workflow_items AS items "
            "ON items.id = outbox.work_item_id WHERE outbox.status = 'pending' AND items.instance_id = ? "
            "ORDER BY outbox.created_at, outbox.id",
            (instance_id,),
        )

    def mark_delivered(self, outbox_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE workflow_outbox SET status = 'delivered' WHERE id = ?",
                (outbox_id,),
            )

    def record_external_task(
        self,
        *,
        provider: str,
        work_item_id: str,
        resource_id: str,
        delivery_id: str | None = None,
    ) -> None:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO workflow_external_tasks
                    (provider, work_item_id, resource_id, delivery_id, status, created_at, completed_at)
                VALUES (?, ?, ?, ?, 'waiting', ?, NULL)
                ON CONFLICT(provider, work_item_id) DO NOTHING
                """,
                (provider, work_item_id, resource_id, delivery_id, _now()),
            )

    def external_tasks(
        self, provider: str, *, status: str = "waiting"
    ) -> list[sqlite3.Row]:
        return self.rows(
            "SELECT * FROM workflow_external_tasks WHERE provider = ? AND status = ? ORDER BY created_at",
            (provider, status),
        )

    def complete_external_task(
        self, provider: str, work_item_id: str, *, status: str = "completed"
    ) -> None:
        if status not in {"completed", "cancelled"}:
            raise ValueError(f"unsupported external task status {status!r}")
        with self.connect() as db:
            db.execute(
                "UPDATE workflow_external_tasks SET status = ?, completed_at = ? WHERE provider = ? AND work_item_id = ?",
                (status, _now(), provider, work_item_id),
            )

    def mark_opened(self, item_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE workflow_items SET status = 'in_progress', opened_at = COALESCE(opened_at, ?) WHERE id = ? AND status IN ('ready', 'in_progress')",
                (_now(), item_id),
            )

    def start_attempt(self, item_id: str, *, lease_seconds: float) -> dict[str, Any]:
        if lease_seconds <= 0:
            raise ValueError("lease duration must be positive")
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=lease_seconds)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = db.execute(
                "SELECT * FROM workflow_items WHERE id = ?", (item_id,)
            ).fetchone()
            if item is None or item["status"] not in ("ready", "in_progress"):
                db.rollback()
                raise ValueError(f"work item {item_id!r} cannot start an attempt")
            active = db.execute(
                """
                SELECT * FROM workflow_attempts
                WHERE work_item_id = ? AND status = 'running'
                  AND lease_expires_at > ?
                """,
                (item_id, now.isoformat()),
            ).fetchone()
            if active is not None:
                db.rollback()
                raise ValueError(f"work item {item_id!r} already has an active lease")
            number = (
                db.execute(
                    "SELECT COUNT(*) AS n FROM workflow_attempts WHERE work_item_id = ?",
                    (item_id,),
                ).fetchone()["n"]
                + 1
            )
            attempt_id = str(uuid4())
            db.execute(
                """
                INSERT INTO workflow_attempts VALUES
                    (?, ?, ?, 'running', ?, NULL, NULL, ?, NULL)
                """,
                (attempt_id, item_id, number, expires.isoformat(), now.isoformat()),
            )
            db.execute(
                "UPDATE workflow_items SET status = 'in_progress', opened_at = COALESCE(opened_at, ?) WHERE id = ?",
                (now.isoformat(), item_id),
            )
            self._event(
                db,
                item["instance_id"],
                "work_item.attempt_started",
                {
                    "work_item_id": item_id,
                    "attempt_id": attempt_id,
                    "attempt_number": number,
                    "lease_expires_at": expires.isoformat(),
                },
            )
            db.commit()
        return {"id": attempt_id, "number": number, "lease_expires_at": expires}

    def finish_attempt(
        self,
        attempt_id: str,
        *,
        status: str,
        error_kind: str | None = None,
        error_message: str | None = None,
    ) -> None:
        if status not in ("succeeded", "failed", "abandoned"):
            raise ValueError(f"unsupported attempt status {status!r}")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            attempt = db.execute(
                "SELECT * FROM workflow_attempts WHERE id = ?", (attempt_id,)
            ).fetchone()
            if attempt is None or attempt["status"] != "running":
                db.rollback()
                return
            item = db.execute(
                "SELECT * FROM workflow_items WHERE id = ?",
                (attempt["work_item_id"],),
            ).fetchone()
            db.execute(
                """
                UPDATE workflow_attempts SET status = ?, error_kind = ?,
                    error_message = ?, finished_at = ? WHERE id = ?
                """,
                (status, error_kind, error_message, _now(), attempt_id),
            )
            self._event(
                db,
                item["instance_id"],
                "work_item.attempt_finished",
                {
                    "work_item_id": item["id"],
                    "attempt_id": attempt_id,
                    "attempt_number": attempt["attempt_number"],
                    "status": status,
                    "error_kind": error_kind,
                },
            )
            db.commit()

    def attempts(self, item_id: str) -> list[sqlite3.Row]:
        return self.rows(
            "SELECT * FROM workflow_attempts WHERE work_item_id = ? ORDER BY attempt_number",
            (item_id,),
        )

    def retry_item(self, item_id: str, *, reason: str) -> bool:
        changed = self.make_ready(item_id)
        if changed:
            item = self.item(item_id)
            with self.connect() as db:
                self._event(
                    db,
                    item["instance_id"],
                    "work_item.retry_scheduled",
                    {"work_item_id": item_id, "reason": reason},
                )
        return changed

    def fail_item(self, item_id: str, *, reason: str) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = db.execute(
                "SELECT * FROM workflow_items WHERE id = ?", (item_id,)
            ).fetchone()
            if item is None or item["status"] not in ("ready", "in_progress"):
                db.rollback()
                return False
            db.execute(
                "UPDATE workflow_items SET status = 'failed', completed_at = ? WHERE id = ?",
                (_now(), item_id),
            )
            db.execute(
                "UPDATE workflow_instances SET status = 'failed', completed_at = ? WHERE id = ?",
                (_now(), item["instance_id"]),
            )
            self._event(
                db,
                item["instance_id"],
                "work_item.failed",
                {"work_item_id": item_id, "reason": reason},
            )
            db.commit()
            return True

    def recover_items(self, instance_id: str, *, max_attempts: int) -> list[str]:
        """Requeue abandoned deliveries and attempts whose leases have expired."""
        recovered: list[str] = []
        now = datetime.now(timezone.utc).isoformat()
        for item in self.items(instance_id):
            if item["status"] not in ("ready", "in_progress"):
                continue
            if item["status"] == "ready":
                pending = self.rows(
                    "SELECT id FROM workflow_outbox WHERE work_item_id = ? AND status = 'pending'",
                    (item["id"],),
                )
                if pending:
                    continue
            attempts = self.attempts(item["id"])
            active = next(
                (
                    attempt
                    for attempt in attempts
                    if attempt["status"] == "running"
                    and attempt["lease_expires_at"] > now
                ),
                None,
            )
            if active is not None:
                continue
            for attempt in attempts:
                if attempt["status"] == "running":
                    self.finish_attempt(
                        attempt["id"],
                        status="abandoned",
                        error_kind="lease_expired",
                        error_message="attempt lease expired before completion",
                    )
            if len(attempts) >= max_attempts:
                self.fail_item(item["id"], reason="retry attempts exhausted")
                continue
            self.retry_item(item["id"], reason="resuming abandoned work item")
            recovered.append(item["id"])
        return recovered

    def record_render(
        self,
        item_id: str,
        *,
        survey: Mapping[str, Any],
        shared_state: Mapping[str, Any],
        state_versions: Mapping[str, int],
    ) -> dict[str, Any]:
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO workflow_item_renders
                    (work_item_id, survey, shared_state, state_versions, rendered_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(work_item_id) DO NOTHING
                """,
                (
                    item_id,
                    json.dumps(dict(survey)),
                    json.dumps(dict(shared_state)),
                    json.dumps(dict(state_versions)),
                    _now(),
                ),
            )
        return self.rendered_item(item_id)

    def rendered_item(self, item_id: str) -> dict[str, Any] | None:
        rows = self.rows(
            "SELECT * FROM workflow_item_renders WHERE work_item_id = ?", (item_id,)
        )
        if not rows:
            return None
        row = rows[0]
        return {
            "survey": json.loads(row["survey"]),
            "shared_state": json.loads(row["shared_state"]),
            "state_versions": json.loads(row["state_versions"]),
            "rendered_at": row["rendered_at"],
        }

    def item_answers(self, item_id: str) -> dict[str, Any] | None:
        rows = self.rows(
            "SELECT answers FROM workflow_submissions WHERE work_item_id = ?",
            (item_id,),
        )
        return json.loads(rows[0]["answers"]) if rows else None

    def complete(
        self, item_id: str, answers: Mapping[str, Any], idempotency_key: str
    ) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            duplicate = db.execute(
                "SELECT work_item_id, answers FROM workflow_submissions WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if duplicate is not None:
                if duplicate["work_item_id"] != item_id or canonical_data(
                    json.loads(duplicate["answers"])
                ) != canonical_data(dict(answers)):
                    raise ValueError(
                        "submission idempotency key was reused with different content"
                    )
                db.rollback()
                return True
            item = db.execute(
                "SELECT * FROM workflow_items WHERE id = ?", (item_id,)
            ).fetchone()
            if item is None or item["status"] not in (
                "ready",
                "in_progress",
                "committing",
            ):
                db.rollback()
                raise ValueError(
                    f"work item {item_id!r} cannot be submitted from its current state"
                )
            intent = db.execute(
                "SELECT * FROM workflow_submission_intents WHERE work_item_id = ?",
                (item_id,),
            ).fetchone()
            if intent is not None:
                if intent["idempotency_key"] != idempotency_key or intent[
                    "answers"
                ] != canonical_data(dict(answers)):
                    raise ValueError("accepted submission is immutable")
                pending = db.execute(
                    "SELECT 1 FROM workflow_effects WHERE work_item_id = ? AND applied = 0",
                    (item_id,),
                ).fetchone()
                if pending:
                    raise ValueError(
                        "submission still has pending shared-state effects"
                    )
            db.execute(
                "INSERT INTO workflow_submissions VALUES (?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    item_id,
                    idempotency_key,
                    json.dumps(dict(answers)),
                    _now(),
                ),
            )
            db.execute(
                "UPDATE workflow_items SET status = 'completed', completed_at = ? WHERE id = ?",
                (_now(), item_id),
            )
            self._event(
                db,
                item["instance_id"],
                "work_item.completed",
                {
                    "work_item_id": item_id,
                    "step_name": item["step_name"],
                    "participant_id": item["participant_id"],
                },
            )
            if intent is not None and intent["attempt_id"] is not None:
                attempt = db.execute(
                    "SELECT * FROM workflow_attempts WHERE id = ?",
                    (intent["attempt_id"],),
                ).fetchone()
                if attempt is not None and attempt["status"] == "running":
                    db.execute(
                        "UPDATE workflow_attempts SET status = 'succeeded', finished_at = ? WHERE id = ?",
                        (_now(), attempt["id"]),
                    )
                    self._event(
                        db,
                        item["instance_id"],
                        "work_item.attempt_finished",
                        {
                            "work_item_id": item_id,
                            "attempt_id": attempt["id"],
                            "attempt_number": attempt["attempt_number"],
                            "status": "succeeded",
                            "error_kind": None,
                        },
                    )
            db.commit()
            return True

    def prepare_submission(
        self,
        item_id: str,
        answers: Mapping[str, Any],
        idempotency_key: str,
        *,
        attempt_id: str | None,
        operations: Iterable[Mapping[str, Any]],
    ) -> bool:
        """Accept one immutable response and its effects before any external write.

        Returns false for an already completed identical submission. A response
        accepted here owns its effects even if the answering worker later exits.
        """
        encoded = canonical_data(dict(answers))
        effects = [canonical_data(dict(operation)) for operation in operations]
        if not idempotency_key:
            raise ValueError("submission idempotency key must be non-empty")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            item = db.execute(
                "SELECT * FROM workflow_items WHERE id = ?", (item_id,)
            ).fetchone()
            if item is None:
                raise KeyError(f"unknown work item {item_id!r}")
            accepted = db.execute(
                "SELECT idempotency_key, answers FROM workflow_submission_intents WHERE work_item_id = ?",
                (item_id,),
            ).fetchone()
            if accepted is not None:
                if (
                    accepted["idempotency_key"] != idempotency_key
                    or canonical_data(json.loads(accepted["answers"])) != encoded
                ):
                    raise ValueError(
                        "work item already has different content; its accepted submission is immutable"
                    )
                db.commit()
                return item["status"] != "completed"
            for table in ("workflow_submissions", "workflow_submission_intents"):
                duplicate = db.execute(
                    f"SELECT work_item_id, answers FROM {table} WHERE idempotency_key = ?",
                    (idempotency_key,),
                ).fetchone()
                if duplicate is not None:
                    if (
                        duplicate["work_item_id"] != item_id
                        or canonical_data(json.loads(duplicate["answers"])) != encoded
                    ):
                        raise ValueError(
                            "submission idempotency key was reused with different content"
                        )
                    db.commit()
                    return item["status"] != "completed"
            if item["status"] not in ("ready", "in_progress"):
                raise ValueError(
                    f"work item {item_id!r} cannot accept a submission from {item['status']!r}"
                )
            instance = db.execute(
                "SELECT status FROM workflow_instances WHERE id = ?",
                (item["instance_id"],),
            ).fetchone()
            if instance["status"] != "running":
                raise ValueError("workflow instance is not running")
            if attempt_id is not None:
                attempt = db.execute(
                    "SELECT * FROM workflow_attempts WHERE id = ?", (attempt_id,)
                ).fetchone()
                if (
                    attempt is None
                    or attempt["work_item_id"] != item_id
                    or attempt["status"] != "running"
                    or attempt["lease_expires_at"] <= _now()
                ):
                    raise ValueError("submission attempt does not own a current lease")
            elif db.execute(
                "SELECT 1 FROM workflow_attempts WHERE work_item_id = ? AND status = 'running'",
                (item_id,),
            ).fetchone():
                raise ValueError(
                    "submission must identify the attempt holding the lease"
                )
            db.execute(
                "INSERT INTO workflow_submission_intents VALUES (?, ?, ?, ?, ?)",
                (item_id, idempotency_key, encoded, attempt_id, _now()),
            )
            for position, operation in enumerate(effects):
                db.execute(
                    "INSERT INTO workflow_effects VALUES (?, ?, ?, 0)",
                    (item_id, position, operation),
                )
            db.execute(
                "UPDATE workflow_items SET status = 'committing' WHERE id = ?",
                (item_id,),
            )
            self._event(
                db,
                item["instance_id"],
                "work_item.submission_accepted",
                {"work_item_id": item_id, "attempt_id": attempt_id},
            )
            db.commit()
            return True

    def submission_intent(self, item_id: str) -> dict[str, Any] | None:
        rows = self.rows(
            "SELECT * FROM workflow_submission_intents WHERE work_item_id = ?",
            (item_id,),
        )
        if not rows:
            return None
        return {**dict(rows[0]), "answers": json.loads(rows[0]["answers"])}

    def pending_effects(self, item_id: str) -> list[dict[str, Any]]:
        return [
            {"position": row["position"], "operation": json.loads(row["operation"])}
            for row in self.rows(
                "SELECT * FROM workflow_effects WHERE work_item_id = ? AND applied = 0 ORDER BY position",
                (item_id,),
            )
        ]

    def effect_applied(self, item_id: str, position: int) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE workflow_effects SET applied = 1 WHERE work_item_id = ? AND position = ?",
                (item_id, position),
            )

    def finish_instance_if_complete(self, instance_id: str) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            remaining = db.execute(
                "SELECT COUNT(*) AS n FROM workflow_items WHERE instance_id = ? AND status NOT IN ('completed', 'skipped', 'superseded')",
                (instance_id,),
            ).fetchone()["n"]
            if remaining:
                db.rollback()
                return False
            changed = db.execute(
                "UPDATE workflow_instances SET status = 'completed', completed_at = ? WHERE id = ? AND status = 'running'",
                (_now(), instance_id),
            ).rowcount
            if changed:
                self._event(db, instance_id, "workflow.completed", {})
            db.commit()
            return bool(changed)

    def events(self, instance_id: str) -> list[dict[str, Any]]:
        return [
            {
                "sequence": row["sequence"],
                "kind": row["kind"],
                **json.loads(row["payload"]),
            }
            for row in self.rows(
                "SELECT * FROM workflow_events WHERE instance_id = ? ORDER BY sequence",
                (instance_id,),
            )
        ]

    @staticmethod
    def _event(
        db: sqlite3.Connection, instance_id: str, kind: str, payload: Mapping[str, Any]
    ) -> None:
        db.execute(
            "INSERT INTO workflow_events(instance_id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
            (instance_id, kind, json.dumps(dict(payload)), _now()),
        )
