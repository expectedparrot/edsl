"""A list of Agents"""

from __future__ import annotations

# csv import moved to agent_list_factories.py
import sys
import random
import warnings
import logging
from collections import defaultdict
from itertools import product


from collections import UserList
from typing import Any, List, Optional, Union, TYPE_CHECKING

# simpleeval imports moved to agent_list_filter.py

from ..base import Base
from ..utilities import is_notebook, remove_edsl_version, dict_hash
from ..dataset.dataset_operations_mixin import AgentListOperationsMixin

from .agent import Agent

from .exceptions import AgentListError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..agents import Agent
    from ..jobs import Jobs
    from ..questions import QuestionBase as Question
    from ..surveys import Survey
    from ..scenarios import ScenarioList
    from ..results import Results


# is_iterable function moved to agent_list_trait_operations.py


# EmptyAgentList moved to agent_list_filter.py


# ResultsExportMixin,
class AgentList(UserList, Base, AgentListOperationsMixin):
    """A list of Agents with additional functionality for manipulation and analysis.

    The AgentList class extends Python's UserList to provide a container for Agent objects
    with methods for filtering, transforming, and analyzing collections of agents.


    >>> AgentList.example().to_scenario_list().drop('age')
    ScenarioList([Scenario({'hair': 'brown', 'height': 5.5}), Scenario({'hair': 'brown', 'height': 5.5})])

    >>> AgentList.example().to_dataset()
    Dataset([{'age': [22, 22]}, {'hair': ['brown', 'brown']}, {'height': [5.5, 5.5]}])

    >>> AgentList.example().select('age', 'hair', 'height').to_pandas()
       age   hair  height
    0   22  brown     5.5
    1   22  brown     5.5


    """

    __documentation__ = (
        "https://docs.expectedparrot.com/en/latest/agents.html#agentlist-class"
    )

    def __init__(
        self,
        data: Optional[list["Agent"]] = None,
        codebook: Optional[dict[str, str]] = None,
    ):
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

    def at(self, index: int) -> "Agent":
        """Get the agent at the specified index position."""
        return self.data[index]

    def first(self) -> "Agent":
        """Get the first agent in the list."""
        return self.data[0]

    def last(self) -> "Agent":
        """Get the last agent in the list."""
        return self.data[-1]

    def set_instruction(self, instruction: str) -> None:
        """Set the instruction for all agents in the list.

        Args:
            instruction: The instruction to set.
        """
        for agent in self.data:
            agent.instruction = instruction

        return self

    def add_instructions(self, instructions: str) -> "AgentList":
        """Apply instructions to all agents in the list.

        This method provides a more intuitive name for setting instructions
        on all agents, avoiding the need to iterate manually.

        Args:
            instructions: The instructions to apply to all agents.

        Returns:
            AgentList: Returns self for method chaining.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> agents = AgentList([Agent(traits={'age': 30}), Agent(traits={'age': 40})])
            >>> agents.add_instructions("Answer as if you were this age")
            AgentList([Agent(traits = {'age': 30}), Agent(traits = {'age': 40})])
        """
        for agent in self.data:
            agent.instruction = instructions
        return self

    @classmethod
    def manage(cls):
        from ..widgets.agent_list_manager import AgentListManagerWidget

        return AgentListManagerWidget()

    def edit(self):
        from ..widgets.agent_list_builder import AgentListBuilderWidget

        return AgentListBuilderWidget(self)

    def set_traits_presentation_template(
        self, traits_presentation_template: str
    ) -> None:
        """Set the traits presentation template for all agents in the list.

        Args:
            traits_presentation_template: The traits presentation template to set.
        """
        for agent in self.data:
            agent.traits_presentation_template = traits_presentation_template

        return None

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

    def drop(self, *field_names: Union[str, List[str]]) -> AgentList:
        """Drop field(s) from all agents in the AgentList.

        Args:
            *field_names: The name(s) of the field(s) to drop. Can be:
                - Single field name: drop("age")
                - Multiple field names: drop("age", "height")
                - List of field names: drop(["age", "height"])

        Returns:
            AgentList: A new AgentList with the specified fields dropped from all agents.

        Examples:
            Drop a single trait from all agents:

            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al_dropped = al.drop("age")
            >>> al_dropped[0].traits
            {'hair': 'brown', 'height': 5.5}

            Drop multiple traits using separate arguments:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al_dropped = al.drop("age", "height")
            >>> al_dropped[0].traits
            {'hair': 'brown'}

            Drop multiple traits using a list:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al_dropped = al.drop(["age", "height"])
            >>> al_dropped[0].traits
            {'hair': 'brown'}
        """
        from .agent_list_trait_operations import AgentListTraitOperations

        return AgentListTraitOperations.drop(self, *field_names)

    def keep(self, *field_names: Union[str, List[str]]) -> AgentList:
        """Keep only the specified fields from all agents in the AgentList.

        Args:
            *field_names: The name(s) of the field(s) to keep. Can be:
                - Single field name: keep("age")
                - Multiple field names: keep("age", "height")
                - List of field names: keep(["age", "height"])

        Returns:
            AgentList: A new AgentList with only the specified fields kept for all agents.

        Examples:
            Keep a single trait for all agents:

            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al_kept = al.keep("age")
            >>> al_kept[0].traits
            {'age': 30}

            Keep multiple traits using separate arguments:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al_kept = al.keep("age", "height")
            >>> al_kept[0].traits
            {'age': 30, 'height': 5.5}

            Keep multiple traits using a list:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al_kept = al.keep(["age", "height"])
            >>> al_kept[0].traits
            {'age': 30, 'height': 5.5}

            Keep agent fields and traits:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown"}, name="John")])
            >>> al_kept = al.keep("name", "age")
            >>> al_kept[0].name
            'John'
            >>> al_kept[0].traits
            {'age': 30}
        """
        from .agent_list_trait_operations import AgentListTraitOperations

        return AgentListTraitOperations.keep(self, *field_names)

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

    def collapse(self, warn_about_none_name: bool = True) -> "AgentList":
        """All agents with the same name have their traits combined.

        >>> al = AgentList([Agent(name = 'steve'), Agent(name = 'roxanne')])
        >>> al.collapse()
        AgentList([Agent(name = \"\"\"steve\"\"\", traits = {}), Agent(name = \"\"\"roxanne\"\"\", traits = {})])
        >>> al = AgentList([Agent(name = 'steve', traits = {'age': 22}), Agent(name = 'steve', traits = {'hair': 'brown'})])
        >>> al.collapse()
        AgentList([Agent(name = \"\"\"steve\"\"\", traits = {'age': 22, 'hair': 'brown'})])
        >>> AgentList.example().collapse(warn_about_none_name = False)
        AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        """
        new_agent_list = AgentList()
        warned_about_none_name = False
        d = {}
        for agent in self:
            if agent.name is None:
                if not warned_about_none_name and warn_about_none_name:
                    warnings.warn("Agent has no name, so it will be ignored.")
                    warned_about_none_name = True
            if agent.name not in d:
                d[agent.name] = agent
            else:
                d[agent.name].traits.update(agent.traits)
        for name, agent in d.items():
            new_agent_list.append(agent)
        return new_agent_list

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
        from .agent_list_trait_operations import AgentListTraitOperations

        return AgentListTraitOperations.rename(self, old_name, new_name)

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
        from .agent_list_trait_operations import AgentListTraitOperations

        return AgentListTraitOperations.select(self, *traits)

    def _apply_names(
        self,
        agent_list_data: list["Agent"],
        trait_keys: tuple[str],
        remove_traits: bool = True,
        separator: str = ",",
        force_name: bool = False,
    ) -> None:
        """Private helper method to apply names to a list of agents.

        Args:
            agent_list_data: List of agents to modify
            trait_keys: The trait keys to use for naming
            remove_traits: Whether to remove the traits used for naming
            separator: The separator to use when joining multiple trait values
            force_name: Whether to force naming even if agents already have names
        """
        if not force_name:
            assert all(
                [agent.name is None for agent in agent_list_data]
            ), "Agents already have names, so naming will not work. Use force_name=True to override."

        new_names = []
        if isinstance(trait_keys, str):
            trait_keys = [trait_keys]
        for agent in agent_list_data:
            trait_values = [agent.traits[key] for key in trait_keys]
            new_name = str(f"{separator}".join([str(value) for value in trait_values]))
            agent.name = str(new_name)
            new_names.append(new_name)
            if remove_traits:
                for key in trait_keys:
                    agent.traits.pop(key)

        assert len(new_names) == len(
            agent_list_data
        ), "The number of new names does not match the number of agents."

    def give_names(
        self,
        *trait_keys: str,
        remove_traits: bool = True,
        separator: str = ",",
        force_name: bool = False,
    ) -> None:
        """Give names to agents based on the values of the specified traits.

        >>> from edsl import Agent
        >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
        ...                Agent(traits = {'a': 1, 'b': 2})])
        >>> al.give_names('a')
        >>> al[0].name
        '1'
        """
        self._apply_names(self.data, trait_keys, remove_traits, separator, force_name)

    def with_names(
        self,
        *trait_keys: str,
        remove_traits: bool = True,
        separator: str = ",",
        force_name: bool = False,
    ) -> AgentList:
        """Return a new AgentList with names based on the values of the specified traits.

        Args:
            *trait_keys: The trait keys to use for naming
            remove_traits: Whether to remove the traits used for naming from the agents
            separator: The separator to use when joining multiple trait values
            force_name: Whether to force naming even if agents already have names

        Returns:
            AgentList: A new AgentList with named agents

        >>> from edsl import Agent
        >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
        ...                Agent(traits = {'a': 1, 'b': 2})])
        >>> al_with_names = al.with_names('a')
        >>> al_with_names[0].name
        '1'
        >>> al[0].name is None  # Original unchanged
        True
        """
        # Create a duplicate to avoid modifying the original
        new_agent_list = self.duplicate()

        # Apply the naming logic to the duplicated agents using the shared helper
        self._apply_names(
            new_agent_list.data, trait_keys, remove_traits, separator, force_name
        )

        return new_agent_list

    def _join(self, other: "AgentList", join_type: str = "inner") -> AgentList:
        """Join two AgentLists (private method).

        Args:
            other: The other AgentList to join
            join_type: The type of join to perform
        """
        from .agent_list_joiner import AgentListJoiner

        return AgentListJoiner._join_two(self, other, join_type=join_type)

    def join(self, other: "AgentList", join_type: str = "inner") -> "AgentList":
        """Join this AgentList with another AgentList.

        Args:
            other: The other AgentList to join with
            join_type: The type of join to perform ("inner", "left", or "right")

        Returns:
            AgentList: A new AgentList containing the joined results

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al1 = AgentList([Agent(name="John", traits={"age": 30})])
            >>> al2 = AgentList([Agent(name="John", traits={"height": 180})])
            >>> joined = al1.join(al2)
            >>> joined[0].traits
            {'age': 30, 'height': 180}
        """
        from .agent_list_joiner import AgentListJoiner

        return AgentListJoiner.join_two(self, other, join_type=join_type)

    @classmethod
    def join_multiple(
        cls, *agent_lists: "AgentList", join_type: str = "inner"
    ) -> "AgentList":
        """Join multiple AgentLists together.

        Args:
            *agent_lists: Variable number of AgentList objects to join
            join_type: The type of join to perform ("inner", "left", or "right")

        Returns:
            AgentList: A new AgentList containing the joined results

        Raises:
            ValueError: If fewer than 2 AgentLists are provided

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al1 = AgentList([Agent(name="John", traits={"age": 30})])
            >>> al2 = AgentList([Agent(name="John", traits={"height": 180})])
            >>> al3 = AgentList([Agent(name="John", traits={"weight": 75})])
            >>> joined = AgentList.join_multiple(al1, al2, al3)
            >>> len(joined)
            1
            >>> joined[0].traits
            {'age': 30, 'height': 180, 'weight': 75}
        """
        from .agent_list_joiner import AgentListJoiner

        return AgentListJoiner.join_multiple(*agent_lists, join_type=join_type)

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
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}, name = 'steve'),
            ...                Agent(traits = {'a': 1, 'b': 2}, name = 'roxanne')])
            >>> len(al.filter("name == 'steve'"))
            1
            >>> len(al.filter("name == 'roxanne'"))
            1
            >>> len(al.filter("name == 'steve' and a == 1"))
            1
            >>> len(al.filter("name == 'steve' and a == 2"))
            0
            >>> len(al.filter("name == 'steve' and a == 1 and b == 2"))
            0
        """
        from .agent_list_filter import AgentListFilter

        return AgentListFilter.filter(self, expression)

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
        from .agent_list_trait_operations import AgentListTraitOperations

        return AgentListTraitOperations.get_all_traits(self)

    @classmethod
    def from_source(
        cls,
        source_type: str,
        *args,
        instructions: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        name_field: Optional[str] = None,
        **kwargs,
    ) -> "AgentList":
        """Create an AgentList from a specified source type.

        This method serves as the main entry point for creating AgentList objects,
        providing a unified interface for various data sources.

        Args:
            source_type: The type of source to create an AgentList from.
                        Valid values include: 'csv', 'tsv', 'excel', 'pandas', etc.
            *args: Positional arguments to pass to the source-specific method.
            instructions: Optional instructions to apply to all created agents.
            codebook: Optional dictionary mapping trait names to descriptions, or a path to a CSV file.
                     If a CSV file is provided, it should have 2 columns: original keys and descriptions.
                     Keys will be automatically converted to pythonic names.
            name_field: The name of the field to use as the agent name (for CSV/Excel sources).
            **kwargs: Additional keyword arguments to pass to the source-specific method.

        Returns:
            An AgentList object created from the specified source.

        Examples:
            >>> # Create agents from a CSV file with instructions
            >>> # agents = AgentList.from_source(
            >>> #     'csv', 'agents.csv',
            >>> #     instructions="Answer as if you were the person described"
            >>> # )
            >>> # 
            >>> # Create agents with a CSV codebook file
            >>> # agents = AgentList.from_source(
            >>> #     'csv', 'agents.csv',
            >>> #     codebook='codebook.csv'  # CSV with keys like "Age in years" -> "age_in_years"
            >>> # )
        """
        from .agent_list_builder import AgentListBuilder

        return AgentListBuilder.from_source(
            source_type,
            *args,
            instructions=instructions,
            codebook=codebook,
            name_field=name_field,
            **kwargs,
        )

    @classmethod
    def from_csv(
        cls,
        file_path: str,
        name_field: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ):
        """Load AgentList from a CSV file.

        .. deprecated::
            Use `AgentList.from_source('csv', ...)` instead.

        >>> import csv
        >>> import os
        >>> with open('/tmp/agents.csv', 'w') as f:
        ...     writer = csv.writer(f)
        ...     _ = writer.writerow(['age', 'hair', 'height'])
        ...     _ = writer.writerow([22, 'brown', 5.5])
        >>> al = AgentList.from_csv('/tmp/agents.csv')  # doctest: +SKIP
        >>> al = AgentList.from_csv('/tmp/agents.csv', name_field='hair')  # doctest: +SKIP
        >>> al = AgentList.from_csv('/tmp/agents.csv', codebook={'age': 'Age in years'})  # doctest: +SKIP
        >>> al = AgentList.from_csv('/tmp/agents.csv', instructions='Answer as a person')  # doctest: +SKIP
        >>> os.remove('/tmp/agents.csv')  # doctest: +SKIP

        :param file_path: The path to the CSV file.
        :param name_field: The name of the field to use as the agent name.
        :param codebook: Optional dictionary mapping trait names to descriptions.
        :param instructions: Optional instructions to apply to all created agents.
        """
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.from_csv(
            file_path,
            name_field=name_field,
            codebook=codebook,
            instructions=instructions,
        )

    def translate_traits(self, codebook: dict[str, str]):
        """Translate traits to a new codebook.

        :param codebook: The new codebook.

        >>> al = AgentList.example()
        >>> codebook = {'hair': {'brown':'Secret word for green'}}
        >>> al.translate_traits(codebook)
        AgentList([Agent(traits = {'age': 22, 'hair': 'Secret word for green', 'height': 5.5}), Agent(traits = {'age': 22, 'hair': 'Secret word for green', 'height': 5.5})])
        """
        from .agent_list_trait_operations import AgentListTraitOperations

        return AgentListTraitOperations.translate_traits(self, codebook)

    def remove_trait(self, trait: str):
        """Remove traits from the AgentList.

        :param traits: The traits to remove.
        >>> from edsl import Agent
        >>> al = AgentList([Agent({'age': 22, 'hair': 'brown', 'height': 5.5}), Agent({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al.remove_trait('age')
        AgentList([Agent(traits = {'hair': 'brown', 'height': 5.5}), Agent(traits = {'hair': 'brown', 'height': 5.5})])
        """
        from .agent_list_trait_operations import AgentListTraitOperations

        return AgentListTraitOperations.remove_trait(self, trait)

    @property
    def names(self) -> List[str]:
        """Returns the names of the agents in the AgentList."""
        return [agent.name for agent in self.data]

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
        from .agent_list_trait_operations import AgentListTraitOperations

        return AgentListTraitOperations.add_trait(self, trait, values)

    @classmethod
    def from_results(cls, results: "Results") -> "AgentList":
        """Create an AgentList from a Results object."""
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.from_results(results)

    @staticmethod
    def get_codebook(file_path: str) -> dict:
        """Returns a codebook dictionary mapping CSV column names to None.

        Reads the header row of a CSV file and creates a codebook with field names as keys
        and None as values.

        Args:
            file_path: Path to the CSV file to read.

        Returns:
            A dictionary with CSV column names as keys and None as values.

        Raises:
            FileNotFoundError: If the specified file path does not exist.
            csv.Error: If there is an error reading the CSV file.
        """
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.get_codebook(file_path)

    def __hash__(self) -> int:
        """Return the hash of the AgentList.

        >>> al = AgentList.example()
        >>> hash(al)
        1681154913465662422
        """
        return dict_hash(self.to_dict(add_edsl_version=False, sorted=True))

    def to(self, target: Union["Question", "Jobs", "Survey"]) -> "Jobs":
        from ..questions import QuestionBase
        from ..surveys import Survey
        from ..jobs import Jobs

        if isinstance(target, QuestionBase):
            return Survey([target]).by(self)
        elif isinstance(target, Jobs):
            return target.by(self)
        elif isinstance(target, Survey):
            return target.by(self)
        else:
            raise ValueError(f"Cannot convert AgentList to {type(target)}")

    def to_dict(self, sorted=False, add_edsl_version=True, full_dict=False):
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
        from .agent_list_serializer import AgentListSerializer

        return AgentListSerializer.to_dict(
            self, sorted=sorted, add_edsl_version=add_edsl_version, full_dict=full_dict
        )

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
        tablefmt: Optional[str] = "rich",
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
            Dataset([{'age': [22, 22]}, {'hair': ['brown', 'brown']}, {'height': [5.5, 5.5]}, {'agent_parameters': [{'instruction': 'You are answering questions as if you were a human. Do not break character.', 'agent_name': None, 'traits_presentation_template': 'Your traits: {{traits}}'}, {'instruction': 'You are answering questions as if you were a human. Do not break character.', 'agent_name': None, 'traits_presentation_template': 'Your traits: {{traits}}'}]}])
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
                    {
                        "instruction": agent.instruction,
                        "agent_name": agent.name,
                        "traits_presentation_template": agent.traits_presentation_template,
                    }
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
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.from_dict(data)

    @classmethod
    def example(
        cls, randomize: bool = False, codebook: Optional[dict[str, str]] = None
    ) -> AgentList:
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
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.example(randomize=randomize, codebook=codebook)

    @classmethod
    def from_list(
        cls,
        trait_name: str,
        values: List[Any],
        codebook: Optional[dict[str, str]] = None,
    ) -> "AgentList":
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
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.from_list(trait_name, values, codebook=codebook)

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
        from .agent_list_code_generator import AgentListCodeGenerator

        return AgentListCodeGenerator.generate_code(self, string=string)

    @classmethod
    def from_scenario_list(cls, scenario_list: "ScenarioList") -> "AgentList":
        """Create an AgentList from a ScenarioList.

        This method supports special fields that map to Agent parameters:
        - "name": Will be used as the agent's name
        - "agent_parameters": A dictionary containing:
            - "instruction": The agent's instruction text
            - "name": The agent's name (overrides the "name" field if present)

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> # Basic usage with traits
            >>> s = ScenarioList([Scenario({'age': 22, 'hair': 'brown', 'height': 5.5})])
            >>> al = AgentList.from_scenario_list(s)
            >>> al
            AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        """
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.from_scenario_list(scenario_list)


if __name__ == "__main__":
    import doctest

    # Just run the standard doctests with verbose flag
    doctest.testmod(
        verbose=True, optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    )
