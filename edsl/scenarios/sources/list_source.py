"""List-based source for ScenarioList creation."""

from __future__ import annotations
from typing import TYPE_CHECKING

from .base import Source
from ..scenario import Scenario

if TYPE_CHECKING:
    pass


class ListSource(Source):
    """Create ScenarioList from a simple list of values."""
    
    source_type = "list"

    def __init__(self, field_name: str, values: list, use_indexes: bool = False):
        self.field_name = field_name
        self.values = values
        self.use_indexes = use_indexes

    @classmethod
    def example(cls) -> "ListSource":
        """Return an example ListSource instance."""
        return cls(
            field_name="text",
            values=["example1", "example2", "example3"],
            use_indexes=True,
        )

    def to_scenario_list(self):
        """Create a ScenarioList from a list of values with a specified field name."""
        from ..scenario_list import ScenarioList

        scenarios = []

        for i, value in enumerate(self.values):
            scenario_dict = {self.field_name: value}
            if self.use_indexes:
                scenario_dict["idx"] = i
            scenarios.append(Scenario(scenario_dict))

        return ScenarioList(scenarios)

