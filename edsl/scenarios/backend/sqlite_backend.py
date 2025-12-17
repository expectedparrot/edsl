# sqlite_backend.py
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, List
from .ops import State, materialize

@dataclass
class SQLiteState(State):
    conn: sqlite3.Connection
    list_id: int

    def __post_init__(self) -> None:
        """Ensure the scenario_list entry exists, creating it with empty meta if needed."""
        row = self.conn.execute(
            "SELECT 1 FROM scenario_lists WHERE id=?",
            (self.list_id,),
        ).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO scenario_lists (id, meta) VALUES (?, ?)",
                (self.list_id, "{}"),
            )

    def get_meta(self) -> dict:
        row = self.conn.execute(
            "SELECT meta FROM scenario_lists WHERE id=?",
            (self.list_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario_list {self.list_id} not found")
        return json.loads(row[0])

    def set_meta(self, meta: dict) -> None:
        self.conn.execute(
            "UPDATE scenario_lists SET meta=? WHERE id=?",
            (json.dumps(meta), self.list_id),
        )

    def get_scenario(self, position: int) -> Any:
        row = self.conn.execute(
            "SELECT payload FROM scenarios WHERE list_id=? AND position=?",
            (self.list_id, position),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario {position} not found")
        return json.loads(row[0])

    def get_all_scenarios(self) -> List[Any]:
        rows = self.conn.execute(
            "SELECT payload FROM scenarios WHERE list_id=? ORDER BY position",
            (self.list_id,),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_length(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM scenarios WHERE list_id=?",
            (self.list_id,),
        ).fetchone()
        return int(row[0])

    def insert_scenario(self, position: int, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO scenarios (list_id, position, payload) VALUES (?, ?, ?)",
            (self.list_id, position, json.dumps(payload, sort_keys=True)),
        )

    def set_override(self, position: int, payload: dict) -> None:
        self.conn.execute(
            """INSERT INTO scenario_list_overrides (list_id, position, payload) 
               VALUES (?, ?, ?)
               ON CONFLICT(list_id, position) DO UPDATE SET payload=excluded.payload""",
            (self.list_id, position, json.dumps(payload, sort_keys=True)),
        )

    def get_override(self, position: int) -> dict | None:
        row = self.conn.execute(
            "SELECT payload FROM scenario_list_overrides WHERE list_id=? AND position=?",
            (self.list_id, position),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def get_materialized_scenario(self, position: int) -> dict:
        raw = self.get_scenario(position)
        meta = self.get_meta()
        override = self.get_override(position)
        return materialize(raw, meta, override)

    def get_all_materialized_scenarios(self) -> List[dict]:
        return [self.get_materialized_scenario(i) for i in range(self.get_length())]
