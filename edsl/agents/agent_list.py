"""A list of Agents"""

from __future__ import annotations

# csv import moved to agent_list_factories.py
import sys
import warnings
import logging
from collections import defaultdict
from functools import wraps
from itertools import product

from collections import UserList
from pathlib import Path
from typing import Any, Callable, Generator, Iterable, List, Optional, Union, TYPE_CHECKING

# simpleeval imports moved to agent_list_filter.py

from ..base import Base
from ..utilities import is_notebook, remove_edsl_version, dict_hash
from ..dataset.dataset_operations_mixin import AgentListOperationsMixin
from .agent import Agent
from .agent_list_builder import AgentListBuilder
from .agent_list_code_generator import AgentListCodeGenerator
from .agent_list_factories import AgentListFactories
from .agent_list_filter import AgentListFilter
from .agent_list_joiner import AgentListJoiner
from .agent_list_representation import AgentListRepresentation
from .agent_list_sampling import AgentListSampling
from .agent_list_serializer import AgentListSerializer
from .agent_list_trait_operations import AgentListTraitOperations

from .exceptions import AgentListError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..agents import Agent
    from ..jobs import Jobs
    from ..questions import QuestionBase as Question
    from ..surveys import Survey
    from ..scenarios import ScenarioList
    from ..results import Results
    from .agent_list_deltas import AgentListDeltas
    from ..dataset import Dataset

