"""
Generic ListStore and VersionedList for list-of-dicts data structures.

ListStore: Immutable store for rows (list of dicts) with metadata.
VersionedList: Git-versioned list with event-sourced mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    Any, Dict, List, Optional, Tuple, Callable, Iterator,
    TypeVar, Generic, Union, Sequence, overload
)

from .models import Event
from .protocols import Remote
from .storage import InMemoryRemote
from .mixin import GitMixin, event


T = TypeVar('T')


# ----------------------------
# ListStore: Immutable store for list-of-dicts
# ----------------------------

@dataclass(frozen=True)
class ListStore:
    """
    Immutable store for list-of-dicts data with metadata.

    Features:
    - Immutable (frozen dataclass)
    - O(1) lookup by index
    - Optional O(1) lookup by key field (via _index)
    - Metadata dict for class-level data

    Usage:
        store = ListStore(rows=[{'id': 1, 'name': 'Alice'}])
        store = store.append({'id': 2, 'name': 'Bob'})  # Returns new store
    """
    rows: Tuple[Dict[str, Any], ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Index field name -> {value -> row_index}
    _index_field: Optional[str] = None
    _index: Optional[Dict[Any, int]] = None

    def __post_init__(self):
        # Build index if index_field specified but index not provided
        if self._index_field is not None and self._index is None:
            idx = {}
            for i, row in enumerate(self.rows):
                if self._index_field in row:
                    idx[row[self._index_field]] = i
            # Use object.__setattr__ since we're frozen
            object.__setattr__(self, '_index', idx)

    @classmethod
    def from_list(cls, rows: List[Dict[str, Any]],
                  metadata: Optional[Dict[str, Any]] = None,
                  index_field: Optional[str] = None) -> "ListStore":
        """Create ListStore from a list of dicts."""
        return cls(
            rows=tuple(rows),
            metadata=metadata or {},
            _index_field=index_field,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for git storage."""
        return {
            'rows': list(self.rows),
            'metadata': dict(self.metadata),
            '_index_field': self._index_field,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ListStore":
        """Deserialize from dict."""
        return cls(
            rows=tuple(data.get('rows', [])),
            metadata=data.get('metadata', {}),
            _index_field=data.get('_index_field'),
        )

    # --- Read operations ---

    def __len__(self) -> int:
        return len(self.rows)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self.rows)

    def __getitem__(self, index: int) -> Dict[str, Any]:
        return self.rows[index]

    def get_by_key(self, key_value: Any) -> Optional[Dict[str, Any]]:
        """O(1) lookup by indexed field value."""
        if self._index is None:
            raise ValueError("No index configured. Use index_field parameter.")
        idx = self._index.get(key_value)
        if idx is not None:
            return self.rows[idx]
        return None

    def to_list(self) -> List[Dict[str, Any]]:
        """Return rows as a list (copy)."""
        return list(self.rows)

    # --- Write operations (return new ListStore) ---

    def append(self, row: Dict[str, Any]) -> "ListStore":
        """Append a row, returns new ListStore."""
        new_rows = self.rows + (dict(row),)
        new_index = None
        if self._index is not None and self._index_field:
            new_index = dict(self._index)
            if self._index_field in row:
                new_index[row[self._index_field]] = len(self.rows)
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=self._index_field,
            _index=new_index,
        )

    def extend(self, rows: Sequence[Dict[str, Any]]) -> "ListStore":
        """Append multiple rows, returns new ListStore."""
        new_rows = self.rows + tuple(dict(r) for r in rows)
        new_index = None
        if self._index is not None and self._index_field:
            new_index = dict(self._index)
            for i, row in enumerate(rows):
                if self._index_field in row:
                    new_index[row[self._index_field]] = len(self.rows) + i
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=self._index_field,
            _index=new_index,
        )

    def update_at(self, index: int, row: Dict[str, Any]) -> "ListStore":
        """Replace row at index, returns new ListStore."""
        if index < 0 or index >= len(self.rows):
            raise IndexError(f"Index {index} out of range")
        new_rows = self.rows[:index] + (dict(row),) + self.rows[index + 1:]
        # Rebuild index (simpler than tracking updates)
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=self._index_field,
        )

    def delete_at(self, index: int) -> "ListStore":
        """Delete row at index, returns new ListStore."""
        if index < 0 or index >= len(self.rows):
            raise IndexError(f"Index {index} out of range")
        new_rows = self.rows[:index] + self.rows[index + 1:]
        # Rebuild index
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=self._index_field,
        )

    def filter(self, predicate: Callable[[Dict[str, Any]], bool]) -> "ListStore":
        """Keep rows matching predicate, returns new ListStore."""
        new_rows = tuple(r for r in self.rows if predicate(r))
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=self._index_field,
        )

    def sort(self, key: Callable[[Dict[str, Any]], Any], reverse: bool = False) -> "ListStore":
        """Sort rows, returns new ListStore."""
        new_rows = tuple(sorted(self.rows, key=key, reverse=reverse))
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=self._index_field,
        )

    def set_metadata(self, key: str, value: Any) -> "ListStore":
        """Set metadata value, returns new ListStore."""
        new_metadata = dict(self.metadata)
        new_metadata[key] = value
        return ListStore(
            rows=self.rows,
            metadata=new_metadata,
            _index_field=self._index_field,
            _index=self._index,
        )

    def update_metadata(self, updates: Dict[str, Any]) -> "ListStore":
        """Update multiple metadata values, returns new ListStore."""
        new_metadata = dict(self.metadata)
        new_metadata.update(updates)
        return ListStore(
            rows=self.rows,
            metadata=new_metadata,
            _index_field=self._index_field,
            _index=self._index,
        )

    # --- Column operations ---

    def update_cell(self, row_index: int, column: str, value: Any) -> "ListStore":
        """Update a single cell value, returns new ListStore."""
        if row_index < 0 or row_index >= len(self.rows):
            raise IndexError(f"Row index {row_index} out of range")
        new_row = dict(self.rows[row_index])
        new_row[column] = value
        return self.update_at(row_index, new_row)

    def add_column(self, column: str, default_value: Any = None) -> "ListStore":
        """Add a new column to all rows with a default value, returns new ListStore."""
        new_rows = tuple(
            {**row, column: default_value} for row in self.rows
        )
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=self._index_field,
        )

    def delete_column(self, column: str) -> "ListStore":
        """Remove a column from all rows, returns new ListStore."""
        new_rows = tuple(
            {k: v for k, v in row.items() if k != column}
            for row in self.rows
        )
        # If we're deleting the index field, clear it
        new_index_field = None if column == self._index_field else self._index_field
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=new_index_field,
        )

    def rename_column(self, old_name: str, new_name: str) -> "ListStore":
        """Rename a column in all rows, returns new ListStore."""
        new_rows = tuple(
            {(new_name if k == old_name else k): v for k, v in row.items()}
            for row in self.rows
        )
        # Update index field if it was renamed
        new_index_field = new_name if old_name == self._index_field else self._index_field
        return ListStore(
            rows=new_rows,
            metadata=self.metadata,
            _index_field=new_index_field,
        )


