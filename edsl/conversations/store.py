"""SQLite persistence for append-only conversation transcripts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping, Sequence
from uuid import uuid4


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteConversationStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS conversation_instances (id TEXT PRIMARY KEY, definition TEXT NOT NULL, participants TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL, completed_at TEXT);
            CREATE TABLE IF NOT EXISTS conversation_utterances (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL, sequence INTEGER NOT NULL, role TEXT NOT NULL, participant_id TEXT NOT NULL, text TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(instance_id, sequence));
            CREATE TABLE IF NOT EXISTS conversation_candidates (id TEXT PRIMARY KEY, instance_id TEXT NOT NULL, sequence INTEGER NOT NULL, role TEXT NOT NULL, participant_id TEXT NOT NULL, text TEXT NOT NULL, selected INTEGER NOT NULL DEFAULT 0, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def create(self, instance_id: str, definition: Mapping[str, Any], participants: Mapping[str, str]) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO conversation_instances VALUES (?, ?, ?, 'running', 0, ?, NULL)", (instance_id, json.dumps(definition), json.dumps(dict(participants)), _now()))

    def state(self, instance_id: str) -> dict[str, Any]:
        with self.connect() as db:
            row = db.execute("SELECT * FROM conversation_instances WHERE id=?", (instance_id,)).fetchone()
        if row is None:
            raise KeyError(instance_id)
        result = dict(row)
        result["definition"] = json.loads(result["definition"])
        result["participants"] = json.loads(result["participants"])
        return result

    def transcript(self, instance_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM conversation_utterances WHERE instance_id=? ORDER BY sequence", (instance_id,)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item["metadata"])
            result.append(item)
        return result

    @staticmethod
    def _check_version(db, instance_id: str, expected_version: int) -> None:
        state = db.execute(
            "SELECT version, status FROM conversation_instances WHERE id=?",
            (instance_id,),
        ).fetchone()
        if state is None:
            raise KeyError(instance_id)
        if state["status"] != "running" or state["version"] != expected_version:
            raise ValueError("stale transcript version or completed conversation")

    @staticmethod
    def _append(
        db, instance_id, expected_version, role, participant_id, text, metadata
    ):
        if not text.strip():
            raise ValueError("conversation utterance cannot be empty")
        utterance_id = str(uuid4())
        db.execute(
            "INSERT INTO conversation_utterances VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                utterance_id,
                instance_id,
                expected_version + 1,
                role,
                participant_id,
                text,
                json.dumps(dict(metadata or {})),
                _now(),
            ),
        )
        db.execute(
            "UPDATE conversation_instances SET version=version+1 WHERE id=?",
            (instance_id,),
        )
        return utterance_id

    def append(
        self,
        instance_id: str,
        *,
        expected_version: int,
        role: str,
        participant_id: str,
        text: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check_version(db, instance_id, expected_version)
            return self._append(
                db, instance_id, expected_version, role, participant_id, text, metadata
            )

    def realize_candidates(
        self,
        instance_id: str,
        candidates: Sequence[Mapping[str, Any]],
        *,
        selected_role: str,
        expected_version: int,
    ) -> str:
        """Commit all candidates and the selected utterance as one versioned write."""
        roles = [candidate["role"] for candidate in candidates]
        if len(set(roles)) != len(roles) or selected_role not in roles:
            raise ValueError("candidate roles must be unique and include the selection")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check_version(db, instance_id, expected_version)
            for candidate in candidates:
                candidate_id = str(uuid4())
                selected = candidate["role"] == selected_role
                db.execute(
                    "INSERT INTO conversation_candidates VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        candidate_id,
                        instance_id,
                        expected_version + 1,
                        candidate["role"],
                        candidate["participant_id"],
                        candidate["text"],
                        int(selected),
                        json.dumps(dict(candidate.get("metadata", {}))),
                        _now(),
                    ),
                )
                if selected:
                    utterance_id = self._append(
                        db,
                        instance_id,
                        expected_version,
                        selected_role,
                        candidate["participant_id"],
                        candidate["text"],
                        {**candidate.get("metadata", {}), "candidate_id": candidate_id},
                    )
            return utterance_id

    def complete(self, instance_id: str) -> None:
        with self.connect() as db:
            db.execute("UPDATE conversation_instances SET status='completed', completed_at=? WHERE id=? AND status='running'", (_now(), instance_id))
