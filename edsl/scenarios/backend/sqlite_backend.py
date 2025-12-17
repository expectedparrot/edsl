# sqlite_backend.py
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple, Dict
from .ops import State, materialize, sha256_hex, canonical_json


@dataclass
class SQLiteState(State):
    conn: sqlite3.Connection
    list_id: int
    _version: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        """Ensure the scenario_list entry exists, creating it if needed."""
        row = self.conn.execute(
            "SELECT current_version FROM scenario_lists WHERE id=?",
            (self.list_id,),
        ).fetchone()
        if row is None:
            self.conn.execute(
                "INSERT INTO scenario_lists (id, current_version) VALUES (?, ?)",
                (self.list_id, 0),
            )
            # Initialize meta at version 0
            self.conn.execute(
                "INSERT INTO scenario_list_meta (list_id, version, meta) VALUES (?, ?, ?)",
                (self.list_id, 0, "{}"),
            )
            self._version = 0
        else:
            self._version = row[0]

    @property
    def version(self) -> int:
        return self._version

    def _increment_version(self) -> int:
        """Increment and return the new version."""
        self._version += 1
        self.conn.execute(
            "UPDATE scenario_lists SET current_version=? WHERE id=?",
            (self._version, self.list_id),
        )
        return self._version

    def get_meta(self, at_version: Optional[int] = None) -> dict:
        """Get meta at a specific version (default: current)."""
        v = at_version if at_version is not None else self._version
        row = self.conn.execute(
            "SELECT meta FROM scenario_list_meta WHERE list_id=? AND version <= ? ORDER BY version DESC LIMIT 1",
            (self.list_id, v),
        ).fetchone()
        if row is None:
            return {}
        return json.loads(row[0])

    def set_meta(self, meta: dict) -> None:
        """Save meta at the current version."""
        self.conn.execute(
            "INSERT OR REPLACE INTO scenario_list_meta (list_id, version, meta) VALUES (?, ?, ?)",
            (self.list_id, self._version, json.dumps(meta)),
        )

    def get_scenario(self, position: int, at_version: Optional[int] = None) -> Any:
        """Get raw scenario at position, optionally at a specific version."""
        v = at_version if at_version is not None else self._version
        row = self.conn.execute(
            "SELECT payload FROM scenarios WHERE list_id=? AND position=? AND version_added <= ?",
            (self.list_id, position, v),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario {position} not found at version {v}")
        return json.loads(row[0])

    def get_scenario_with_digest(self, position: int, at_version: Optional[int] = None) -> Tuple[dict, str]:
        """Get raw scenario and its digest at position."""
        v = at_version if at_version is not None else self._version
        row = self.conn.execute(
            "SELECT payload, digest FROM scenarios WHERE list_id=? AND position=? AND version_added <= ?",
            (self.list_id, position, v),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario {position} not found at version {v}")
        return json.loads(row[0]), row[1]

    def get_digest_at_position(self, position: int, at_version: Optional[int] = None) -> str:
        """Get the digest of the scenario at a position."""
        v = at_version if at_version is not None else self._version
        row = self.conn.execute(
            "SELECT digest FROM scenarios WHERE list_id=? AND position=? AND version_added <= ?",
            (self.list_id, position, v),
        ).fetchone()
        if row is None:
            raise KeyError(f"scenario {position} not found at version {v}")
        return row[0]

    def get_all_digests(self, at_version: Optional[int] = None) -> List[str]:
        """Get all digests in position order at a version."""
        v = at_version if at_version is not None else self._version
        rows = self.conn.execute(
            "SELECT digest FROM scenarios WHERE list_id=? AND version_added <= ? ORDER BY position",
            (self.list_id, v),
        ).fetchall()
        return [row[0] for row in rows]

    def get_all_scenarios(self, at_version: Optional[int] = None) -> List[Any]:
        """Get all raw scenarios, optionally at a specific version."""
        v = at_version if at_version is not None else self._version
        rows = self.conn.execute(
            "SELECT payload FROM scenarios WHERE list_id=? AND version_added <= ? ORDER BY position",
            (self.list_id, v),
        ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_length(self, at_version: Optional[int] = None) -> int:
        """Get number of scenarios, optionally at a specific version."""
        v = at_version if at_version is not None else self._version
        row = self.conn.execute(
            "SELECT COUNT(*) FROM scenarios WHERE list_id=? AND version_added <= ?",
            (self.list_id, v),
        ).fetchone()
        return int(row[0])

    def insert_scenario(self, position: int, payload: dict) -> None:
        """Insert a scenario at the current version."""
        # Compute digest from payload (excluding _digest field itself)
        payload_for_digest = {k: v for k, v in payload.items() if k != "_digest"}
        digest = sha256_hex(canonical_json(payload_for_digest))
        self.conn.execute(
            "INSERT INTO scenarios (list_id, position, digest, version_added, payload) VALUES (?, ?, ?, ?, ?)",
            (self.list_id, position, digest, self._version, json.dumps(payload, sort_keys=True)),
        )

    # Digest-based override methods
    def set_override(self, position: int, payload: dict) -> None:
        """Set an override by position (looks up digest internally)."""
        digest = self.get_digest_at_position(position)
        self.set_override_by_digest(digest, payload)

    def set_override_by_digest(self, digest: str, payload: dict) -> None:
        """Set an override by digest at the current version."""
        self.conn.execute(
            "INSERT INTO scenario_list_overrides (list_id, digest, version, payload) VALUES (?, ?, ?, ?)",
            (self.list_id, digest, self._version, json.dumps(payload, sort_keys=True)),
        )

    def get_override(self, position: int, at_version: Optional[int] = None) -> dict | None:
        """Get override by position (looks up digest internally)."""
        try:
            digest = self.get_digest_at_position(position, at_version)
            return self.get_override_by_digest(digest, at_version)
        except KeyError:
            return None

    def get_override_by_digest(self, digest: str, at_version: Optional[int] = None) -> dict | None:
        """Get the override for a digest at a specific version."""
        v = at_version if at_version is not None else self._version
        row = self.conn.execute(
            """SELECT payload FROM scenario_list_overrides 
               WHERE list_id=? AND digest=? AND version <= ? 
               ORDER BY version DESC LIMIT 1""",
            (self.list_id, digest, v),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def get_materialized_scenario(self, position: int, at_version: Optional[int] = None) -> dict:
        """Get fully materialized scenario at a position and version."""
        v = at_version if at_version is not None else self._version
        raw, digest = self.get_scenario_with_digest(position, at_version=v)
        meta = self.get_meta(at_version=v)
        override = self.get_override_by_digest(digest, at_version=v)
        return materialize(raw, meta, override)

    def get_all_materialized_scenarios(self, at_version: Optional[int] = None) -> List[dict]:
        """Get all materialized scenarios at a version."""
        v = at_version if at_version is not None else self._version
        length = self.get_length(at_version=v)
        return [self.get_materialized_scenario(i, at_version=v) for i in range(length)]

    # History methods
    def append_history(self, method_name: str, args: tuple, kwargs: dict) -> None:
        """Record an operation in the history log."""
        # For add_values, don't store the full values list - just metadata
        if method_name == "add_values" and args:
            key = args[0]
            values = args[1] if len(args) > 1 else kwargs.get("values", [])
            lightweight_args = json.dumps([key, {"_count": len(values)}])
        else:
            lightweight_args = json.dumps(args)
        
        self.conn.execute(
            "INSERT INTO scenario_list_history (list_id, version, method_name, args, kwargs) VALUES (?, ?, ?, ?, ?)",
            (self.list_id, self._version, method_name, lightweight_args, json.dumps(kwargs)),
        )

    def get_history(self, up_to_version: Optional[int] = None) -> List[Tuple[int, str, tuple, dict]]:
        """Get history up to a version. Returns list of (version, method_name, args, kwargs)."""
        v = up_to_version if up_to_version is not None else self._version
        rows = self.conn.execute(
            "SELECT version, method_name, args, kwargs FROM scenario_list_history WHERE list_id=? AND version <= ? ORDER BY version",
            (self.list_id, v),
        ).fetchall()
        return [(row[0], row[1], tuple(json.loads(row[2])), json.loads(row[3])) for row in rows]

    # Snapshot methods
    def save_snapshot(self) -> None:
        """Save a snapshot of current materialized state."""
        scenarios = self.get_all_materialized_scenarios()
        meta = self.get_meta()
        self.conn.execute(
            "INSERT OR REPLACE INTO scenario_list_snapshots (list_id, version, scenarios, meta) VALUES (?, ?, ?, ?)",
            (self.list_id, self._version, json.dumps(scenarios), json.dumps(meta)),
        )

    def get_snapshot(self, at_version: int) -> Optional[Tuple[int, List[dict], dict]]:
        """Get the most recent snapshot at or before at_version. Returns (version, scenarios, meta) or None."""
        row = self.conn.execute(
            "SELECT version, scenarios, meta FROM scenario_list_snapshots WHERE list_id=? AND version <= ? ORDER BY version DESC LIMIT 1",
            (self.list_id, at_version),
        ).fetchone()
        if row is None:
            return None
        return (row[0], json.loads(row[1]), json.loads(row[2]))

    # Delta/sync methods for push/pull
    def get_delta(self, from_version: int, to_version: Optional[int] = None) -> Dict[str, Any]:
        """Get all changes between from_version and to_version for syncing."""
        to_v = to_version if to_version is not None else self._version
        
        # Scenarios added in this range
        scenarios = self.conn.execute(
            """SELECT position, digest, version_added, payload 
               FROM scenarios 
               WHERE list_id=? AND version_added > ? AND version_added <= ?
               ORDER BY position""",
            (self.list_id, from_version, to_v),
        ).fetchall()
        
        # Meta changes in this range
        meta_changes = self.conn.execute(
            """SELECT version, meta 
               FROM scenario_list_meta 
               WHERE list_id=? AND version > ? AND version <= ?
               ORDER BY version""",
            (self.list_id, from_version, to_v),
        ).fetchall()
        
        # Overrides added in this range
        overrides = self.conn.execute(
            """SELECT digest, version, payload 
               FROM scenario_list_overrides 
               WHERE list_id=? AND version > ? AND version <= ?
               ORDER BY version""",
            (self.list_id, from_version, to_v),
        ).fetchall()
        
        # History entries in this range
        history = self.conn.execute(
            """SELECT version, method_name, args, kwargs 
               FROM scenario_list_history 
               WHERE list_id=? AND version > ? AND version <= ?
               ORDER BY version""",
            (self.list_id, from_version, to_v),
        ).fetchall()
        
        return {
            "from_version": from_version,
            "to_version": to_v,
            "scenarios": [
                {"position": r[0], "digest": r[1], "version_added": r[2], "payload": json.loads(r[3])}
                for r in scenarios
            ],
            "meta_changes": [
                {"version": r[0], "meta": json.loads(r[1])}
                for r in meta_changes
            ],
            "overrides": [
                {"digest": r[0], "version": r[1], "payload": json.loads(r[2])}
                for r in overrides
            ],
            "history": [
                {"version": r[0], "method_name": r[1], "args": json.loads(r[2]), "kwargs": json.loads(r[3])}
                for r in history
            ],
        }

    def apply_delta(self, delta: Dict[str, Any]) -> None:
        """Apply a delta from another instance to sync state."""
        # Verify we're at the expected base version
        if self._version != delta["from_version"]:
            raise ValueError(f"Version mismatch: local is at {self._version}, delta expects {delta['from_version']}")
        
        # Apply scenarios
        for s in delta["scenarios"]:
            self.conn.execute(
                "INSERT INTO scenarios (list_id, position, digest, version_added, payload) VALUES (?, ?, ?, ?, ?)",
                (self.list_id, s["position"], s["digest"], s["version_added"], json.dumps(s["payload"], sort_keys=True)),
            )
        
        # Apply meta changes
        for m in delta["meta_changes"]:
            self.conn.execute(
                "INSERT INTO scenario_list_meta (list_id, version, meta) VALUES (?, ?, ?)",
                (self.list_id, m["version"], json.dumps(m["meta"])),
            )
        
        # Apply overrides
        for o in delta["overrides"]:
            self.conn.execute(
                "INSERT INTO scenario_list_overrides (list_id, digest, version, payload) VALUES (?, ?, ?, ?)",
                (self.list_id, o["digest"], o["version"], json.dumps(o["payload"], sort_keys=True)),
            )
        
        # Apply history
        for h in delta["history"]:
            self.conn.execute(
                "INSERT INTO scenario_list_history (list_id, version, method_name, args, kwargs) VALUES (?, ?, ?, ?, ?)",
                (self.list_id, h["version"], h["method_name"], json.dumps(h["args"]), json.dumps(h["kwargs"])),
            )
        
        # Update version
        self._version = delta["to_version"]
        self.conn.execute(
            "UPDATE scenario_lists SET current_version=? WHERE id=?",
            (self._version, self.list_id),
        )
