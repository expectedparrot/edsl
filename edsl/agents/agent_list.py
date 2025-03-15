"""A list of Agents
"""

from __future__ import annotations
import csv
import sys
import random
import logging
from collections import defaultdict
from itertools import product


from collections import UserList
from collections.abc import Iterable
from typing import Any, List, Optional, Union, TYPE_CHECKING

from simpleeval import EvalWithCompoundTypes, NameNotDefined

from ..base import Base
from ..utilities import is_notebook, remove_edsl_version, dict_hash
from ..dataset.dataset_operations_mixin import AgentListOperationsMixin

from .agent import Agent

from .exceptions import AgentListError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..agents import Agent


def is_iterable(obj):
    return isinstance(obj, Iterable)


class EmptyAgentList:
    def __repr__(self):
        return "Empty AgentList"


# ResultsExportMixin,
class AgentList(UserList, Base, AgentListOperationsMixin):
    """A list of Agents with additional functionality for manipulation and analysis.

    The AgentList class extends Python's UserList to provide a container for Agent objects
    with methods for filtering, transforming, and analyzing collections of agents.


    >>> AgentList.example().to_scenario_list()
    ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5}), Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])

    >>> AgentList.example().to_dataset()
    Dataset([{'age': [22, 22]}, {'hair': ['brown', 'brown']}, {'height': [5.5, 5.5]}])

    >>> AgentList.example().to_pandas()
       age   hair  height
    0   22  brown     5.5
    1   22  brown     5.5


    """

    __documentation__ = (
        "https://docs.expectedparrot.com/en/latest/agents.html#agentlist-class"
    )

    def __init__(self, data: Optional[list["Agent"]] = None, codebook: Optional[dict[str, str]] = None):
        """Initialize a new AgentList.

        >>> from edsl import Agent
        >>> al = AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}),
        ...                Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al
        AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al_with_codebook = AgentList([Agent(traits = {'age': 22})], codebook={'age': 'Age in years'})
        >>> al_with_codebook[0].codebook
        {'age': 'Age in years'}

        Args:
            data: A list of Agent objects. If None, creates an empty AgentList.
            codebook: Optional dictionary mapping trait names to descriptions. 
                      If provided, will be applied to all agents in the list.
        """
        if data is not None:
            super().__init__(data)
        else:
            super().__init__()
            
        # Apply codebook to all agents if provided
        if codebook is not None:
            self.set_codebook(codebook)

    def shuffle(self, seed: Optional[str] = None) -> AgentList:
        """Randomly shuffle the agents in place.

        Args:
            seed: Optional seed for the random number generator to ensure reproducibility.

        Returns:
            AgentList: The shuffled AgentList (self).
        """
        if seed is not None:
            random.seed(seed)
        random.shuffle(self.data)
        return self

    def sample(self, n: int, seed: Optional[str] = None) -> AgentList:
        """Return a random sample of agents.

        Args:
            n: The number of agents to sample.
            seed: Optional seed for the random number generator to ensure reproducibility.

        Returns:
            AgentList: A new AgentList containing the sampled agents.
        """

        if seed:
            random.seed(seed)
        return AgentList(random.sample(self.data, n))

    def duplicate(self) -> AgentList:
        """Create a deep copy of the AgentList.

        Returns:
            AgentList: A new AgentList containing copies of all agents.

        Examples:
            >>> al = AgentList.example()
            >>> al2 = al.duplicate()
            >>> al2 == al
            True
            >>> id(al2) == id(al)
            False
        """
        return AgentList([a.duplicate() for a in self.data])

    def rename(self, old_name: str, new_name: str) -> AgentList:
        """Rename a trait across all agents in the list.

        Args:
            old_name: The current name of the trait.
            new_name: The new name to assign to the trait.

        Returns:
            AgentList: A new AgentList with the renamed trait.

        Examples:
            >>> from edsl import Agent
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
            ...                Agent(traits = {'a': 1, 'b': 2})])
            >>> al2 = al.rename('a', 'c')
            >>> assert al2 == AgentList([Agent(traits = {'c': 1, 'b': 1}),
            ...                         Agent(traits = {'c': 1, 'b': 2})])
            >>> assert al != al2
        """
        newagents = []
        for agent in self:
            newagents.append(agent.rename(old_name, new_name))
        return AgentList(newagents)

    def select(self, *traits) -> AgentList:
        """Create a new AgentList with only the specified traits.

        Args:
            *traits: Variable number of trait names to keep.

        Returns:
            AgentList: A new AgentList containing agents with only the selected traits.

        Examples:
            >>> from edsl import Agent
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
            ...                Agent(traits = {'a': 1, 'b': 2})])
            >>> al.select('a')
            AgentList([Agent(traits = {'a': 1}), Agent(traits = {'a': 1})])
        """
        if len(traits) == 1:
            traits_to_select = [list(traits)[0]]
        else:
            traits_to_select = list(traits)

        return AgentList([agent.select(*traits_to_select) for agent in self.data])

    def filter(self, expression: str) -> AgentList:
        """Filter agents based on a boolean expression.

        Args:
            expression: A string containing a boolean expression to evaluate against
                each agent's traits.

        Returns:
            AgentList: A new AgentList containing only agents that satisfy the expression.

        Examples:
            >>> from edsl import Agent
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
            ...                Agent(traits = {'a': 1, 'b': 2})])
            >>> al.filter("b == 2")
            AgentList([Agent(traits = {'a': 1, 'b': 2})])
        """

        def create_evaluator(agent: "Agent"):
            """Create an evaluator for the given agent."""
            return EvalWithCompoundTypes(names=agent.traits)

        try:
            new_data = [
                agent for agent in self.data if create_evaluator(agent).eval(expression)
            ]
        except NameNotDefined:
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
        >>> from edsl import Agent
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
    def from_csv(cls, file_path: str, name_field: Optional[str] = None, codebook: Optional[dict[str, str]] = None):
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
        >>> al = AgentList.from_csv('/tmp/agents.csv', codebook={'age': 'Age in years'})
        >>> al[0].codebook
        {'age': 'Age in years'}
        >>> os.remove('/tmp/agents.csv')

        :param file_path: The path to the CSV file.
        :param name_field: The name of the field to use as the agent name.
        :param codebook: Optional dictionary mapping trait names to descriptions.
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
                    agent_list.append(Agent(traits=row, name=agent_name, codebook=codebook))
                else:
                    agent_list.append(Agent(traits=row, codebook=codebook))
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
        >>> from edsl import Agent
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
        edsl.agents.exceptions.AgentListError: The passed values have to be the same length as the agent list.
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
        return dict_hash(self.to_dict(add_edsl_version=False, sorted=True))

    def to_dict(self, sorted=False, add_edsl_version=True):
        """Serialize the AgentList to a dictionary.

        >>> AgentList.example().to_dict(add_edsl_version=False)
        {'agent_list': [{'traits': {'age': 22, 'hair': 'brown', 'height': 5.5}}, {'traits': {'age': 22, 'hair': 'brown', 'height': 5.5}}]}
        >>> example_codebook = {'age': 'Age in years'}
        >>> al = AgentList.example().set_codebook(example_codebook)
        >>> result = al.to_dict(add_edsl_version=False)
        >>> 'codebook' in result
        True
        >>> result['codebook'] == example_codebook
        True
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
        
        # Add codebook if all agents have the same codebook
        if len(self.data) > 0:
            # Get the first agent's codebook
            first_codebook = self.data[0].codebook
            
            # Check if all agents have the same codebook
            all_same = all(agent.codebook == first_codebook for agent in self.data)
            
            # Only include codebook if it's non-empty and consistent across all agents
            if all_same and first_codebook:
                d["codebook"] = first_codebook
                
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

    def _summary(self) -> dict:
        return {
            "agents": len(self),
        }
    
    def set_codebook(self, codebook: dict[str, str]) -> AgentList:
        """Set the codebook for the AgentList.

        >>> from edsl import Agent
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


    def table(
        self,
        *fields,
        tablefmt: Optional[str] = None,
        pretty_labels: Optional[dict] = None,
    ) -> Any:
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
        """Convert the AgentList to a Dataset.

        Args:
            traits_only: If True, only include agent traits. If False, also include
                agent parameters like instructions and names.

        Returns:
            Dataset: A dataset containing the agents' traits and optionally their parameters.

        Examples:
            >>> from edsl import AgentList
            >>> al = AgentList.example()
            >>> al.to_dataset()
            Dataset([{'age': [22, 22]}, {'hair': ['brown', 'brown']}, {'height': [5.5, 5.5]}])
            >>> al.to_dataset(traits_only=False)  # doctest: +NORMALIZE_WHITESPACE
            Dataset([{'age': [22, 22]}, {'hair': ['brown', 'brown']}, {'height': [5.5, 5.5]}, {'agent_parameters': [{'instruction': 'You are answering questions as if you were a human. Do not break character.', 'agent_name': None}, {'instruction': 'You are answering questions as if you were a human. Do not break character.', 'agent_name': None}]}])
        """
        from ..dataset import Dataset

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

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> "AgentList":
        """Deserialize the dictionary back to an AgentList object.

        :param: data: A dictionary representing an AgentList.

        >>> from edsl import Agent
        >>> al = AgentList([Agent.example(), Agent.example()])
        >>> al2 = AgentList.from_dict(al.to_dict())
        >>> al2 == al
        True
        >>> example_codebook = {'age': 'Age in years'}
        >>> al = AgentList([Agent.example()]).set_codebook(example_codebook)
        >>> al2 = AgentList.from_dict(al.to_dict())
        >>> al2[0].codebook == example_codebook
        True
        """
        from .agent import Agent

        agents = [Agent.from_dict(agent_dict) for agent_dict in data["agent_list"]]
        agent_list = cls(agents)
        
        # Apply codebook if present in the dictionary
        if "codebook" in data and data["codebook"]:
            agent_list.set_codebook(data["codebook"])
            
        return agent_list

    @classmethod
    def example(cls, randomize: bool = False, codebook: Optional[dict[str, str]] = None) -> AgentList:
        """
        Returns an example AgentList instance.

        :param randomize: If True, uses Agent's randomize method.
        :param codebook: Optional dictionary mapping trait names to descriptions.
        
        >>> al = AgentList.example()
        >>> al
        AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al = AgentList.example(codebook={'age': 'Age in years'})
        >>> al[0].codebook
        {'age': 'Age in years'}
        """
        from .agent import Agent

        agent_list = cls([Agent.example(randomize), Agent.example(randomize)])
        
        if codebook:
            agent_list.set_codebook(codebook)
            
        return agent_list

    @classmethod
    def from_list(self, trait_name: str, values: List[Any], codebook: Optional[dict[str, str]] = None) -> "AgentList":
        """Create an AgentList from a list of values.

        :param trait_name: The name of the trait.
        :param values: A list of values.
        :param codebook: Optional dictionary mapping trait names to descriptions.

        >>> AgentList.from_list('age', [22, 23])
        AgentList([Agent(traits = {'age': 22}), Agent(traits = {'age': 23})])
        >>> al = AgentList.from_list('age', [22], codebook={'age': 'Age in years'})
        >>> al[0].codebook
        {'age': 'Age in years'}
        """
        from .agent import Agent

        agent_list = AgentList([Agent({trait_name: value}) for value in values])
        
        if codebook:
            agent_list.set_codebook(codebook)
            
        return agent_list

    def __mul__(self, other: AgentList) -> AgentList:
        """Takes the cross product of two AgentLists."""
        new_sl = []
        for s1, s2 in list(product(self, other)):
            new_sl.append(s1 + s2)
        return AgentList(new_sl)

    def code(self, string=True) -> Union[str, list[str]]:
        """Return code to construct an AgentList.

        >>> al = AgentList.example()
        >>> print(al.code())
        from edsl import Agent
        from edsl import AgentList
        agent_list = AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        """
        lines = [
            "from edsl import Agent",
            "from edsl import AgentList",
        ]
        lines.append(f"agent_list = AgentList({self.data})")
        if string:
            return "\n".join(lines)
        return lines


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE)
