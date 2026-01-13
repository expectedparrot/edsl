"""SQLite database source for ScenarioList creation."""

from __future__ import annotations
import os
from typing import Optional, TYPE_CHECKING

from .base import Source
from ...scenario import Scenario

if TYPE_CHECKING:
    pass


class SQLiteSource(Source):
    """Create ScenarioList from a SQLite database table."""

    source_type = "sqlite"

    def __init__(self, db_path: str, table: str, fields: Optional[list] = None):
        self.db_path = db_path
        self.table = table
        self.fields = fields

    @classmethod
    def example(cls) -> "SQLiteSource":
        """Return an example SQLiteSource instance."""
        import sqlite3
        import tempfile

        # Create a temporary SQLite database for the example
        fd, temp_path = tempfile.mkstemp(suffix=".db", prefix="edsl_test_")
        os.close(fd)  # Close the file descriptor

        # Connect to the database and create a sample table
        conn = sqlite3.connect(temp_path)
        cursor = conn.cursor()

        # Create a simple table
        cursor.execute(
            "CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT, value INTEGER)"
        )

        # Insert sample data
        sample_data = [(1, "Alpha", 100), (2, "Beta", 200), (3, "Gamma", 300)]
        cursor.executemany("INSERT INTO test_table VALUES (?, ?, ?)", sample_data)

        conn.commit()
        conn.close()

        return cls(
            db_path=temp_path, table="test_table", fields=["id", "name", "value"]
        )

    def to_scenario_list(self):
        """Create a ScenarioList from a SQLite database."""
        from ...scenario_list import ScenarioList
        import sqlite3

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # If fields weren't provided, get all fields from the table
        fields = self.fields
        if fields is None:
            cursor.execute(f"PRAGMA table_info({self.table})")
            fields = [row[1] for row in cursor.fetchall()]

        # Query the data
        field_placeholders = ", ".join(fields)
        cursor.execute(f"SELECT {field_placeholders} FROM {self.table}")
        rows = cursor.fetchall()

        # Create scenarios
        scenarios = []
        for row in rows:
            scenario_dict = dict(zip(fields, row))
            scenarios.append(Scenario(scenario_dict))

        conn.close()
        return ScenarioList(scenarios)
