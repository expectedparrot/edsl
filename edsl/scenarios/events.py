from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

try:
    from .column_store import ColumnStore, _gen_col_id, _gen_row_id
    from .event_registry import register_event, SerializableEvent, _gen_event_id
except ImportError:
    from column_store import ColumnStore, _gen_col_id, _gen_row_id
    from event_registry import register_event, SerializableEvent, _gen_event_id


@register_event
@dataclass(frozen=True)
class AppendRows(SerializableEvent):
    """Append multiple rows to the store."""
    event_type = "append_rows"

    version: int
    rows: List[Dict[str, Any]]
    row_ids: List[str] = field(default_factory=list)  # Optional: pre-generated row IDs
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        m = len(self.rows)
        
        # Generate row IDs if not provided
        new_row_ids = self.row_ids if self.row_ids else [_gen_row_id() for _ in range(m)]
        
        # Extend existing columns with None
        for col_id in store._cols:
            store._cols[col_id].extend([None] * m)

        start = store._nrows
        store._nrows += m
        
        # Add row IDs
        store._row_ids.extend(new_row_ids)

        for j, row in enumerate(self.rows):
            i = start + j
            for name, value in row.items():
                # Check if column name exists
                if name not in store._col_names:
                    # Create new column with generated ID
                    col_id = _gen_col_id()
                    store._col_names[name] = col_id
                    store._cols[col_id] = [None] * store._nrows
                
                col_id = store._col_names[name]
                store._cols[col_id][i] = value


@register_event
@dataclass(frozen=True)
class AppendRow(SerializableEvent):
    """Append a single row to the store."""
    event_type = "append_row"

    version: int
    row: Dict[str, Any]
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        AppendRows(version=self.version, rows=[self.row], event_id=self.event_id).execute(store)


@register_event
@dataclass(frozen=True)
class RenameColumn(SerializableEvent):
    """
    Rename a column. O(1) operation - just updates the name→ID mapping.
    The actual column data (stored by ID) is unchanged.
    """
    event_type = "rename_column"

    version: int
    old: str
    new: str
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if self.old in store._col_names and self.new not in store._col_names:
            # Just update the name mapping - data stays in place
            col_id = store._col_names.pop(self.old)
            store._col_names[self.new] = col_id


@register_event
@dataclass(frozen=True)
class MetaUpdate(SerializableEvent):
    event_type = "meta_update"

    version: int
    patch: Dict[str, Any]
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        store._meta.update(self.patch)

@register_event
@dataclass(frozen=True)
class DropColumns(SerializableEvent):
    """Drop columns by name."""
    event_type = "drop_columns"

    version: int
    cols: List[str]  # Column names to drop
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        for name in self.cols:
            if name in store._col_names:
                col_id = store._col_names.pop(name)
                store._cols.pop(col_id)


@register_event
@dataclass(frozen=True)
class SetValue(SerializableEvent):
    """Set a specific cell value by row index and column name."""
    event_type = "set_value"

    version: int
    row: int
    col: str  # Column name
    value: Any
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        col_id = store._col_names[self.col]
        store._cols[col_id][self.row] = self.value

@register_event
@dataclass(frozen=True)
class MetaSet(SerializableEvent):
    event_type = "meta_set"

    version: int
    key: str
    value: Any
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        store._meta[self.key] = self.value


@register_event
@dataclass(frozen=True)
class AddColumn(SerializableEvent):
    """Add a new column with given values."""
    event_type = "add_column"

    version: int
    column_name: str
    values: List[Any]
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        col_id = _gen_col_id()
        store._col_names[self.column_name] = col_id
        store._cols[col_id] = self.values


@register_event
@dataclass(frozen=True)
class FilterRows(SerializableEvent):
    """Filter rows based on an expression. Removes rows that don't match."""

    event_type = "filter_rows"

    version: int
    expression: Dict[str, Any]  # Serialized Expression
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        try:
            from .filters import Expression
        except ImportError:
            from filters import Expression

        expr = Expression.from_dict(self.expression)

        # Get current rows with row IDs for tracking
        rows_with_ids = []
        for i in range(store._nrows):
            row = {name: store._cols[col_id][i] for name, col_id in store._col_names.items()}
            row['_row_id'] = store._row_ids[i]
            rows_with_ids.append(row)

        # Filter rows using names (exclude _row_id from evaluation)
        filtered = [row for row in rows_with_ids if expr.evaluate({k: v for k, v in row.items() if k != '_row_id'})]

        # Rebuild columns from filtered rows (preserving column IDs)
        for name, col_id in store._col_names.items():
            store._cols[col_id] = [row.get(name) for row in filtered]
        
        # Rebuild row_ids
        store._row_ids = [row['_row_id'] for row in filtered]

        store._nrows = len(filtered)


@register_event
@dataclass(frozen=True)
class DeleteRows(SerializableEvent):
    """Delete rows at specified indices or by row IDs."""

    event_type = "delete_rows"

    version: int
    indices: List[int] = field(default_factory=list)  # Row indices to delete
    by_row_ids: List[str] = field(default_factory=list)  # Or delete by row ID
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        # Convert negative indices to positive and create set for O(1) lookup
        indices_to_delete = set()
        
        # Add indices from direct specification
        for idx in self.indices:
            if idx < 0:
                idx = store._nrows + idx
            if 0 <= idx < store._nrows:
                indices_to_delete.add(idx)
        
        # Add indices from row IDs
        for row_id in self.by_row_ids:
            try:
                idx = store._row_ids.index(row_id)
                indices_to_delete.add(idx)
            except ValueError:
                pass  # Row ID not found, skip

        # Rebuild columns without deleted rows (using IDs)
        for col_id, col_values in store._cols.items():
            store._cols[col_id] = [
                val for i, val in enumerate(col_values) 
                if i not in indices_to_delete
            ]
        
        # Rebuild row_ids without deleted rows
        store._row_ids = [
            rid for i, rid in enumerate(store._row_ids)
            if i not in indices_to_delete
        ]

        store._nrows = store._nrows - len(indices_to_delete)


@register_event
@dataclass(frozen=True)
class SelectColumns(SerializableEvent):
    """Keep only specified columns (by name), dropping all others.
    
    The columns are also reordered to match the order specified in `cols`.
    """

    event_type = "select_columns"

    version: int
    cols: List[str]  # Column names to keep (in desired order)
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        names_to_keep = set(self.cols)
        names_to_drop = [n for n in store._col_names if n not in names_to_keep]
        
        # Drop unwanted columns
        for name in names_to_drop:
            col_id = store._col_names.pop(name)
            store._cols.pop(col_id)
        
        # Reorder remaining columns to match the order in self.cols
        # Build new col_names dict in the correct order
        new_col_names = {}
        for name in self.cols:
            if name in store._col_names:
                new_col_names[name] = store._col_names[name]
        store._col_names = new_col_names


