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
# Row Selection Events
# =============================================================================

@dataclass(frozen=True)
class KeepRowsByIndicesEvent(Event):
    """Event that keeps only rows at specified indices (inverse of RemoveRowsEvent)."""
    indices: tuple[int, ...]  # indices to keep


# =============================================================================
# Nested Field Events (for structures like Agent with 'traits' dict)
# =============================================================================

@dataclass(frozen=True)
class DropNestedFieldsEvent(Event):
    """Event that drops fields from a nested dict field in all entries."""
    parent_field: str  # e.g., 'traits'
    fields: tuple[str, ...]  # fields to drop from the nested dict


@dataclass(frozen=True)
class KeepNestedFieldsEvent(Event):
    """Event that keeps only specified fields in a nested dict field."""
    parent_field: str  # e.g., 'traits'
    fields: tuple[str, ...]  # fields to keep in the nested dict


@dataclass(frozen=True)
class RenameNestedFieldEvent(Event):
    """Event that renames a field within a nested dict field."""
    parent_field: str  # e.g., 'traits'
    old_name: str
    new_name: str


@dataclass(frozen=True)
class AddNestedFieldByIndexEvent(Event):
    """Event that adds a field to a nested dict with per-entry values."""
    parent_field: str  # e.g., 'traits'
    field: str  # field name to add
    values: tuple[Any, ...]  # per-entry values


@dataclass(frozen=True)
class TranslateNestedValuesEvent(Event):
    """Event that translates values in nested fields based on a mapping."""
    parent_field: str  # e.g., 'traits'
    value_map: tuple[tuple[str, tuple[tuple[Any, Any], ...]], ...]  # (field_name, ((old, new), ...))


@dataclass(frozen=True)
class NumberifyNestedFieldsEvent(Event):
    """Event that converts string values to numbers in nested fields."""
    parent_field: str  # e.g., 'traits'
    conversions: tuple[tuple[int, str, Any], ...]  # (entry_idx, field, new_value)


# =============================================================================
# Agent-Specific Events
# =============================================================================

@dataclass(frozen=True)
class SetAgentNamesEvent(Event):
    """Event that sets names for agents (name field at entry level)."""
    names: tuple[str, ...]  # per-entry names


@dataclass(frozen=True)
class CollapseByFieldEvent(Event):
    """Event that collapses entries with same field value, merging nested dicts."""
    group_field: str  # field to group by (e.g., 'name')
    merge_field: str  # nested dict field to merge (e.g., 'traits')
    result_entries: tuple[dict[str, Any], ...]  # pre-computed collapsed entries


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
        # Row/Entry Events
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
        case ClearEntriesEvent():
            return store.clear_entries()
        case ReplaceAllEntriesEvent():
            return store.replace_all_entries(event.entries)
        case ReorderEntriesEvent():
            return store.reorder_entries(event.new_order)
        case KeepRowsByIndicesEvent():
            return store.keep_rows_by_indices(event.indices)
        
        # Field Events
        case AddFieldToAllEntriesEvent():
            return store.add_field_to_all(event.field, event.value)
        case AddFieldByIndexEvent():
            return store.add_field_by_index(event.field, event.values)
        case DropFieldsEvent():
            return store.drop_fields(event.fields)
        case KeepFieldsEvent():
            return store.keep_fields(event.fields)
        case RenameFieldsEvent():
            return store.rename_fields(event.rename_map)
        case ReorderKeysEvent():
            return store.reorder_keys(event.new_order)
        case TransformFieldEvent():
            return store.transform_field(event.field, event.new_field, event.new_values)
        case UniquifyFieldEvent():
            return store.uniquify_field(event.field, event.new_values)
        
        # Nested Field Events
        case DropNestedFieldsEvent():
            return store.drop_nested_fields(event.parent_field, event.fields)
        case KeepNestedFieldsEvent():
            return store.keep_nested_fields(event.parent_field, event.fields)
        case RenameNestedFieldEvent():
            return store.rename_nested_field(event.parent_field, event.old_name, event.new_name)
        case AddNestedFieldByIndexEvent():
            return store.add_nested_field_by_index(event.parent_field, event.field, event.values)
        case TranslateNestedValuesEvent():
            return store.translate_nested_values(event.parent_field, event.value_map)
        case NumberifyNestedFieldsEvent():
            return store.numberify_nested_fields(event.parent_field, event.conversions)
        
        # Agent-Specific Events
        case SetAgentNamesEvent():
            return store.set_field_by_index('name', event.names)
        case CollapseByFieldEvent():
            return store.collapse_by_field(event.group_field, event.merge_field, event.result_entries)
        
        # Value Events
        case FillNaEvent():
            return store.fill_na(event.fill_value)
        case StringCatFieldEvent():
            return store.string_cat_field(event.field, event.addend, event.position)
        case ReplaceValuesEvent():
            return store.replace_values(event.replacements)
        case NumberifyEvent():
            return store.numberify(event.conversions)
        
        # Meta Events
        case SetMetaEvent():
            return store.set_meta(event.key, event.value)
        case UpdateMetaEvent():
            return store.update_meta(event.updates)
        case RemoveMetaKeyEvent():
            return store.remove_meta_key(event.key)
        
        # Composite Events
        case ReplaceEntriesAndMetaEvent():
            return store.replace_entries_and_meta(event.entries, event.meta_updates)
        
        case _:
            raise ValueError(f"Unknown event type: {type(event)}")

