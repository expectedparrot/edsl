"""Pandas DataFrame source for ScenarioList creation."""

from __future__ import annotations
from typing import TYPE_CHECKING

from .base import Source
from ...scenario import Scenario
from ...exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class PandasSource(Source):
    """Create ScenarioList from a pandas DataFrame."""

    source_type = "pandas"

    def __init__(self, df):
        """
        Initialize a PandasSource with a pandas DataFrame.

        Args:
            df: A pandas DataFrame.
        """
        try:
            import pandas as pd

            if not isinstance(df, pd.DataFrame):
                raise ScenarioError("Input must be a pandas DataFrame")
            self.df = df
        except ImportError:
            raise ImportError("pandas is required for PandasSource")

    @classmethod
    def example(cls) -> "PandasSource":
        """Return an example PandasSource instance."""
        try:
            import pandas as pd

            # Create a sample DataFrame for the example
            sample_data = {
                "name": ["Alice", "Bob", "Charlie", "David"],
                "age": [30, 25, 35, 28],
                "city": ["New York", "San Francisco", "Boston", "Seattle"],
            }
            df = pd.DataFrame(sample_data)

            return cls(df)
        except ImportError:
            # Create a mock instance that doesn't actually need pandas
            instance = cls.__new__(cls)

            # Override the to_scenario_list method just for the example
            def mock_to_scenario_list(self):
                from ...scenario_list import ScenarioList

                # Create a simple mock ScenarioList
                scenarios = [
                    Scenario({"name": "Alice", "age": 30, "city": "New York"}),
                    Scenario({"name": "Bob", "age": 25, "city": "San Francisco"}),
                    Scenario({"name": "Charlie", "age": 35, "city": "Boston"}),
                    Scenario({"name": "David", "age": 28, "city": "Seattle"}),
                ]
                return ScenarioList(scenarios)

            # Replace the method on this instance only
            import types

            instance.to_scenario_list = types.MethodType(
                mock_to_scenario_list, instance
            )

            return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a pandas DataFrame."""
        from ...scenario_list import ScenarioList

        # Convert DataFrame records to scenarios
        scenarios = []
        for _, row in self.df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)