# ----------------------------
# Events for VersionedList
# ----------------------------

@dataclass(frozen=True)
class AppendRowEvent:
    """Event: append a single row."""
    row: Dict[str, Any]
    name: str = "append_row"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'row': self.row}

    def execute(self, store: ListStore) -> ListStore:
        return store.append(self.row)


@dataclass(frozen=True)
class ExtendRowsEvent:
    """Event: append multiple rows."""
    rows: Tuple[Dict[str, Any], ...]
    name: str = "extend_rows"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'rows': list(self.rows)}

    def execute(self, store: ListStore) -> ListStore:
        return store.extend(self.rows)


@dataclass(frozen=True)
class UpdateRowEvent:
    """Event: update row at index."""
    index: int
    row: Dict[str, Any]
    name: str = "update_row"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'index': self.index, 'row': self.row}

    def execute(self, store: ListStore) -> ListStore:
        return store.update_at(self.index, self.row)


@dataclass(frozen=True)
class DeleteRowEvent:
    """Event: delete row at index."""
    index: int
    name: str = "delete_row"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'index': self.index}

    def execute(self, store: ListStore) -> ListStore:
        return store.delete_at(self.index)


@dataclass(frozen=True)
class FilterRowsEvent:
    """Event: filter rows (stores indices to keep)."""
    keep_indices: Tuple[int, ...]
    name: str = "filter_rows"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'keep_indices': list(self.keep_indices)}

    def execute(self, store: ListStore) -> ListStore:
        new_rows = tuple(store.rows[i] for i in self.keep_indices)
        return ListStore(
            rows=new_rows,
            metadata=store.metadata,
            _index_field=store._index_field,
        )


