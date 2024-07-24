"""A list of Agent objects.

Example usage:

.. code-block:: python

    al = AgentList([Agent.example(), Agent.example()])
    len(al)
    2
    
"""

from __future__ import annotations
import csv
import json
from collections import UserList
from typing import Any, List, Optional, Union
from rich import print_json
from rich.table import Table
from simpleeval import EvalWithCompoundTypes
from edsl.Base import Base
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version


class AgentList(UserList, Base):
    """A list of Agents."""

    def __init__(self, data: Optional[list["Agent"]] = None):
        """Initialize a new AgentList.

        :param data: A list of Agents.
        """
        if data is not None:
            super().__init__(data)
        else:
            super().__init__()

    def shuffle(self, seed: Optional[str] = "edsl") -> AgentList:
        """Shuffle the AgentList.

        :param seed: The seed for the random number generator.
        """
        import random

        random.seed(seed)
        random.shuffle(self.data)
        return self

    def sample(self, n: int, seed="edsl") -> AgentList:
        """Return a random sample of agents.

        :param n: The number of agents to sample.
        :param seed: The seed for the random number generator.
        """
        import random

        random.seed(seed)
        return AgentList(random.sample(self.data, n))

    def rename(self, old_name, new_name):
        """Rename a trait in the AgentList.

        :param old_name: The old name of the trait.
        :param new_name: The new name of the trait.
        """
        for agent in self.data:
            agent.rename(old_name, new_name)
        return self

    def select(self, *traits) -> AgentList:
        """Selects agents with only the references traits.

        >>> from edsl.agents.Agent import Agent
        >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}), Agent(traits = {'a': 1, 'b': 2})])
        >>> al.select('a')
        AgentList([Agent(traits = {'a': 1}), Agent(traits = {'a': 1})])

        """

        if len(traits) == 1:
            traits_to_select = [list(traits)[0]]
        else:
            traits_to_select = list(traits)

        return AgentList([agent.select(*traits_to_select) for agent in self.data])

    def filter(self, expression: str) -> AgentList:
        """
        Filter a list of agents based on an expression.

        >>> from edsl.agents.Agent import Agent
        >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}), Agent(traits = {'a': 1, 'b': 2})])
        >>> al.filter("b == 2")
        AgentList([Agent(traits = {'a': 1, 'b': 2})])
        """

        def create_evaluator(agent: "Agent"):
            """Create an evaluator for the given result.
            The 'combined_dict' is a mapping of all values for that Result object.
            """
            return EvalWithCompoundTypes(names=agent.traits)

        try:
            # iterates through all the results and evaluates the expression
            new_data = [
                agent for agent in self.data if create_evaluator(agent).eval(expression)
            ]
        except Exception as e:
            print(f"Exception:{e}")
            raise Exception(f"Error in filter. Exception:{e}")

        return AgentList(new_data)

    @classmethod
    def from_csv(cls, file_path: str):
        """Load AgentList from a CSV file.

        >>> import csv
        >>> import os
        >>> with open('/tmp/agents.csv', 'w') as f:
        ...     writer = csv.writer(f)
        ...     _ = writer.writerow(['age', 'hair', 'height'])
        ...     _ = writer.writerow([22, 'brown', 5.5])
        >>> al = AgentList.from_csv('/tmp/agents.csv')
        >>> al
        AgentList([Agent(traits = {'age': '22', 'hair': 'brown', 'height': '5.5'})])
        >>> os.remove('/tmp/agents.csv')

        :param file_path: The path to the CSV file.
        """
        from edsl.agents.Agent import Agent

        agent_list = []
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                agent_list.append(Agent(row))
        return cls(agent_list)

    def translate_traits(self, values_codebook: dict[str, str]):
        """Translate traits to a new codebook.

        :param codebook: The new codebook.
        """
        for agent in self.data:
            agent.translate_traits(codebook)
        return self

    def remove_trait(self, trait: str):
        """Remove traits from the AgentList.

        :param traits: The traits to remove.
        >>> from edsl.agents.Agent import Agent
        >>> al = AgentList([Agent({'age': 22, 'hair': 'brown', 'height': 5.5}), Agent({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al.remove_trait('age')
        AgentList([Agent(traits = {'hair': 'brown', 'height': 5.5}), Agent(traits = {'hair': 'brown', 'height': 5.5})])
        """
        for agent in self.data:
            _ = agent.remove_trait(trait)
        return self

    @staticmethod
    def get_codebook(file_path: str):
        """Return the codebook for a CSV file.

        :param file_path: The path to the CSV file.
        """
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            return {field: None for field in reader.fieldnames}

    def __hash__(self) -> int:
        from edsl.utilities.utilities import dict_hash

        data = self.to_dict()
        # data['agent_list'] = sorted(data['agent_list'], key=lambda x: dict_hash(x)
        return dict_hash(self._to_dict(sorted=True))

    def _to_dict(self, sorted=False):
        if sorted:
            data = self.data[:]
            data.sort(key=lambda x: hash(x))
        else:
            data = self.data

        return {"agent_list": [agent.to_dict() for agent in data]}

    def __eq__(self, other: AgentList) -> bool:
        return self._to_dict(sorted=True) == other._to_dict(sorted=True)

    @add_edsl_version
    def to_dict(self):
        """Return dictionary of AgentList to serialization."""
        return self._to_dict()

    def __repr__(self):
        return f"AgentList({self.data})"

    def print(self, format: Optional[str] = None):
        """Print the AgentList."""
        print_json(json.dumps(self._to_dict()))

    def _repr_html_(self):
        """Return an HTML representation of the AgentList."""
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict()["agent_list"])

    def to_scenario_list(self) -> "ScenarioList":
        """Return a list of scenarios."""
        from edsl.scenarios.ScenarioList import ScenarioList
        from edsl.scenarios.Scenario import Scenario

        return ScenarioList([Scenario(agent.traits) for agent in self.data])

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> "AgentList":
        """Deserialize the dictionary back to an AgentList object.

        :param: data: A dictionary representing an AgentList.
        >>> from edsl.agents.Agent import Agent
        >>> al = AgentList([Agent.example(), Agent.example()])
        >>> al2 = AgentList.from_dict(al.to_dict())
        >>> al2 == al
        True
        """
        from edsl.agents.Agent import Agent

        agents = [Agent.from_dict(agent_dict) for agent_dict in data["agent_list"]]
        return cls(agents)

    @classmethod
    def example(cls, randomize: bool = False) -> AgentList:
        """
        Returns an example AgentList instance.

        :param randomize: If True, uses Agent's randomize method.
        """
        from edsl.agents.Agent import Agent

        return cls([Agent.example(randomize), Agent.example(randomize)])

    @classmethod
    def from_list(self, trait_name: str, values: List[Any]):
        """Create an AgentList from a list of values.

        :param trait_name: The name of the trait.
        :param values: A list of values.
        """
        from edsl.agents.Agent import Agent

        return AgentList([Agent({trait_name: value}) for value in values])

    def __mul__(self, other: AgentList) -> AgentList:
        """Takes the cross product of two AgentLists."""
        from itertools import product

        new_sl = []
        for s1, s2 in list(product(self, other)):
            new_sl.append(s1 + s2)
        return AgentList(new_sl)

    def code(self, string=True) -> Union[str, list[str]]:
        """Return code to construct an AgentList.

        >>> al = AgentList.example()
        >>> print(al.code())
        from edsl.agents.Agent import Agent
        from edsl.agents.AgentList import AgentList
        agent_list = AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        """
        lines = [
            "from edsl.agents.Agent import Agent",
            "from edsl.agents.AgentList import AgentList",
        ]
        lines.append(f"agent_list = AgentList({self.data})")
        if string:
            return "\n".join(lines)
        return lines

    def rich_print(self) -> Table:
        """Display an object as a rich table."""
        table = Table(title="AgentList")
        table.add_column("Agents", style="bold")
        for agent in self.data:
            table.add_row(agent.rich_print())
        return table


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
