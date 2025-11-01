"""Parquet file source for ScenarioList creation."""

from __future__ import annotations
import os
from typing import TYPE_CHECKING

from .base import Source
from ..scenario import Scenario

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class ParquetSource(Source):
    """Create ScenarioList from Parquet files."""
    
    source_type = "parquet"

    def __init__(self, file_path: str):
        """
        Initialize a ParquetSource with a path to a Parquet file.

        Args:
            file_path: Path to the Parquet file.
        """
        self.file_path = file_path

    @classmethod
    def example(cls) -> "ParquetSource":
        """Return an example ParquetSource instance."""
        import tempfile

        try:
            import pandas as pd

            # Create a temporary Parquet file with sample data
            fd, temp_path = tempfile.mkstemp(suffix=".parquet", prefix="edsl_test_")
            os.close(fd)  # Close the file descriptor

            # Create sample data
            df = pd.DataFrame(
                {
                    "name": ["Alice", "Bob", "Charlie"],
                    "age": [30, 25, 35],
                    "city": ["New York", "San Francisco", "Boston"],
                }
            )

            # Write to Parquet file
            df.to_parquet(temp_path)

            return cls(file_path=temp_path)

        except ImportError:
            # Create a mock instance with an override if pandas or pyarrow is not available
            instance = cls(file_path="/path/to/nonexistent/file.parquet")

            # Override the to_scenario_list method just for the example
            def mock_to_scenario_list(self):
                from ..scenario_list import ScenarioList

                # Create a simple mock ScenarioList with sample data
                scenarios = [
                    Scenario({"name": "Alice", "age": 30, "city": "New York"}),
                    Scenario({"name": "Bob", "age": 25, "city": "San Francisco"}),
                    Scenario({"name": "Charlie", "age": 35, "city": "Boston"}),
                ]
                return ScenarioList(scenarios)

            # Replace the method on this instance only
            import types

            instance.to_scenario_list = types.MethodType(
                mock_to_scenario_list, instance
            )

            return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a Parquet file."""
        from ..scenario_list import ScenarioList

        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Parquet files")

        try:
            import pyarrow  # noqa: F401
        except ImportError:
            raise ImportError("pyarrow is required to read Parquet files")

        # Read the Parquet file
        df = pd.read_parquet(self.file_path)

        # Convert DataFrame to ScenarioList
        scenarios = []
        for _, row in df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)

