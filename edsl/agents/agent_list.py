"""A list of Agents
"""

from __future__ import annotations
import csv
import sys
from collections import UserList
from collections.abc import Iterable

from typing import Any, List, Optional, Union, TYPE_CHECKING

from simpleeval import EvalWithCompoundTypes, NameNotDefined

from edsl.base import Base
from edsl.utilities.remove_edsl_version import remove_edsl_version
from edsl.exceptions.agents import AgentListError
from edsl.utilities.is_notebook import is_notebook
#from edsl.results.ResultsExportMixin import ResultsExportMixin
import logging
from edsl.agents import Agent


from ..dataset.dataset_operations_mixin import AgentListOperationsMixin

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from edsl.scenarios import ScenarioList
    from edsl.agents.Agent import Agent
    from pandas import DataFrame


def is_iterable(obj):
    return isinstance(obj, Iterable)


class EmptyAgentList:
    def __repr__(self):
        return "Empty AgentList"


# ResultsExportMixin,
class AgentList(UserList, Base, AgentListOperationsMixin):
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

    def shuffle(self, seed: Optional[str] = None) -> AgentList:
        """Shuffle the AgentList.

        :param seed: The seed for the random number generator.
        """
        import random

        if seed is not None:
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

    def to_pandas(self) -> "DataFrame":
        """Return a pandas DataFrame.

        >>> from edsl.agents.Agent import Agent
        >>> al = AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al.to_pandas()
           age   hair  height
        0   22  brown     5.5
        1   22  brown     5.5
        """
        return self.to_scenario_list().to_pandas()

    def tally(
        self, *fields: Optional[str], top_n: Optional[int] = None, output="Dataset"
    ) -> Union[dict, "Dataset"]:
        """Tally the values of a field or perform a cross-tab of multiple fields.

        :param fields: The field(s) to tally, multiple fields for cross-tabulation.

        >>> al = AgentList.example()
        >>> al.tally('age')
        Dataset([{'age': [22]}, {'count': [2]}])
        """
        return self.to_scenario_list().tally(*fields, top_n=top_n, output=output)

    def duplicate(self):
        """Duplicate the AgentList.

        >>> al = AgentList.example()
        >>> al2 = al.duplicate()
        >>> al2 == al
        True
        >>> id(al2) == id(al)
        False
        """
        return AgentList([a.duplicate() for a in self.data])

    def rename(self, old_name, new_name) -> AgentList:
        """Rename a trait in the AgentList.

        :param old_name: The old name of the trait.
        :param new_name: The new name of the trait.
        :param inplace: Whether to rename the trait in place.

        >>> from edsl.agents import Agent
        >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}), Agent(traits = {'a': 1, 'b': 2})])
        >>> al2 = al.rename('a', 'c')
        >>> assert al2 == AgentList([Agent(traits = {'c': 1, 'b': 1}), Agent(traits = {'c': 1, 'b': 2})])
        >>> assert al != al2
        """
        newagents = []
        for agent in self:
            newagents.append(agent.rename(old_name, new_name))
        return AgentList(newagents)

    def select(self, *traits) -> AgentList:
        """Selects agents with only the references traits.

        >>> from edsl.agents import Agent
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

        >>> from edsl.agents import Agent
        >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}), Agent(traits = {'a': 1, 'b': 2})])
        >>> al.filter("b == 2")
        AgentList([Agent(traits = {'a': 1, 'b': 2})])
        """

        def create_evaluator(agent: "Agent"):
            """Create an evaluator for the given result.
            The 'combined_dict' is a mapping of all values for that Result object.
            """
            return EvalWithCompoundTypes(names=agent.traits)

            # iterates through all the results and evaluates the expression

        try:
            new_data = [
                agent for agent in self.data if create_evaluator(agent).eval(expression)
            ]
        except NameNotDefined as e:
            e = AgentListError(f"'{expression}' is not a valid expression.")
            if is_notebook():
                print(e, file=sys.stderr)
            else:
                raise e

            return EmptyAgentList()

        if len(new_data) == 0:
            return EmptyAgentList()

        return AgentList(new_data)

    @property
    def all_traits(self) -> list[str]:
        """Return all traits in the AgentList.
        >>> from edsl.agents import Agent
        >>> agent_1 = Agent(traits = {'age': 22})
        >>> agent_2 = Agent(traits = {'hair': 'brown'})
        >>> al = AgentList([agent_1, agent_2])
        >>> al.all_traits
        ['age', 'hair']
        """
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
        from .agent import Agent

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

    def translate_traits(self, codebook: dict[str, str]):
        """Translate traits to a new codebook.

        :param codebook: The new codebook.

        >>> al = AgentList.example()
        >>> codebook = {'hair': {'brown':'Secret word for green'}}
        >>> al.translate_traits(codebook)
        AgentList([Agent(traits = {'age': 22, 'hair': 'Secret word for green', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'Secret word for green', 'height': 5.5})])
        """
        new_agents = []
        for agent in self.data:
            new_agents.append(agent.translate_traits(codebook))
        return AgentList(new_agents)

    def remove_trait(self, trait: str):
        """Remove traits from the AgentList.

        :param traits: The traits to remove.
        >>> from edsl.agents import Agent
        >>> al = AgentList([Agent({'age': 22, 'hair': 'brown', 'height': 5.5}), Agent({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al.remove_trait('age')
        AgentList([Agent(traits = {'hair': 'brown', 'height': 5.5}), Agent(traits = {'hair': 'brown', 'height': 5.5})])
        """
        agents = []
        new_al = self.duplicate()
        for agent in new_al.data:
            agents.append(agent.remove_trait(trait))
        return AgentList(agents)

    def add_trait(self, trait: str, values: List[Any]) -> AgentList:
        """Adds a new trait to every agent, with values taken from values.

        :param trait: The name of the trait.
        :param values: The valeues(s) of the trait. If a single value is passed, it is used for all agents.

        >>> al = AgentList.example()
        >>> new_al = al.add_trait('new_trait', 1)
        >>> new_al.select('new_trait').to_scenario_list().to_list()
        [1, 1]
        >>> al.add_trait('new_trait', [1, 2, 3])
        Traceback (most recent call last):
        ...
        edsl.exceptions.agents.AgentListError: The passed values have to be the same length as the agent list.
        ...
        """
        if not is_iterable(values):
            new_agents = []
            value = values
            for agent in self.data:
                new_agents.append(agent.add_trait(trait, value))
            return AgentList(new_agents)

        if len(values) != len(self):
            e = AgentListError(
                "The passed values have to be the same length as the agent list."
            )
            if is_notebook():
                print(e, file=sys.stderr)
            else:
                raise e
        new_agents = []
        for agent, value in zip(self.data, values):
            new_agents.append(agent.add_trait(trait, value))
        return AgentList(new_agents)

    @staticmethod
    def get_codebook(file_path: str):
        """Return the codebook for a CSV file.

        :param file_path: The path to the CSV file.
        """
        with open(file_path, "r") as f:
            reader = csv.DictReader(f)
            return {field: None for field in reader.fieldnames}

    def __hash__(self) -> int:
        """Return the hash of the AgentList.

        >>> al = AgentList.example()
        >>> hash(al)
        1681154913465662422
        """
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False, sorted=True))

    def to_dict(self, sorted=False, add_edsl_version=True):
        """Serialize the AgentList to a dictionary.

        >>> AgentList.example().to_dict(add_edsl_version=False)
        {'agent_list': [{'traits': {'age': 22, 'hair': 'brown', 'height': 5.5}}, {'traits': {'age': 22, 'hair': 'brown', 'height': 5.5}}]}

        """
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
            "agents": len(self),
        }

    def set_codebook(self, codebook: dict[str, str]) -> AgentList:
        """Set the codebook for the AgentList.

        >>> from edsl.agents import Agent
        >>> a = Agent(traits = {'hair': 'brown'})
        >>> al = AgentList([a, a])
        >>> _ = al.set_codebook({'hair': "Color of hair on driver's license"})
        >>> al[0].codebook
        {'hair': "Color of hair on driver's license"}


        :param codebook: The codebook.
        """
        for agent in self.data:
            agent.codebook = codebook

        return self

    def to_csv(self, file_path: str):
        """Save the AgentList to a CSV file.

        :param file_path: The path to the CSV file.
        """
        self.to_scenario_list().to_csv(file_path)

    def to_list(self, include_agent_name=False) -> list[tuple]:
        """Return a list of tuples."""
        return self.to_scenario_list(include_agent_name).to_list()

    def to_scenario_list(
        self, include_agent_name: bool = False, include_instruction: bool = False
    ) -> ScenarioList:
        """Converts the agent to a scenario list."""
        from edsl.scenarios.ScenarioList import ScenarioList
        from edsl.scenarios.Scenario import Scenario

        # raise NotImplementedError("This method is not implemented yet.")

        scenario_list = ScenarioList()
        for agent in self.data:
            d = agent.traits
            if include_agent_name:
                d["agent_name"] = agent.name
            if include_instruction:
                d["instruction"] = agent.instruction
            scenario_list.append(Scenario(d))
        return scenario_list


    def table(
        self,
        *fields,
        tablefmt: Optional[str] = None,
        pretty_labels: Optional[dict] = None,
    ) -> Table:
        if len(self) == 0:
            e = AgentListError("Cannot create a table from an empty AgentList.")
            if is_notebook():
                print(e, file=sys.stderr)
                return None
            else:
                raise e
        return (
            self.to_scenario_list()
            .to_dataset()
            .table(*fields, tablefmt=tablefmt, pretty_labels=pretty_labels)
        )

    def to_dataset(self, traits_only: bool = True):
        """
        Convert the AgentList to a Dataset.

        >>> from edsl.agents import AgentList
        >>> al = AgentList.example()
        >>> al.to_dataset()
        Dataset([{'age': [22, 22]}, {'hair': ['brown', 'brown']}, {'height': [5.5, 5.5]}])
        >>> al.to_dataset(traits_only = False)
        Dataset([{'age': [22, 22]}, {'hair': ['brown', 'brown']}, {'height': [5.5, 5.5]}, {'agent_parameters': [{'instruction': 'You are answering questions as if you were a human. Do not break character.', 'agent_name': None}, {'instruction': 'You are answering questions as if you were a human. Do not break character.', 'agent_name': None}]}])
        """
        from ..dataset import Dataset
        from collections import defaultdict

        agent_trait_keys = []
        for agent in self:
            agent_keys = list(agent.traits.keys())
            for key in agent_keys:
                if key not in agent_trait_keys:
                    agent_trait_keys.append(key)

        data = defaultdict(list)
        for agent in self:
            for trait_key in agent_trait_keys:
                data[trait_key].append(agent.traits.get(trait_key, None))
            if not traits_only:
                data["agent_parameters"].append(
                    {"instruction": agent.instruction, "agent_name": agent.name}
                )
        return Dataset([{key: entry} for key, entry in data.items()])

    def tree(self, node_order: Optional[List[str]] = None):
        return self.to_scenario_list().tree(node_order)

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> "AgentList":
        """Deserialize the dictionary back to an AgentList object.

        :param: data: A dictionary representing an AgentList.
        >>> from edsl.agents import Agent
        >>> al = AgentList([Agent.example(), Agent.example()])
        >>> al2 = AgentList.from_dict(al.to_dict())
        >>> al2 == al
        True
        """
        from edsl.agents import Agent

        agents = [Agent.from_dict(agent_dict) for agent_dict in data["agent_list"]]
        return cls(agents)

    @classmethod
    def example(cls, randomize: bool = False) -> AgentList:
        """
        Returns an example AgentList instance.

        :param randomize: If True, uses Agent's randomize method.
        """
        from edsl.agents import Agent

        return cls([Agent.example(randomize), Agent.example(randomize)])

    @classmethod
    def from_list(self, trait_name: str, values: List[Any]):
        """Create an AgentList from a list of values.

        :param trait_name: The name of the trait.
        :param values: A list of values.

        >>> AgentList.from_list('age', [22, 23])
        AgentList([Agent(traits = {'age': 22}), Agent(traits = {'age': 23})])
        """
        from edsl.agents import Agent

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
        from edsl.agents import Agent
        from edsl.agents import AgentList
        agent_list = AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        """
        lines = [
            "from edsl.agents import Agent",
            "from edsl.agents import AgentList",
        ]
        lines.append(f"agent_list = AgentList({self.data})")
        if string:
            return "\n".join(lines)
        return lines


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
