"""
EDSL Store Module - Event-sourced data storage infrastructure.

This module provides the foundational components for event-sourced data storage:

- **Codec**: Protocol for encoding/decoding domain objects to/from primitives
- **Event**: Base class and concrete event types for state changes
- **Store**: The data store that holds entries and metadata
- **apply_event**: Function to apply events to a store

Example:
    >>> from edsl.store import Store, AppendRowEvent, apply_event
    >>> store = Store(entries=[], meta={})
    >>> event = AppendRowEvent(row={'name': 'Alice', 'age': 30})
    >>> apply_event(event, store)
    >>> len(store.entries)
    1

Created: 2026-01-08
"""

from .codec import Codec
from .events import (
    Event,
    # Row/Entry Events
    AppendRowEvent,
    UpdateRowEvent,
    RemoveRowsEvent,
    InsertRowEvent,
    UpdateEntryFieldEvent,
    ClearEntriesEvent,
    ReplaceAllEntriesEvent,
    ReorderEntriesEvent,
    KeepRowsByIndicesEvent,
    # Field Events
    AddFieldToAllEntriesEvent,
    AddFieldByIndexEvent,
    DropFieldsEvent,
    KeepFieldsEvent,
    RenameFieldsEvent,
    ReorderKeysEvent,
    TransformFieldEvent,
    UniquifyFieldEvent,
    # Nested Field Events
    DropNestedFieldsEvent,
    KeepNestedFieldsEvent,
    RenameNestedFieldEvent,
    AddNestedFieldByIndexEvent,
    TranslateNestedValuesEvent,
    NumberifyNestedFieldsEvent,
    # Agent-Specific Events
    SetAgentNamesEvent,
    CollapseByFieldEvent,
    # Survey-Specific Events
    AddRuleEvent,
    RemoveRulesForQuestionEvent,
    UpdateRuleIndicesEvent,
    SetMemoryPlanEvent,
    AddMemoryForQuestionEvent,
    AddQuestionGroupEvent,
    AddPseudoIndexEvent,
    RemovePseudoIndexEvent,
    UpdatePseudoIndicesEvent,
    # Value Events
    FillNaEvent,
    StringCatFieldEvent,
    ReplaceValuesEvent,
    NumberifyEvent,
    # Meta Events
    SetMetaEvent,
    UpdateMetaEvent,
    RemoveMetaKeyEvent,
    # Composite Events
    ReplaceEntriesAndMetaEvent,
    apply_event,
    # Registry functions
    EVENT_REGISTRY,
    get_event_class,
    create_event,
    list_events,
)
from .store import Store

__all__ = [
    # Codec
    "Codec",
    # Row/Entry Events
    "Event",
    "AppendRowEvent",
    "UpdateRowEvent",
    "RemoveRowsEvent",
    "InsertRowEvent",
    "UpdateEntryFieldEvent",
    "ClearEntriesEvent",
    "ReplaceAllEntriesEvent",
    "ReorderEntriesEvent",
    "KeepRowsByIndicesEvent",
    # Field Events
    "AddFieldToAllEntriesEvent",
    "AddFieldByIndexEvent",
    "DropFieldsEvent",
    "KeepFieldsEvent",
    "RenameFieldsEvent",
    "ReorderKeysEvent",
    "TransformFieldEvent",
    "UniquifyFieldEvent",
    # Nested Field Events
    "DropNestedFieldsEvent",
    "KeepNestedFieldsEvent",
    "RenameNestedFieldEvent",
    "AddNestedFieldByIndexEvent",
    "TranslateNestedValuesEvent",
    "NumberifyNestedFieldsEvent",
    # Agent-Specific Events
    "SetAgentNamesEvent",
    "CollapseByFieldEvent",
    # Survey-Specific Events
    "AddRuleEvent",
    "RemoveRulesForQuestionEvent",
    "UpdateRuleIndicesEvent",
    "SetMemoryPlanEvent",
    "AddMemoryForQuestionEvent",
    "AddQuestionGroupEvent",
    "AddPseudoIndexEvent",
    "RemovePseudoIndexEvent",
    "UpdatePseudoIndicesEvent",
    # Value Events
    "FillNaEvent",
    "StringCatFieldEvent",
    "ReplaceValuesEvent",
    "NumberifyEvent",
    # Meta Events
    "SetMetaEvent",
    "UpdateMetaEvent",
    "RemoveMetaKeyEvent",
    # Composite Events
    "ReplaceEntriesAndMetaEvent",
    "apply_event",
    # Registry functions
    "EVENT_REGISTRY",
    "get_event_class",
    "create_event",
    "list_events",
    # Store
    "Store",
]

