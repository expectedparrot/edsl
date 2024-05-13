"""A list of Scenarios to be used in a survey."""
from __future__ import annotations
import csv
from collections import UserList
from collections.abc import Iterable

from typing import Any, Optional, Union, List

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

    def _repr_html_(self) -> str:
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    def expand(self, expand_field: str) -> ScenarioList:
        """Expand the ScenarioList by a field.

        Example usage:

        >>> s = ScenarioList( [ Scenario({'a':1, 'b':[1,2]}) ] )
        >>> s.expand('b')
        ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])

        """

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

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.filter("b == 2")
        ScenarioList([Scenario({'a': 1, 'b': 2})])
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
    def from_csv(cls, filename: str) -> ScenarioList:
        """Create a ScenarioList from a CSV file.

        >>> import tempfile
        >>> import os
        >>> with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='.csv') as f:
        ...     _ = f.write("name,age,location\\nAlice,30,New York\\nBob,25,Los Angeles\\n")
        ...     temp_filename = f.name
        >>> scenario_list = ScenarioList.from_csv(temp_filename)
        >>> len(scenario_list)
        2
        >>> scenario_list[0]['name']
        'Alice'
        >>> scenario_list[1]['age']
        '25'
        """

        observations = []
        with open(filename, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                observations.append(Scenario(dict(zip(header, row))))
        return cls(observations)

    @add_edsl_version
    def to_dict(self) -> dict[str, Any]:
        """Return the `ScenarioList` as a dictionary.

        >>> s = ScenarioList([Scenario({'food': 'wood chips'}), Scenario({'food': 'wood-fired pizza'})])
        >>> s.to_dict()
        {'scenarios': [{'food': 'wood chips', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}, {'food': 'wood-fired pizza', 'edsl_version': '...', 'edsl_class_name': 'Scenario'}], 'edsl_version': '...', 'edsl_class_name': 'ScenarioList'}
        """
        return {"scenarios": [s.to_dict() for s in self]}

    @classmethod
    def gen(cls, scenario_dicts_list: List[dict]) -> ScenarioList:
        """Create a `ScenarioList` from a list of dictionaries."""
        return cls([Scenario(s) for s in scenario_dicts_list])

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data) -> ScenarioList:
        """Create a `ScenarioList` from a dictionary."""
        return cls([Scenario.from_dict(s) for s in data["scenarios"]])

    def code(self) -> str:
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
    def example(cls) -> ScenarioList:
        """Return an example of the `ScenarioList`."""
        return cls([Scenario.example(), Scenario.example()])

    def rich_print(self) -> None:
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
    # from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice
    # from edsl.scenarios.Scenario import Scenario

    # q = QuestionMultipleChoice(
    #     question_text="Do you enjoy the taste of {{food}}?",
    #     question_options=["Yes", "No"],
    #     question_name="food_preference",
    # )

    # scenario_list = ScenarioList(
    #     [Scenario({"food": "wood chips"}), Scenario({"food": "wood-fired pizza"})]
    # )

    # print(scenario_list.code())

    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
