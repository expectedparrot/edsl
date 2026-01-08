from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, TYPE_CHECKING


def _gen_col_id() -> str:
    """Generate a unique column ID."""
    return str(uuid.uuid4())


def _gen_row_id() -> str:
    """Generate a unique row ID."""
    return str(uuid.uuid4())


class Event(Protocol):
    version: int
    def execute(self, store: "ColumnStore") -> None: ...


class ColumnStore:
    """
    A column-oriented data store with ID-based column AND row storage.
    
    Both columns and rows are stored with stable UUIDs, with separate name/order mappings.
    This makes rename and reorder operations O(1) - just update mappings, not data.
    
    Attributes:
        _cols: Dict mapping column_id → list of values (indexed by row position)
        _col_names: Dict mapping column_name → column_id
        _row_ids: List of row UUIDs in display order
        _nrows: Number of rows
        _meta: Arbitrary metadata
        _version: Event version number
    
    Design:
        - Column data is stored by column UUID, values indexed by position
        - Row order is determined by _row_ids list
        - Position i in _cols[col_id] corresponds to _row_ids[i]
        - Reordering rows = reordering _row_ids (O(n) but no data copying)
        - Renaming columns = updating _col_names mapping (O(1))
    """
    
    def __init__(
        self,
        *,
        cols: Optional[Dict[str, List[Any]]] = None,
        col_names: Optional[Dict[str, str]] = None,
        row_ids: Optional[List[str]] = None,
        nrows: int = 0,
        meta: Optional[Dict[str, Any]] = None,
        version: int = 0,
        log: Optional["EventLog"] = None,
        branch: Optional[str] = None,
    ):
        self._cols = cols or {}  # col_id → values
        self._col_names = col_names or {}  # col_name → col_id
        self._row_ids = row_ids or []  # ordered list of row UUIDs
        self._nrows = nrows
        self._meta = dict(meta or {})
        self._version = version
        
        # Track applied event IDs to prevent duplicate application
        # This is a defensive measure against bugs in version/snapshot logic
        self._applied_event_ids: set = set()
        
        # Ensure _row_ids matches _nrows if not provided
        if not self._row_ids and self._nrows > 0:
            self._row_ids = [_gen_row_id() for _ in range(self._nrows)]
        
    # ─────────────────────────────────────────────────────────────
    # ID ↔ Name helpers
    # ─────────────────────────────────────────────────────────────
    
    def _name_to_id(self, name: str) -> str:
        """Get column ID from name. Raises KeyError if not found."""
        return self._col_names[name]

    def _id_to_name(self, col_id: str) -> str:
        """Get column name from ID. Raises KeyError if not found."""
        for name, cid in self._col_names.items():
            if cid == col_id:
                return name
        raise KeyError(f"No column with ID {col_id}")

    def _get_col_by_name(self, name: str) -> List[Any]:
        """Get column values by name."""
        return self._cols[self._name_to_id(name)]

    @classmethod
    def from_rows(
        cls,
        rows: Sequence[Mapping[str, Any]],
        *,
        meta: Optional[Dict[str, Any]] = None,
    ) -> "ColumnStore":
        """Create a ColumnStore from a sequence of row dicts.
        
        Note: Column order is preserved based on first appearance across all rows.
        """
        # Collect names preserving insertion order (first seen wins)
        seen = set()
        names = []
        for r in rows:
            for k in r:
                if k not in seen:
                    seen.add(k)
                    names.append(k)
        
        # Generate IDs for each column name (dict preserves insertion order in Python 3.7+)
        col_names = {name: _gen_col_id() for name in names}
        
        # Generate IDs for each row
        row_ids = [_gen_row_id() for _ in rows]
        
        # Build column data using IDs
        cols = {col_id: [] for col_id in col_names.values()}
        for r in rows:
            for name, col_id in col_names.items():
                cols[col_id].append(r.get(name))
        
        return cls(cols=cols, col_names=col_names, row_ids=row_ids, nrows=len(rows), meta=meta)
    
    @classmethod
    def from_events(
        cls,
        events: List[Event],
    ) -> "ColumnStore":
        """
        Create a ColumnStore by replaying a sequence of events.
        
        Args:
            events: Events to replay
            log: Optional EventLog to attach
            branch: Optional branch name
        
        Returns:
            ColumnStore with state resulting from replaying events
        """
        store = cls(
            cols={},
            col_names={},
            row_ids=[],
            nrows=0,
            meta={},
            version=0,
        )
        
        for event in events:
            event.execute(store)
        
        return store

    def to_rows(self, include_row_id: bool = False) -> List[Dict[str, Any]]:
        """Convert to list of row dicts (using column names, not IDs).
        
        Args:
            include_row_id: If True, include '_row_id' in each row dict
        
        Returns:
            List of row dictionaries in current order
        """
        rows = []
        for i in range(self._nrows):
            row = {}
            if include_row_id and self._row_ids:
                row['_row_id'] = self._row_ids[i]
            for name, col_id in self._col_names.items():
                row[name] = self._cols[col_id][i]
            rows.append(row)
        return rows

    # ─────────────────────────────────────────────────────────────
    # Serialization
    # ─────────────────────────────────────────────────────────────

    @property
    def version(self) -> int:
        return self._version

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict (preserves internal ID-based structure)."""
        return {
            "cols": self._cols,
            "col_names": self._col_names,
            "row_ids": self._row_ids,
            "nrows": self._nrows,
            "meta": self._meta,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ColumnStore":
        """Deserialize from dict."""
        return cls(
            cols=d["cols"],
            col_names=d["col_names"],
            row_ids=d.get("row_ids"),  # Optional for backward compat
            nrows=d["nrows"],
            meta=d["meta"],
        )

    # ─────────────────────────────────────────────────────────────
    # Event application
    # ─────────────────────────────────────────────────────────────

    def apply(self, events: Iterable[Event]) -> None:
        events_list = list(events)
        pending = sorted(
            (e for e in events_list if e.version > self._version),
            key=lambda e: e.version,
        )

        for e in pending:
            if e.version != self._version + 1:
                raise ValueError("Non-contiguous event stream")
            e.execute(self)
            self._version = e.version
        
        
    def snapshot(self) -> "ColumnStore":
        """
        Create a branch (fork) at current state.
        
        Returns a new ColumnStore on a new branch, sharing the same EventLog.
        Both stores can evolve independently.
        
        Returns:
            New ColumnStore instance on the forked branch
        
        Example:
            store = ColumnStore.from_rows([{"a": 1}], log=EventLog())
            forked = store.snapshot()
            # store and forked now have independent histories
        """    
        # Create new ColumnStore with same data but different branch
        return ColumnStore(
            cols=copy.deepcopy(self._cols),
            col_names=copy.deepcopy(self._col_names),
            row_ids=list(self._row_ids),  # Copy row IDs
            nrows=self._nrows,
            meta=copy.deepcopy(self._meta),
        )
    
    def get_row_id(self, index: int) -> str:
        """Get the row ID at the given index."""
        if index < 0:
            index = self._nrows + index
        return self._row_ids[index]
    
    def get_row_index(self, row_id: str) -> int:
        """Get the index of a row by its ID. Returns -1 if not found."""
        try:
            return self._row_ids.index(row_id)
        except ValueError:
            return -1
    
    def get_row_by_id(self, row_id: str) -> Optional[Dict[str, Any]]:
        """Get a row by its ID. Returns None if not found."""
        idx = self.get_row_index(row_id)
        if idx == -1:
            return None
        row = {}
        for name, col_id in self._col_names.items():
            row[name] = self._cols[col_id][idx]
        return row
    
    @property
    def row_ids(self) -> List[str]:
        """Return list of row IDs in current order."""
        return list(self._row_ids)
    
    def __repr__(self) -> str:
        names = list(self._col_names.keys())
        col_str = ", ".join(names[:5])
        if len(names) > 5:
            col_str += f", ... ({len(names) - 5} more)"
        
        # Show preview of first few rows (using names)
        preview_rows = min(3, self._nrows)
        if preview_rows > 0 and names:
            rows_preview = []
            for i in range(preview_rows):
                row = {name: self._cols[self._col_names[name]][i] for name in names[:3]}
                rows_preview.append(str(row))
            rows_str = "; ".join(rows_preview)
            if self._nrows > preview_rows:
                rows_str += f"; ... ({self._nrows - preview_rows} more rows)"
        else:
            rows_str = "(empty)"
        
        meta_str = f", meta={self._meta}" if self._meta else ""
        
        return f"ColumnStore(cols=[{col_str}], nrows={self._nrows}, version={self._version}{meta_str})\n  Data: {rows_str}"

    def __len__(self) -> int:
        return self._nrows

    def __getitem__(self, name: str) -> List[Any]:
        """Get a column by name."""
        return self._get_col_by_name(name)

    @property
    def columns(self) -> List[str]:
        """Return list of column names."""
        return list(self._col_names.keys())

    @property
    def shape(self) -> tuple:
        """Return (nrows, ncols) like pandas."""
        return (self._nrows, len(self._col_names))
        
    def to_arrow(self) -> "pyarrow.Table":
        """
        Export to a PyArrow Table.
        
        Returns:
            pyarrow.Table with columns named by column names (not IDs).
        
        Example:
            >>> store = ColumnStore.from_rows([{'a': 1, 'b': 'x'}, {'a': 2, 'b': 'y'}])
            >>> table = store.to_arrow()
            >>> table.to_pandas()
               a  b
            0  1  x
            1  2  y
        """
        import pyarrow as pa
        
        # Build dict with column names as keys
        data = {name: self._cols[col_id] for name, col_id in self._col_names.items()}
        return pa.Table.from_pydict(data)

    @classmethod
    def from_arrow(cls, table: "pyarrow.Table", meta: Optional[Dict[str, Any]] = None) -> "ColumnStore":
        """
        Create a ColumnStore from a PyArrow Table.
        
        Args:
            table: PyArrow Table to import
            meta: Optional metadata dict
            
        Returns:
            ColumnStore with data from the table
        """
        import pyarrow as pa
        
        col_names = {}
        cols = {}
        
        for name in table.column_names:
            col_id = _gen_col_id()
            col_names[name] = col_id
            # Convert to Python list
            cols[col_id] = table.column(name).to_pylist()
        
        # Generate row IDs
        row_ids = [_gen_row_id() for _ in range(table.num_rows)]
        
        return cls(
            cols=cols,
            col_names=col_names,
            row_ids=row_ids,
            nrows=table.num_rows,
            meta=meta,
        )

    def to_parquet(self, path: Optional[str] = None) -> str:
        """
        Write to a Parquet file.
        
        Args:
            path: File path to write to. If None, writes to 'store.parquet'
                  in the current directory.
        
        Returns:
            The path the file was written to.
        """
        import pyarrow.parquet as pq
        
        if path is None:
            path = "store.parquet"
        
        table = self.to_arrow()
        pq.write_table(table, path)
        return path

    @classmethod
    def from_parquet(cls, path: str, meta: Optional[Dict[str, Any]] = None) -> "ColumnStore":
        """
        Read from a Parquet file.
        
        Args:
            path: File path to read from
            meta: Optional metadata dict
            
        Returns:
            ColumnStore with data from the file
        """
        import pyarrow.parquet as pq
        
        table = pq.read_table(path)
        return cls.from_arrow(table, meta=meta)

    @classmethod
    def example(cls) -> "ColumnStore":
        return cls.from_rows(
            [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
            meta={"codebook": {"a": "age", "b": "income"}},
        )


if __name__ == "__main__":
    # Demo ColumnStore directly
    c = ColumnStore.from_rows(
        [{"a": 1, "b": 2}, {"a": 3, "b": 4}],
        meta={"codebook": {"a": "age", "b": "income"}},
    )
    print("ColumnStore example:")
    print(c)
    print(f"Columns: {c.columns}")
    print(f"Shape: {c.shape}")
    print(f"Rows: {c.to_rows()}")