@register_event
@dataclass(frozen=True)
class SortRows(SerializableEvent):
    """Sort rows by one or more fields (by column name)."""

    event_type = "sort_rows"

    version: int
    fields: Tuple[str, ...]  # Column names to sort by, in priority order
    reverse: bool = False  # If True, sort descending
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        # Get current rows with row IDs
        rows_with_ids = []
        for i in range(store._nrows):
            row = {name: store._cols[col_id][i] for name, col_id in store._col_names.items()}
            row['_row_id'] = store._row_ids[i]
            rows_with_ids.append(row)

        # Sort rows by field names - handle None values by sorting them last
        def sort_key(row):
            def normalize(val):
                # Sort None to the end
                return (val is None, val if val is not None else "")
            return tuple(normalize(row.get(f)) for f in self.fields)

        sorted_rows = sorted(rows_with_ids, key=sort_key, reverse=self.reverse)

        # Rebuild columns from sorted rows (preserving column IDs)
        for name, col_id in store._col_names.items():
            store._cols[col_id] = [row.get(name) for row in sorted_rows]
        
        # Update row_ids order
        store._row_ids = [row['_row_id'] for row in sorted_rows]


@register_event
@dataclass(frozen=True)
class ReplaceValues(SerializableEvent):
    """Replace specific values across the store."""

    event_type = "replace_values"

    version: int
    replacements: Dict[str, Any]  # {old_value_as_string: new_value}
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        for col_name, col_values in store._cols.items():
            for i, val in enumerate(col_values):
                str_val = str(val)
                if str_val in self.replacements:
                    col_values[i] = self.replacements[str_val]


@register_event
@dataclass(frozen=True)
class FillNA(SerializableEvent):
    """Fill None/null values with a specified value."""

    event_type = "fill_na"

    version: int
    value: Any  # Value to fill nulls with
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        for col_values in store._cols.values():
            for i, val in enumerate(col_values):
                if val is None:
                    col_values[i] = self.value


# ─────────────────────────────────────────────────────────────
# High-Priority Events (Phase 2)
# ─────────────────────────────────────────────────────────────

@register_event
@dataclass(frozen=True)
class ExpandRows(SerializableEvent):
    """
    Expand rows by unpacking list values in one or more columns.
    
    Single column: For each row where the column contains a list,
    creates multiple rows (one per list element).
    
    Multiple columns (aligned): All specified columns must have lists of
    equal length. Expands in lockstep - the i-th elements from each column
    are combined into one expanded row.
    
    Non-list values (except strings) are treated as single-element lists.
    
    Args:
        columns: Tuple of column names to expand
        number_field: If True, add {column}_number with 1-based index for each column
    """

    event_type = "expand_rows"

    version: int
    columns: Tuple[str, ...]  # Column names containing lists to expand
    number_field: bool = False  # If True, add {column}_number with 1-based index
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        rows = store.to_rows()
        expanded_rows = []
        new_row_ids = []
        
        # Single column case
        if len(self.columns) == 1:
            col = self.columns[0]
            for i, row in enumerate(rows):
                values = row.get(col)
                # Treat non-list values (except strings) as single-element lists
                if not isinstance(values, list) or isinstance(values, str):
                    values = [values]
                
                for idx, val in enumerate(values):
                    new_row = dict(row)
                    new_row[col] = val
                    if self.number_field:
                        new_row[f"{col}_number"] = idx + 1
                    expanded_rows.append(new_row)
                    # Generate new row ID for each expanded row
                    new_row_ids.append(_gen_row_id())
        else:
            # Multi-column aligned expansion
            for i, row in enumerate(rows):
                value_lists = []
                for col in self.columns:
                    vals = row.get(col)
                    if not isinstance(vals, list) or isinstance(vals, str):
                        vals = [vals]
                    value_lists.append(list(vals))
                
                # Check lengths match
                lengths = {len(v) for v in value_lists}
                if len(lengths) != 1:
                    # Skip rows with mismatched lengths (or could raise error)
                    continue
                
                for idx, tuple_vals in enumerate(zip(*value_lists)):
                    new_row = dict(row)
                    for col, val in zip(self.columns, tuple_vals):
                        new_row[col] = val
                        if self.number_field:
                            new_row[f"{col}_number"] = idx + 1
                    expanded_rows.append(new_row)
                    # Generate new row ID for each expanded row
                    new_row_ids.append(_gen_row_id())

        # Handle new columns if number_field is True
        if self.number_field:
            for col in self.columns:
                number_col_name = f"{col}_number"
                if number_col_name not in store._col_names:
                    col_id = _gen_col_id()
                    store._col_names[number_col_name] = col_id
                    store._cols[col_id] = []

        # Rebuild columns from expanded rows
        for name, col_id in store._col_names.items():
            store._cols[col_id] = [row.get(name) for row in expanded_rows]
        
        # Update row_ids
        store._row_ids = new_row_ids

        store._nrows = len(expanded_rows)


@register_event
@dataclass(frozen=True)
class DeduplicateRows(SerializableEvent):
    """
    Remove duplicate rows based on all columns or specified columns.
    Keeps the first occurrence of each unique combination.
    """

    event_type = "deduplicate_rows"

    version: int
    columns: List[str] = None  # If None, deduplicate on all columns
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        # Get rows with row IDs
        rows_with_ids = []
        for i in range(store._nrows):
            row = {name: store._cols[col_id][i] for name, col_id in store._col_names.items()}
            row['_row_id'] = store._row_ids[i]
            rows_with_ids.append(row)
        
        # Determine which columns to use for deduplication
        dedup_cols = self.columns if self.columns else list(store._col_names.keys())
        
        seen = set()
        unique_rows = []
        
        for row in rows_with_ids:
            # Create a hashable key from the dedup columns
            key = tuple(
                tuple(v) if isinstance(v, list) else v
                for v in (row.get(col) for col in dedup_cols)
            )
            if key not in seen:
                seen.add(key)
                unique_rows.append(row)

        # Rebuild columns from unique rows
        for name, col_id in store._col_names.items():
            store._cols[col_id] = [row.get(name) for row in unique_rows]
        
        # Update row_ids (keep row IDs of first occurrences)
        store._row_ids = [row['_row_id'] for row in unique_rows]

        store._nrows = len(unique_rows)


