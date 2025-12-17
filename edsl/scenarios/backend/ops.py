# ops.py
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Protocol


class State(Protocol):
    """Backend adapter. Same ops run against either implementation."""
    def get_meta(self) -> dict: ...
    def set_meta(self, meta: dict) -> None: ...
    def get_length(self) -> int: ...
    def insert_scenario(self, position: int, payload: dict) -> None: ...
    def set_override(self, position: int, payload: dict) -> None: ...
    def get_override(self, position: int) -> dict | None: ...


def canonical_json(x: Any) -> str:
    # Stable JSON for hashing / equivalence
    return json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


@dataclass
class Op:
    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        raise NotImplementedError


@dataclass
class LoadMeta(Op):
    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        ctx["meta"] = st.get_meta()

@dataclass
class ValidateNoDroppedKeys(Op):
    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        meta = ctx["meta"]
        payload = ctx["payload"]  # view payload
        dropped = set(meta.get("drop", []))
        bad = dropped.intersection(payload.keys())
        if bad:
            raise ValueError(f"Cannot write dropped keys: {sorted(bad)}")

@dataclass
class AddDrop(Op):
    """
    Add a drop mapping to meta: key -> None.
    Future appends will drop this key.
    """
    key: str

    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        meta = ctx["meta"]
        drops = meta.setdefault("drop", [])
        drops.append(self.key)


@dataclass
class AddValues(Op):
    """
    Add values override to the overrides table/structure.
    Each position gets an override payload with key -> value.
    """
    key: str
    values: list

    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        for position, value in enumerate(self.values):
            # Get existing override for this position, or start fresh
            existing = st.get_override(position) or {}
            existing[self.key] = value
            st.set_override(position, existing)


@dataclass
class ApplyRenames(Op):
    """
    Shared normalization logic: if old key present, rewrite to new key
    (unless new key already present).
    """
    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        meta = ctx["meta"]
        payload = dict(ctx["payload"])
        for old, new in meta.get("rename", {}).items():
            if old in payload and new not in payload:
                payload[new] = payload.pop(old)
        ctx["payload"] = payload


@dataclass
class ComputeDigest(Op):
    """
    Shared derived-field logic. This is the "convincer":
    both backends must compute the same digest of the canonical payload.
    """
    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        payload = ctx["payload"]
        digest = sha256_hex(canonical_json(payload))
        # store derived field into payload
        payload2 = dict(payload)
        payload2["_digest"] = digest
        ctx["payload"] = payload2


@dataclass
class AssignPosition(Op):
    """
    Shared logic to decide where append lands.
    """
    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        ctx["position"] = st.get_length()


@dataclass
class PersistScenario(Op):
    """
    This is the only backend-specific "effect", but it's expressed as a single op.
    """
    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        st.insert_scenario(ctx["position"], ctx["payload"])


@dataclass
class AddRename(Op):
    """
    Add a rename mapping to meta: old_key -> new_key.
    Future appends will apply this rename.
    """
    old_key: str
    new_key: str

    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        meta = ctx["meta"]
        renames = meta.setdefault("rename", {})
        renames[self.old_key] = self.new_key


@dataclass
class PersistMeta(Op):
    """
    Save the (possibly modified) meta back to the backend.
    """
    def run(self, st: State, ctx: Dict[str, Any]) -> None:
        st.set_meta(ctx["meta"])


def materialize(payload: dict, meta: dict, override: dict = None) -> dict:
    """
    Apply meta transforms (renames, drops) and overrides to a raw payload.
    This is the read-side view projection, not a tracked operation.
    
    Args:
        payload: The raw scenario payload
        meta: The meta dict containing renames, drops, etc.
        override: Optional override dict for this position (from overrides table)
    """
    result = dict(payload)
    for old, new in meta.get("rename", {}).items():
        if old in result and new not in result:
            result[new] = result.pop(old)
    for key in meta.get("drop", []):
        if key in result:
            result.pop(key)
    # Apply overrides if provided
    if override:
        result.update(override)
    return result