class AgentList(UserList, Base, AgentListOperationsMixin):
    """A list of Agents with additional functionality for manipulation and analysis.

    The AgentList class extends Python's UserList to provide a container for Agent objects
    with methods for filtering, transforming, and analyzing collections of agents.


    >>> AgentList.example().to_scenario_list().drop('age')
    ScenarioList([Scenario({'hair': 'brown', 'height': 5.5}), Scenario({'hair': 'brown', 'height': 5.5})])

    >>> AgentList.example().to_dataset()
    Dataset([{'age': [22, 22]}, {'hair': ['brown', 'brown']}, {'height': [5.5, 5.5]}])

    """

    __documentation__ = (
        "https://docs.expectedparrot.com/en/latest/agents.html#agentlist-class"
    )

    def __init__(
        self,
        data: Optional[list["Agent"] | str] = None,
        codebook: Optional[dict[str, str]] = None,
        traits_presentation_template: Optional[str] = None,
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
        if data is not None and isinstance(data, str):
            al = AgentList.pull(data)
            self.__dict__.update(al.__dict__)
            return

        if data is not None:
            super().__init__(data)
        else:
            super().__init__()

        # Apply codebook to all agents if provided
        if codebook is not None:
            self.set_codebook(codebook)

        self._codebook = codebook

        # Apply traits_presentation_template to all agents if provided
        self._traits_presentation_template = traits_presentation_template
        if traits_presentation_template is not None:
            self.set_traits_presentation_template(traits_presentation_template)
        self._agent_list_serializer = AgentListSerializer(self)
        self._agent_list_representation = AgentListRepresentation(self)
        self._agent_list_sampling = AgentListSampling(self)
        self._agent_list_trait_operations = AgentListTraitOperations(self)
        self._agent_list_joiner = AgentListJoiner(self)
        self._agent_list_filter = AgentListFilter(self)

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

    def set_dynamic_traits(self, function: Callable) -> None:
        """Set the dynamic traits for all agents in the list.

        Args:
            function: The function to set.
        """
        for agent in self.data:
            agent.traits_manager.set_dynamic_function(function)

    def set_dynamic_traits_from_question_map(
        self, q_to_traits: dict[str, list[str]]
    ) -> "AgentList":
        """Configure dynamic traits for each agent from a question→traits mapping (in-place).

        Each agent will get a dynamic traits function that, when asked a question whose
        ``question_name`` is present in ``q_to_traits``, returns a dict mapping the
        corresponding trait name(s) to the agent's original static value(s) for those trait(s).

        A warning is emitted if the set of mapped trait names does not exactly equal the
        set of trait keys present in this AgentList.

        Args:
            q_to_traits: Mapping from question name to list of trait keys, e.g.
                ``{"geo": ["hometown"], "cuisine": ["food"]}``.

        Returns:
            AgentList: self (modified in-place).

        Examples:
            >>> from edsl import Agent, AgentList
            >>> a_alice = Agent(name="Alice", traits={'hometown': 'Boston', 'food': 'beans'})
            >>> a_bob = Agent(name="Bob", traits={'hometown': 'SF', 'food': 'sushi'})
            >>> al = AgentList([a_alice, a_bob])
            >>> _ = al.set_dynamic_traits_from_question_map({'geo': ['hometown'], 'cuisine': ['food']})
            >>> class Q:
            ...     def __init__(self, name): self.question_name = name
            >>> al[0].dynamic_traits_function(Q('geo'))['hometown']
            'Boston'
            >>> al[1].dynamic_traits_function(Q('geo'))['hometown']
            'SF'
            >>> al[0].dynamic_traits_function(Q('cuisine'))['food']
            'beans'
        """
        # Flatten mapping values (lists of trait keys only)
        expected_trait_keys: set[str] = set()
        for value in q_to_traits.values():
            expected_trait_keys.update(value)
        actual_trait_keys = set(self.trait_keys)
        if expected_trait_keys != actual_trait_keys:
            missing_in_map = actual_trait_keys - expected_trait_keys
            extra_in_map = expected_trait_keys - actual_trait_keys
            warnings.warn(
                "Question→trait map does not perfectly overlap agent traits. "
                f"Missing in map: {sorted(missing_in_map)}; Extra in map: {sorted(extra_in_map)}"
            )

        for agent in self.data:
            base = dict(
                agent.traits
            )  # snapshot static traits before setting dynamic function

            def f(question, base_traits=base, qmap=q_to_traits):
                keys = qmap[question.question_name]
                return {k: base_traits[k] for k in keys}

            agent.dynamic_traits_function = f

        return self

    def with_categories(self, *categories: str) -> "AgentList":
        """Return a new AgentList with agents filtered to only specified categories.

        This method applies the with_categories method to each agent in the list,
        creating new agents that contain only traits belonging to the specified categories.

        Args:
            *categories: Variable number of category names to include in the filtered agents.

        Returns:
            AgentList: A new AgentList with agents containing only traits from the specified categories.

        Raises:
            AgentErrors: If any category is not found in an agent's trait_categories.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> a1 = Agent(traits={'age': 30, 'hometown': 'Boston', 'food': 'beans'})
            >>> a1.add_category('demographics', ['age', 'hometown'])
            >>> a1.add_category('preferences', ['food'])
            >>> a2 = Agent(traits={'age': 25, 'hometown': 'SF', 'food': 'sushi'})
            >>> a2.add_category('demographics', ['age', 'hometown'])
            >>> a2.add_category('preferences', ['food'])
            >>> al = AgentList([a1, a2])
            >>> demographics_only = al.with_categories('demographics')
            >>> demographics_only[0].traits
            {'age': 30, 'hometown': 'Boston'}
            >>> demographics_only[1].traits
            {'age': 25, 'hometown': 'SF'}
        """
        return AgentList([agent.with_categories(*categories) for agent in self.data])

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
            AgentList([Agent(traits = {'age': 30}, instruction = \"\"\"Answer as if you were this age\"\"\"), Agent(traits = {'age': 40}, instruction = \"\"\"Answer as if you were this age\"\"\")])
        """
        for agent in self.data:
            agent.instruction = instructions
        return self

    def __add__(self, other: AgentList) -> AgentList:
        """Add two AgentLists together."""
        # have to have the same traits + codebook
        if self.trait_keys != other.trait_keys:
            raise ValueError("AgentLists must have the same traits and codebook")

        if hasattr(self, "codebook") and hasattr(other, "codebook"):
            if self.codebook != other.codebook:
                raise ValueError("AgentLists must have the same codebook")

        return AgentList(
            self.data + other.data,
            codebook=self.codebook if hasattr(self, "codebook") else None,
            traits_presentation_template=self._traits_presentation_template,
        )

    @property
    def trait_keys(self) -> List[str]:
        """Get the trait keys for the AgentList."""
        keys = set()
        for agent in self.data:
            keys.update(agent.traits.keys())
        return list(keys)

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

    def set_codebook(self, codebook: dict[str, str]) -> None:
        """Set the codebook for the AgentList.

        >>> from edsl import Agent
        >>> a = Agent(traits = {'hair': 'brown'})
        >>> al = AgentList([a, a])
        >>> al.set_codebook({'hair': "Color of hair on driver's license"})
        >>> al[0].codebook
        {'hair': "Color of hair on driver's license"}

        :param codebook: The codebook.
        """
        for agent in self.data:
            agent.codebook = codebook

    @wraps(AgentListSampling.shuffle)
    def shuffle(self, seed: Optional[str] = None) -> AgentList:
        return self._agent_list_sampling.shuffle(seed)

    @wraps(AgentListSampling.sample)
    def sample(self, n: int, seed: Optional[str] = None) -> AgentList:
        return self._agent_list_sampling.sample(n, seed)

    @wraps(AgentListSampling.split)
    def split(
        self, frac_left: float, seed: Optional[int] = None
    ) -> tuple[AgentList, AgentList]:
        return self._agent_list_sampling.split(frac_left, seed)

    def apply_deltas(self, deltas: "AgentListDeltas") -> AgentList:
        """Apply an AgentListDeltas to create a new agent list with updated agents.

        This is a convenience method that delegates to AgentListDeltas.apply().
        All agent names in the deltas must match the names in this agent list.

        Args:
            deltas: The AgentListDeltas to apply

        Returns:
            A new AgentList with updated agents

        Raises:
            AgentListError: If agent names in deltas don't match the agent list

        Examples:
            Apply deltas to an agent list:

            >>> from edsl import Agent, AgentList, AgentDelta, AgentListDeltas
            >>> agent1 = Agent(name='Alice', traits={'age': 30})
            >>> agent2 = Agent(name='Bob', traits={'age': 25})
            >>> agent_list = AgentList([agent1, agent2])
            >>> deltas = AgentListDeltas({
            ...     'Alice': AgentDelta({'age': 31}),
            ...     'Bob': AgentDelta({'age': 26})
            ... })
            >>> updated_list = agent_list.apply_deltas(deltas)
            >>> [agent.traits['age'] for agent in updated_list]
            [31, 26]

            Error when names don't match:

            >>> bad_deltas = AgentListDeltas({'Charlie': AgentDelta({'age': 40})})
            >>> agent_list.apply_deltas(bad_deltas)  # doctest: +ELLIPSIS
            Traceback (most recent call last):
            ...
            edsl.agents.exceptions.AgentListError: ...
        """
        return deltas.apply(self)

    @wraps(AgentListTraitOperations.drop)
    def drop(self, *field_names: Union[str, List[str]]) -> AgentList:
        return self._agent_list_trait_operations.drop(*field_names)

    @wraps(AgentListTraitOperations.keep)
    def keep(self, *field_names: Union[str, List[str]]) -> AgentList:
        return self._agent_list_trait_operations.keep(*field_names)

    @wraps(AgentListSampling.duplicate)
    def duplicate(self) -> AgentList:
        return self._agent_list_sampling.duplicate()

    # def collapse(self, warn_about_none_name: bool = True) -> "AgentList":
    #     """All agents with the same name have their traits combined.

    #     >>> al = AgentList([Agent(name = 'steve'), Agent(name = 'roxanne')])
    #     >>> al.collapse()
    #     AgentList([Agent(name = \"\"\"steve\"\"\", traits = {}), Agent(name = \"\"\"roxanne\"\"\", traits = {})])
    #     >>> al = AgentList([Agent(name = 'steve', traits = {'age': 22}), Agent(name = 'steve', traits = {'hair': 'brown'})])
    #     >>> al.collapse()
    #     AgentList([Agent(name = \"\"\"steve\"\"\", traits = {'age': 22, 'hair': 'brown'})])
    #     >>> AgentList.example().collapse(warn_about_none_name = False)
    #     AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
    #     """
    #     new_agent_list = AgentList()
    #     warned_about_none_name = False
    #     d = {}
    #     for agent in self:
    #         if agent.name is None:
    #             if not warned_about_none_name and warn_about_none_name:
    #                 warnings.warn("Agent has no name, so it will be ignored.")
    #                 warned_about_none_name = True
    #         if agent.name not in d:
    #             d[agent.name] = agent
    #         else:
    #             d[agent.name].traits.update(agent.traits)
    #     for name, agent in d.items():
    #         new_agent_list.append(agent)
    #     return new_agent_list

    @wraps(AgentListTraitOperations.rename)
    def rename(self, old_name: str, new_name: str) -> AgentList:
        return self._agent_list_trait_operations.rename(old_name, new_name)

    @wraps(AgentListTraitOperations.select)
    def select(self, *traits) -> AgentList:
        return self._agent_list_trait_operations.select(*traits)

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

    def give_uuid_names(self) -> None:
        """Give the agents uuid names."""
        import uuid

        for agent in self:
            agent.name = str(uuid.uuid4())
        return None

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

    @wraps(AgentListJoiner._join)
    def _join(self, other: "AgentList", join_type: str = "inner") -> AgentList:
        return self._agent_list_joiner._join(other, join_type=join_type)

    @wraps(AgentListJoiner.join)
    def join(self, other: "AgentList", join_type: str = "inner") -> "AgentList":
        return self._agent_list_joiner.join(other, join_type=join_type)

    @classmethod
    @wraps(AgentListJoiner.join_multiple)
    def join_multiple(
        cls, *agent_lists: "AgentList", join_type: str = "inner"
    ) -> "AgentList":
        return AgentListJoiner.join_multiple(*agent_lists, join_type=join_type)

    @wraps(AgentListFilter.filter)
    def filter(self, expression: str) -> AgentList:
        return self._agent_list_filter.filter(expression)

    @property
    @wraps(AgentListTraitOperations.all_traits.fget)
    def all_traits(self) -> list[str]:
        return self._agent_list_trait_operations.all_traits

    @classmethod
    @wraps(AgentListBuilder.from_source)
    def from_source(
        cls,
        source_type_or_data,
        *args,
        instructions: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        name_field: Optional[str] = None,
        **kwargs,
    ) -> "AgentList":
        return AgentListBuilder.from_source(
            source_type_or_data,
            *args,
            instructions=instructions,
            codebook=codebook,
            name_field=name_field,
            **kwargs,
        )

    @wraps(AgentListTraitOperations.translate_traits)
    def translate_traits(self, codebook: dict[str, str]):
        return self._agent_list_trait_operations.translate_traits(codebook)

    @wraps(AgentListTraitOperations.remove_trait)
    def remove_trait(self, trait: str):
        return self._agent_list_trait_operations.remove_trait(trait)

    @property
    def names(self) -> List[str]:
        """Returns the names of the agents in the AgentList."""
        return [agent.name for agent in self.data]

    @wraps(AgentListTraitOperations.add_trait)
    def add_trait(self, trait: str, values: List[Any]) -> AgentList:
        return self._agent_list_trait_operations.add_trait(trait, values)

    @wraps(AgentListTraitOperations.numberify)
    def numberify(self) -> AgentList:
        return self._agent_list_trait_operations.numberify()

    @wraps(AgentListTraitOperations.filter_na)
    def filter_na(self, fields: Union[str, List[str]] = "*") -> AgentList:
        return self._agent_list_trait_operations.filter_na(fields)

    @classmethod
    @wraps(AgentListFactories.from_csv)
    def from_csv(
        cls,
        file_path: str,
        name_field: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        instructions: Optional[str] = None,
    ) -> "AgentList":
        return AgentListFactories.from_csv(
            file_path, name_field=name_field, codebook=codebook, instructions=instructions,
        )

    @classmethod
    @wraps(AgentListFactories.from_results)
    def from_results(
        cls, results: "Results", question_names: Optional[List[str]] = None
    ) -> "AgentList":
        return AgentListFactories.from_results(results, question_names)

    @staticmethod
    @wraps(AgentListFactories.get_codebook)
    def get_codebook(file_path: str) -> dict:
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

    @wraps(AgentListSerializer.to_dict)
    def to_dict(self, sorted=False, add_edsl_version=True, full_dict=False):
        return self._agent_list_serializer.to_dict(
            sorted=sorted, add_edsl_version=add_edsl_version, full_dict=full_dict
        )

    @wraps(AgentListSerializer.to_jsonl)
    def to_jsonl(self, filename: Union[str, Path, None] = None) -> Optional[str]:
        return self._agent_list_serializer.to_jsonl(filename=filename)

    @classmethod
    @wraps(AgentListSerializer.from_jsonl)
    def from_jsonl(cls, source: Union[str, Path, Iterable[str]]) -> AgentList:
        return AgentListSerializer.from_jsonl(source)

    @classmethod
    @wraps(AgentListSerializer.iter_agents_from_jsonl)
    def iter_agents_from_jsonl(
        cls, source: Union[str, Path, Iterable[str]]
    ) -> Generator[Agent, None, None]:
        return AgentListSerializer.iter_agents_from_jsonl(source)

    def __eq__(self, other: AgentList) -> bool:
        return self.to_dict(sorted=True, add_edsl_version=False) == other.to_dict(
            sorted=True, add_edsl_version=False
        )

    @wraps(AgentListRepresentation.repr)
    def __repr__(self):
        return self._agent_list_representation.repr()

    @wraps(AgentListRepresentation.eval_repr)
    def _eval_repr_(self) -> str:
        return self._agent_list_representation.eval_repr()

    @wraps(AgentListRepresentation.summary_repr)
    def _summary_repr(self, MAX_AGENTS: int = 10, MAX_TRAITS: int = 10) -> str:
        return self._agent_list_representation.summary_repr(MAX_AGENTS, MAX_TRAITS)

    @wraps(AgentListRepresentation.summary)
    def _summary(self) -> dict:
        return self._agent_list_representation.summary()

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

    def to_dataset(self, traits_only: bool = True) -> 'Dataset':
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
    @wraps(AgentListFactories.from_dict)
    def from_dict(cls, data: dict) -> "AgentList":
        return AgentListFactories.from_dict(data)

    @classmethod
    @wraps(AgentListFactories.example)
    def example(
        cls, randomize: bool = False, codebook: Optional[dict[str, str]] = None
    ) -> AgentList:
        return AgentListFactories.example(randomize=randomize, codebook=codebook)

    @classmethod
    @wraps(AgentListFactories.from_list)
    def from_list(
        cls,
        trait_name: str,
        values: List[Any],
        codebook: Optional[dict[str, str]] = None,
    ) -> "AgentList":
        return AgentListFactories.from_list(trait_name, values, codebook=codebook)

    def __mul__(self, other: AgentList) -> AgentList:
        """Takes the cross product of two AgentLists."""
        new_sl = []
        for s1, s2 in list(product(self, other)):
            new_sl.append(s1 + s2)
        return AgentList(new_sl)

    @property
    def codebook(self) -> dict[str, str]:
        """Return the codebook for the AgentList."""
        if self._codebook is None:
            codebook = self[0].codebook
            for i, agent in enumerate(self):
                if agent.codebook != codebook:
                    # Find the differences
                    first_keys = set(codebook.keys())
                    current_keys = set(agent.codebook.keys())

                    missing_keys = first_keys - current_keys
                    extra_keys = current_keys - first_keys
                    different_values = {
                        k
                        for k in (first_keys & current_keys)
                        if codebook[k] != agent.codebook[k]
                    }

                    error_parts = [
                        f"Codebook mismatch: Agent at index {i} has a different codebook than agent at index 0.",
                        "",
                    ]

                    if missing_keys:
                        error_parts.append(
                            f"  Missing keys in agent {i}: {sorted(missing_keys)}"
                        )
                    if extra_keys:
                        error_parts.append(
                            f"  Extra keys in agent {i}: {sorted(extra_keys)}"
                        )
                    if different_values:
                        error_parts.append(
                            f"  Different descriptions for: {sorted(different_values)}"
                        )
                        for key in sorted(different_values):
                            error_parts.append(
                                f"    - '{key}': agent 0 has '{codebook[key]}' vs agent {i} has '{agent.codebook[key]}'"
                            )

                    error_parts.extend(
                        [
                            "",
                            "Fix options:",
                            "  1. Ensure all agents use the same codebook when creating them",
                            "  2. Remove codebooks from all agents if not needed",
                            f"  3. Update agent {i}'s codebook to match agent 0's codebook",
                        ]
                    )

                    raise AgentListError("\n".join(error_parts))
            self._codebook = codebook
        return self._codebook

    @wraps(AgentListCodeGenerator.generate_code)
    def code(self, string=True) -> Union[str, list[str]]:
        return AgentListCodeGenerator.generate_code(self, string=string)

    @classmethod
    @wraps(AgentListFactories.from_scenario_list)
    def from_scenario_list(cls, scenario_list: "ScenarioList") -> "AgentList":
        return AgentListFactories.from_scenario_list(scenario_list)



if __name__ == "__main__":
    import doctest

    # Just run the standard doctests with verbose flag
    doctest.testmod(
        verbose=True, optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    )