def _seeded_rng(seed: str):
    """
    Create a seeded random number generator that produces the same 
    sequence in Python and TypeScript.
    Uses a simple hash-based approach for cross-language compatibility.
    """
    # Convert seed string to initial state using djb2-like hash
    h = 0
    for c in seed:
        h = ((h * 31) + ord(c)) & 0xFFFFFFFF
    
    def next_random():
        nonlocal h
        # xorshift-style mixing
        h ^= (h >> 16) & 0xFFFFFFFF
        h = (h * 2246822507) & 0xFFFFFFFF
        h ^= (h >> 13) & 0xFFFFFFFF
        h = (h * 3266489909) & 0xFFFFFFFF
        h ^= (h >> 16) & 0xFFFFFFFF
        return (h & 0x7FFFFFFF) / 0x80000000  # Return 0-1 float
    
    return next_random


@register_event
@dataclass(frozen=True)
class ShuffleRows(SerializableEvent):
    """
    Shuffle rows in random order.
    Uses a seed for reproducibility across Python and TypeScript.
    """

    event_type = "shuffle_rows"

    version: int
    seed: str  # Seed for reproducibility (string to be JSON-serializable)
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        # Get rows with row IDs
        rows_with_ids = []
        for i in range(store._nrows):
            row = {name: store._cols[col_id][i] for name, col_id in store._col_names.items()}
            row['_row_id'] = store._row_ids[i]
            rows_with_ids.append(row)
        
        rng = _seeded_rng(self.seed)
        
        # Fisher-Yates shuffle
        for i in range(len(rows_with_ids) - 1, 0, -1):
            j = int(rng() * (i + 1))
            rows_with_ids[i], rows_with_ids[j] = rows_with_ids[j], rows_with_ids[i]

        # Rebuild columns from shuffled rows
        for name, col_id in store._col_names.items():
            store._cols[col_id] = [row.get(name) for row in rows_with_ids]
        
        # Update row_ids order
        store._row_ids = [row['_row_id'] for row in rows_with_ids]


@register_event
@dataclass(frozen=True)
class SampleRows(SerializableEvent):
    """
    Take a random sample of n rows.
    Uses a seed for reproducibility across Python and TypeScript.
    """

    event_type = "sample_rows"

    version: int
    n: int  # Number of rows to sample
    seed: str  # Seed for reproducibility
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        # Clamp n to available rows
        n = min(self.n, store._nrows)
        
        # Get rows with row IDs
        rows_with_ids = []
        for i in range(store._nrows):
            row = {name: store._cols[col_id][i] for name, col_id in store._col_names.items()}
            row['_row_id'] = store._row_ids[i]
            rows_with_ids.append(row)
        
        rng = _seeded_rng(self.seed)
        
        # Fisher-Yates partial shuffle for sampling
        for i in range(n):
            j = i + int(rng() * (len(rows_with_ids) - i))
            rows_with_ids[i], rows_with_ids[j] = rows_with_ids[j], rows_with_ids[i]
        
        sampled = rows_with_ids[:n]

        # Rebuild columns from sampled rows
        for name, col_id in store._col_names.items():
            store._cols[col_id] = [row.get(name) for row in sampled]
        
        # Update row_ids
        store._row_ids = [row['_row_id'] for row in sampled]

        store._nrows = len(sampled)


@register_event
@dataclass(frozen=True)
class CastTypes(SerializableEvent):
    """
    Cast column values to specified types.
    Supports: 'int', 'float', 'str', 'bool', 'auto' (auto-detect numeric).
    """

    event_type = "cast_types"

    version: int
    columns: Dict[str, str]  # {column_name: target_type}
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        def try_cast(value, target_type):
            if value is None:
                return None
            try:
                if target_type == "int":
                    return int(float(value))  # Handle "3.0" -> 3
                elif target_type == "float":
                    return float(value)
                elif target_type == "str":
                    return str(value)
                elif target_type == "bool":
                    if isinstance(value, bool):
                        return value
                    if isinstance(value, str):
                        return value.lower() in ("true", "1", "yes", "on")
                    return bool(value)
                elif target_type == "auto":
                    # Try int first, then float, otherwise keep as-is
                    try:
                        f = float(value)
                        if f == int(f):
                            return int(f)
                        return f
                    except (ValueError, TypeError):
                        return value
                else:
                    return value
            except (ValueError, TypeError):
                return value

        for col_name, target_type in self.columns.items():
            if col_name not in store._col_names:
                continue
            col_id = store._col_names[col_name]
            store._cols[col_id] = [
                try_cast(v, target_type) for v in store._cols[col_id]
            ]


@register_event
@dataclass(frozen=True)
class UnpackList(SerializableEvent):
    """
    Unpack a column containing lists into multiple columns.
    Each list element becomes a new column with a generated or provided name.
    
    Example:
        column 'scores' = [10, 20, 30]
        -> scores_0 = 10, scores_1 = 20, scores_2 = 30
    """

    event_type = "unpack_list"

    version: int
    column: str  # Column name containing lists to unpack
    new_names: Tuple[str, ...] = ()  # Names for new columns; if empty, auto-generate
    keep_original: bool = True  # Whether to keep the original column
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if self.column not in store._col_names:
            return

        col_id = store._col_names[self.column]
        col_values = store._cols[col_id]

        # Determine max list length and column names
        max_len = 0
        for val in col_values:
            if isinstance(val, (list, tuple)):
                max_len = max(max_len, len(val))

        if max_len == 0:
            return

        # Use provided names or generate them
        if self.new_names:
            names = list(self.new_names)
            # Pad with generated names if not enough provided
            while len(names) < max_len:
                names.append(f"{self.column}_{len(names)}")
        else:
            names = [f"{self.column}_{i}" for i in range(max_len)]

        # Create new columns
        for i, name in enumerate(names[:max_len]):
            if name not in store._col_names:
                new_col_id = _gen_col_id()
                store._col_names[name] = new_col_id
            else:
                new_col_id = store._col_names[name]

            # Extract values at index i from each list
            new_values = []
            for val in col_values:
                if isinstance(val, (list, tuple)) and i < len(val):
                    new_values.append(val[i])
                elif isinstance(val, (list, tuple)):
                    new_values.append(None)
                elif max_len == 1:
                    # Single value case - treat as single-element list
                    new_values.append(val if i == 0 else None)
                else:
                    new_values.append(None)
            store._cols[new_col_id] = new_values

        # Remove original column if requested
        if not self.keep_original:
            store._cols.pop(col_id)
            del store._col_names[self.column]


