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
    AppendRowEvent,
    UpdateRowEvent,
    RemoveRowsEvent,
    InsertRowEvent,
    UpdateEntryFieldEvent,
    SetMetaEvent,
    UpdateMetaEvent,
    RemoveMetaKeyEvent,
    ClearEntriesEvent,
    AddFieldToAllEntriesEvent,
    AddFieldByIndexEvent,
    ReplaceAllEntriesEvent,
    DropFieldsEvent,
    KeepFieldsEvent,
    RenameFieldsEvent,
    ReorderEntriesEvent,
    FillNaEvent,
    StringCatFieldEvent,
    ReplaceValuesEvent,
    UniquifyFieldEvent,
    NumberifyEvent,
    TransformFieldEvent,
    ReplaceEntriesAndMetaEvent,
    ReorderKeysEvent,
    apply_event,
)
from .store import Store

__all__ = [
    # Codec
    "Codec",
    # Events
    "Event",
    "AppendRowEvent",
    "UpdateRowEvent",
    "RemoveRowsEvent",
    "InsertRowEvent",
    "UpdateEntryFieldEvent",
    "SetMetaEvent",
    "UpdateMetaEvent",
    "RemoveMetaKeyEvent",
    "ClearEntriesEvent",
    "AddFieldToAllEntriesEvent",
    "AddFieldByIndexEvent",
    "ReplaceAllEntriesEvent",
    "DropFieldsEvent",
    "KeepFieldsEvent",
    "RenameFieldsEvent",
    "ReorderEntriesEvent",
    "FillNaEvent",
    "StringCatFieldEvent",
    "ReplaceValuesEvent",
    "UniquifyFieldEvent",
    "NumberifyEvent",
    "TransformFieldEvent",
    "ReplaceEntriesAndMetaEvent",
    "ReorderKeysEvent",
    "apply_event",
    # Store
    "Store",
]

