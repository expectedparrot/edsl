"""
Store class for event-sourced data storage.

The Store holds entries (list of dicts) and metadata, providing methods
for all operations that events can trigger.

Created: 2026-01-08
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, List


@dataclass
class Store:
    """Event-sourced data store holding entries and metadata.
    
    The Store is the central data structure that events operate on.
    Each method corresponds to an event type and mutates the store in-place.
    
    Attributes:
        entries: List of dictionaries, each representing a row/record.
        meta: Dictionary of metadata (e.g., codebook, pagination info).
    """
    entries: List[dict[str, Any]]
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the store to a dictionary."""
        return asdict(self)

    # =========================================================================
    # Row/Entry Operations
    # =========================================================================

    def append(self, item: dict[str, Any]) -> "Store":
        """Append an entry to the store."""
        self.entries.append(item)
        return self

    def update_row(self, index: int, row: dict[str, Any]) -> "Store":
        """Replace an entry at the specified index."""
        self.entries[index] = row
        return self

    def remove_rows(self, indices: tuple[int, ...]) -> "Store":
        """Remove entries at specified indices."""
        indices_to_remove = set(indices)
        self.entries = [
            row for i, row in enumerate(self.entries) 
            if i not in indices_to_remove
        ]
        return self

    def insert_row(self, index: int, row: dict[str, Any]) -> "Store":
        """Insert an entry at a specified index."""
        self.entries.insert(index, row)
        return self

    def update_entry_field(self, index: int, field: str, value: Any) -> "Store":
        """Update a specific field in an entry at a given index."""
        self.entries[index][field] = value
        return self

    def clear_entries(self) -> "Store":
        """Remove all entries."""
        self.entries.clear()
        return self

    def replace_all_entries(self, entries: tuple[dict[str, Any], ...]) -> "Store":
        """Replace all entries with new ones."""
        self.entries = list(entries)
        return self

    def reorder_entries(self, new_order: tuple[int, ...]) -> "Store":
        """Reorder entries by new index positions."""
        self.entries = [self.entries[i] for i in new_order]
        return self

    # =========================================================================
    # Field Operations
    # =========================================================================

    def add_field_to_all(self, field: str, value: Any) -> "Store":
        """Add a field with the same value to all entries."""
        for entry in self.entries:
            entry[field] = value
        return self

    def add_field_by_index(self, field: str, values: tuple[Any, ...]) -> "Store":
        """Add a field with values corresponding to each entry by index."""
        for i, entry in enumerate(self.entries):
            entry[field] = values[i]
        return self

    def drop_fields(self, fields: tuple[str, ...]) -> "Store":
        """Drop specified fields from all entries."""
        fields_set = set(fields)
        for entry in self.entries:
            for field in fields_set:
                entry.pop(field, None)
        return self

    def keep_fields(self, fields: tuple[str, ...]) -> "Store":
        """Keep only specified fields in all entries."""
        fields_set = set(fields)
        for i, entry in enumerate(self.entries):
            self.entries[i] = {k: v for k, v in entry.items() if k in fields_set}
        return self

    def rename_fields(self, rename_map: tuple[tuple[str, str], ...]) -> "Store":
        """Rename fields in all entries."""
        for entry in self.entries:
            for old_name, new_name in rename_map:
                if old_name in entry:
                    entry[new_name] = entry.pop(old_name)
        return self

    def reorder_keys(self, new_order: tuple[str, ...]) -> "Store":
        """Reorder keys in all entries according to the specified order."""
        self.entries = [
            {key: entry[key] for key in new_order if key in entry}
            for entry in self.entries
        ]
        return self

    def transform_field(self, field: str, new_field: str, new_values: tuple[Any, ...]) -> "Store":
        """Update field with pre-computed transformed values."""
        for i, entry in enumerate(self.entries):
            entry[new_field] = new_values[i]
        return self

    def uniquify_field(self, field: str, new_values: tuple[Any, ...]) -> "Store":
        """Update field values with pre-computed unique values."""
        for i, entry in enumerate(self.entries):
            if field in entry:
                entry[field] = new_values[i]
        return self

    # =========================================================================
    # Value Operations
    # =========================================================================

    def fill_na(self, fill_value: Any) -> "Store":
        """Fill NA/None values with a specified value."""
        import math
        
        def is_null(val):
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
                if str_val in ["nan", "none", "null", ""]:
                    return True
            return False
        
        for entry in self.entries:
            for key in entry:
                if is_null(entry[key]):
                    entry[key] = fill_value
        return self

    def string_cat_field(self, field: str, addend: str, position: str) -> "Store":
        """Concatenate a string to a field in all entries."""
        for entry in self.entries:
            if field in entry:
                current = entry[field]
                if isinstance(current, str):
                    if position == "prefix":
                        entry[field] = addend + current
                    else:  # suffix
                        entry[field] = current + addend
        return self

    def replace_values(self, replacements: tuple[tuple[str, Any], ...]) -> "Store":
        """Replace values in all entries based on a mapping."""
        replacements_dict = dict(replacements)
        for entry in self.entries:
            for key in entry:
                str_val = str(entry[key])
                if str_val in replacements_dict:
                    entry[key] = replacements_dict[str_val]
        return self

    def numberify(self, conversions: tuple[tuple[int, str, Any], ...]) -> "Store":
        """Apply pre-computed numeric conversions."""
        for entry_idx, field, new_value in conversions:
            self.entries[entry_idx][field] = new_value
        return self

    # =========================================================================
    # Meta Operations
    # =========================================================================

    def set_meta(self, key: str, value: Any) -> "Store":
        """Set a single key-value pair in meta."""
        self.meta[key] = value
        return self

    def update_meta(self, updates: dict[str, Any]) -> "Store":
        """Merge multiple key-value pairs into meta."""
        self.meta.update(updates)
        return self

    def remove_meta_key(self, key: str) -> "Store":
        """Remove a key from meta."""
        self.meta.pop(key, None)
        return self

    # =========================================================================
    # Composite Operations
    # =========================================================================

    def replace_entries_and_meta(
        self, entries: tuple[dict[str, Any], ...], meta_updates: tuple[tuple[str, Any], ...]
    ) -> "Store":
        """Replace all entries and update meta in one operation."""
        self.entries = list(entries)
        for key, value in meta_updates:
            self.meta[key] = value
        return self

    # =========================================================================
    # Serialization
    # =========================================================================

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Store":
        """Create a Store from a dictionary."""
        return cls(**data)

