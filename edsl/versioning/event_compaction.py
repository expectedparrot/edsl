"""
Event compaction for reducing event log size.

Provides:
- Combining sequential events that cancel out
- Merging consecutive updates to the same row
- Identifying redundant operations
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Set
from enum import Enum


@dataclass
class CompactedEvent:
    """A compacted event with provenance information."""
    event_name: str
    event_payload: Dict[str, Any]
    original_count: int  # How many events this represents
    original_indices: List[int]  # Which original events were compacted


@dataclass
class CompactionResult:
    """Result of compacting a sequence of events."""
    compacted_events: List[CompactedEvent]
    original_count: int
    compacted_count: int
    savings_percent: float
    removed_events: List[Tuple[int, str, str]]  # (index, event_name, reason)


class EventCompactor:
    """
    Compacts sequences of events to reduce storage and replay time.

    Compaction strategies:
    1. Remove append+remove pairs for the same row
    2. Merge consecutive updates to the same row
    3. Combine multiple field operations into one
    4. Remove no-op operations
    """

    def compact(
        self,
        events: List[Tuple[str, Dict[str, Any]]],
        aggressive: bool = False
    ) -> CompactionResult:
        """
        Compact a sequence of events.

        Args:
            events: List of (event_name, event_payload) tuples
            aggressive: If True, apply more aggressive compaction

        Returns:
            CompactionResult with compacted events
        """
        if not events:
            return CompactionResult(
                compacted_events=[],
                original_count=0,
                compacted_count=0,
                savings_percent=0.0,
                removed_events=[]
            )

        removed_events = []

        # Pass 1: Remove append+remove pairs
        events, removed = self._remove_append_remove_pairs(events)
        removed_events.extend(removed)

        # Pass 2: Merge consecutive updates to same row
        events, removed = self._merge_row_updates(events)
        removed_events.extend(removed)

        # Pass 3: Combine field operations
        events, removed = self._combine_field_ops(events)
        removed_events.extend(removed)

        if aggressive:
            # Pass 4: Remove no-op operations
            events, removed = self._remove_no_ops(events)
            removed_events.extend(removed)

        # Build compacted result
        compacted = []
        for i, (event_name, payload) in enumerate(events):
            compacted.append(CompactedEvent(
                event_name=event_name,
                event_payload=payload,
                original_count=1,  # Could track this better
                original_indices=[i]
            ))

        original_count = len(events) + len(removed_events)
        compacted_count = len(compacted)
        savings = (1 - compacted_count / original_count) * 100 if original_count > 0 else 0

        return CompactionResult(
            compacted_events=compacted,
            original_count=original_count,
            compacted_count=compacted_count,
            savings_percent=round(savings, 2),
            removed_events=removed_events
        )

    def _remove_append_remove_pairs(
        self,
        events: List[Tuple[str, Dict[str, Any]]]
    ) -> Tuple[List[Tuple[str, Dict[str, Any]]], List[Tuple[int, str, str]]]:
        """Remove append_row followed by remove_rows that removes that row."""
        result = []
        removed = []
        skip_indices: Set[int] = set()

        # Track appended rows and their indices
        for i, (event_name, payload) in enumerate(events):
            if i in skip_indices:
                continue

            if event_name == "append_row":
                # Look ahead for a remove that targets this row
                row_index = len([e for e in events[:i] if e[0] == "append_row"]) + len(result)

                for j in range(i + 1, len(events)):
                    if j in skip_indices:
                        continue
                    next_name, next_payload = events[j]
                    if next_name == "remove_rows":
                        indices = next_payload.get("indices", [])
                        if row_index in indices and len(indices) == 1:
                            # This append is immediately removed
                            skip_indices.add(i)
                            skip_indices.add(j)
                            removed.append((i, event_name, "cancelled by remove_rows"))
                            removed.append((j, next_name, "cancels append_row"))
                            break
                    elif next_name in ("append_row", "insert_row"):
                        # Row indices shift, stop looking
                        break

                if i not in skip_indices:
                    result.append((event_name, payload))
            else:
                if i not in skip_indices:
                    result.append((event_name, payload))

        return result, removed

    def _merge_row_updates(
        self,
        events: List[Tuple[str, Dict[str, Any]]]
    ) -> Tuple[List[Tuple[str, Dict[str, Any]]], List[Tuple[int, str, str]]]:
        """Merge consecutive update_row events for the same row."""
        if not events:
            return [], []

        result = []
        removed = []
        i = 0

        while i < len(events):
            event_name, payload = events[i]

            if event_name == "update_row":
                target_index = payload.get("index")
                merged_row = payload.get("row", {}).copy()
                merged_count = 1
                j = i + 1

                # Look for consecutive updates to the same row
                while j < len(events):
                    next_name, next_payload = events[j]
                    if next_name == "update_row" and next_payload.get("index") == target_index:
                        # Merge this update
                        merged_row.update(next_payload.get("row", {}))
                        removed.append((j, next_name, f"merged into update at {i}"))
                        merged_count += 1
                        j += 1
                    else:
                        break

                result.append(("update_row", {"index": target_index, "row": merged_row}))
                i = j
            else:
                result.append((event_name, payload))
                i += 1

        return result, removed

    def _combine_field_ops(
        self,
        events: List[Tuple[str, Dict[str, Any]]]
    ) -> Tuple[List[Tuple[str, Dict[str, Any]]], List[Tuple[int, str, str]]]:
        """Combine consecutive field operations."""
        if not events:
            return [], []

        result = []
        removed = []
        i = 0

        while i < len(events):
            event_name, payload = events[i]

            if event_name == "add_field_to_all_entries":
                # Look for consecutive add_field operations
                fields_to_add = {payload.get("field"): payload.get("value")}
                j = i + 1

                while j < len(events):
                    next_name, next_payload = events[j]
                    if next_name == "add_field_to_all_entries":
                        fields_to_add[next_payload.get("field")] = next_payload.get("value")
                        removed.append((j, next_name, f"combined with add_field at {i}"))
                        j += 1
                    else:
                        break

                if len(fields_to_add) > 1:
                    # Convert to update_meta or batch
                    for field, value in fields_to_add.items():
                        result.append(("add_field_to_all_entries", {"field": field, "value": value}))
                else:
                    result.append((event_name, payload))
                i = j

            elif event_name == "rename_fields":
                # Combine consecutive rename operations
                rename_map = dict(payload.get("rename_map", []))
                j = i + 1

                while j < len(events):
                    next_name, next_payload = events[j]
                    if next_name == "rename_fields":
                        # Chain renames: if a->b then b->c, result is a->c
                        next_map = dict(next_payload.get("rename_map", []))
                        new_map = {}
                        for old, new in rename_map.items():
                            if new in next_map:
                                new_map[old] = next_map[new]
                            else:
                                new_map[old] = new
                        for old, new in next_map.items():
                            if old not in [v for v in rename_map.values()]:
                                new_map[old] = new
                        rename_map = new_map
                        removed.append((j, next_name, f"combined with rename at {i}"))
                        j += 1
                    else:
                        break

                result.append(("rename_fields", {"rename_map": list(rename_map.items())}))
                i = j

            elif event_name == "drop_fields":
                # Combine consecutive drop operations
                fields_to_drop = set(payload.get("fields", []))
                j = i + 1

                while j < len(events):
                    next_name, next_payload = events[j]
                    if next_name == "drop_fields":
                        fields_to_drop.update(next_payload.get("fields", []))
                        removed.append((j, next_name, f"combined with drop_fields at {i}"))
                        j += 1
                    else:
                        break

                result.append(("drop_fields", {"fields": list(fields_to_drop)}))
                i = j
            else:
                result.append((event_name, payload))
                i += 1

        return result, removed

    def _remove_no_ops(
        self,
        events: List[Tuple[str, Dict[str, Any]]]
    ) -> Tuple[List[Tuple[str, Dict[str, Any]]], List[Tuple[int, str, str]]]:
        """Remove operations that have no effect."""
        result = []
        removed = []

        for i, (event_name, payload) in enumerate(events):
            is_no_op = False
            reason = ""

            if event_name == "drop_fields" and not payload.get("fields"):
                is_no_op = True
                reason = "empty fields list"
            elif event_name == "rename_fields" and not payload.get("rename_map"):
                is_no_op = True
                reason = "empty rename_map"
            elif event_name == "remove_rows" and not payload.get("indices"):
                is_no_op = True
                reason = "empty indices list"
            elif event_name == "update_meta" and not payload.get("updates"):
                is_no_op = True
                reason = "empty updates"
            elif event_name == "keep_fields":
                fields = payload.get("fields", [])
                if fields is None or (isinstance(fields, list) and len(fields) == 0):
                    is_no_op = True
                    reason = "empty fields list would clear all"

            if is_no_op:
                removed.append((i, event_name, f"no-op: {reason}"))
            else:
                result.append((event_name, payload))

        return result, removed

    def analyze_compaction_potential(
        self,
        events: List[Tuple[str, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """
        Analyze events without actually compacting.

        Returns statistics about potential compaction.
        """
        # Count event types
        event_counts: Dict[str, int] = {}
        for event_name, _ in events:
            event_counts[event_name] = event_counts.get(event_name, 0) + 1

        # Find potential optimizations
        append_count = event_counts.get("append_row", 0)
        remove_count = event_counts.get("remove_rows", 0)
        update_count = event_counts.get("update_row", 0)

        # Run compaction to get actual numbers
        result = self.compact(events, aggressive=True)

        return {
            "total_events": len(events),
            "event_types": event_counts,
            "potential_reduction": result.original_count - result.compacted_count,
            "potential_savings_percent": result.savings_percent,
            "compaction_details": {
                "append_remove_pairs": len([r for r in result.removed_events if "cancelled by" in r[2]]),
                "merged_updates": len([r for r in result.removed_events if "merged" in r[2]]),
                "combined_ops": len([r for r in result.removed_events if "combined" in r[2]]),
                "no_ops": len([r for r in result.removed_events if "no-op" in r[2]]),
            }
        }


# Convenience functions

def compact_events(
    events: List[Tuple[str, Dict[str, Any]]],
    aggressive: bool = False
) -> CompactionResult:
    """Compact a sequence of events."""
    return EventCompactor().compact(events, aggressive)


def analyze_events(
    events: List[Tuple[str, Dict[str, Any]]]
) -> Dict[str, Any]:
    """Analyze compaction potential for events."""
    return EventCompactor().analyze_compaction_potential(events)
