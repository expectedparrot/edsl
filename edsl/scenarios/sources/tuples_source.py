"""Tuples-based source for ScenarioList creation."""

from __future__ import annotations
from typing import TYPE_CHECKING

from .base import Source
from ..scenario import Scenario
from ..exceptions import ScenarioError

if TYPE_CHECKING:
    pass


class TuplesSource(Source):
    """Create ScenarioList from a list of tuples with field names."""

    source_type = "list_of_tuples"

    def __init__(
        self, field_names: list[str], values: list[tuple], use_indexes: bool = False
    ):
        self.field_names = field_names
        self.values = values
        self.use_indexes = use_indexes

        # Validate inputs
        if not all(isinstance(v, (tuple, list)) for v in values):
            raise ScenarioError("All values must be tuples or lists")

    @classmethod
    def example(cls) -> "TuplesSource":
        """Return an example TuplesSource instance."""
        return cls(
            field_names=["name", "age", "city"],
            values=[
                ("Alice", 30, "New York"),
                ("Bob", 25, "San Francisco"),
                ("Charlie", 35, "Boston"),
            ],
            use_indexes=True,
        )

    def to_scenario_list(self):
        """Create a ScenarioList from a list of tuples with specified field names."""
        from ..scenario_list import ScenarioList

        scenarios = []

        for i, value_tuple in enumerate(self.values):
            if len(value_tuple) != len(self.field_names):
                raise ScenarioError(
                    f"Tuple {i} has {len(value_tuple)} elements, but {len(self.field_names)} field names were provided."
                )

            scenario_dict = dict(zip(self.field_names, value_tuple))
            if self.use_indexes:
                scenario_dict["idx"] = i
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)