@dataclass(frozen=True)
class SortRowsEvent:
    """Event: sort rows by field."""
    key_field: str
    reverse: bool = False
    name: str = "sort_rows"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'key_field': self.key_field, 'reverse': self.reverse}

    def execute(self, store: ListStore) -> ListStore:
        return store.sort(key=lambda r: r.get(self.key_field), reverse=self.reverse)


@dataclass(frozen=True)
class SetMetadataEvent:
    """Event: set a metadata field."""
    key: str
    value: Any
    name: str = "set_metadata"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'key': self.key, 'value': self.value}

    def execute(self, store: ListStore) -> ListStore:
        return store.set_metadata(self.key, self.value)


@dataclass(frozen=True)
class UpdateCellEvent:
    """Event: update a single cell value."""
    row_index: int
    column: str
    value: Any
    name: str = "update_cell"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'row_index': self.row_index, 'column': self.column, 'value': self.value}

    def execute(self, store: ListStore) -> ListStore:
        return store.update_cell(self.row_index, self.column, self.value)


@dataclass(frozen=True)
class AddColumnEvent:
    """Event: add a new column to all rows."""
    column: str
    default_value: Any = None
    name: str = "add_column"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'column': self.column, 'default_value': self.default_value}

    def execute(self, store: ListStore) -> ListStore:
        return store.add_column(self.column, self.default_value)


@dataclass(frozen=True)
class DeleteColumnEvent:
    """Event: delete a column from all rows."""
    column: str
    name: str = "delete_column"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'column': self.column}

    def execute(self, store: ListStore) -> ListStore:
        return store.delete_column(self.column)


@dataclass(frozen=True)
class RenameColumnEvent:
    """Event: rename a column in all rows."""
    old_name: str
    new_name: str
    name: str = "rename_column"

    @property
    def payload(self) -> Dict[str, Any]:
        return {'old_name': self.old_name, 'new_name': self.new_name}

    def execute(self, store: ListStore) -> ListStore:
        return store.rename_column(self.old_name, self.new_name)


# ----------------------------
# VersionedList: Git-versioned list
# ----------------------------

