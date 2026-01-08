"""
Event classes for event-sourced Store operations.

This module defines all event types that can be applied to a Store,
along with the apply_event dispatcher function.

Created: 2026-01-08
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .store import Store


@dataclass(frozen=True)
class Event:
    """Base class for all store events."""
    
    @property
    def name(self) -> str:
        """Return the event name in snake_case."""
        name = type(self).__name__
        if name.endswith("Event"):
            name = name[:-5]
        # CamelCase to snake_case
        return ''.join(f'_{c.lower()}' if c.isupper() else c for c in name).lstrip('_')
    
    @property
    def payload(self) -> Dict[str, Any]:
        """Return the event data as a dictionary."""
        return asdict(self)


# =============================================================================
# Row/Entry Events
# =============================================================================

@dataclass(frozen=True)
class AppendRowEvent(Event):
    """Event that appends a row to entries."""
    row: dict[str, Any]


@dataclass(frozen=True)
class UpdateRowEvent(Event):
    """Event that updates a row at a specific index."""
    index: int
    row: dict[str, Any]


@dataclass(frozen=True)
class RemoveRowsEvent(Event):
    """Event that removes rows at specified indices."""
    indices: tuple[int, ...]  # tuple for hashability


@dataclass(frozen=True)
class InsertRowEvent(Event):
    """Event that inserts a row at a specified index."""
    index: int
    row: dict[str, Any]


@dataclass(frozen=True)
class UpdateEntryFieldEvent(Event):
    """Event that updates a specific field in an entry at a given index."""
    index: int
    field: str
    value: Any


@dataclass(frozen=True)
class ClearEntriesEvent(Event):
    """Event that removes all entries."""
    pass


@dataclass(frozen=True)
class ReplaceAllEntriesEvent(Event):
    """Event that replaces all entries with new ones."""
    entries: tuple[dict[str, Any], ...]  # tuple for hashability


@dataclass(frozen=True)
class ReorderEntriesEvent(Event):
    """Event that reorders entries by new index positions."""
    new_order: tuple[int, ...]  # tuple of indices


# =============================================================================
# Field Events
# =============================================================================

@dataclass(frozen=True)
class AddFieldToAllEntriesEvent(Event):
    """Event that adds a field with the same value to all entries."""
    field: str
    value: Any


@dataclass(frozen=True)
class AddFieldByIndexEvent(Event):
    """Event that adds a field with values corresponding to each entry by index."""
    field: str
    values: tuple[Any, ...]  # tuple for hashability


@dataclass(frozen=True)
class DropFieldsEvent(Event):
    """Event that drops specified fields from all entries."""
    fields: tuple[str, ...]  # tuple for hashability


@dataclass(frozen=True)
class KeepFieldsEvent(Event):
    """Event that keeps only specified fields in all entries."""
    fields: tuple[str, ...]  # tuple for hashability


@dataclass(frozen=True)
class RenameFieldsEvent(Event):
    """Event that renames fields in all entries."""
    rename_map: tuple[tuple[str, str], ...]  # (old, new) pairs


@dataclass(frozen=True)
class ReorderKeysEvent(Event):
    """Event that reorders keys in all entries."""
    new_order: tuple[str, ...]  # ordered key names


@dataclass(frozen=True)
class TransformFieldEvent(Event):
    """Event that transforms field values with pre-computed results."""
    field: str
    new_field: str  # can be same as field for in-place transform
    new_values: tuple[Any, ...]  # pre-computed transformed values


@dataclass(frozen=True)
class UniquifyFieldEvent(Event):
    """Event that makes field values unique by appending suffixes."""
    field: str
    new_values: tuple[Any, ...]  # pre-computed unique values


# =============================================================================
# Value Events
# =============================================================================

@dataclass(frozen=True)
class FillNaEvent(Event):
    """Event that fills NA/None values with a specified value."""
    fill_value: Any


@dataclass(frozen=True)
class StringCatFieldEvent(Event):
    """Event that concatenates a string to a field in all entries."""
    field: str
    addend: str
    position: str  # "prefix" or "suffix"


@dataclass(frozen=True)
class ReplaceValuesEvent(Event):
    """Event that replaces values in all entries based on a mapping."""
    replacements: tuple[tuple[str, Any], ...]  # (old_str_value, new_value) pairs


@dataclass(frozen=True)
class NumberifyEvent(Event):
    """Event that converts string values to numeric types."""
    conversions: tuple[tuple[int, str, Any], ...]  # (entry_idx, field, new_value)


# =============================================================================
# Meta Events
# =============================================================================

@dataclass(frozen=True)
class SetMetaEvent(Event):
    """Event that sets a single key-value pair in meta."""
    key: str
    value: Any


@dataclass(frozen=True)
class UpdateMetaEvent(Event):
    """Event that merges multiple key-value pairs into meta."""
    updates: dict[str, Any]


@dataclass(frozen=True)
class RemoveMetaKeyEvent(Event):
    """Event that removes a key from meta."""
    key: str


# =============================================================================
# Composite Events
# =============================================================================

@dataclass(frozen=True)
class ReplaceEntriesAndMetaEvent(Event):
    """Event that replaces all entries and updates meta simultaneously."""
    entries: tuple[dict[str, Any], ...]  # tuple for hashability
    meta_updates: tuple[tuple[str, Any], ...]  # key-value pairs


# =============================================================================
# Event Dispatcher
# =============================================================================

def apply_event(event: Event, store: "Store") -> "Store":
    """Apply an event to a store, returning the modified store.
    
    Args:
        event: The event to apply.
        store: The store to modify.
        
    Returns:
        The modified store (same instance, mutated in-place).
        
    Raises:
        ValueError: If the event type is unknown.
    """
    match event:
        case AppendRowEvent():
            return store.append(event.row)
        case UpdateRowEvent():
            return store.update_row(event.index, event.row)
        case RemoveRowsEvent():
            return store.remove_rows(event.indices)
        case InsertRowEvent():
            return store.insert_row(event.index, event.row)
        case UpdateEntryFieldEvent():
            return store.update_entry_field(event.index, event.field, event.value)
        case SetMetaEvent():
            return store.set_meta(event.key, event.value)
        case UpdateMetaEvent():
            return store.update_meta(event.updates)
        case RemoveMetaKeyEvent():
            return store.remove_meta_key(event.key)
        case ClearEntriesEvent():
            return store.clear_entries()
        case AddFieldToAllEntriesEvent():
            return store.add_field_to_all(event.field, event.value)
        case AddFieldByIndexEvent():
            return store.add_field_by_index(event.field, event.values)
        case ReplaceAllEntriesEvent():
            return store.replace_all_entries(event.entries)
        case DropFieldsEvent():
            return store.drop_fields(event.fields)
        case KeepFieldsEvent():
            return store.keep_fields(event.fields)
        case RenameFieldsEvent():
            return store.rename_fields(event.rename_map)
        case ReorderEntriesEvent():
            return store.reorder_entries(event.new_order)
        case FillNaEvent():
            return store.fill_na(event.fill_value)
        case StringCatFieldEvent():
            return store.string_cat_field(event.field, event.addend, event.position)
        case ReplaceValuesEvent():
            return store.replace_values(event.replacements)
        case UniquifyFieldEvent():
            return store.uniquify_field(event.field, event.new_values)
        case NumberifyEvent():
            return store.numberify(event.conversions)
        case TransformFieldEvent():
            return store.transform_field(event.field, event.new_field, event.new_values)
        case ReplaceEntriesAndMetaEvent():
            return store.replace_entries_and_meta(event.entries, event.meta_updates)
        case ReorderKeysEvent():
            return store.reorder_keys(event.new_order)
        case _:
            raise ValueError(f"Unknown event type: {type(event)}")

