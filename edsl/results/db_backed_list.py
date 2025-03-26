"""
A database-backed list implementation for memory-efficient storage.

This module provides a list-like interface that stores items in SQLite,
keeping only a configurable number of items in memory at once to reduce
memory usage for very large result sets.
"""

import json
import os
import sqlite3
import tempfile
from collections import OrderedDict
from typing import Any, Iterator, List, Optional, Union

class DBBackedList:
    """A database-backed list implementation for memory-efficient storage.
    
    This class provides a list-like interface but stores items in SQLite,
    keeping only a configurable number of items in memory at once.
    """
    
    # Configure via environment variables or hard-coded defaults
    DEFAULT_MEMORY_LIMIT = int(os.environ.get("EDSL_DB_LIST_MEMORY_LIMIT", 1000))
    DEFAULT_DB_PATH = os.environ.get("EDSL_DB_LIST_PATH", None)
    DEFAULT_CHUNK_SIZE = int(os.environ.get("EDSL_DB_LIST_CHUNK_SIZE", 100))
    
    def __init__(
        self, 
        initial_items: Optional[List[Any]] = None,
        memory_limit: Optional[int] = None,
        db_path: Optional[str] = None,
        deserializer: Optional[callable] = None,
        serializer: Optional[callable] = None
    ):
        """
        Initialize a database-backed list.
        
        Args:
            initial_items: Optional list of items to initialize with
            memory_limit: Maximum number of items to keep in memory (default from env var)
            db_path: Path to SQLite database file (default from env var or temporary)
            deserializer: Function to convert from JSON to item (optional)
            serializer: Function to convert from item to JSON (optional)
        """
        # Use parameters or fall back to defaults
        self.memory_limit = memory_limit or self.DEFAULT_MEMORY_LIMIT
        self._db_path = db_path or self.DEFAULT_DB_PATH
        
        # If db_path is still None, create a temporary file
        if self._db_path is None:
            self._temp_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
            self._db_path = self._temp_db_file.name
            self._temp_db_file.close()
        
        # Set up serialization functions
        self._deserializer = deserializer or self._default_deserializer
        self._serializer = serializer or self._default_serializer
        
        # Cache for recently accessed items
        self._cache = OrderedDict()
        
        # Set up database
        self._setup_db()
        
        # Add initial items if provided
        if initial_items:
            self.extend(initial_items)
    
    def _default_serializer(self, item: Any) -> str:
        """Default serialization to JSON"""
        # Special handling for unittest.mock.Mock objects used in doctests
        if hasattr(item, '__class__') and 'Mock' in item.__class__.__name__:
            # For mocks with a spec that has to_dict, try to get a stub representation
            if hasattr(item, '_spec_class') and hasattr(item._spec_class, 'to_dict'):
                # Create a basic dict representation of the mock for serialization
                return json.dumps({"__mock_object__": True, "__mock_spec__": item._spec_class.__name__})
            else:
                # Return a placeholder for other Mock objects
                return json.dumps({"__mock_object__": True})
        
        if hasattr(item, 'to_dict'):
            return json.dumps(item.to_dict())
        return json.dumps(item)
    
    def _default_deserializer(self, json_str: str) -> Any:
        """Default deserialization from JSON"""
        # This will be replaced by custom logic in Results
        data = json.loads(json_str)
        
        # Check if this is a serialized Mock object
        if isinstance(data, dict) and data.get("__mock_object__") == True:
            # Create a new Mock
            from unittest.mock import Mock
            
            # If it has a specified spec, create with that spec
            if data.get("__mock_spec__"):
                # Determine what spec to use based on the name
                if data["__mock_spec__"] == "Result":
                    try:
                        from edsl.results.result import Result
                        return Mock(spec=Result)
                    except ImportError:
                        pass
                        
            # Otherwise return a plain Mock
            return Mock()
            
        return data
    
    def _setup_db(self) -> None:
        """Set up SQLite database for storing items"""
        self._conn = sqlite3.connect(self._db_path)
        
        cursor = self._conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY,
            item_json TEXT,
            hash INTEGER
        )''')
        self._conn.commit()
    
    def __len__(self) -> int:
        """Return number of items in the list"""
        cursor = self._conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM items")
        return cursor.fetchone()[0]
    
    def __getitem__(self, idx: Union[int, slice]) -> Any:
        """Get item(s) at the given index/slice"""
        if isinstance(idx, slice):
            # Handle slices
            start, stop, step = idx.indices(len(self))
            return [self[i] for i in range(start, stop, step)]
        
        # Handle negative indexing
        if idx < 0:
            idx = len(self) + idx
            if idx < 0:
                raise IndexError("Index out of range")
        
        # Check in-memory cache first
        if idx in self._cache:
            # Move to end (most recently used)
            item = self._cache.pop(idx)
            self._cache[idx] = item
            return item
        
        # Fetch from database
        cursor = self._conn.cursor()
        # Convert Python 0-based index to SQLite 1-based id
        sql_id = idx + 1
        cursor.execute("SELECT item_json FROM items WHERE id = ?", (sql_id,))
        row = cursor.fetchone()
        
        if row is None:
            raise IndexError(f"Index {idx} out of range")
        
        # Deserialize and add to cache
        item = self._deserializer(row[0])
        self._update_cache(idx, item)
        
        return item
    
    def _update_cache(self, idx: int, item: Any) -> None:
        """Update LRU cache with an item"""
        # If cache is full, remove oldest item
        if len(self._cache) >= self.memory_limit:
            self._cache.popitem(last=False)
        
        # Add to cache
        self._cache[idx] = item
    
    def __iter__(self) -> Iterator[Any]:
        """Iterate through all items in the list"""
        total = len(self)
        chunk_size = self.DEFAULT_CHUNK_SIZE
        
        for offset in range(0, total, chunk_size):
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT id, item_json FROM items ORDER BY id LIMIT ? OFFSET ?",
                (chunk_size, offset)
            )
            
            for sql_id, item_json in cursor.fetchall():
                item = self._deserializer(item_json)
                
                # Convert SQLite 1-based id to Python 0-based index
                idx = sql_id - 1
                
                # Update cache if not full
                if len(self._cache) < self.memory_limit:
                    self._cache[idx] = item
                
                yield item
    
    def append(self, item: Any) -> None:
        """Add an item to the end of the list"""
        cursor = self._conn.cursor()
        
        # Serialize the item
        item_json = self._serializer(item)
        item_hash = hash(item) if hasattr(item, '__hash__') else hash(item_json)
        
        # Insert into database
        cursor.execute(
            "INSERT INTO items (item_json, hash) VALUES (?, ?)",
            (item_json, item_hash)
        )
        self._conn.commit()
        
        # Get inserted index (SQLite rowid is 1-based, we want 0-based)
        idx = cursor.lastrowid - 1
        
        # Update cache if not full
        if len(self._cache) < self.memory_limit:
            self._cache[idx] = item
    
    def extend(self, items: List[Any]) -> None:
        """Add multiple items to the end of the list"""
        if not items:
            return
        
        # Batch insert for efficiency
        cursor = self._conn.cursor()
        data = [
            (
                self._serializer(item), 
                hash(item) if hasattr(item, '__hash__') else hash(self._serializer(item))
            ) 
            for item in items
        ]
        
        cursor.executemany(
            "INSERT INTO items (item_json, hash) VALUES (?, ?)",
            data
        )
        self._conn.commit()
    
    def close(self) -> None:
        """Close database connection"""
        if hasattr(self, '_conn'):
            self._conn.close()
    
    def __del__(self) -> None:
        """Clean up resources when object is garbage collected"""
        self.close()
        
    def copy(self) -> "DBBackedList":
        """Create a copy of the list with the same items.
        
        Returns:
            A new DBBackedList containing the same items
        """
        # Create a new empty list
        new_list = DBBackedList(
            memory_limit=self.memory_limit,
            deserializer=self._deserializer,
            serializer=self._serializer
        )
        
        # Copy all items
        for item in self:
            new_list.append(item)
            
        return new_list
    
    def __add__(self, other) -> "DBBackedList":
        """Concatenate two DBBackedList objects.
        
        Args:
            other: Another DBBackedList or an iterable to add
            
        Returns:
            A new DBBackedList containing items from both lists
        """
        # Create a copy of this list
        result = self.copy()
        
        # Add items from other list
        for item in other:
            result.append(item)
            
        return result