class VersionedList(GitMixin):
    """
    Git-versioned list of dicts with event-sourced mutations.

    Data operations (append, update, delete) return new instances - original unchanged.
    Git operations (commit, pull, push, checkout) mutate in place and return self for chaining.

    Example:
        vl = VersionedList([{'x': 1}, {'x': 2}])
        vl = vl.append({'x': 3})  # Returns new instance, reassign

        # Git operations mutate in place
        vl.git_commit("added row")  # No reassign needed

        # Chaining works
        vl.git_commit("msg").git_push()

        # Branch and checkout
        vl.git_branch("feature")
        vl = vl.append({'x': 100})
        vl.git_commit("feature work")
        vl.git_checkout("main")  # Mutates vl back to 3 rows

        # Remote operations
        origin = InMemoryRemote()
        vl.git_add_remote("origin", origin)
        vl.git_push()

        # Clone
        vl2 = VersionedList.git_clone(origin)
    """

    _versioned = 'store'
    _store_class = ListStore

    def __init__(
        self,
        rows: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        index_field: Optional[str] = None,
    ):
        super().__init__()
        self.store = ListStore.from_list(
            rows or [],
            metadata=metadata,
            index_field=index_field,
        )

    # --- Properties for convenient access ---

    @property
    def rows(self) -> Tuple[Dict[str, Any], ...]:
        """Access underlying rows."""
        return self.store.rows

    @property
    def metadata(self) -> Dict[str, Any]:
        """Access metadata."""
        return self.store.metadata

    def __len__(self) -> int:
        return len(self.store)

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self.store)

    def __getitem__(self, index: int) -> Dict[str, Any]:
        return self.store[index]

    def to_list(self) -> List[Dict[str, Any]]:
        """Return rows as a list (copy)."""
        return self.store.to_list()

    def get_by_key(self, key_value: Any) -> Optional[Dict[str, Any]]:
        """O(1) lookup by indexed field value."""
        return self.store.get_by_key(key_value)

    # --- Mutating operations (return new VersionedList) ---

    @event
    def append(self, row: Dict[str, Any]) -> AppendRowEvent:
        """Append a row. Returns new VersionedList with pending event."""
        return AppendRowEvent(row=dict(row))

    @event
    def extend(self, rows: Sequence[Dict[str, Any]]) -> ExtendRowsEvent:
        """Append multiple rows. Returns new VersionedList with pending event."""
        return ExtendRowsEvent(rows=tuple(dict(r) for r in rows))

    @event
    def update_at(self, index: int, row: Dict[str, Any]) -> UpdateRowEvent:
        """Update row at index. Returns new VersionedList with pending event."""
        return UpdateRowEvent(index=index, row=dict(row))

    @event
    def delete_at(self, index: int) -> DeleteRowEvent:
        """Delete row at index. Returns new VersionedList with pending event."""
        return DeleteRowEvent(index=index)

    def filter(self, predicate: Callable[[Dict[str, Any]], bool]) -> "VersionedList":
        """
        Filter rows by predicate. Returns new VersionedList with pending event.

        Note: We capture the indices to keep (for reproducibility) rather than
        the predicate function (which can't be serialized).
        """
        keep_indices = tuple(i for i, r in enumerate(self.store.rows) if predicate(r))
        return self._apply_filter_event(keep_indices)

    @event
    def _apply_filter_event(self, keep_indices: Tuple[int, ...]) -> FilterRowsEvent:
        return FilterRowsEvent(keep_indices=keep_indices)

    @event
    def sort_by(self, key_field: str, reverse: bool = False) -> SortRowsEvent:
        """Sort rows by field. Returns new VersionedList with pending event."""
        return SortRowsEvent(key_field=key_field, reverse=reverse)

    @event
    def set_metadata(self, key: str, value: Any) -> SetMetadataEvent:
        """Set metadata field. Returns new VersionedList with pending event."""
        return SetMetadataEvent(key=key, value=value)

    # --- Cell and column operations ---

    @event
    def update_cell(self, row_index: int, column: str, value: Any) -> UpdateCellEvent:
        """Update a single cell value. Returns new VersionedList with pending event."""
        return UpdateCellEvent(row_index=row_index, column=column, value=value)

    @event
    def add_column(self, column: str, default_value: Any = None) -> AddColumnEvent:
        """Add a new column to all rows. Returns new VersionedList with pending event."""
        return AddColumnEvent(column=column, default_value=default_value)

    @event
    def delete_column(self, column: str) -> DeleteColumnEvent:
        """Delete a column from all rows. Returns new VersionedList with pending event."""
        return DeleteColumnEvent(column=column)

    @event
    def rename_column(self, old_name: str, new_name: str) -> RenameColumnEvent:
        """Rename a column in all rows. Returns new VersionedList with pending event."""
        return RenameColumnEvent(old_name=old_name, new_name=new_name)

    # --- Convenience methods ---

    def select(self, *fields: str) -> "VersionedList":
        """
        Project to specified fields only.
        Returns new VersionedList with only the specified columns.
        """
        projected_rows = [
            {k: row.get(k) for k in fields}
            for row in self.store.rows
        ]
        # This creates a new list with a replace-all event
        return self._replace_rows(projected_rows)

    def _replace_rows(self, new_rows: List[Dict[str, Any]]) -> "VersionedList":
        """Internal: replace all rows (for operations that transform all data)."""
        # Stage a filter that keeps nothing, then extend with new rows
        # Or we could add a ReplaceAllEvent
        self._ensure_git_init()
        new_store = ListStore.from_list(
            new_rows,
            metadata=self.store.metadata,
            index_field=self.store._index_field,
        )
        new_git = self._git.apply_event("replace_all", {"rows": new_rows})
        new_instance = self._from_state(new_store.to_dict())
        new_instance._git = new_git
        new_instance._needs_git_init = False
        return new_instance

    def __repr__(self) -> str:
        staged = " (staged)" if self.has_staged else ""
        return f"VersionedList({len(self)} rows, branch={self.branch_name}{staged})"

    # --- Staged (mutable) versions of data operations ---
    # Access via staged_append, staged_extend, etc.
    # These mutate in place and return self for chaining.

    _STAGEABLE_METHODS = {
        'append', 'extend', 'update_at', 'delete_at', 'filter', 'sort_by',
        'set_metadata', 'update_cell', 'add_column', 'delete_column',
        'rename_column', 'select',
    }

    def _make_staged_method(self, method_name: str):
        """Create a staged (mutable) version of an immutable method."""
        # Get the wrapped method through normal attribute access (includes @event wrapping)
        original_method = getattr(self, method_name)

        def staged_wrapper(*args, **kwargs):
            new_instance = original_method(*args, **kwargs)
            # Copy the new state back to self
            self.store = new_instance.store
            self._git = new_instance._git
            return self

        return staged_wrapper

    def __getattr__(self, name: str):
        if name.startswith('staged_'):
            method_name = name[7:]  # Remove 'staged_' prefix
            if method_name in self._STAGEABLE_METHODS:
                return self._make_staged_method(method_name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


# ----------------------------
# Factory for creating typed versioned lists
# ----------------------------

def create_versioned_list_class(
    name: str,
    row_validator: Optional[Callable[[Dict[str, Any]], bool]] = None,
    default_metadata: Optional[Dict[str, Any]] = None,
) -> type:
    """
    Factory to create a custom VersionedList subclass.

    Args:
        name: Class name
        row_validator: Optional function to validate rows on append
        default_metadata: Default metadata for new instances

    Example:
        PersonList = create_versioned_list_class(
            "PersonList",
            row_validator=lambda r: 'name' in r and 'age' in r,
            default_metadata={'schema_version': 1},
        )

        pl = PersonList([{'name': 'Alice', 'age': 30}])
    """

    class CustomVersionedList(VersionedList):
        def __init__(
            self,
            rows: Optional[List[Dict[str, Any]]] = None,
            metadata: Optional[Dict[str, Any]] = None,
            index_field: Optional[str] = None,
        ):
            merged_metadata = dict(default_metadata or {})
            if metadata:
                merged_metadata.update(metadata)
            super().__init__(rows, metadata=merged_metadata, index_field=index_field)

        @event
        def append(self, row: Dict[str, Any]) -> AppendRowEvent:
            if row_validator and not row_validator(row):
                raise ValueError(f"Row validation failed: {row}")
            return AppendRowEvent(row=dict(row))

        @event
        def extend(self, rows: Sequence[Dict[str, Any]]) -> ExtendRowsEvent:
            if row_validator:
                for row in rows:
                    if not row_validator(row):
                        raise ValueError(f"Row validation failed: {row}")
            return ExtendRowsEvent(rows=tuple(dict(r) for r in rows))

    CustomVersionedList.__name__ = name
    CustomVersionedList.__qualname__ = name
    return CustomVersionedList