@register_event
@dataclass(frozen=True)
class UnpackColumn(SerializableEvent):
    """
    Unpack a column containing dicts into multiple columns.
    Each key in the dict becomes a new column.
    """

    event_type = "unpack_column"

    version: int
    column: str  # Column name containing dicts to unpack
    prefix: str = ""  # Optional prefix for new column names
    drop_field: bool = True  # Whether to remove the original column
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if self.column not in store._col_names:
            return

        col_id = store._col_names[self.column]
        col_values = store._cols[col_id]

        # Collect all keys from all dict values
        all_keys = set()
        for val in col_values:
            if isinstance(val, dict):
                all_keys.update(val.keys())

        if not all_keys:
            return

        # Create new columns for each key
        for key in all_keys:
            new_col_name = f"{self.prefix}{key}" if self.prefix else key
            if new_col_name not in store._col_names:
                new_col_id = _gen_col_id()
                store._col_names[new_col_name] = new_col_id
                store._cols[new_col_id] = []
            else:
                new_col_id = store._col_names[new_col_name]
                store._cols[new_col_id] = []

            # Extract values
            for val in col_values:
                if isinstance(val, dict):
                    store._cols[new_col_id].append(val.get(key))
                else:
                    store._cols[new_col_id].append(None)

        # Remove the original column if requested
        if self.drop_field:
            store._cols.pop(col_id)
            del store._col_names[self.column]


@register_event
@dataclass(frozen=True)
class UniquifyColumn(SerializableEvent):
    """
    Make all values in a column unique by appending suffixes (_1, _2, etc.) to duplicates.
    
    The first occurrence of each value is unchanged; subsequent duplicates get
    suffixes like _1, _2, _3, etc.
    
    Example:
        ['item', 'item', 'item', 'other'] -> ['item', 'item_1', 'item_2', 'other']
    """

    event_type = "uniquify_column"

    version: int
    column: str  # Column name to uniquify
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if self.column not in store._col_names:
            return

        col_id = store._col_names[self.column]
        col_values = store._cols[col_id]

        seen_values = {}  # Maps original value to count of occurrences
        new_values = []

        for value in col_values:
            if value not in seen_values:
                # First occurrence - use original value
                new_values.append(value)
                seen_values[value] = 1
            else:
                # Duplicate - append suffix
                suffix_num = seen_values[value]
                new_value = f"{value}_{suffix_num}"
                new_values.append(new_value)
                seen_values[value] += 1

        store._cols[col_id] = new_values


@register_event
@dataclass(frozen=True)
class RenameColumnsToValid(SerializableEvent):
    """
    Rename columns to be valid Python identifiers.
    
    Uses a mapping dict to specify new names. The mapping is stored in the
    codebook metadata for reference.
    
    Args:
        mapping: Dict mapping old column names to new valid names.
                 Only columns in this mapping are renamed.
    """

    event_type = "rename_columns_to_valid"

    version: int
    mapping: Dict[str, str]  # {old_name: new_name}
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        # Apply each rename
        for old_name, new_name in self.mapping.items():
            if old_name in store._col_names and new_name not in store._col_names:
                col_id = store._col_names.pop(old_name)
                store._col_names[new_name] = col_id
        
        # Update codebook in metadata
        codebook = store._meta.get("codebook", {})
        codebook.update(self.mapping)
        store._meta["codebook"] = codebook


@register_event
@dataclass(frozen=True)
class ZipColumns(SerializableEvent):
    """
    Zip two columns into a new column containing dicts.
    
    For each row, creates dict(zip(col_a[i], col_b[i])) and stores in new column.
    The values in col_a become dict keys, values in col_b become dict values.
    
    Example:
        col_a: [["a", "b"], ["x", "y"]]
        col_b: [[1, 2], [9, 8]]
        result: [{"a": 1, "b": 2}, {"x": 9, "y": 8}]
    """

    event_type = "zip_columns"

    version: int
    col_keys: str  # Column name containing keys (iterables)
    col_values: str  # Column name containing values (iterables)
    new_column: str  # Name for the new column containing dicts
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if self.col_keys not in store._col_names:
            return
        if self.col_values not in store._col_names:
            return

        keys_col_id = store._col_names[self.col_keys]
        vals_col_id = store._col_names[self.col_values]
        
        keys_data = store._cols[keys_col_id]
        vals_data = store._cols[vals_col_id]

        # Create new column with zipped dicts
        new_col_id = _gen_col_id()
        new_values = []
        
        for keys, vals in zip(keys_data, vals_data):
            try:
                # Handle case where keys/vals might not be iterable
                if keys is None or vals is None:
                    new_values.append(None)
                else:
                    new_values.append(dict(zip(keys, vals)))
            except (TypeError, ValueError):
                new_values.append(None)
        
        store._col_names[self.new_column] = new_col_id
        store._cols[new_col_id] = new_values


