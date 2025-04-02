import sqlite3
import tempfile
import os
import json
from collections.abc import MutableSequence

from ..results.result import Result


class SQLiteList(MutableSequence):
    """
    A MutableSequence that stores its data in a temporary SQLite file.
    The file is removed when close() is called.
    """

    _TABLE_NAME = "list_data"  # Class constant instead of instance parameter

    def __init__(
        self,
        data=None,
        serialize=lambda obj: (
            json.dumps(obj.to_dict()) if hasattr(obj, "to_dict") else json.dumps(obj)
        ),
        deserialize=lambda data: (
            Result.from_dict(json.loads(data))
            if hasattr(Result, "from_dict")
            else json.loads(data)
        ),
    ):
        self.serialize = serialize
        self.deserialize = deserialize

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

        result = SQLiteList(serialize=self.serialize, deserialize=self.deserialize)

        # Copy all items from self
        for i in range(len(self)):
            result.append(self[i])

        # Copy all items from other
        for i in range(len(other)):
            result.append(other[i])

        return result


# Example usage
if __name__ == "__main__":
    sq_list = SQLiteList()

    # Insert some values
    sq_list.insert(0, "apple")
    sq_list.insert(1, "banana")
    sq_list.insert(2, "cherry")
    sq_list.insert(len(sq_list), "date")

    print("All items:", [sq_list[i] for i in range(len(sq_list))])
    print("sq_list representation:", sq_list)

    sq_list.close()
