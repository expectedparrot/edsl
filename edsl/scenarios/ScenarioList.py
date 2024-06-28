"""A list of Scenarios to be used in a survey."""

from __future__ import annotations
import csv
from collections import UserList
from collections.abc import Iterable
from collections import Counter

from typing import Any, Optional, Union, List

from rich.table import Table
from simpleeval import EvalWithCompoundTypes

from edsl.scenarios.Scenario import Scenario
from edsl.Base import Base
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version
from edsl.scenarios.ScenarioListPdfMixin import ScenarioListPdfMixin

from edsl.utilities.interface import print_scenario_list

from edsl.utilities import is_valid_variable_name


class ScenarioList(Base, UserList, ScenarioListPdfMixin):
    """Class for creating a list of scenarios to be used in a survey."""

    def __init__(self, data: Optional[list] = None):
        """Initialize the ScenarioList class."""
        if data is not None:
            super().__init__(data)
        else:
            super().__init__([])

    def __hash__(self) -> int:
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self._to_dict())

    def __repr__(self):
        return f"ScenarioList({self.data})"

    def __mul__(self, other: ScenarioList) -> ScenarioList:
        """Takes the cross product of two ScenarioLists."""
        from itertools import product

        new_sl = []
        for s1, s2 in list(product(self, other)):
            new_sl.append(s1 + s2)
        return ScenarioList(new_sl)

    def times(self, other: ScenarioList) -> ScenarioList:
        """Takes the cross product of two ScenarioLists."""
        return self.__mul__(other)

    def shuffle(self, seed: Optional[str] = "edsl") -> ScenarioList:
        """Shuffle the ScenarioList."""
        import random

        random.seed(seed)
        random.shuffle(self.data)
        return self

    def _repr_html_(self) -> str:
        from edsl.utilities.utilities import data_to_html

        data = self.to_dict()
        _ = data.pop("edsl_version")
        _ = data.pop("edsl_class_name")
        for s in data["scenarios"]:
            _ = s.pop("edsl_version")
            _ = s.pop("edsl_class_name")
        return data_to_html(data)

    def tally(self, field) -> dict:
        """Return a tally of the values in the field.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.tally('b')
        {1: 1, 2: 1}
        """
        return dict(Counter([scenario[field] for scenario in self]))

    def sample(self, n: int, seed="edsl") -> ScenarioList:
        """Return a random sample from the ScenarioList"""
        import random

        if seed != "edsl":
            random.seed(seed)

        return ScenarioList(random.sample(self.data, n))

    def expand(self, expand_field: str) -> ScenarioList:
        """Expand the ScenarioList by a field.

        Example:

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

    def mutate(self, new_var_string: str, functions_dict: dict = None) -> ScenarioList:
        """
        Return a new ScenarioList with a new variable added.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.mutate("c = a + b")
        ScenarioList([Scenario({'a': 1, 'b': 2, 'c': 3}), Scenario({'a': 1, 'b': 1, 'c': 2})])
        """
        if "=" not in new_var_string:
            raise Exception(
                f"Mutate requires an '=' in the string, but '{new_var_string}' doesn't have one."
            )
        raw_var_name, expression = new_var_string.split("=", 1)
        var_name = raw_var_name.strip()
        if not is_valid_variable_name(var_name):
            raise Exception(f"{var_name} is not a valid variable name.")

        # create the evaluator
        functions_dict = functions_dict or {}

        def create_evaluator(scenario) -> EvalWithCompoundTypes:
            return EvalWithCompoundTypes(names=scenario, functions=functions_dict)

        def new_scenario(old_scenario: Scenario, var_name: str) -> Scenario:
            evaluator = create_evaluator(old_scenario)
            value = evaluator.eval(expression)
            new_s = old_scenario.copy()
            new_s[var_name] = value
            return new_s

        try:
            new_data = [new_scenario(s, var_name) for s in self]
        except Exception as e:
            raise Exception(f"Error in mutate. Exception:{e}")

        return ScenarioList(new_data)

    def order_by(self, field: str, reverse: bool = False) -> ScenarioList:
        """Order the scenarios by a field.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.order_by('b')
        ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        """
        return ScenarioList(sorted(self, key=lambda x: x[field], reverse=reverse))

    def filter(self, expression: str) -> ScenarioList:
        """
        Filter a list of scenarios based on an expression.

        Example:

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

    def select(self, *fields) -> ScenarioList:
        """
        Selects scenarios with only the references fields.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.select('a')
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        if len(fields) == 1:
            fields_to_select = [list(fields)[0]]
        else:
            fields_to_select = list(fields)

        return ScenarioList(
            [scenario.select(fields_to_select) for scenario in self.data]
        )

    def drop(self, *fields) -> ScenarioList:
        """Drop fields from the scenarios.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.drop('a')
        ScenarioList([Scenario({'b': 1}), Scenario({'b': 2})])
        """
        return ScenarioList([scenario.drop(fields) for scenario in self.data])

    @classmethod
    def from_list(cls, name, values) -> ScenarioList:
        """Create a ScenarioList from a list of values.

        Example:

        >>> ScenarioList.from_list('name', ['Alice', 'Bob'])
        ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        """
        return cls([Scenario({name: value}) for value in values])

    def add_list(self, name, values) -> ScenarioList:
        """Add a list of values to a ScenarioList.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.add_list('age', [30, 25])
        ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        """
        for i, value in enumerate(values):
            if i < len(self):
                self[i][name] = value
            else:
                self.append(Scenario({name: value}))
        return self

    def add_value(self, name, value):
        """Add a value to all scenarios in a ScenarioList.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.add_value('age', 30)
        ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 30})])
        """
        for scenario in self:
            scenario[name] = value
        return self

    def rename(self, replacement_dict: dict) -> ScenarioList:
        new_list = ScenarioList([])
        for obj in self:
            new_obj = obj.rename(replacement_dict)
            new_list.append(new_obj)
        return new_list

    @classmethod
    def from_sqlite(cls, filepath: str, table: str):
        import sqlite3

        with sqlite3.connect(filepath) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table}")
            columns = [description[0] for description in cursor.description]
            data = cursor.fetchall()
        return cls([Scenario(dict(zip(columns, row))) for row in data])

    @classmethod
    def from_pandas(cls, df) -> ScenarioList:
        """Create a ScenarioList from a pandas DataFrame.

        Example:

        >>> import pandas as pd
        >>> df = pd.DataFrame({'name': ['Alice', 'Bob'], 'age': [30, 25], 'location': ['New York', 'Los Angeles']})
        >>> ScenarioList.from_pandas(df)
        ScenarioList([Scenario({'name': 'Alice', 'age': 30, 'location': 'New York'}), Scenario({'name': 'Bob', 'age': 25, 'location': 'Los Angeles'})])
        """
        return cls([Scenario(row) for row in df.to_dict(orient="records")])

    @classmethod
    def from_csv(cls, filename: str) -> ScenarioList:
        """Create a ScenarioList from a CSV file.

        Example:

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

    def _to_dict(self) -> dict:
        return {"scenarios": [s._to_dict() for s in self]}

    @add_edsl_version
    def to_dict(self) -> dict[str, Any]:
        """Return the `ScenarioList` as a dictionary.

        Example:

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

    def print(
        self,
        format: Optional[str] = None,
        max_rows: Optional[int] = None,
        pretty_labels: Optional[dict] = None,
        filename: str = None,
    ):
        print_scenario_list(self)
        # if format is None:
        #     if is_notebook():
        #         format = "html"
        #     else:
        #         format = "rich"

        # if pretty_labels is None:
        #     pretty_labels = {}

        # if format not in ["rich", "html", "markdown"]:
        #     raise ValueError("format must be one of 'rich', 'html', or 'markdown'.")

        # if max_rows is not None:
        #     new_data = self[:max_rows]
        # else:
        #     new_data = self

        # if format == "rich":
        #     print_list_of_dicts_with_rich(
        #         new_data, filename=filename, split_at_dot=False
        #     )
        # elif format == "html":
        #     notebook = is_notebook()
        #     html = print_list_of_dicts_as_html_table(
        #         new_data, filename=None, interactive=False, notebook=notebook
        #     )
        #     # print(html)
        #     display(HTML(html))
        # elif format == "markdown":
        #     print_list_of_dicts_as_markdown_table(new_data, filename=filename)

    def __getitem__(self, key: Union[int, slice]) -> Any:
        """Return the item at the given index."""
        if isinstance(key, slice):
            return ScenarioList(super().__getitem__(key))
        elif isinstance(key, int):
            return super().__getitem__(key)
        else:
            return self.to_dict()[key]

    def to_agent_list(self):
        """Convert the ScenarioList to an AgentList.

        Example:

        >>> s = ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5}), Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> s.to_agent_list()
        AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        """
        from edsl.agents.AgentList import AgentList
        from edsl.agents.Agent import Agent

        return AgentList([Agent(traits=s.data) for s in self])

    def chunk(
        self,
        field,
        num_words: Optional[int] = None,
        num_lines: Optional[int] = None,
        include_original=False,
        hash_original=False,
    ) -> "ScenarioList":
        """Chunk the scenarios based on a field.

        Example:

        >>> s = ScenarioList([Scenario({'text': 'The quick brown fox jumps over the lazy dog.'})])
        >>> s.chunk('text', num_words=3)
        ScenarioList([Scenario({'text': 'The quick brown', 'text_chunk': 0}), Scenario({'text': 'fox jumps over', 'text_chunk': 1}), Scenario({'text': 'the lazy dog.', 'text_chunk': 2})])
        """
        new_scenarios = []
        for scenario in self:
            replacement_scenarios = scenario.chunk(
                field,
                num_words=num_words,
                num_lines=num_lines,
                include_original=include_original,
                hash_original=hash_original,
            )
            new_scenarios.extend(replacement_scenarios)
        return ScenarioList(new_scenarios)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
