"""SQLite persistence for workflow instances, work items, events, and outbox."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable, Mapping
from uuid import uuid4


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
                """
            )

    def create_instance(
        self,
        instance_id: str,
        definition: Mapping[str, Any],
        participants: Iterable[tuple[str, Mapping[str, Any]]],
    ) -> None:
        now = _now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO workflow_instances VALUES (?, ?, 'running', ?, NULL)",
                (instance_id, json.dumps(definition), now),
            )
            for participant_id, agent in participants:
                db.execute(
                    "INSERT INTO workflow_participants VALUES (?, ?, ?)",
                    (instance_id, participant_id, json.dumps(agent)),
                )
            self._event(db, instance_id, "workflow.started", {})
            db.commit()

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
                "INSERT INTO workflow_outbox VALUES (?, ?, 'pending', ?, ?)",
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

    def skip(self, item_id: str, *, reason: str) -> bool:
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
                "UPDATE workflow_items SET status = 'skipped', completed_at = ? WHERE id = ?",
                (_now(), item_id),
            )
            db.execute(
                "UPDATE workflow_outbox SET status = 'cancelled' WHERE work_item_id = ? AND status = 'pending'",
                (item_id,),
            )
            self._event(
                db,
                item["instance_id"],
                "work_item.skipped",
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

    def pending_outbox(self) -> list[sqlite3.Row]:
        return self.rows(
            "SELECT * FROM workflow_outbox WHERE status = 'pending' ORDER BY created_at, id"
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

    def complete_external_task(self, provider: str, work_item_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE workflow_external_tasks SET status = 'completed', completed_at = ? WHERE provider = ? AND work_item_id = ?",
                (_now(), provider, work_item_id),
            )

    def mark_opened(self, item_id: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE workflow_items SET status = 'in_progress', opened_at = COALESCE(opened_at, ?) WHERE id = ? AND status IN ('ready', 'in_progress')",
                (_now(), item_id),
            )

    def record_render(
        self,
        item_id: str,
        *,
        survey: Mapping[str, Any],
        shared_state: Mapping[str, Any],
        state_versions: Mapping[str, int],
    ) -> None:
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
                "SELECT work_item_id FROM workflow_submissions WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if duplicate is not None:
                db.rollback()
                return duplicate["work_item_id"] == item_id
            item = db.execute(
                "SELECT * FROM workflow_items WHERE id = ?", (item_id,)
            ).fetchone()
            if item is None or item["status"] not in ("ready", "in_progress"):
                db.rollback()
                raise ValueError(
                    f"work item {item_id!r} cannot be submitted from its current state"
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
            db.commit()
            return True

    def finish_instance_if_complete(self, instance_id: str) -> bool:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            remaining = db.execute(
                "SELECT COUNT(*) AS n FROM workflow_items WHERE instance_id = ? AND status NOT IN ('completed', 'skipped')",
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
