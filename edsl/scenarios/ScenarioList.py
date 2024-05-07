"""A list of Scenarios to be used in a survey."""
from __future__ import annotations
from collections import UserList
from typing import Any, Optional, Union

from rich.table import Table
from simpleeval import EvalWithCompoundTypes

from edsl.scenarios.Scenario import Scenario
from edsl.Base import Base

from edsl.utilities.decorators import add_edsl_version, remove_edsl_version

class ScenarioList(Base, UserList):
    """Class for creating a list of scenarios to be used in a survey."""

    def __init__(self, data: Optional[list] = None):
        """Initialize the ScenarioList class."""
        if data is not None:
            super().__init__(data)

    def __repr__(self):
        return f"ScenarioList({self.data})"

    def expand(self, expand_field) -> ScenarioList:
        """Expand the ScenarioList by a field."""
        from collections.abc import Iterable

        new_scenarios = []
        for scenario in self:
            values = scenario[expand_field]
            if not isinstance(values, Iterable) or isinstance(values, str):
                values = [values]
            for value in values:
                new_scenario = scenario.copy()
                new_scenario[expand_field] = value
                new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    def filter(self, expression: str) -> ScenarioList:
        """
        Filter a list of scenarios based on an expression.
        """

        def create_evaluator(scenario: Scenario):
            """Create an evaluator for the given result.
            The 'combined_dict' is a mapping of all values for that Result object.
            """
            return EvalWithCompoundTypes(names=scenario)

        try:
            # iterates through all the results and evaluates the expression
            new_data = [
                scenario
                for scenario in self.data
                if create_evaluator(scenario).eval(expression)
            ]
        except Exception as e:
            print(f"Exception:{e}")
            raise Exception(f"Error in filter. Exception:{e}")

        return ScenarioList(new_data)

    @classmethod
    def from_csv(cls, filename):
        """Create a ScenarioList from a CSV file."""
        import csv

        observations = []
        with open(filename, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                observations.append(Scenario(dict(zip(header, row))))
        return cls(observations)

    @add_edsl_version
    def to_dict(self):
        """Return the `ScenarioList` as a dictionary."""
        return {"scenarios": [s.to_dict() for s in self]}

    @classmethod
    def gen(cls, scenario_dicts_list):
        """Create a `ScenarioList` from a list of dictionaries."""
        return cls([Scenario(s) for s in scenario_dicts_list])

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data):
        """Create a `ScenarioList` from a dictionary."""
        return cls([Scenario.from_dict(s) for s in data["scenarios"]])

    def code(self):
        ## TODO: Refactor to only use the questions actually in the survey
        """Create the Python code representation of a survey."""
        header_lines = [
            "from edsl.scenarios.Scenario import Scenario",
            "from edsl.scenarios.ScenarioList import ScenarioList",
        ]
        lines = ["\n".join(header_lines)]
        names = []
        for index, scenario in enumerate(self):
            lines.append(f"scenario_{index} = " + repr(scenario))
            names.append(f"scenario_{index}")
        lines.append(f"scenarios = ScenarioList([{', '.join(names)}])")
        return lines

    @classmethod
    def example(cls):
        """Return an example of the `ScenarioList`."""
        return cls([Scenario.example(), Scenario.example()])

    def rich_print(self):
        """Display an object as a table."""
        table = Table(title="ScenarioList")
        table.add_column("Index", style="bold")
        table.add_column("Scenario")
        for i, s in enumerate(self):
            table.add_row(str(i), s.rich_print())
        return table

    def __getitem__(self, key: Union[int, slice]) -> Any:
        """Return the item at the given index."""
        if isinstance(key, slice):
            return ScenarioList(super().__getitem__(key))
        elif isinstance(key, int):
            return super().__getitem__(key)
        else:
            return self.to_dict()[key]


if __name__ == "__main__":
    from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
    from edsl.scenarios.Scenario import Scenario

    q = QuestionMultipleChoice(
        question_text="Do you enjoy the taste of {{food}}?",
        question_options=["Yes", "No"],
        question_name="food_preference",
    )

    scenario_list = ScenarioList(
        [Scenario({"food": "wood chips"}), Scenario({"food": "wood-fired pizza"})]
    )

    print(scenario_list.code())

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
