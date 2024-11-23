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
from typing import Any, List, Optional, Union, TYPE_CHECKING
from rich import print_json
from rich.table import Table
from simpleeval import EvalWithCompoundTypes
from edsl.Base import Base
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version

from collections.abc import Iterable

from edsl.exceptions.agents import AgentListError

if TYPE_CHECKING:
    from edsl.scenarios.ScenarioList import ScenarioList


def is_iterable(obj):
    return isinstance(obj, Iterable)


class AgentList(UserList, Base):
    """A list of Agents."""

    __documentation__ = (
        "https://docs.expectedparrot.com/en/latest/agents.html#agentlist-class"
    )

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

    def sample(self, n: int, seed: Optional[str] = None) -> AgentList:
        """Return a random sample of agents.

        :param n: The number of agents to sample.
        :param seed: The seed for the random number generator.
        """
        import random

        if seed:
            random.seed(seed)
        return AgentList(random.sample(self.data, n))

    def to_pandas(self):
        """Return a pandas DataFrame."""
        return self.to_scenario_list().to_pandas()

    def tally(self):
        return self.to_scenario_list().tally()

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
            raise AgentListError(f"Error in filter. Exception:{e}")

        return AgentList(new_data)

    @property
    def all_traits(self):
        d = {}
        for agent in self:
            d.update(agent.traits)
        return list(d.keys())

    @classmethod
    def from_csv(cls, file_path: str, name_field: Optional[str] = None):
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
        >>> al = AgentList.from_csv('/tmp/agents.csv', name_field='hair')
        >>> al
        AgentList([Agent(name = \"""brown\""", traits = {'age': '22', 'height': '5.5'})])
        >>> os.remove('/tmp/agents.csv')

        :param file_path: The path to the CSV file.
        :param name_field: The name of the field to use as the agent name.
        """
        from edsl.agents.Agent import Agent

        agent_list = []
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "name" in row:
                    import warnings

                    warnings.warn("Using 'name' field in the CSV for the Agent name")
                    name_field = "name"
                if name_field is not None:
                    agent_name = row.pop(name_field)
                    agent_list.append(Agent(traits=row, name=agent_name))
                else:
                    agent_list.append(Agent(traits=row))
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

    def add_trait(self, trait, values):
        """Adds a new trait to every agent, with values taken from values.

        :param trait: The name of the trait.
        :param values: The valeues(s) of the trait. If a single value is passed, it is used for all agents.

        >>> al = AgentList.example()
        >>> al.add_trait('new_trait', 1)
        AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5, 'new_trait': 1}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5, 'new_trait': 1})])
        >>> al.select('new_trait').to_scenario_list().to_list()
        [1, 1]
        >>> al.add_trait('new_trait', [1, 2, 3])
        Traceback (most recent call last):
        ...
        edsl.exceptions.agents.AgentListError: The passed values have to be the same length as the agent list.
        ...
        """
        if not is_iterable(values):
            value = values
            for agent in self.data:
                agent.add_trait(trait, value)
            return self

        if len(values) != len(self):
            raise AgentListError(
                "The passed values have to be the same length as the agent list."
            )
        for agent, value in zip(self.data, values):
            agent.add_trait(trait, value)
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

        return dict_hash(self.to_dict(add_edsl_version=False, sorted=True))

    def to_dict(self, sorted=False, add_edsl_version=True):
        """Serialize the AgentList to a dictionary."""
        if sorted:
            data = self.data[:]
            data.sort(key=lambda x: hash(x))
        else:
            data = self.data

        d = {
            "agent_list": [
                agent.to_dict(add_edsl_version=add_edsl_version) for agent in data
            ]
        }
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "AgentList"

        return d

    def __eq__(self, other: AgentList) -> bool:
        return self.to_dict(sorted=True, add_edsl_version=False) == other.to_dict(
            sorted=True, add_edsl_version=False
        )

    def __repr__(self):
        return f"AgentList({self.data})"

    def _summary(self):
        return {
            "EDSL Class": "AgentList",
            "Number of agents": len(self),
            "Agent trait fields": self.all_traits,
        }

    def _repr_html_(self):
        """Return an HTML representation of the AgentList."""
        footer = f"<a href={self.__documentation__}>(docs)</a>"
        return str(self.summary(format="html")) + footer

    def to_csv(self, file_path: str):
        """Save the AgentList to a CSV file.

        :param file_path: The path to the CSV file.
        """
        self.to_scenario_list().to_csv(file_path)

    def to_list(self, include_agent_name=False) -> list[tuple]:
        """Return a list of tuples."""
        return self.to_scenario_list(include_agent_name).to_list()

    def to_scenario_list(self, include_agent_name=False) -> ScenarioList:
        """Return a list of scenarios."""
        from edsl.scenarios.ScenarioList import ScenarioList
        from edsl.scenarios.Scenario import Scenario

        if include_agent_name:
            return ScenarioList(
                [
                    Scenario(agent.traits | {"agent_name": agent.name})
                    for agent in self.data
                ]
            )
        return ScenarioList([Scenario(agent.traits) for agent in self.data])

    def table(
        self,
        *fields,
        tablefmt: Optional[str] = None,
        pretty_labels: Optional[dict] = None,
    ) -> Table:
        return (
            self.to_scenario_list()
            .to_dataset()
            .table(*fields, tablefmt=tablefmt, pretty_labels=pretty_labels)
        )

    def tree(self, node_order: Optional[List[str]] = None):
        return self.to_scenario_list().tree(node_order)

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

        >>> AgentList.from_list('age', [22, 23])
        AgentList([Agent(traits = {'age': 22}), Agent(traits = {'age': 23})])
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
