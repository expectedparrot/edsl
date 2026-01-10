"""
Delta compression for state snapshots.

Provides:
- Computing deltas between states
- Applying deltas to reconstruct states
- Storage savings estimation
"""

from __future__ import annotations
import json
import hashlib
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class DeltaOp(str, Enum):
    """Delta operation types."""

    ADD_ROW = "add_row"
    REMOVE_ROW = "remove_row"
    UPDATE_ROW = "update_row"
    ADD_FIELD = "add_field"
    REMOVE_FIELD = "remove_field"
    UPDATE_FIELD = "update_field"
    SET_META = "set_meta"
    REMOVE_META = "remove_meta"


@dataclass
class DeltaOperation:
    """A single delta operation."""

    op: DeltaOp
    path: str  # e.g., "entries.0", "entries.0.name", "meta.codebook"
    value: Any = None  # For add/update operations
    old_value: Any = None  # For update operations (optional, for verification)


@dataclass
class Delta:
    """A delta between two states."""

    base_state_id: str
    target_state_id: str
    operations: List[DeltaOperation]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_state_id": self.base_state_id,
            "target_state_id": self.target_state_id,
            "operations": [
                {"op": op.op.value, "path": op.path, "value": op.value}
                for op in self.operations
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Delta":
        return cls(
            base_state_id=data["base_state_id"],
            target_state_id=data["target_state_id"],
            operations=[
                DeltaOperation(
                    op=DeltaOp(op["op"]), path=op["path"], value=op.get("value")
                )
                for op in data["operations"]
            ],
        )


class DeltaCompressor:
    """
    Computes and applies deltas between states.

    Deltas are more compact than full snapshots when changes are small.
    """

    def compute_delta(
        self,
        base_state: Dict[str, Any],
        target_state: Dict[str, Any],
        base_state_id: str,
        target_state_id: str,
    ) -> Delta:
        """
        Compute the delta from base_state to target_state.

        Args:
            base_state: The starting state {"entries": [...], "meta": {...}}
            target_state: The ending state
            base_state_id: ID of base state (for reference)
            target_state_id: ID of target state

        Returns:
            Delta object with operations to transform base to target
        """
        operations = []

        # Compare entries
        base_entries = base_state.get("entries", [])
        target_entries = target_state.get("entries", [])

        # Simple approach: compare by index
        # For more sophisticated diffing, could use LCS or similar

        max_len = max(len(base_entries), len(target_entries))

        for i in range(max_len):
            if i >= len(base_entries):
                # Row added
                operations.append(
                    DeltaOperation(
                        op=DeltaOp.ADD_ROW, path=f"entries.{i}", value=target_entries[i]
                    )
                )
            elif i >= len(target_entries):
                # Row removed (from end)
                operations.append(
                    DeltaOperation(
                        op=DeltaOp.REMOVE_ROW,
                        path=f"entries.{i}",
                        old_value=base_entries[i],
                    )
                )
            elif base_entries[i] != target_entries[i]:
                # Row changed - compute field-level diff
                field_ops = self._diff_row(base_entries[i], target_entries[i], i)
                if len(field_ops) < 3:  # Field-level more efficient
                    operations.extend(field_ops)
                else:  # Full row replacement more efficient
                    operations.append(
                        DeltaOperation(
                            op=DeltaOp.UPDATE_ROW,
                            path=f"entries.{i}",
                            value=target_entries[i],
                            old_value=base_entries[i],
                        )
                    )

        # Compare meta
        base_meta = base_state.get("meta", {})
        target_meta = target_state.get("meta", {})

        # Keys in target but not base
        for key in target_meta:
            if key not in base_meta:
                operations.append(
                    DeltaOperation(
                        op=DeltaOp.SET_META, path=f"meta.{key}", value=target_meta[key]
                    )
                )
            elif base_meta[key] != target_meta[key]:
                operations.append(
                    DeltaOperation(
                        op=DeltaOp.SET_META,
                        path=f"meta.{key}",
                        value=target_meta[key],
                        old_value=base_meta[key],
                    )
                )

        # Keys removed
        for key in base_meta:
            if key not in target_meta:
                operations.append(
                    DeltaOperation(
                        op=DeltaOp.REMOVE_META,
                        path=f"meta.{key}",
                        old_value=base_meta[key],
                    )
                )

        return Delta(
            base_state_id=base_state_id,
            target_state_id=target_state_id,
            operations=operations,
        )

    def _diff_row(
        self, base_row: Dict[str, Any], target_row: Dict[str, Any], row_index: int
    ) -> List[DeltaOperation]:
        """Compute field-level diff for a row."""
        operations = []

        # Fields added or changed
        for key in target_row:
            if key not in base_row:
                operations.append(
                    DeltaOperation(
                        op=DeltaOp.ADD_FIELD,
                        path=f"entries.{row_index}.{key}",
                        value=target_row[key],
                    )
                )
            elif base_row[key] != target_row[key]:
                operations.append(
                    DeltaOperation(
                        op=DeltaOp.UPDATE_FIELD,
                        path=f"entries.{row_index}.{key}",
                        value=target_row[key],
                        old_value=base_row[key],
                    )
                )

        # Fields removed
        for key in base_row:
            if key not in target_row:
                operations.append(
                    DeltaOperation(
                        op=DeltaOp.REMOVE_FIELD,
                        path=f"entries.{row_index}.{key}",
                        old_value=base_row[key],
                    )
                )

        return operations

    def apply_delta(self, base_state: Dict[str, Any], delta: Delta) -> Dict[str, Any]:
        """
        Apply a delta to a base state to produce target state.

        Args:
            base_state: The starting state
            delta: Delta to apply

        Returns:
            The resulting state after applying delta
        """
        import copy

        result = copy.deepcopy(base_state)

        # Ensure entries and meta exist
        if "entries" not in result:
            result["entries"] = []
        if "meta" not in result:
            result["meta"] = {}

        for op in delta.operations:
            parts = op.path.split(".")

            if op.op == DeltaOp.ADD_ROW:
                idx = int(parts[1])
                while len(result["entries"]) <= idx:
                    result["entries"].append({})
                result["entries"][idx] = op.value

            elif op.op == DeltaOp.REMOVE_ROW:
                idx = int(parts[1])
                if idx < len(result["entries"]):
                    result["entries"].pop(idx)

            elif op.op == DeltaOp.UPDATE_ROW:
                idx = int(parts[1])
                if idx < len(result["entries"]):
                    result["entries"][idx] = op.value

            elif op.op == DeltaOp.ADD_FIELD or op.op == DeltaOp.UPDATE_FIELD:
                idx = int(parts[1])
                field = parts[2]
                if idx < len(result["entries"]):
                    result["entries"][idx][field] = op.value

            elif op.op == DeltaOp.REMOVE_FIELD:
                idx = int(parts[1])
                field = parts[2]
                if idx < len(result["entries"]) and field in result["entries"][idx]:
                    del result["entries"][idx][field]

            elif op.op == DeltaOp.SET_META:
                key = parts[1]
                result["meta"][key] = op.value

            elif op.op == DeltaOp.REMOVE_META:
                key = parts[1]
                if key in result["meta"]:
                    del result["meta"][key]

        return result

    def estimate_savings(
        self,
        base_state: Dict[str, Any],
        target_state: Dict[str, Any],
        base_state_id: str = "base",
        target_state_id: str = "target",
    ) -> Dict[str, Any]:
        """
        Estimate storage savings from using delta vs full snapshot.

        Returns:
            Dict with size comparisons and savings percentage
        """
        # Compute sizes
        full_size = len(json.dumps(target_state, sort_keys=True).encode())

        delta = self.compute_delta(
            base_state, target_state, base_state_id, target_state_id
        )
        delta_size = len(json.dumps(delta.to_dict(), sort_keys=True).encode())

        savings = full_size - delta_size
        savings_pct = (savings / full_size * 100) if full_size > 0 else 0

        return {
            "full_snapshot_bytes": full_size,
            "delta_bytes": delta_size,
            "savings_bytes": savings,
            "savings_percent": round(savings_pct, 2),
            "operations_count": len(delta.operations),
            "use_delta": delta_size < full_size,
        }


# Convenience functions


def compute_delta(
    base_state: Dict[str, Any],
    target_state: Dict[str, Any],
    base_id: str = "base",
    target_id: str = "target",
) -> Delta:
    """Compute delta between two states."""
    return DeltaCompressor().compute_delta(base_state, target_state, base_id, target_id)


def apply_delta(base_state: Dict[str, Any], delta: Delta) -> Dict[str, Any]:
    """Apply delta to base state."""
    return DeltaCompressor().apply_delta(base_state, delta)


def estimate_savings(
    base_state: Dict[str, Any], target_state: Dict[str, Any]
) -> Dict[str, Any]:
    """Estimate storage savings from using delta."""
    return DeltaCompressor().estimate_savings(base_state, target_state)