@register_event
@dataclass(frozen=True)
class TransformColumn(SerializableEvent):
    """
    Transform values in a column using built-in operations or safe expressions.
    
    Option 1 - Built-in operations:
        operation: Name of operation (e.g., "upper", "abs", "round")
        args: Dict of arguments for the operation
        
    Option 2 - Expression:
        operation: "expr"
        args: {"expression": "price * 1.1"}
    
    Supported operations:
        String: upper, lower, strip, lstrip, rstrip, replace, split, len, slice
        Math: abs, round, floor, ceil, sqrt, log, exp, add, subtract, multiply, divide, mod, power, negate
        Type: to_int, to_float, to_str, to_bool
        Expression: expr (safe arithmetic/string expressions)
    """

    event_type = "transform_column"

    version: int
    column: str
    operation: str
    new_column: str = None  # If None, overwrites the original column
    args: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=_gen_event_id)

    # Safe functions allowed in expressions
    SAFE_FUNCTIONS = {
        'len': len,
        'str': str,
        'int': int,
        'float': float,
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
    }

    def _apply_operation(self, value: Any) -> Any:
        """Apply the operation to a single value."""
        import math
        
        if value is None:
            return None
        
        op = self.operation.lower()
        args = self.args or {}
        
        # String operations
        if op == "upper":
            return str(value).upper()
        elif op == "lower":
            return str(value).lower()
        elif op == "strip":
            return str(value).strip()
        elif op == "lstrip":
            return str(value).lstrip()
        elif op == "rstrip":
            return str(value).rstrip()
        elif op == "replace":
            return str(value).replace(args.get("old", ""), args.get("new", ""))
        elif op == "split":
            return str(value).split(args.get("sep", None))
        elif op == "slice":
            start = args.get("start", 0)
            end = args.get("end", None)
            return str(value)[start:end]
        elif op == "len":
            return len(value) if hasattr(value, "__len__") else None
        
        # Math operations
        elif op == "abs":
            return abs(value) if isinstance(value, (int, float)) else value
        elif op == "round":
            digits = args.get("digits", 0)
            return round(value, digits) if isinstance(value, (int, float)) else value
        elif op == "floor":
            return math.floor(value) if isinstance(value, (int, float)) else value
        elif op == "ceil":
            return math.ceil(value) if isinstance(value, (int, float)) else value
        elif op == "sqrt":
            return math.sqrt(value) if isinstance(value, (int, float)) and value >= 0 else None
        elif op == "log":
            base = args.get("base", math.e)
            return math.log(value, base) if isinstance(value, (int, float)) and value > 0 else None
        elif op == "exp":
            return math.exp(value) if isinstance(value, (int, float)) else value
        elif op == "add":
            amount = args.get("amount", 0)
            return value + amount if isinstance(value, (int, float)) else value
        elif op == "subtract":
            amount = args.get("amount", 0)
            return value - amount if isinstance(value, (int, float)) else value
        elif op == "multiply":
            factor = args.get("factor", 1)
            return value * factor if isinstance(value, (int, float)) else value
        elif op == "divide":
            divisor = args.get("divisor", 1)
            return value / divisor if isinstance(value, (int, float)) and divisor != 0 else None
        elif op == "mod":
            divisor = args.get("divisor", 1)
            return value % divisor if isinstance(value, (int, float)) and divisor != 0 else None
        elif op == "power":
            exp = args.get("exponent", 1)
            return value ** exp if isinstance(value, (int, float)) else value
        elif op == "negate":
            return -value if isinstance(value, (int, float)) else value
        
        # Type conversions
        elif op == "to_int":
            try:
                return int(value)
            except (ValueError, TypeError):
                return None
        elif op == "to_float":
            try:
                return float(value)
            except (ValueError, TypeError):
                return None
        elif op == "to_str":
            return str(value)
        elif op == "to_bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "on")
            return bool(value)
        
        # Expression evaluation
        elif op == "expr":
            return self._eval_expression(value, args.get("expression", "x"))
        
        return value

    def _eval_expression(self, value: Any, expression: str) -> Any:
        """Safely evaluate an expression with the current value as 'x'."""
        import ast
        import operator
        
        # Safe operators
        safe_ops = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
            ast.UAdd: operator.pos,
        }
        
        def safe_eval(node, context):
            if isinstance(node, ast.Expression):
                return safe_eval(node.body, context)
            elif isinstance(node, ast.Constant):
                return node.value
            elif isinstance(node, ast.Num):  # Python 3.7 compat
                return node.n
            elif isinstance(node, ast.Str):  # Python 3.7 compat
                return node.s
            elif isinstance(node, ast.Name):
                if node.id in context:
                    return context[node.id]
                raise ValueError(f"Unknown variable: {node.id}")
            elif isinstance(node, ast.BinOp):
                left = safe_eval(node.left, context)
                right = safe_eval(node.right, context)
                op_func = safe_ops.get(type(node.op))
                if op_func is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op_func(left, right)
            elif isinstance(node, ast.UnaryOp):
                operand = safe_eval(node.operand, context)
                op_func = safe_ops.get(type(node.op))
                if op_func is None:
                    raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
                return op_func(operand)
            elif isinstance(node, ast.Call):
                func_name = node.func.id if isinstance(node.func, ast.Name) else None
                if func_name not in self.SAFE_FUNCTIONS:
                    raise ValueError(f"Function not allowed: {func_name}")
                args = [safe_eval(arg, context) for arg in node.args]
                return self.SAFE_FUNCTIONS[func_name](*args)
            else:
                raise ValueError(f"Unsupported expression: {type(node).__name__}")
        
        try:
            tree = ast.parse(expression, mode='eval')
            return safe_eval(tree, {'x': value})
        except Exception:
            return None

    def execute(self, store: ColumnStore) -> None:
        if self.column not in store._col_names:
            return

        col_id = store._col_names[self.column]
        col_values = store._cols[col_id]

        new_values = [self._apply_operation(v) for v in col_values]

        # Store in new column or overwrite
        target_col = self.new_column or self.column
        if target_col == self.column:
            store._cols[col_id] = new_values
        else:
            if target_col not in store._col_names:
                new_col_id = _gen_col_id()
                store._col_names[target_col] = new_col_id
                store._cols[new_col_id] = new_values
            else:
                existing_col_id = store._col_names[target_col]
                store._cols[existing_col_id] = new_values


@register_event
@dataclass(frozen=True)
class GroupByAggregate(SerializableEvent):
    """
    Group rows by id columns and apply aggregation functions to other columns.
    
    Args:
        id_vars: Columns to group by (become row identifiers)
        aggregations: Dict mapping column_name -> aggregation_type
                     Supported types: "sum", "mean", "min", "max", "count", 
                                     "first", "last", "list", "concat"
    
    Example:
        id_vars: ("category",)
        aggregations: {"value": "sum", "name": "list"}
        
        Input:  [{"category": "A", "value": 10, "name": "x"},
                 {"category": "A", "value": 20, "name": "y"},
                 {"category": "B", "value": 5, "name": "z"}]
        Output: [{"category": "A", "value": 30, "name": ["x", "y"]},
                 {"category": "B", "value": 5, "name": ["z"]}]
    """

    event_type = "group_by_aggregate"

    version: int
    id_vars: Tuple[str, ...]
    aggregations: Dict[str, str]  # column -> aggregation type
    event_id: str = field(default_factory=_gen_event_id)

    SUPPORTED_AGGS = {"sum", "mean", "avg", "min", "max", "count", "first", "last", "list", "concat"}

    @staticmethod
    def _aggregate(values: List[Any], agg_type: str) -> Any:
        """Apply aggregation function to a list of values."""
        # Filter out None values for numeric aggregations
        numeric_values = [v for v in values if v is not None and isinstance(v, (int, float))]
        
        if agg_type == "sum":
            return sum(numeric_values) if numeric_values else 0
        elif agg_type in ("mean", "avg"):
            return sum(numeric_values) / len(numeric_values) if numeric_values else None
        elif agg_type == "min":
            non_none = [v for v in values if v is not None]
            return min(non_none) if non_none else None
        elif agg_type == "max":
            non_none = [v for v in values if v is not None]
            return max(non_none) if non_none else None
        elif agg_type == "count":
            return len(values)
        elif agg_type == "first":
            return values[0] if values else None
        elif agg_type == "last":
            return values[-1] if values else None
        elif agg_type == "list":
            return values
        elif agg_type == "concat":
            return ", ".join(str(v) for v in values if v is not None)
        else:
            return values  # fallback to list

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        rows = store.to_rows()
        
        # Group rows by id_vars
        from collections import defaultdict
        grouped: Dict[tuple, Dict[str, List]] = defaultdict(lambda: defaultdict(list))
        
        for row in rows:
            key = tuple(row.get(id_var) for id_var in self.id_vars)
            for col_name in self.aggregations.keys():
                grouped[key][col_name].append(row.get(col_name))

        # Build aggregated rows
        new_rows = []
        for key, group_data in grouped.items():
            new_row = dict(zip(self.id_vars, key))
            for col_name, agg_type in self.aggregations.items():
                values = group_data.get(col_name, [])
                new_row[col_name] = self._aggregate(values, agg_type)
            new_rows.append(new_row)

        # Rebuild store
        store._cols.clear()
        store._col_names.clear()

        # Columns: id_vars + aggregated columns
        all_cols = list(self.id_vars) + list(self.aggregations.keys())
        
        for col_name in all_cols:
            col_id = _gen_col_id()
            store._col_names[col_name] = col_id
            store._cols[col_id] = [r.get(col_name) for r in new_rows]

        # Generate new row IDs for aggregated rows
        store._row_ids = [_gen_row_id() for _ in new_rows]
        store._nrows = len(new_rows)


