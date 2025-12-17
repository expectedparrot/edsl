# memory_backend.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .ops import State, materialize, sha256_hex, canonical_json


@dataclass
class MemoryState(State):
    """In-memory backend with version tracking and digest-based overrides."""
    
    # Versioned storage
    _meta_history: Dict[int, dict] = field(default_factory=dict)
    _scenarios: List[Tuple[int, str, dict]] = field(default_factory=list)  # [(version_added, digest, payload), ...]
    _overrides: Dict[str, List[Tuple[int, dict]]] = field(default_factory=dict)  # digest -> [(version, payload), ...]
    _history: List[Tuple[int, str, tuple, dict]] = field(default_factory=list)  # [(version, method, args, kwargs), ...]
    _version: int = field(default=0)

    def __post_init__(self):
        # Initialize meta at version 0
        if 0 not in self._meta_history:
            self._meta_history[0] = {}

    @property
    def version(self) -> int:
        return self._version

    def _increment_version(self) -> int:
        """Increment and return the new version."""
        self._version += 1
        return self._version

    def get_meta(self, at_version: Optional[int] = None) -> dict:
        """Get meta at a specific version (default: current)."""
        v = at_version if at_version is not None else self._version
        # Find the highest version <= v that has meta
        applicable_versions = [ver for ver in self._meta_history.keys() if ver <= v]
        if not applicable_versions:
            return {}
        return self._meta_history[max(applicable_versions)]

    def set_meta(self, meta: dict) -> None:
        """Save meta at the current version."""
        self._meta_history[self._version] = meta

    def get_length(self, at_version: Optional[int] = None) -> int:
        """Get number of scenarios at a version."""
        v = at_version if at_version is not None else self._version
        return sum(1 for ver, _, _ in self._scenarios if ver <= v)

    def insert_scenario(self, position: int, payload: dict) -> None:
        """Insert a scenario at the current version."""
        # Append-only: position must be at end
        expected_pos = self.get_length()
        assert position == expected_pos, f"Expected position {expected_pos}, got {position}"
        # Compute digest from payload (excluding _digest field itself)
        payload_for_digest = {k: v for k, v in payload.items() if k != "_digest"}
        digest = sha256_hex(canonical_json(payload_for_digest))
        self._scenarios.append((self._version, digest, payload))

    def get_scenario(self, position: int, at_version: Optional[int] = None) -> Any:
        """Get raw scenario at position, optionally at a specific version."""
        v = at_version if at_version is not None else self._version
        # Filter scenarios that exist at this version
        scenarios_at_v = [(ver, dig, p) for ver, dig, p in self._scenarios if ver <= v]
        if position >= len(scenarios_at_v):
            raise KeyError(f"scenario {position} not found at version {v}")
        return scenarios_at_v[position][2]

    def get_scenario_with_digest(self, position: int, at_version: Optional[int] = None) -> Tuple[dict, str]:
        """Get raw scenario and its digest at position."""
        v = at_version if at_version is not None else self._version
        scenarios_at_v = [(ver, dig, p) for ver, dig, p in self._scenarios if ver <= v]
        if position >= len(scenarios_at_v):
            raise KeyError(f"scenario {position} not found at version {v}")
        return scenarios_at_v[position][2], scenarios_at_v[position][1]

    def get_digest_at_position(self, position: int, at_version: Optional[int] = None) -> str:
        """Get the digest of the scenario at a position."""
        v = at_version if at_version is not None else self._version
        scenarios_at_v = [(ver, dig, p) for ver, dig, p in self._scenarios if ver <= v]
        if position >= len(scenarios_at_v):
            raise KeyError(f"scenario {position} not found at version {v}")
        return scenarios_at_v[position][1]

    def get_all_digests(self, at_version: Optional[int] = None) -> List[str]:
        """Get all digests in position order at a version."""
        v = at_version if at_version is not None else self._version
        return [dig for ver, dig, _ in self._scenarios if ver <= v]

    def get_all_scenarios(self, at_version: Optional[int] = None) -> List[Any]:
        """Get all raw scenarios at a version."""
        v = at_version if at_version is not None else self._version
        return [p for ver, _, p in self._scenarios if ver <= v]

    def set_override(self, position: int, payload: dict) -> None:
        """Set an override by position (looks up digest internally)."""
        digest = self.get_digest_at_position(position)
        self.set_override_by_digest(digest, payload)

    def set_override_by_digest(self, digest: str, payload: dict) -> None:
        """Set an override by digest at the current version."""
        if digest not in self._overrides:
            self._overrides[digest] = []
        self._overrides[digest].append((self._version, payload))

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
        if digest not in self._overrides:
            return None
        # Find the highest version <= v
        applicable = [(ver, p) for ver, p in self._overrides[digest] if ver <= v]
        if not applicable:
            return None
        return max(applicable, key=lambda x: x[0])[1]

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
        # For add_values, store lightweight metadata
        if method_name == "add_values" and args:
            key = args[0]
            values = args[1] if len(args) > 1 else kwargs.get("values", [])
            lightweight_args = (key, {"_count": len(values)})
        else:
            lightweight_args = args
        self._history.append((self._version, method_name, lightweight_args, kwargs))

    def get_history(self, up_to_version: Optional[int] = None) -> List[Tuple[int, str, tuple, dict]]:
        """Get history up to a version."""
        v = up_to_version if up_to_version is not None else self._version
        return [(ver, method, args, kwargs) for ver, method, args, kwargs in self._history if ver <= v]

    # Delta/sync methods for push/pull
    def get_delta(self, from_version: int, to_version: Optional[int] = None) -> Dict[str, Any]:
        """Get all changes between from_version and to_version for syncing."""
        to_v = to_version if to_version is not None else self._version
        
        # Scenarios added in this range
        scenarios = []
        pos = 0
        for ver, digest, payload in self._scenarios:
            if ver > from_version and ver <= to_v:
                scenarios.append({
                    "position": pos,
                    "digest": digest,
                    "version_added": ver,
                    "payload": payload,
                })
            if ver <= to_v:
                pos += 1
        
        # Meta changes in this range
        meta_changes = [
            {"version": ver, "meta": meta}
            for ver, meta in sorted(self._meta_history.items())
            if ver > from_version and ver <= to_v
        ]
        
        # Overrides added in this range
        overrides = []
        for digest, override_list in self._overrides.items():
            for ver, payload in override_list:
                if ver > from_version and ver <= to_v:
                    overrides.append({
                        "digest": digest,
                        "version": ver,
                        "payload": payload,
                    })
        overrides.sort(key=lambda x: x["version"])
        
        # History entries in this range
        history = [
            {"version": ver, "method_name": method, "args": list(args), "kwargs": kwargs}
            for ver, method, args, kwargs in self._history
            if ver > from_version and ver <= to_v
        ]
        
        return {
            "from_version": from_version,
            "to_version": to_v,
            "scenarios": scenarios,
            "meta_changes": meta_changes,
            "overrides": overrides,
            "history": history,
        }

    def apply_delta(self, delta: Dict[str, Any]) -> None:
        """Apply a delta from another instance to sync state."""
        # Verify we're at the expected base version
        if self._version != delta["from_version"]:
            raise ValueError(f"Version mismatch: local is at {self._version}, delta expects {delta['from_version']}")
        
        # Apply scenarios
        for s in delta["scenarios"]:
            self._scenarios.append((s["version_added"], s["digest"], s["payload"]))
        
        # Apply meta changes
        for m in delta["meta_changes"]:
            self._meta_history[m["version"]] = m["meta"]
        
        # Apply overrides
        for o in delta["overrides"]:
            if o["digest"] not in self._overrides:
                self._overrides[o["digest"]] = []
            self._overrides[o["digest"]].append((o["version"], o["payload"]))
        
        # Apply history
        for h in delta["history"]:
            self._history.append((h["version"], h["method_name"], tuple(h["args"]), h["kwargs"]))
        
        # Update version
        self._version = delta["to_version"]
