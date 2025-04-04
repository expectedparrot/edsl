import sqlite3
import tempfile
import os
import json
from typing import Any, Callable
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
            for item in data:
                self.append(item)

    def _create_table_if_not_exists(self):
        query = f"CREATE TABLE IF NOT EXISTS {self._TABLE_NAME} (idx INTEGER UNIQUE, value BLOB)"
        with self.conn:
            self.conn.execute(query)

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
        """
        if not isinstance(other, SQLiteList):
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'"
            )

        result = SQLiteList()

        # Copy all items from self
        for i in range(len(self)):
            result.append(self[i])

        # Copy all items from other
        for i in range(len(other)):
            result.append(other[i])

        return result

    def stream(self):
        """Stream items from the database without loading everything into memory."""
        cursor = self.conn.execute(f"SELECT value FROM {self._TABLE_NAME} ORDER BY idx")
        for row in cursor:
            yield self.deserialize(row[0])

    def __iter__(self):
        """Iterate over items using streaming."""
        return self.stream()

    def equals(self, other):
        """Memory-efficient comparison of two SQLiteLists."""
        if len(self) != len(other):
            return False
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
        
        # Connect to the source database
        source_conn = sqlite3.connect(source_db_path)
        source_cursor = source_conn.cursor()
        
        try:
            # Get all data from the source database, maintaining the index
            source_cursor.execute(f"SELECT idx, value FROM {self._TABLE_NAME} ORDER BY idx")
            rows = source_cursor.fetchall()
            
            # Insert data into this database
            for idx, serialized_value in rows:
                # Deserialize the value from the source database
                deserialized_value = self.deserialize(serialized_value)
                # This database will handle serialization when inserting
                self.insert(idx, deserialized_value)
                
        finally:
            # Clean up
            source_cursor.close()
            source_conn.close()

    def __del__(self):
        """Clean up the temporary file when the object is deleted."""
        try:
            self.conn.close()
            os.unlink(self.db_path)
        except:
            pass


# Example usage
if __name__ == "__main__":
    pass
    # sq_list = SQLiteList()

    # # Insert some values
    # sq_list.insert(0, "apple")
    # sq_list.insert(1, "banana")
    # sq_list.insert(2, "cherry")
    # sq_list.insert(len(sq_list), "date")

    # print("All items:", [sq_list[i] for i in range(len(sq_list))])
    # print("sq_list representation:", sq_list)

    # sq_list.close()