@register_event
@dataclass(frozen=True)
class UnpivotRows(SerializableEvent):
    """
    Unpivot (melt) data from wide to long format.
    
    Creates new rows for each value_var, with 'variable' and 'value' columns.
    
    Args:
        id_vars: Columns to keep as identifiers
        value_vars: Columns to unpivot (if None, all non-id columns)
    """

    event_type = "unpivot_rows"

    version: int
    id_vars: Tuple[str, ...] = ()
    value_vars: Tuple[str, ...] = None  # None means all non-id columns
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        rows = store.to_rows()
        
        # Determine value_vars
        if self.value_vars:
            val_vars = list(self.value_vars)
        else:
            val_vars = [c for c in store._col_names.keys() if c not in self.id_vars]

        new_rows = []
        for row in rows:
            for var in val_vars:
                new_row = {id_var: row.get(id_var) for id_var in self.id_vars}
                new_row["variable"] = var
                new_row["value"] = row.get(var)
                new_rows.append(new_row)

        # Rebuild store with new structure
        # Clear existing columns
        store._cols.clear()
        store._col_names.clear()

        # Add id_var columns
        for id_var in self.id_vars:
            col_id = _gen_col_id()
            store._col_names[id_var] = col_id
            store._cols[col_id] = [r.get(id_var) for r in new_rows]

        # Add variable and value columns
        var_col_id = _gen_col_id()
        store._col_names["variable"] = var_col_id
        store._cols[var_col_id] = [r["variable"] for r in new_rows]

        val_col_id = _gen_col_id()
        store._col_names["value"] = val_col_id
        store._cols[val_col_id] = [r["value"] for r in new_rows]

        # Generate new row IDs for unpivoted rows
        store._row_ids = [_gen_row_id() for _ in new_rows]
        store._nrows = len(new_rows)


@register_event
@dataclass(frozen=True)
class PivotRows(SerializableEvent):
    """
    Pivot data from long to wide format.
    
    Args:
        id_vars: Columns to use as row identifiers
        var_name: Column containing variable names (default: "variable")
        value_name: Column containing values (default: "value")
    """

    event_type = "pivot_rows"

    version: int
    id_vars: Tuple[str, ...] = ()
    var_name: str = "variable"
    value_name: str = "value"
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        rows = store.to_rows()
        
        # Group by id_vars
        pivoted: Dict[tuple, Dict[str, Any]] = {}
        all_variables = set()

        for row in rows:
            id_key = tuple(row.get(id_var) for id_var in self.id_vars)
            if id_key not in pivoted:
                pivoted[id_key] = {id_var: row.get(id_var) for id_var in self.id_vars}
            
            variable = row.get(self.var_name)
            value = row.get(self.value_name)
            if variable is not None:
                pivoted[id_key][variable] = value
                all_variables.add(variable)

        new_rows = list(pivoted.values())

        # Rebuild store
        store._cols.clear()
        store._col_names.clear()

        # All columns: id_vars + pivoted variables
        all_cols = list(self.id_vars) + sorted(all_variables)
        
        for col_name in all_cols:
            col_id = _gen_col_id()
            store._col_names[col_name] = col_id
            store._cols[col_id] = [r.get(col_name) for r in new_rows]

        # Generate new row IDs for pivoted rows
        store._row_ids = [_gen_row_id() for _ in new_rows]
        store._nrows = len(new_rows)


@register_event
@dataclass(frozen=True)
class ReorderColumns(SerializableEvent):
    """
    Reorder columns according to a specified order.
    
    Args:
        new_order: List of column names in desired order
    """

    event_type = "reorder_columns"

    version: int
    new_order: Tuple[str, ...]
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        # Validate all columns exist
        for col in self.new_order:
            if col not in store._col_names:
                return  # Skip if invalid
        
        # Create new col_names dict in desired order
        new_col_names = {}
        for col_name in self.new_order:
            new_col_names[col_name] = store._col_names[col_name]
        
        # Add any columns not in new_order at the end
        for col_name, col_id in store._col_names.items():
            if col_name not in new_col_names:
                new_col_names[col_name] = col_id
        
        store._col_names.clear()
        store._col_names.update(new_col_names)


