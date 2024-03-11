"""Class for storing and retrieving data from a SQLite database."""
from edsl import Config
import sqlite3
from collections import UserList
from edsl.Base import Base
from rich.table import Table

config = Config()

path = config.get("EDSL_DATABASE_PATH")


class Cache(Base, UserList):
    """Class for storing and retrieving data from a SQLite database."""

    def __init__(self, data=None, schema=None):
        """Initialize the Cache object."""
        self.db_path = config.get("EDSL_DATABASE_PATH")[len("sqlite:///") :]
        self.table_name = "responses"

        if data is None or schema is None:
            result = self.load_data()
            self.data = result["data"]
            self.schema = result["schema"]
        else:
            self.data = data
            self.schema = schema

    def _connect(self, db_path=None):
        """Connect to the SQLite database."""
        return sqlite3.connect(db_path if db_path else self.db_path)

    def load_data(self):
        """Load data from the SQLite database."""
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(f"PRAGMA table_info({self.table_name})")
            schema = cur.fetchall()
            cur.execute(f"SELECT * FROM {self.table_name}")
            return {
                "data": [
                    dict(zip([col[1] for col in schema], row)) for row in cur.fetchall()
                ],
                "schema": schema,
            }

    def save_data_to_new_db(self, new_db_path):
        """Save data to a new SQLite database."""
        with self._connect(new_db_path) as new_conn:
            new_cur = new_conn.cursor()
            # Create table in new database
            columns = ", ".join([f"{col[1]} {col[2]}" for col in self.schema])
            new_cur.execute(f"CREATE TABLE IF NOT EXISTS {self.table_name} ({columns})")

            # Insert data into new table
            placeholders = ", ".join(["?"] * len(self.schema))
            new_cur.executemany(
                f"INSERT INTO {self.table_name} ({', '.join([col[1] for col in self.schema])}) VALUES ({placeholders})",
                [tuple(row[col[1]] for col in self.schema) for row in self.data],
            )
            new_conn.commit()

    def _table_row(self, row):
        """Create a table row from a dictionary."""
        table = Table()
        table.add_column("Key")
        table.add_column("Value")
        for key, value in row.items():
            table.add_row(str(key), str(value))
        return table

    def rich_print(self):
        """Print the cache as a rich table."""
        table = Table(title="Cache")
        table.add_column("Entry", style="bold")
        for index, row in enumerate(self.data):
            table.add_row(self._table_row(row))
        return table

    @classmethod
    def example(cls):
        """Return an example Cache object."""
        data0 = """{'id': 1, 'model': 'gpt-3.5-turbo'}"""
        schema = [
            (0, "id", "INTEGER", 1, None, 1),
            (1, "model", "VARCHAR(100)", 1, None, 0),
            (2, "parameters", "TEXT", 1, None, 0),
            (3, "system_prompt", "TEXT", 1, None, 0),
            (4, "prompt", "TEXT", 1, None, 0),
            (5, "output", "TEXT", 1, None, 0),
        ]
        return cls(data=[eval(data0)], schema=schema)

    def __repr__(self):
        """Return a string representation of the Cache object."""
        return f"Cache(data={self.data}, schema={self.schema})"

    def code():
        """Return the code for the Cache class."""
        pass

    def add_row(self, row_data):
        """Add a row to the cache."""
        if set(row_data.keys()) != set([col[1] for col in self.schema]):
            raise ValueError("Row keys do not match table schema")
        self.data.append(row_data)

    def to_dict(self):
        """Return the cache as a dictionary."""
        return {"schema": self.schema, "data": self.data}

    @classmethod
    def from_dict(cls, data):
        """Create a Cache object from a dictionary."""
        raw_schema = data["schema"]
        schema = [tuple(col) for col in raw_schema]  # Convert to tuples
        cache = cls(data=data["data"], schema=schema)
        return cache


if __name__ == "__main__":
    cache = Cache()
    cache.print()
    # cache.load_data()
