import sqlite3
import tempfile
import os
import json
from typing import Any, Callable, Iterable, Iterator, List, Optional
from abc import ABC, abstractmethod
from collections.abc import MutableSequence


class SQLiteList(MutableSequence, ABC):
    """
    An abstract base class for a MutableSequence that stores its data in a temporary SQLite file.
    The file is removed when close() is called.
    Subclasses must implement serialize and deserialize methods.
    """

    _TABLE_NAME = "list_data"  # Class constant instead of instance parameter

    @abstractmethod
    def serialize(self, value: Any) -> str:
        """Convert a value to a string for storage in SQLite."""
        pass

    @abstractmethod
    def deserialize(self, value: str) -> Any:
        """Convert a stored string back to its original value."""
        pass

    def __init__(self, data=None):
        # Create a temporary file for our SQLite database
        tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = tmpfile.name
        # Close the file handle immediately; SQLite only needs the path
        tmpfile.close()

        self.conn = sqlite3.connect(self.db_path)
        self._create_table_if_not_exists()

        # Initialize with data if provided
        if data is not None:
            self._batch_insert(data)

    def _create_table_if_not_exists(self):
        query = f"CREATE TABLE IF NOT EXISTS {self._TABLE_NAME} (idx INTEGER UNIQUE, value BLOB)"
        with self.conn:
            self.conn.execute(query)
            # Create an index for faster lookups
            self.conn.execute(f"CREATE INDEX IF NOT EXISTS idx_index ON {self._TABLE_NAME} (idx)")

    def _batch_insert(self, data: Iterable) -> None:
        """
        Insert items one at a time to minimize memory usage.
        
        Args:
            data: Iterable containing items to insert
        """
        with self.conn:
            # Use a single transaction for better performance
            for idx, item in enumerate(data):
                # Serialize and insert one item at a time to minimize memory usage
                serialized = self.serialize(item)
                self.conn.execute(
                    f"INSERT INTO {self._TABLE_NAME} (idx, value) VALUES (?, ?)",
                    (idx, serialized)
                )
                # Clear reference to allow garbage collection
                del serialized

    def __len__(self):
        cursor = self.conn.execute(f"SELECT COUNT(*) FROM {self._TABLE_NAME}")
        (count,) = cursor.fetchone()
        return count

    def __getitem__(self, index):
        if isinstance(index, slice):
            # Handle slice object
            start, stop, step = index.indices(len(self))
            if step == 1:  # Simple range
                cursor = self.conn.execute(
                    f"SELECT value FROM {self._TABLE_NAME} WHERE idx >= ? AND idx < ? ORDER BY idx",
                    (start, stop)
                )
                return [self.deserialize(row[0]) for row in cursor]
            else:  # Need to handle step
                indices = range(start, stop, step)
                return [self[i] for i in indices]
            
        # Handle integer index
        if index < 0:
            index = len(self) + index
        if not 0 <= index < len(self):
            raise IndexError("list index out of range")

        cursor = self.conn.execute(
            f"SELECT value FROM {self._TABLE_NAME} WHERE idx=?", (index,)
        )
        row = cursor.fetchone()
        if row is None:
            raise IndexError("list index out of range")
        return self.deserialize(row[0])

    def __setitem__(self, index, value):
        if index < 0:
            index = len(self) + index
        if not 0 <= index < len(self):
            raise IndexError("list assignment index out of range")

        serialized = self.serialize(value)
        with self.conn:
            self.conn.execute(
                f"UPDATE {self._TABLE_NAME} SET value=? WHERE idx=?",
                (serialized, index),
            )

    def __delitem__(self, index):
        if index < 0:
            index = len(self) + index
        if not 0 <= index < len(self):
            raise IndexError("list assignment index out of range")

        with self.conn:
            self.conn.execute(f"DELETE FROM {self._TABLE_NAME} WHERE idx=?", (index,))
            self.conn.execute(
                f"UPDATE {self._TABLE_NAME} SET idx = idx - 1 WHERE idx > ?", (index,)
            )

    def insert(self, index, value):
        """
        Inserts a value at the given index by shifting everything
        at or after `index` up by one in descending order.
        """
        length = len(self)
        if index < 0:
            index = 0
        if index > length:
            index = length

        serialized = self.serialize(value)
        with self.conn:
            # Shift every idx >= `index` up by 1, in descending order
            for i in reversed(range(index, length)):
                self.conn.execute(
                    f"UPDATE {self._TABLE_NAME} SET idx = ? WHERE idx = ?",
                    (i + 1, i),
                )

            # Now insert the new item
            self.conn.execute(
                f"INSERT INTO {self._TABLE_NAME} (idx, value) VALUES (?, ?)",
                (index, serialized),
            )

    def append(self, value):
        """Append a value to the end of the list."""
        index = len(self)
        serialized = self.serialize(value)
        with self.conn:
            self.conn.execute(
                f"INSERT INTO {self._TABLE_NAME} (idx, value) VALUES (?, ?)",
                (index, serialized),
            )

    def extend(self, values: Iterable) -> None:
        """
        Extend the list by appending all items in the given iterable.
        
        Processes one item at a time to minimize memory usage.
        
        Args:
            values: Iterable of values to append
        """
        start_idx = len(self)
        with self.conn:
            # Use a single transaction for efficiency
            for i, item in enumerate(values):
                # Serialize and insert one at a time to minimize memory usage
                serialized = self.serialize(item)
                self.conn.execute(
                    f"INSERT INTO {self._TABLE_NAME} (idx, value) VALUES (?, ?)",
                    (start_idx + i, serialized)
                )
                # Clear reference to allow garbage collection
                del serialized

    def close(self):
        """
        Close the database connection and remove the temporary file.
        """
        self.conn.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def __repr__(self):
        num_items = len(self)
        preview_count = min(num_items, 10)
        items = [self[i] for i in range(preview_count)]
        if preview_count < num_items:
            return f"{items}... (total {num_items} items)"
        else:
            return str(items)

    def __add__(self, other):
        """
        Concatenates two SQLiteLists and returns a new SQLiteList containing all elements.
        Use memory-efficient copy operation.
        """
        if not isinstance(other, SQLiteList):
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'"
            )

        # Create a new instance of the same class
        result = type(self)()
        
        # Use stream to copy all items from self
        result.extend(self.stream())
        
        # Use stream to copy all items from other
        result.extend(other.stream())

        return result

    def stream(self) -> Iterator[Any]:
        """Stream items from the database without loading everything into memory."""
        cursor = self.conn.execute(f"SELECT value FROM {self._TABLE_NAME} ORDER BY idx")
        for row in cursor:
            yield self.deserialize(row[0])

    def stream_batched(self, batch_size: int = 1000) -> Iterator[List[Any]]:
        """
        Stream items in batches to reduce memory usage and improve performance.
        
        Args:
            batch_size: Number of items to yield in each batch
            
        Yields:
            Lists of deserialized items, with at most batch_size items per list
        """
        cursor = self.conn.execute(f"SELECT value FROM {self._TABLE_NAME} ORDER BY idx")
        batch = []
        
        for row in cursor:
            batch.append(self.deserialize(row[0]))
            if len(batch) >= batch_size:
                yield batch
                batch = []
                
        if batch:  # Don't forget the last batch if it's not full
            yield batch

    def __iter__(self):
        """Iterate over items using streaming."""
        return self.stream()

    def equals(self, other):
        """Memory-efficient comparison of two SQLiteLists."""
        if len(self) != len(other):
            return False
        
        # Compare in batches to reduce memory usage
        batch_size = 1000
        self_batches = self.stream_batched(batch_size)
        other_batches = other.stream_batched(batch_size) if hasattr(other, 'stream_batched') else None
        
        if other_batches:
            # Both objects support batched streaming
            for self_batch, other_batch in zip(self_batches, other_batches):
                if len(self_batch) != len(other_batch):
                    return False
                for i in range(len(self_batch)):
                    if self_batch[i] != other_batch[i]:
                        return False
            return True
        else:
            # Fall back to item-by-item comparison
            for i in range(len(self)):
                if self[i] != other[i]:
                    return False
            return True

    def __eq__(self, other):
        """Use memory-efficient comparison by default."""
        return self.equals(other)

    def copy_from(self, source_db_path: str) -> None:
        """Copy data from another SQLite database file.
        
        Args:
            source_db_path: Path to the source SQLite database file
            
        Raises:
            sqlite3.Error: If there's an error accessing the source database
        """
        import sqlite3
        import time
        import shutil
        import tempfile
        
        # Make a temporary copy of the source database to avoid locking issues
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_file:
            temp_db_path = temp_file.name
        
        try:
            # Copy the source database to a temporary file
            shutil.copy2(source_db_path, temp_db_path)
            
            # Connect to the copied database
            source_conn = sqlite3.connect(temp_db_path)
            source_cursor = source_conn.cursor()
            
            try:
                # Check if the table exists in the source database
                source_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self._TABLE_NAME}'")
                if not source_cursor.fetchone():
                    return  # Table doesn't exist in source, nothing to copy
                
                # Get data from source database
                source_cursor.execute(f"SELECT idx, value FROM {self._TABLE_NAME} ORDER BY idx")
                rows = source_cursor.fetchall()
                
                # Empty the current database
                with self.conn:
                    self.conn.execute(f"DELETE FROM {self._TABLE_NAME}")
                
                # Insert data into the destination database
                with self.conn:
                    self.conn.executemany(
                        f"INSERT INTO {self._TABLE_NAME} (idx, value) VALUES (?, ?)",
                        rows
                    )
            finally:
                source_cursor.close()
                source_conn.close()
        finally:
            # Clean up the temporary file
            import os
            if os.path.exists(temp_db_path):
                try:
                    os.unlink(temp_db_path)
                except:
                    pass

    def __del__(self):
        """Clean up the temporary file when the object is deleted."""
        try:
            self.conn.close()
            os.unlink(self.db_path)
        except:
            pass