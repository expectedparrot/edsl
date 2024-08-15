"""A list of Scenarios to be used in a survey."""

from __future__ import annotations
from typing import Any, Optional, Union, List, Callable
import csv
import random
from collections import UserList, Counter
from collections.abc import Iterable

from simpleeval import EvalWithCompoundTypes

from edsl.Base import Base
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version
from edsl.scenarios.Scenario import Scenario
from edsl.scenarios.ScenarioListPdfMixin import ScenarioListPdfMixin
from edsl.scenarios.ScenarioListExportMixin import ScenarioListExportMixin


class ScenarioListMixin(ScenarioListPdfMixin, ScenarioListExportMixin):
    pass


class ScenarioList(Base, UserList, ScenarioListMixin):
    """Class for creating a list of scenarios to be used in a survey."""

    def __init__(self, data: Optional[list] = None):
        """Initialize the ScenarioList class."""
        if data is not None:
            super().__init__(data)
        else:
            super().__init__([])

    @property
    def parameters(self) -> set:
        """Return the set of parameters in the ScenarioList

        Example:

        >>> s = ScenarioList([Scenario({'a': 1}), Scenario({'b': 2})])
        >>> s.parameters == {'a', 'b'}
        True
        """
        if len(self) == 0:
            return set()

        return set.union(*[set(s.keys()) for s in self])

    def __hash__(self) -> int:
        """Return the hash of the ScenarioList.

        >>> s = ScenarioList.example()
        >>> hash(s)
        1262252885757976162
        """
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self._to_dict(sort=True))

    def __repr__(self):
        return f"ScenarioList({self.data})"

    def __mul__(self, other: ScenarioList) -> ScenarioList:
        """Takes the cross product of two ScenarioLists.

        >>> s1 = ScenarioList.from_list("a", [1, 2])
        >>> s2 = ScenarioList.from_list("b", [3, 4])
        >>> s1 * s2
        ScenarioList([Scenario({'a': 1, 'b': 3}), Scenario({'a': 1, 'b': 4}), Scenario({'a': 2, 'b': 3}), Scenario({'a': 2, 'b': 4})])
        """
        from itertools import product

        new_sl = []
        for s1, s2 in list(product(self, other)):
            new_sl.append(s1 + s2)
        return ScenarioList(new_sl)

    def times(self, other: ScenarioList) -> ScenarioList:
        """Takes the cross product of two ScenarioLists.

        Example:

        >>> s1 = ScenarioList([Scenario({'a': 1}), Scenario({'a': 2})])
        >>> s2 = ScenarioList([Scenario({'b': 1}), Scenario({'b': 2})])
        >>> s1.times(s2)
        ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2}), Scenario({'a': 2, 'b': 1}), Scenario({'a': 2, 'b': 2})])
        """
        return self.__mul__(other)

    def shuffle(self, seed: Optional[str] = "edsl") -> ScenarioList:
        """Shuffle the ScenarioList.

        >>> s = ScenarioList.from_list("a", [1,2,3,4])
        >>> s.shuffle()
        ScenarioList([Scenario({'a': 3}), Scenario({'a': 4}), Scenario({'a': 1}), Scenario({'a': 2})])
        """
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
        """Return a random sample from the ScenarioList

        >>> s = ScenarioList.from_list("a", [1,2,3,4,5,6])
        >>> s.sample(3)
        ScenarioList([Scenario({'a': 2}), Scenario({'a': 1}), Scenario({'a': 3})])
        """

        random.seed(seed)

        return ScenarioList(random.sample(self.data, n))

    def expand(self, expand_field: str, number_field=False) -> ScenarioList:
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
            for index, value in enumerate(values):
                new_scenario = scenario.copy()
                new_scenario[expand_field] = value
                if number_field:
                    new_scenario[expand_field + "_number"] = index + 1
                new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict[str, Callable]] = None
    ) -> ScenarioList:
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
        from edsl.utilities.utilities import is_valid_variable_name

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

    def order_by(self, *fields: str, reverse: bool = False) -> ScenarioList:
        """Order the scenarios by one or more fields.

        Example:

        >>> s = ScenarioList([Scenario({'a': 1, 'b': 2}), Scenario({'a': 1, 'b': 1})])
        >>> s.order_by('b', 'a')
        ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        """

        def get_sort_key(scenario: Any) -> tuple:
            return tuple(scenario[field] for field in fields)

        return ScenarioList(sorted(self, key=get_sort_key, reverse=reverse))

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

    def from_urls(
        self, urls: list[str], field_name: Optional[str] = "text"
    ) -> ScenarioList:
        """Create a ScenarioList from a list of URLs.

        :param urls: A list of URLs.
        :param field_name: The name of the field to store the text from the URLs.


        """
        return ScenarioList([Scenario.from_url(url, field_name) for url in urls])

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

    def to_dataset(self) -> "Dataset":
        """
        >>> s = ScenarioList.from_list("a", [1,2,3])
        >>> s.to_dataset()
        Dataset([{'a': [1, 2, 3]}])
        >>> s = ScenarioList.from_list("a", [1,2,3]).add_list("b", [4,5,6])
        >>> s.to_dataset()
        Dataset([{'a': [1, 2, 3]}, {'b': [4, 5, 6]}])
        """
        from edsl.results.Dataset import Dataset

        keys = self[0].keys()
        data = [{key: [scenario[key] for scenario in self.data]} for key in keys]
        return Dataset(data)

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

    def add_value(self, name: str, value: Any) -> ScenarioList:
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
        """Rename the fields in the scenarios.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s.rename({'name': 'first_name', 'age': 'years'})
        ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])

        """

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

    def to_key_value(self, field: str, value=None) -> Union[dict, set]:
        """Return the set of values in the field.

        Example:

        >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
        >>> s.to_key_value('name') == {'Alice', 'Bob'}
        True
        """
        if value is None:
            return {scenario[field] for scenario in self}
        else:
            return {scenario[field]: scenario[value] for scenario in self}

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
        from edsl.scenarios.Scenario import Scenario

        observations = []
        with open(filename, "r") as f:
            reader = csv.reader(f)
            header = next(reader)
            for row in reader:
                observations.append(Scenario(dict(zip(header, row))))
        return cls(observations)

    def _to_dict(self, sort=False) -> dict:
        if sort:
            data = sorted(self, key=lambda x: hash(x))
        else:
            data = self
        return {"scenarios": [s._to_dict() for s in data]}

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
        """Create a `ScenarioList` from a list of dictionaries.

        Example:

        >>> ScenarioList.gen([{'name': 'Alice'}, {'name': 'Bob'}])
        ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])

        """
        from edsl.scenarios.Scenario import Scenario

        return cls([Scenario(s) for s in scenario_dicts_list])

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data) -> ScenarioList:
        """Create a `ScenarioList` from a dictionary."""
        from edsl.scenarios.Scenario import Scenario

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
    def example(cls, randomize: bool = False) -> ScenarioList:
        """
        Return an example ScenarioList instance.

        :params randomize: If True, use Scenario's randomize method to randomize the values.
        """
        return cls([Scenario.example(randomize), Scenario.example(randomize)])

    def rich_print(self) -> None:
        """Display an object as a table."""
        from rich.table import Table

        table = Table(title="ScenarioList")
        table.add_column("Index", style="bold")
        table.add_column("Scenario")
        for i, s in enumerate(self):
            table.add_row(str(i), s.rich_print())
        return table

    # def print(
    #     self,
    #     format: Optional[str] = None,
    #     max_rows: Optional[int] = None,
    #     pretty_labels: Optional[dict] = None,
    #     filename: str = None,
    # ):
    #     from edsl.utilities.interface import print_scenario_list

    #     print_scenario_list(self[:max_rows])

    def __getitem__(self, key: Union[int, slice]) -> Any:
        """Return the item at the given index.

        Example:
        >>> s = ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5}), Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> s[0]
        Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})

        >>> s[:1]
        ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])

        """
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