@register_event
@dataclass(frozen=True)
class CollapseRows(SerializableEvent):
    """
    Collapse rows by grouping on all columns except a specified field,
    collecting the field's values into a list (or joined string).
    
    Args:
        field: Column to collapse
        separator: If provided, join values with this separator; otherwise keep as list
        prefix: Prefix for each value when joining
        postfix: Postfix for each value when joining
        add_count: If True, add a 'num_collapsed_rows' column
    """

    event_type = "collapse_rows"

    version: int
    field: str
    separator: str = None
    prefix: str = ""
    postfix: str = ""
    add_count: bool = False
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return
        if self.field not in store._col_names:
            return

        rows = store.to_rows()
        
        # Group by all columns except the field
        id_vars = [c for c in store._col_names.keys() if c != self.field]
        
        from collections import defaultdict
        grouped: Dict[tuple, List] = defaultdict(list)
        
        for row in rows:
            key = tuple(row.get(id_var) for id_var in id_vars)
            grouped[key].append(row.get(self.field))

        new_rows = []
        for key, values in grouped.items():
            new_row = dict(zip(id_vars, key))
            if self.separator is not None:
                formatted = [f"{self.prefix}{v}{self.postfix}" for v in values]
                new_row[self.field] = self.separator.join(str(v) for v in formatted)
            else:
                new_row[self.field] = values
            if self.add_count:
                new_row["num_collapsed_rows"] = len(values)
            new_rows.append(new_row)

        # Rebuild store
        store._cols.clear()
        store._col_names.clear()

        # Determine all columns
        all_cols = id_vars + [self.field]
        if self.add_count:
            all_cols.append("num_collapsed_rows")

        for col_name in all_cols:
            col_id = _gen_col_id()
            store._col_names[col_name] = col_id
            store._cols[col_id] = [r.get(col_name) for r in new_rows]

        # Generate new row IDs for collapsed rows
        store._row_ids = [_gen_row_id() for _ in new_rows]
        store._nrows = len(new_rows)


@register_event
@dataclass(frozen=True)
class FilterNA(SerializableEvent):
    """
    Remove rows where specified columns contain NA values (None, NaN, "nan", "none", "null").
    
    Args:
        columns: List of column names to check. If None or empty, checks all columns.
    """

    event_type = "filter_na"

    version: int
    columns: Tuple[str, ...] = None  # Columns to check; None means all columns
    event_id: str = field(default_factory=_gen_event_id)

    @staticmethod
    def _is_na(val: Any) -> bool:
        """Check if a value is considered NA."""
        import math
        if val is None:
            return True
        if isinstance(val, float):
            try:
                if math.isnan(val):
                    return True
            except (TypeError, ValueError):
                pass
        if hasattr(val, "__str__"):
            str_val = str(val).lower()
            if str_val in ["nan", "none", "null"]:
                return True
        return False

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return

        # Determine which columns to check
        if self.columns:
            check_cols = [c for c in self.columns if c in store._col_names]
        else:
            check_cols = list(store._col_names.keys())

        if not check_cols:
            return

        # Find rows to keep (those without NA in checked columns)
        keep_indices = []
        for i in range(store._nrows):
            has_na = False
            for col_name in check_cols:
                col_id = store._col_names[col_name]
                val = store._cols[col_id][i]
                if self._is_na(val):
                    has_na = True
                    break
            if not has_na:
                keep_indices.append(i)

        # Filter all columns
        for col_id in store._cols:
            store._cols[col_id] = [store._cols[col_id][i] for i in keep_indices]
        
        # Filter row_ids
        store._row_ids = [store._row_ids[i] for i in keep_indices]

        store._nrows = len(keep_indices)


