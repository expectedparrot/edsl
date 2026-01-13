"""Stata (.dta) file source for ScenarioList creation."""

from __future__ import annotations
from typing import TYPE_CHECKING

from .base import Source
from ...scenario import Scenario

if TYPE_CHECKING:
    pass


class StataSource(Source):
    """Create ScenarioList from Stata (.dta) files with optional metadata."""

    source_type = "dta"

    def __init__(self, file_path: str, include_metadata: bool = True):
        """
        Initialize a StataSource with a path to a Stata data file.

        Args:
            file_path: Path to the Stata (.dta) file.
            include_metadata: If True, extract and preserve variable labels and value labels
                            as additional metadata in the ScenarioList.
        """
        self.file_path = file_path
        self.include_metadata = include_metadata

    @classmethod
    def example(cls) -> "StataSource":
        """Return an example StataSource instance."""

        # Since we can't easily create a real Stata file for testing,
        # we'll create a mock instance with an override
        instance = cls(file_path="/path/to/nonexistent/file.dta")

        # Override the to_scenario_list method just for the example
        def mock_to_scenario_list(self):
            from ...scenario_list import ScenarioList

            # Create a simple mock ScenarioList with Stata-like data
            scenarios = [
                Scenario({"id": 1, "gender": 1, "income": 50000, "education": 2}),
                Scenario({"id": 2, "gender": 2, "income": 45000, "education": 3}),
                Scenario({"id": 3, "gender": 1, "income": 60000, "education": 4}),
            ]

            result = ScenarioList(scenarios)

            # Add metadata similar to what would be in a Stata file
            if self.include_metadata:
                result.codebook = {
                    "variable_labels": {
                        "gender": "Gender (1=Male, 2=Female)",
                        "income": "Annual income in USD",
                        "education": "Education level (1-4)",
                    },
                    "value_labels": {
                        "gender": {1: "Male", 2: "Female"},
                        "education": {
                            1: "High School",
                            2: "Associate",
                            3: "Bachelor",
                            4: "Graduate",
                        },
                    },
                }

            return result

        # Replace the method on this instance only
        import types

        instance.to_scenario_list = types.MethodType(mock_to_scenario_list, instance)

        return instance

    def to_scenario_list(self):
        """Create a ScenarioList from a Stata data file."""
        from ...scenario_list import ScenarioList

        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to read Stata files")

        # Read the Stata file with pandas
        df = pd.read_stata(self.file_path)

        # Create scenarios
        scenarios = []
        for _, row in df.iterrows():
            scenario_dict = row.to_dict()
            scenarios.append(Scenario(scenario_dict))

        # Create the basic ScenarioList
        result = ScenarioList(scenarios)

        # Extract and preserve metadata if requested
        if self.include_metadata:
            # Get variable labels (if any)
            variable_labels = {}
            if hasattr(df, "variable_labels") and df.variable_labels:
                variable_labels = df.variable_labels

            # Get value labels (if any)
            value_labels = {}
            if hasattr(df, "value_labels") and df.value_labels:
                value_labels = df.value_labels

            # Store the metadata in the ScenarioList's codebook
            if variable_labels or value_labels:
                result.codebook = {
                    "variable_labels": variable_labels,
                    "value_labels": value_labels,
                }

        return result
