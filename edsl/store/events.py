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
# Survey-Specific Events
# =============================================================================

@dataclass(frozen=True)
class AddRuleEvent(Event):
    """Event that adds a navigation rule to the survey."""
    rule_dict: dict[str, Any]  # Serialized rule


@dataclass(frozen=True)
class RemoveRulesForQuestionEvent(Event):
    """Event that removes all rules for a specific question index."""
    question_index: int


@dataclass(frozen=True)
class UpdateRuleIndicesEvent(Event):
    """Event that updates rule indices after question insertion/deletion."""
    index_offset: int  # Amount to offset indices by
    from_index: int  # Only update indices >= this value


@dataclass(frozen=True)
class SetMemoryPlanEvent(Event):
    """Event that sets the memory plan for the survey."""
    memory_plan_dict: dict[str, Any]  # Serialized memory plan


@dataclass(frozen=True)
class AddMemoryForQuestionEvent(Event):
    """Event that adds memory entries for a specific question."""
    focal_question: str
    prior_questions: tuple[str, ...]


@dataclass(frozen=True)
class AddQuestionGroupEvent(Event):
    """Event that adds a question group to the survey."""
    group_name: str
    start_index: int
    end_index: int


@dataclass(frozen=True)
class AddPseudoIndexEvent(Event):
    """Event that adds a pseudo index for an instruction."""
    entry_name: str  # Using entry_name to avoid conflict with Event.name property
    pseudo_index: float


@dataclass(frozen=True)
class RemovePseudoIndexEvent(Event):
    """Event that removes a pseudo index."""
    entry_name: str  # Using entry_name to avoid conflict with Event.name property


@dataclass(frozen=True)
class UpdatePseudoIndicesEvent(Event):
    """Event that updates pseudo indices after insertion/deletion."""
    index_offset: int
    from_index: float


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
        
        # Survey-Specific Events
        case AddRuleEvent():
            return store.add_rule(event.rule_dict)
        case RemoveRulesForQuestionEvent():
            return store.remove_rules_for_question(event.question_index)
        case UpdateRuleIndicesEvent():
            return store.update_rule_indices(event.index_offset, event.from_index)
        case SetMemoryPlanEvent():
            return store.set_memory_plan(event.memory_plan_dict)
        case AddMemoryForQuestionEvent():
            return store.add_memory_for_question(event.focal_question, event.prior_questions)
        case AddQuestionGroupEvent():
            return store.add_question_group(event.group_name, event.start_index, event.end_index)
        case AddPseudoIndexEvent():
            return store.add_pseudo_index(event.entry_name, event.pseudo_index)
        case RemovePseudoIndexEvent():
            return store.remove_pseudo_index(event.entry_name)
        case UpdatePseudoIndicesEvent():
            return store.update_pseudo_indices(event.index_offset, event.from_index)
        
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


# =============================================================================
# Event Registry
# =============================================================================

# Build registry mapping snake_case names to event classes
EVENT_REGISTRY: Dict[str, type] = {}

def _build_registry():
    """Build the event registry from all Event subclasses in this module."""
    import inspect
    for name, obj in globals().items():
        if (inspect.isclass(obj)
            and issubclass(obj, Event)
            and obj is not Event
            and name.endswith('Event')):
            # Create instance to get the snake_case name
            # We need a dummy instance - use empty values
            EVENT_REGISTRY[obj.__name__] = obj

_build_registry()


def get_event_class(event_name: str) -> type:
    """
    Get an event class by name.

    Args:
        event_name: Either the class name (e.g., 'AppendRowEvent')
                   or snake_case name (e.g., 'append_row')

    Returns:
        The event class.

    Raises:
        ValueError: If event name is not found.
    """
    # Try direct class name lookup first
    if event_name in EVENT_REGISTRY:
        return EVENT_REGISTRY[event_name]

    # Try snake_case to class name conversion
    # append_row -> AppendRowEvent
    class_name = ''.join(word.capitalize() for word in event_name.split('_')) + 'Event'
    if class_name in EVENT_REGISTRY:
        return EVENT_REGISTRY[class_name]

    raise ValueError(f"Unknown event: {event_name}. Available events: {list(EVENT_REGISTRY.keys())}")


def create_event(event_name: str, payload: Dict[str, Any]) -> Event:
    """
    Create an event instance from a name and payload.

    Handles type conversions needed for frozen dataclasses:
    - Lists are converted to tuples for hashability
    - Nested lists of lists/dicts are converted appropriately

    Args:
        event_name: Either class name or snake_case name
        payload: Dictionary of event parameters

    Returns:
        An Event instance.

    Raises:
        ValueError: If event name is not found or payload is invalid.
    """
    event_class = get_event_class(event_name)

    # Convert lists to tuples recursively for hashability
    def convert_for_frozen(value: Any) -> Any:
        if isinstance(value, list):
            # Check if it's a list of tuples (like rename_map)
            if value and isinstance(value[0], (list, tuple)) and len(value[0]) == 2:
                return tuple(tuple(item) for item in value)
            return tuple(convert_for_frozen(item) for item in value)
        elif isinstance(value, dict):
            # Keep dicts as-is (they're used as row data)
            return value
        return value

    converted_payload = {k: convert_for_frozen(v) for k, v in payload.items()}

    try:
        return event_class(**converted_payload)
    except TypeError as e:
        raise ValueError(f"Invalid payload for {event_name}: {e}")


def list_events() -> Dict[str, Dict[str, Any]]:
    """
    List all available events with their parameter schemas.

    Returns:
        Dictionary mapping event names to their schemas.
    """
    import dataclasses
    result = {}
    for class_name, event_class in EVENT_REGISTRY.items():
        # Get snake_case name
        name = class_name
        if name.endswith("Event"):
            name = name[:-5]
        snake_name = ''.join(f'_{c.lower()}' if c.isupper() else c for c in name).lstrip('_')

        # Get fields from dataclass
        fields = {}
        for field in dataclasses.fields(event_class):
            field_type = str(field.type)
            # Clean up type representation
            field_type = field_type.replace("typing.", "").replace("<class '", "").replace("'>", "")
            fields[field.name] = field_type

        result[snake_name] = {
            "class_name": class_name,
            "fields": fields,
            "doc": event_class.__doc__ or "",
        }
    return result