@register_event
@dataclass(frozen=True)
class ChunkRows(SerializableEvent):
    """
    Chunk text in a column by word count or line count, creating multiple rows per chunk.
    
    For each row, splits the text in the specified column and creates new rows,
    adding metadata columns: {column}_chunk (index), {column}_char_count, {column}_word_count.
    
    Args:
        column: Column name containing text to chunk
        num_words: Number of words per chunk (mutually exclusive with num_lines)
        num_lines: Number of lines per chunk (mutually exclusive with num_words)
        include_original: If True, keep the original text in {column}_original
        hash_original: If True, store a hash of the original text instead
    """

    event_type = "chunk_rows"

    version: int
    column: str
    num_words: int = None
    num_lines: int = None
    include_original: bool = False
    hash_original: bool = False
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return
        if self.column not in store._col_names:
            return

        rows = store.to_rows()
        new_rows = []
        new_row_ids = []

        for row in rows:
            text = row.get(self.column, "")
            if text is None:
                text = ""
            text = str(text)

            # Chunk the text
            chunks = self._chunk_text(text)
            
            for chunk_idx, chunk_text in enumerate(chunks):
                new_row = dict(row)
                new_row[self.column] = chunk_text
                new_row[f"{self.column}_chunk"] = chunk_idx
                new_row[f"{self.column}_char_count"] = len(chunk_text)
                new_row[f"{self.column}_word_count"] = len(chunk_text.split())
                
                if self.include_original:
                    if self.hash_original:
                        import hashlib
                        new_row[f"{self.column}_original"] = hashlib.md5(text.encode()).hexdigest()
                    else:
                        new_row[f"{self.column}_original"] = text
                
                new_rows.append(new_row)
                # Generate new row ID for each chunk
                new_row_ids.append(_gen_row_id())

        # Add new metadata columns if they don't exist
        for suffix in ["_chunk", "_char_count", "_word_count"]:
            col_name = f"{self.column}{suffix}"
            if col_name not in store._col_names:
                store._col_names[col_name] = _gen_col_id()
                store._cols[store._col_names[col_name]] = []
        
        if self.include_original:
            orig_col = f"{self.column}_original"
            if orig_col not in store._col_names:
                store._col_names[orig_col] = _gen_col_id()
                store._cols[store._col_names[orig_col]] = []

        # Rebuild columns from new rows
        for name, col_id in store._col_names.items():
            store._cols[col_id] = [row.get(name) for row in new_rows]

        # Update row IDs
        store._row_ids = new_row_ids
        store._nrows = len(new_rows)

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks based on num_words or num_lines."""
        if not text:
            return [text]
        
        if self.num_words is not None:
            words = text.split()
            chunks = []
            for i in range(0, len(words), self.num_words):
                chunk_words = words[i:i + self.num_words]
                chunks.append(" ".join(chunk_words))
            return chunks if chunks else [""]
        
        elif self.num_lines is not None:
            lines = text.split("\n")
            chunks = []
            for i in range(0, len(lines), self.num_lines):
                chunk_lines = lines[i:i + self.num_lines]
                chunks.append("\n".join(chunk_lines))
            return chunks if chunks else [""]
        
        # No chunking specified, return as-is
        return [text]


@register_event
@dataclass(frozen=True)
class TackOnRow(SerializableEvent):
    """
    Duplicate a row at a given index with optional value replacements, and append it.
    
    Args:
        source_index: Index of the row to duplicate (supports negative indexing)
        replacements: Dict of column_name -> new_value to apply to the duplicated row
    """

    event_type = "tack_on_row"

    version: int
    source_index: int  # Row index to duplicate
    replacements: Dict[str, Any]  # Column values to replace in the new row
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if store._nrows == 0:
            return
        
        # Resolve negative index
        idx = self.source_index
        if idx < 0:
            idx = store._nrows + idx
        if idx < 0 or idx >= store._nrows:
            return  # Invalid index, skip
        
        # For each column, duplicate the value at source_index and append
        for col_name, col_id in store._col_names.items():
            col_values = store._cols[col_id]
            # Get value from source row, apply replacement if specified
            if col_name in self.replacements:
                new_value = self.replacements[col_name]
            else:
                new_value = col_values[idx]
            col_values.append(new_value)
        
        # Generate new row ID for the duplicated row
        store._row_ids.append(_gen_row_id())
        store._nrows += 1


@register_event
@dataclass(frozen=True)
class NumberifyColumns(SerializableEvent):
    """
    Convert string values to numeric types where possible.
    
    Conversion rules:
    - None values remain None
    - Already numeric values (int, float) remain unchanged
    - String values that can be parsed as integers are converted to int
    - String values that can be parsed as floats are converted to float
    - String values that cannot be parsed remain as strings
    - Empty strings remain as empty strings
    """

    event_type = "numberify_columns"

    version: int
    event_id: str = field(default_factory=_gen_event_id)

    @staticmethod
    def _try_numeric(value: Any) -> Any:
        """Attempt to convert a value to int or float."""
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        if not isinstance(value, str):
            return value
        if value == "":
            return value
        
        # Try int first
        try:
            return int(value)
        except ValueError:
            pass
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        return value

    def execute(self, store: ColumnStore) -> None:
        for col_name, col_id in store._col_names.items():
            col_values = store._cols[col_id]
            store._cols[col_id] = [self._try_numeric(v) for v in col_values]


@register_event
@dataclass(frozen=True)
class ConcatToColumn(SerializableEvent):
    """
    Concatenate a string to all values in a column.
    
    Can append (suffix) or prepend (prefix) the string to existing values.
    Values are converted to strings before concatenation.
    
    Args:
        column: Column name to modify
        value: String to concatenate
        position: "suffix" (default) to append, "prefix" to prepend
    
    Example:
        column: ["hello", "world"]
        value: "!"
        position: "suffix"
        result: ["hello!", "world!"]
    """

    event_type = "concat_to_column"

    version: int
    column: str
    value: str  # String to concatenate
    position: str = "suffix"  # "suffix" or "prefix"
    event_id: str = field(default_factory=_gen_event_id)

    def execute(self, store: ColumnStore) -> None:
        if self.column not in store._col_names:
            return

        col_id = store._col_names[self.column]
        col_values = store._cols[col_id]

        new_values = []
        for v in col_values:
            if v is None:
                new_values.append(self.value if self.position == "prefix" else self.value)
            elif self.position == "prefix":
                new_values.append(self.value + str(v))
            else:  # suffix
                new_values.append(str(v) + self.value)
        
        store._cols[col_id] = new_values


# ─────────────────────────────────────────────────────────────
# Snapshot Events (Non-replayable - wholesale state replacement)
# ─────────────────────────────────────────────────────────────

@register_event
@dataclass(frozen=True)
class VibesSnapshot(SerializableEvent):
    """
    Wholesale replacement of store data from a vibes (AI) operation.
    
    This event is NOT replayable in the traditional sense - it doesn't
    transform state, it replaces it entirely. The event stores:
    - The complete new data (as rows)
    - Metadata about what operation was performed (for audit trail)
    
    Unlike most events which are transformations (filter, add, edit),
    this event is a checkpoint: "here's the new state, generated by AI".
    
    This enables vibes operations (translate, edit, enrich) to:
    1. Create new versions on the same store/branch
    2. Preserve full version history (can revert to pre-vibe state)
    3. Record what operation was performed for audit
    
    Args:
        version: The new version number
        rows: Complete new data as list of dicts
        operation: Name of the vibes operation (e.g., "translate", "edit", "enrich")
        params: Parameters passed to the operation (for audit trail)
        task_id: Optional reference to the service task that generated this
        col_names: Optional column name to ID mapping (if None, derived from rows)
        row_ids: Optional row IDs (if None, new ones are generated)
    
    Example:
        Original:
            v0: init (rows=[{name: "Alice"}, {name: "Bob"}])
            v1: append_row({name: "Charlie"})
        
        After translate to Spanish:
            v2: vibes_snapshot(
                    rows=[{name: "Alicia"}, {name: "Roberto"}, {name: "Carlos"}],
                    operation="translate",
                    params={"target_language": "Spanish"}
                )
        
        User can checkout(1) to get pre-translation state.
    """
    
    event_type = "vibes_snapshot"
    
    version: int
    rows: Tuple[Dict[str, Any], ...]  # Immutable tuple for frozen dataclass
    operation: str  # e.g., "translate", "edit", "filter", "enrich", "clean"
    params: Dict[str, Any] = field(default_factory=dict)  # Operation parameters
    task_id: str = ""  # Optional reference to service task
    col_names: Dict[str, str] = None  # Optional col_name -> col_id mapping
    row_ids: Tuple[str, ...] = None  # Optional row IDs
    event_id: str = field(default_factory=_gen_event_id)
    
    def execute(self, store: ColumnStore) -> None:
        """
        Wholesale replace the store's data with the new snapshot.
        
        This completely replaces:
        - All columns
        - All column name mappings
        - All row IDs
        - Row count
        
        Metadata is preserved.
        """
        rows = list(self.rows)  # Convert tuple back to list for processing
        
        if not rows:
            # Empty snapshot - clear everything
            store._cols.clear()
            store._col_names.clear()
            store._row_ids = []
            store._nrows = 0
            return
        
        # Get all column names from the rows
        all_col_names = set()
        for row in rows:
            all_col_names.update(row.keys())
        
        # Use provided col_names mapping or generate new IDs
        if self.col_names:
            new_col_names = dict(self.col_names)
            # Add any missing columns
            for name in all_col_names:
                if name not in new_col_names:
                    new_col_names[name] = _gen_col_id()
        else:
            # Generate new column IDs for all columns
            new_col_names = {name: _gen_col_id() for name in all_col_names}
        
        # Use provided row_ids or generate new ones
        if self.row_ids:
            new_row_ids = list(self.row_ids)
        else:
            new_row_ids = [_gen_row_id() for _ in rows]
        
        # Build new column data
        new_cols = {col_id: [] for col_id in new_col_names.values()}
        for row in rows:
            for name, col_id in new_col_names.items():
                new_cols[col_id].append(row.get(name))
        
        # Replace store state
        store._cols = new_cols
        store._col_names = new_col_names
        store._row_ids = new_row_ids
        store._nrows = len(rows)