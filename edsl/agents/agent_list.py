"""A list of Agents with event-sourced state management.

AgentList provides a collection of Agent objects with advanced operations.
It uses an event-sourcing architecture where all mutations are captured as events,
enabling version control and immutability patterns.
"""

from __future__ import annotations

# csv import moved to agent_list_factories.py
import sys
import random
import warnings
import logging
from collections import defaultdict
from collections.abc import MutableSequence
from itertools import product

from ..base.decorators import polly_command

from typing import Any, Callable, List, Optional, Union, TYPE_CHECKING

# simpleeval imports moved to agent_list_filter.py

from ..base import Base
from ..utilities import is_notebook, remove_edsl_version, dict_hash, list_split
from ..dataset.dataset_operations_mixin import AgentListOperationsMixin
from ..config import RICH_STYLES

from .agent import Agent

from .exceptions import AgentListError

# Import event-sourcing infrastructure
from ..versioning import GitMixin, event
from ..store import (
    Store,
    Event,
    # Row/Entry Events
    AppendRowEvent,
    UpdateRowEvent,
    RemoveRowsEvent,
    InsertRowEvent,
    ClearEntriesEvent,
    ReplaceAllEntriesEvent,
    ReorderEntriesEvent,
    KeepRowsByIndicesEvent,
    # Field Events
    AddFieldToAllEntriesEvent,
    AddFieldByIndexEvent,
    # Nested Field Events (for traits)
    DropNestedFieldsEvent,
    KeepNestedFieldsEvent,
    RenameNestedFieldEvent,
    AddNestedFieldByIndexEvent,
    TranslateNestedValuesEvent,
    NumberifyNestedFieldsEvent,
    # Agent-Specific Events
    SetAgentNamesEvent,
    CollapseByFieldEvent,
    # Meta Events
    SetMetaEvent,
    apply_event,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..agents import Agent
    from ..jobs import Jobs
    from ..questions import QuestionBase as Question
    from ..surveys import Survey
    from ..scenarios import ScenarioList
    from ..results import Results
    from .agent_list_deltas import AgentListDeltas


# is_iterable function moved to agent_list_trait_operations.py


# EmptyAgentList moved to agent_list_filter.py


class AgentCodec:
    """Codec for Agent objects - handles encoding/decoding for the Store."""

    def encode(self, obj: Union["Agent", dict[str, Any]]) -> dict[str, Any]:
        """Encode an Agent to a dictionary for storage."""
        if isinstance(obj, dict):
            return dict(obj)
        return obj.to_dict(add_edsl_version=False)

    def decode(self, data: dict[str, Any]) -> "Agent":
        """Decode a dictionary back to an Agent object."""
        return Agent.from_dict(data)


class AgentListMeta(Base.__class__):
    """Metaclass for AgentList that enables dynamic service accessor access.
    
    Inherits from Base's metaclass (RegisterSubclassesMeta) to avoid metaclass conflicts.
    
    This metaclass intercepts class-level attribute access (e.g., AgentList.vibes)
    and returns service accessor instances from the edsl.services registry.
    
    Examples:
        >>> accessor = AgentList.vibes  # Returns agent_vibes accessor
    """
    
    def __getattr__(cls, name: str):
        """Called when AgentList.{name} is accessed and {name} isn't found normally."""
        # Lazy import to avoid circular dependencies
        from edsl.services.accessors import get_service_accessor
        
        # Map 'vibes' or 'vibe' to 'agent_vibes' service
        if name in ("vibes", "vibe"):
            service_name = "agent_vibes"
        else:
            service_name = name
        
        accessor = get_service_accessor(service_name, owner_class=cls)
        if accessor is not None:
            return accessor
        
        # Standard AttributeError
        raise AttributeError(f"type object 'AgentList' has no attribute '{name}'")


class AgentList(GitMixin, MutableSequence, Base, AgentListOperationsMixin, metaclass=AgentListMeta):
    """A list of Agents with additional functionality for manipulation and analysis.

    The AgentList class uses an event-sourcing architecture where all mutations are
    captured as events and applied to a Store backend. This enables version control,
    immutability patterns, and integration with git-like operations via GitMixin.

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

    # Event-sourcing infrastructure
    _versioned = "store"
    _store_class = Store
    _event_handler = apply_event
    _codec = AgentCodec()

    # Allowed instance attributes - prevents external code from storing temporary data
    _allowed_attrs = frozenset(
        {
            # Core state
            "store",
            # Properties with setters
            "_codebook",
            # Agent cache (preserves non-serializable methods like answer_question_directly)
            "_agent_cache",
            # GitMixin
            "_git",
            "_needs_git_init",
            "_last_push_result",
        }
    )

    def __getattr__(self, name: str):
        """Intercept attribute access to provide service accessor instances.
        
        This method is called when an attribute isn't found normally on the instance.
        It checks if the attribute name matches a registered service and returns
        the appropriate accessor bound to this AgentList instance.
        
        Examples:
            >>> al = AgentList.example()
            >>> _ = al.vibes  # Returns agent_vibes accessor bound to this instance
        """
        # Lazy import to avoid circular dependencies
        from edsl.services.accessors import get_service_accessor
        
        # Map 'vibes' or 'vibe' to 'agent_vibes' service
        if name in ("vibes", "vibe"):
            service_name = "agent_vibes"
        else:
            service_name = name
        
        accessor = get_service_accessor(service_name, instance=self)
        if accessor is not None:
            return accessor
        
        raise AttributeError(f"'AgentList' object has no attribute '{name}'")

    def __setattr__(self, name: str, value: Any) -> None:
        """Restrict attribute setting to allowed attributes only.

        This prevents external code from using AgentList instances to store
        temporary data, enforcing immutability through the event-based Store mechanism.
        """
        if name in self._allowed_attrs:
            super().__setattr__(name, value)
        else:
            raise AttributeError(
                f"Cannot set attribute '{name}' on AgentList. "
                f"AgentList is immutable - use event-based methods to modify data."
            )

    def _validate_agent_consistency(
        self,
        agent: "Agent",
        expected_codebook: dict,
        expected_template: Optional[str],
        expected_instruction: Optional[str],
    ) -> None:
        """Validate that an agent has consistent codebook, template, and instruction.

        This method ensures all agents in an AgentList have identical codebook,
        traits_presentation_template, and instruction values. If an agent has
        different values, an AgentListError is raised.

        Args:
            agent: The agent to validate
            expected_codebook: The expected codebook value (from first agent or list)
            expected_template: The expected traits_presentation_template value
            expected_instruction: The expected instruction value

        Raises:
            AgentListError: If the agent's values differ from expected values
        """
        if agent.codebook != expected_codebook:
            raise AgentListError(
                f"Agent codebook {agent.codebook} differs from AgentList codebook {expected_codebook}. "
                f"All agents in an AgentList must have the same codebook."
            )

        agent_template = agent.traits_presentation_template
        if agent_template != expected_template:
            raise AgentListError(
                f"Agent traits_presentation_template differs from AgentList template. "
                f"All agents in an AgentList must have the same traits_presentation_template."
            )

        agent_instruction = agent.instruction
        if agent_instruction != expected_instruction:
            raise AgentListError(
                f"Agent instruction differs from AgentList instruction. "
                f"All agents in an AgentList must have the same instruction."
            )

    def __init__(
        self,
        data: Optional[list["Agent"] | str] = None,
        codebook: Optional[dict[str, str]] = None,
        traits_presentation_template: Optional[str] = None,
        instruction: Optional[str] = None,
    ):
        """Initialize a new AgentList.

        >>> from edsl import Agent
        >>> al = AgentList([Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5}),
        ...                Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> len(al)
        2
        >>> al[0].traits['age']
        22
        >>> al_with_codebook = AgentList([Agent(traits = {'age': 22})], codebook={'age': 'Age in years'})
        >>> al_with_codebook[0].codebook
        {'age': 'Age in years'}
        >>> al_with_template = AgentList([Agent(traits = {'age': 22})],
        ...                              traits_presentation_template="Age: {{age}}")
        >>> al_with_template.traits_presentation_template
        'Age: {{age}}'
        >>> al_with_instruction = AgentList([Agent(traits = {'age': 22})],
        ...                                 instruction="Answer as a person of this age")
        >>> al_with_instruction.instruction
        'Answer as a person of this age'

        Args:
            data: A list of Agent objects. If None, creates an empty AgentList.
            codebook: Optional dictionary mapping trait names to descriptions.
                      If provided, will be applied to all agents in the list.
            traits_presentation_template: Optional Jinja2 template for formatting traits.
                      If provided, will be applied to all agents in the list.
            instruction: Optional instruction text for how agents should behave.
                      If provided, will be applied to all agents in the list.

        Raises:
            AgentListError: If agents have inconsistent codebook, traits_presentation_template,
                           or instruction values (when the respective parameter is not explicitly provided).
        """
        super().__init__()  # Initialize GitMixin

        data_to_store = []
        original_agents = (
            []
        )  # Cache original agents to preserve non-serializable methods
        canonical_codebook = codebook
        canonical_template = traits_presentation_template
        canonical_instruction = instruction

        if data is not None and isinstance(data, str):
            al = AgentList.pull(data)
            if codebook is not None:
                raise ValueError(
                    "Codebook cannot be provided when pulling from a remote source"
                )
            if traits_presentation_template is not None:
                raise ValueError(
                    "traits_presentation_template cannot be provided when pulling from a remote source"
                )
            if instruction is not None:
                raise ValueError(
                    "instruction cannot be provided when pulling from a remote source"
                )
            canonical_codebook = al.codebook
            canonical_template = al.traits_presentation_template
            canonical_instruction = al.instruction
            for item in al.data:
                data_to_store.append(self._codec.encode(item))
                original_agents.append(item)
        else:
            agents_list = list(data or [])

            # Extract canonical values from first agent (if not explicitly provided)
            if agents_list:
                first_agent = agents_list[0]

                codebook_provided = codebook is not None
                template_provided = traits_presentation_template is not None
                instruction_provided = instruction is not None

                # If not explicitly provided, extract from first agent
                if not codebook_provided:
                    canonical_codebook = first_agent.codebook
                if not template_provided:
                    canonical_template = first_agent.traits_presentation_template
                if not instruction_provided:
                    canonical_instruction = first_agent.instruction

                # Validate consistency for values not explicitly provided
                # (explicit values override all agents; extracted values must match)
                for agent in agents_list:
                    if not codebook_provided and agent.codebook != canonical_codebook:
                        raise AgentListError(
                            f"Agent codebook {agent.codebook} differs from AgentList codebook {canonical_codebook}. "
                            f"All agents in an AgentList must have the same codebook."
                        )
                    if (
                        not template_provided
                        and agent.traits_presentation_template != canonical_template
                    ):
                        raise AgentListError(
                            f"Agent traits_presentation_template differs from AgentList template. "
                            f"All agents in an AgentList must have the same traits_presentation_template."
                        )
                    if (
                        not instruction_provided
                        and agent.instruction != canonical_instruction
                    ):
                        raise AgentListError(
                            f"Agent instruction differs from AgentList instruction. "
                            f"All agents in an AgentList must have the same instruction."
                        )

            for item in agents_list:
                # Encode Agent objects to dicts for primitive store
                data_to_store.append(self._codec.encode(item))
                original_agents.append(item)

        # Initialize the Store with encoded agents and metadata
        self.store = Store(
            entries=data_to_store,
            meta={
                "codebook": canonical_codebook or {},
                "traits_presentation_template": canonical_template,
                "instruction": canonical_instruction,
            },
        )
        self._codebook = None  # Will be read from store.meta
        # Cache original agents to preserve non-serializable methods like answer_question_directly
        self._agent_cache = original_agents if original_agents else None

    def _apply_list_attributes(self, agent: "Agent") -> None:
        """Apply list-level codebook, template, and instruction to an agent without changing 'explicitly set' flags.

        This method applies values from store.meta to an agent while preserving the
        agent's original 'set' flags. This ensures that agents accessed through the
        list don't appear different in serialization than they did originally.
        """
        codebook = self.store.meta.get("codebook", {})
        template = self.store.meta.get("traits_presentation_template")
        instruction = self.store.meta.get("instruction")

        # Apply codebook (descriptor handles storage)
        agent.codebook = codebook

        # Apply template directly to internal attribute to avoid setting the "explicitly set" flag
        if template is not None:
            agent._traits_presentation_template = template
            # Invalidate cached hash if it exists
            if hasattr(agent, "_cached_hash"):
                delattr(agent, "_cached_hash")

        # Apply instruction directly to internal attribute to avoid setting the "set_instructions" flag
        if instruction is not None:
            agent._instruction = instruction
            # Invalidate cached hash if it exists
            if hasattr(agent, "_cached_hash"):
                delattr(agent, "_cached_hash")

    @property
    def data(self) -> List["Agent"]:
        """Return Agent objects, using cache if available to preserve non-serializable methods.

        Applies the canonical codebook and traits_presentation_template from store.meta
        to all returned agents, ensuring consistency across the list.
        """
        # If we have cached agents and the count matches, use them
        # (cache is valid only if no structural changes were made)
        cache = getattr(self, "_agent_cache", None)
        if cache is not None and len(cache) == len(self.store.entries):
            # Apply canonical values to cached agents
            for agent in cache:
                self._apply_list_attributes(agent)
            return cache

        # Otherwise, decode from store (loses non-serializable methods)
        agents = []
        for row in self.store.entries:
            agent = self._codec.decode(row)
            # Apply canonical values from list
            self._apply_list_attributes(agent)
            agents.append(agent)
        return agents

    @event
    def append(self, item: "Agent") -> AppendRowEvent:
        """Add an agent to the list.

        If the list is empty, the agent's codebook, traits_presentation_template, and
        instruction become the canonical values for the list. Otherwise, the agent must
        have matching values or an AgentListError is raised.

        Raises:
            AgentListError: If the agent's codebook, traits_presentation_template, or
                instruction differs from the list's canonical values.

        Returns:
            AgentList: Self with the agent added.
        """
        is_first_agent = len(self.store.entries) == 0

        if not is_first_agent:
            expected_codebook = self.store.meta.get("codebook", {})
            expected_template = self.store.meta.get("traits_presentation_template")
            expected_instruction = self.store.meta.get("instruction")
            self._validate_agent_consistency(
                item, expected_codebook, expected_template, expected_instruction
            )

        # If this was the first agent, update meta with its values
        if is_first_agent:
            self.store.meta["codebook"] = item.codebook
            self.store.meta["traits_presentation_template"] = (
                item.traits_presentation_template
            )
            self.store.meta["instruction"] = item.instruction

        # Invalidate cache since we modified the store
        self._agent_cache = None

        # Return the event - @event decorator handles applying to store AND tracking for git
        return AppendRowEvent(row=self._codec.encode(item))

    # Required MutableSequence abstract methods
    def __getitem__(self, index):
        """Get item at index.

        Example:
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'a': 12})])
            >>> al[0].traits['a']
            12
        """
        if isinstance(index, slice):
            return self.__class__(list(self.data[index]), self.codebook.copy())
        return self.data[index]

    @event
    def __setitem__(self, index, value) -> UpdateRowEvent:
        """Set item at index.

        The agent being set must have matching codebook, traits_presentation_template,
        and instruction values or an AgentListError is raised.

        Raises:
            AgentListError: If the agent's codebook, traits_presentation_template, or
                instruction differs from the list's canonical values.
        """
        expected_codebook = self.store.meta.get("codebook", {})
        expected_template = self.store.meta.get("traits_presentation_template")
        expected_instruction = self.store.meta.get("instruction")
        self._validate_agent_consistency(
            value, expected_codebook, expected_template, expected_instruction
        )
        return UpdateRowEvent(index=index, row=self._codec.encode(value))

    @event
    def __delitem__(self, index) -> RemoveRowsEvent:
        """Delete item at index."""
        return RemoveRowsEvent(indices=(index,))

    def __len__(self):
        """Return number of items."""
        return len(self.store.entries)

    def __iter__(self):
        """Iterate over agents using the data property."""
        return iter(self.data)

    @event
    def insert(self, index, value) -> InsertRowEvent:
        """Insert value at index.

        If the list is empty, the agent's codebook, traits_presentation_template, and
        instruction become the canonical values for the list. Otherwise, the agent must
        have matching values or an AgentListError is raised.

        Raises:
            AgentListError: If the agent's codebook, traits_presentation_template, or
                instruction differs from the list's canonical values.
        """
        if len(self.store.entries) > 0:
            expected_codebook = self.store.meta.get("codebook", {})
            expected_template = self.store.meta.get("traits_presentation_template")
            expected_instruction = self.store.meta.get("instruction")
            self._validate_agent_consistency(
                value, expected_codebook, expected_template, expected_instruction
            )

        return InsertRowEvent(index=index, row=self._codec.encode(value))

    @event
    def clear(self) -> ClearEntriesEvent:
        """Remove all agents from the list."""
        return ClearEntriesEvent()

    def at(self, index: int) -> "Agent":
        """Get the agent at the specified index position."""
        return self.data[index]

    def first(self) -> "Agent":
        """Get the first agent in the list."""
        return self.data[0]

    def last(self) -> "Agent":
        """Get the last agent in the list."""
        return self.data[-1]

    @event
    def set_instruction(self, instruction: str) -> SetMetaEvent:
        """Set the instruction for all agents in the list.

        This updates the list-level instruction which is applied to all agents
        when they are accessed. The instruction is stored in store.meta.

        Args:
            instruction: The instruction to set.

        Returns:
            SetMetaEvent: Event that sets instruction in store.meta.
        """
        # Invalidate cache so new instruction is applied on next access
        self._agent_cache = None
        return SetMetaEvent(key="instruction", value=instruction)

    def set_dynamic_traits(self, function: Callable) -> "AgentList":
        """Set the dynamic traits for all agents in the list.

        Note: This method bypasses the event-sourcing system because callable
        functions cannot be serialized. Dynamic traits are applied to the
        Agent objects when accessed but are not persisted in the Store.
        You should call this method after all event-based modifications are complete.

        Args:
            function: The function to set.

        Returns:
            AgentList: self for method chaining.
        """
        # This bypasses event-sourcing since functions can't be serialized
        for agent in self.data:
            agent.traits_manager.set_dynamic_function(function)
        return self

    def set_dynamic_traits_from_question_map(
        self, q_to_traits: dict[str, list[str]]
    ) -> "AgentList":
        """Configure dynamic traits for each agent from a question→traits mapping.

        Note: This method bypasses the event-sourcing system because callable
        functions cannot be serialized. Dynamic traits are applied to the
        Agent objects when accessed but are not persisted in the Store.
        Since agents are decoded fresh each time from the Store, you must
        apply this function each time you need to use dynamic traits.

        Each agent will get a dynamic traits function that, when asked a question whose
        ``question_name`` is present in ``q_to_traits``, returns a dict mapping the
        corresponding trait name(s) to the agent's original static value(s) for those trait(s).

        A warning is emitted if the set of mapped trait names does not exactly equal the
        set of trait keys present in this AgentList.

        Args:
            q_to_traits: Mapping from question name to list of trait keys, e.g.
                ``{"geo": ["hometown"], "cuisine": ["food"]}``.

        Returns:
            AgentList: self for method chaining.

        Examples:
            To use dynamic traits, work directly with Agent objects:

            >>> from edsl import Agent
            >>> agent = Agent(name="Alice", traits={'hometown': 'Boston', 'food': 'beans'})
            >>> def f(question, base=agent.traits):
            ...     if question.question_name == 'geo':
            ...         return {'hometown': base['hometown']}
            ...     return {}
            >>> agent.dynamic_traits_function = f
            >>> class Q:
            ...     def __init__(self, name): self.question_name = name
            >>> agent.dynamic_traits_function(Q('geo'))['hometown']
            'Boston'
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

    @event
    def add_instructions(self, instructions: str) -> SetMetaEvent:
        """Apply instructions to all agents in the list.

        This method provides a more intuitive name for setting instructions
        on all agents, avoiding the need to iterate manually. The instruction
        is stored at the list level in store.meta and applied to all agents
        when they are accessed.

        Args:
            instructions: The instructions to apply to all agents.

        Returns:
            AgentList: A new AgentList with updated instructions.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> agents = AgentList([Agent(traits={'age': 30}), Agent(traits={'age': 40})])
            >>> agents = agents.add_instructions("Answer as if you were this age")
            >>> agents[0].instruction
            'Answer as if you were this age'
        """
        # Invalidate cache so new instruction is applied on next access
        self._agent_cache = None
        return SetMetaEvent(key="instruction", value=instructions)

    def __add__(self, other: AgentList) -> AgentList:
        """Add two AgentLists together."""
        # have to have the same traits + codebook
        if self.trait_keys != other.trait_keys:
            raise ValueError("AgentLists must have the same traits and codebook")

        if hasattr(self, "codebook") and hasattr(other, "codebook"):
            if self.codebook != other.codebook:
                raise ValueError("AgentLists must have the same codebook")

        if self.traits_presentation_template != other.traits_presentation_template:
            raise ValueError(
                "AgentLists must have the same traits_presentation_template"
            )

        if self.instruction != other.instruction:
            raise ValueError("AgentLists must have the same instruction")

        return AgentList(
            self.data + other.data,
            codebook=self.codebook if hasattr(self, "codebook") else None,
            traits_presentation_template=self.traits_presentation_template,
            instruction=self.instruction,
        )

    @property
    def trait_keys(self) -> List[str]:
        """Get the trait keys for the AgentList."""
        keys = set()
        for agent in self.data:
            keys.update(agent.traits.keys())
        return list(keys)

    @classmethod
    def manage(cls):
        from ..widgets.agent_list_manager import AgentListManagerWidget

        return AgentListManagerWidget()

    def edit(self):
        from ..widgets.agent_list_builder import AgentListBuilderWidget

        return AgentListBuilderWidget(self)

    @event
    def set_traits_presentation_template(
        self, traits_presentation_template: str
    ) -> SetMetaEvent:
        """Set the traits presentation template for all agents in the list.

        This updates the canonical template in store.meta. When agents are
        accessed via the data property, they will receive this template value,
        ensuring all agents in the list have consistent templates.

        Args:
            traits_presentation_template: The Jinja2 template to set for all agents.

        Returns:
            SetMetaEvent: Event that updates the template in store.meta.
        """
        return SetMetaEvent(
            key="traits_presentation_template", value=traits_presentation_template
        )

    @event
    def shuffle(self, seed: Optional[str] = None) -> ReorderEntriesEvent:
        """Randomly shuffle the agents in place.

        Args:
            seed: Optional seed for the random number generator to ensure reproducibility.

        Returns:
            AgentList: The shuffled AgentList.
        """
        indices = list(range(len(self.store.entries)))
        if seed is not None:
            random.seed(seed)
        random.shuffle(indices)
        return ReorderEntriesEvent(new_order=tuple(indices))

    @event
    def sample(self, n: int, seed: Optional[str] = None) -> KeepRowsByIndicesEvent:
        """Return a random sample of agents.

        Args:
            n: The number of agents to sample.
            seed: Optional seed for the random number generator to ensure reproducibility.

        Returns:
            AgentList: A new AgentList with sampled agents.
        """
        if seed:
            random.seed(seed)
        indices = random.sample(range(len(self.store.entries)), n)
        return KeepRowsByIndicesEvent(indices=tuple(indices))

    @polly_command
    def split(
        self, frac_left: float, seed: Optional[int] = None
    ) -> tuple[AgentList, AgentList]:
        """Split the AgentList into two random groups.

        Randomly assigns agents to two groups (left and right) based on the specified
        fraction. Useful for creating train/test splits or other random partitions.

        Args:
            frac_left: Fraction (0-1) of agents to assign to the left group.
            seed: Optional random seed for reproducibility.

        Returns:
            tuple[AgentList, AgentList]: A tuple containing (left, right) AgentLists.

        Raises:
            ValueError: If frac_left is not between 0 and 1.

        Examples:
            Split an agent list 70/30:

            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'id': i}) for i in range(10)])
            >>> left, right = al.split(0.7, seed=42)
            >>> len(left)
            7
            >>> len(right)
            3

            Create reproducible splits:

            >>> al = AgentList([Agent(traits={'id': i}) for i in range(5)])
            >>> left1, right1 = al.split(0.6, seed=123)
            >>> left2, right2 = al.split(0.6, seed=123)
            >>> len(left1) == len(left2) and len(right1) == len(right2)
            True
        """
        return list_split(self, frac_left, seed)

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

    @event
    def drop(self, *field_names: Union[str, List[str]]) -> DropNestedFieldsEvent:
        """Drop field(s) from all agents in the AgentList.

        Args:
            *field_names: The name(s) of the field(s) to drop. Can be:
                - Single field name: drop("age")
                - Multiple field names: drop("age", "height")
                - List of field names: drop(["age", "height"])

        Returns:
            AgentList: A new AgentList with the specified fields dropped.

        Examples:
            Drop a single trait from all agents:

            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al = al.drop("age")
            >>> al[0].traits
            {'hair': 'brown', 'height': 5.5}

            Drop multiple traits using separate arguments:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al = al.drop("age", "height")
            >>> al[0].traits
            {'hair': 'brown'}

            Drop multiple traits using a list:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al = al.drop(["age", "height"])
            >>> al[0].traits
            {'hair': 'brown'}
        """
        # Flatten field names (handle lists and individual args)
        fields_to_drop = []
        for f in field_names:
            if isinstance(f, list):
                fields_to_drop.extend(f)
            else:
                fields_to_drop.append(f)

        return DropNestedFieldsEvent(
            parent_field="traits", fields=tuple(fields_to_drop)
        )

    @event
    def keep(self, *field_names: Union[str, List[str]]) -> KeepNestedFieldsEvent:
        """Keep only the specified fields from all agents in the AgentList.

        Args:
            *field_names: The name(s) of the field(s) to keep. Can be:
                - Single field name: keep("age")
                - Multiple field names: keep("age", "height")
                - List of field names: keep(["age", "height"])

        Returns:
            AgentList: A new AgentList with only the specified fields kept.

        Examples:
            Keep a single trait for all agents:

            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al = al.keep("age")
            >>> al[0].traits
            {'age': 30}

            Keep multiple traits using separate arguments:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al = al.keep("age", "height")
            >>> al[0].traits
            {'age': 30, 'height': 5.5}

            Keep multiple traits using a list:

            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al = al.keep(["age", "height"])
            >>> al[0].traits
            {'age': 30, 'height': 5.5}
        """
        # Flatten field names
        fields_to_keep = []
        for f in field_names:
            if isinstance(f, list):
                fields_to_keep.extend(f)
            else:
                fields_to_keep.append(f)

        return KeepNestedFieldsEvent(
            parent_field="traits", fields=tuple(fields_to_keep)
        )

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

    @event
    def collapse(self, warn_about_none_name: bool = True) -> CollapseByFieldEvent:
        """All agents with the same name have their traits combined.

        >>> al = AgentList([Agent(name = 'steve'), Agent(name = 'roxanne')])
        >>> al = al.collapse()
        >>> len(al)
        2
        >>> al = AgentList([Agent(name = 'steve', traits = {'age': 22}), Agent(name = 'steve', traits = {'hair': 'brown'})])
        >>> al = al.collapse()
        >>> len(al)
        1
        >>> al[0].traits
        {'age': 22, 'hair': 'brown'}
        >>> al = AgentList.example()
        >>> al = al.collapse(warn_about_none_name = False)
        >>> len(al)
        1
        """
        warned_about_none_name = False
        d = {}  # name -> merged entry dict

        for entry in self.store.entries:
            name = entry.get("name")
            if name is None:
                if not warned_about_none_name and warn_about_none_name:
                    warnings.warn("Agent has no name, so it will be ignored.")
                    warned_about_none_name = True

            if name not in d:
                d[name] = dict(entry)
            else:
                # Merge traits
                if "traits" in entry and "traits" in d[name]:
                    d[name]["traits"].update(entry["traits"])
                elif "traits" in entry:
                    d[name]["traits"] = dict(entry["traits"])

        result_entries = tuple(d.values())
        return CollapseByFieldEvent(
            group_field="name", merge_field="traits", result_entries=result_entries
        )

    @event
    def rename(self, old_name: str, new_name: str) -> RenameNestedFieldEvent:
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
            >>> al = al.rename('a', 'c')
            >>> sorted(al[0].traits.items())
            [('b', 1), ('c', 1)]
        """
        return RenameNestedFieldEvent(
            parent_field="traits", old_name=old_name, new_name=new_name
        )

    @event
    def select(self, *traits) -> KeepNestedFieldsEvent:
        """Select only specified traits from all agents.

        Args:
            *traits: Variable number of trait names to keep.

        Returns:
            AgentList: A new AgentList with only selected traits.

        Examples:
            >>> from edsl import Agent
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
            ...                Agent(traits = {'a': 1, 'b': 2})])
            >>> al = al.select('a')
            >>> al[0].traits
            {'a': 1}
        """
        return KeepNestedFieldsEvent(parent_field="traits", fields=tuple(traits))

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

    @event
    def give_uuid_names(self) -> SetAgentNamesEvent:
        """Give the agents uuid names."""
        import uuid

        names = tuple(str(uuid.uuid4()) for _ in self.store.entries)
        return SetAgentNamesEvent(names=names)

    @event
    def give_names(
        self,
        *trait_keys: str,
        remove_traits: bool = True,
        separator: str = ",",
        force_name: bool = False,
    ) -> ReplaceAllEntriesEvent:
        """Give names to agents based on the values of the specified traits.

        >>> from edsl import Agent
        >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
        ...                Agent(traits = {'a': 1, 'b': 2})])
        >>> al = al.give_names('a')
        >>> al[0].name
        '1'
        """
        if not force_name:
            for entry in self.store.entries:
                if entry.get("name") is not None:
                    raise AgentListError(
                        "Agents already have names. Use force_name=True to override."
                    )

        new_entries = []
        for entry in self.store.entries:
            new_entry = dict(entry)
            traits = new_entry.get("traits", {})

            # Build name from trait values
            trait_values = [str(traits.get(key, "")) for key in trait_keys]
            new_name = separator.join(trait_values)
            new_entry["name"] = new_name

            # Remove traits used for naming if requested
            if remove_traits and "traits" in new_entry:
                new_traits = dict(new_entry["traits"])
                for key in trait_keys:
                    new_traits.pop(key, None)
                new_entry["traits"] = new_traits

            new_entries.append(new_entry)

        return ReplaceAllEntriesEvent(entries=tuple(new_entries))

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
        # Create a duplicate and apply naming via the event-decorated method
        new_agent_list = self.duplicate()
        return new_agent_list.give_names(
            *trait_keys,
            remove_traits=remove_traits,
            separator=separator,
            force_name=force_name,
        )

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

    @event
    def filter(self, expression: str) -> RemoveRowsEvent:
        """Filter agents based on a boolean expression.

        Args:
            expression: A string containing a boolean expression to evaluate against
                each agent's traits.

        Returns:
            AgentList: A new AgentList with only matching agents.

        Examples:
            >>> from edsl import Agent
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
            ...                Agent(traits = {'a': 1, 'b': 2})])
            >>> al = al.filter("b == 2")
            >>> len(al)
            1
            >>> al[0].traits
            {'a': 1, 'b': 2}

            Filter by name:

            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}, name = 'steve'),
            ...                Agent(traits = {'a': 1, 'b': 2}, name = 'roxanne')])
            >>> al = al.filter("name == 'steve'")
            >>> len(al)
            1
            >>> al[0].name
            'steve'
        """
        from simpleeval import simple_eval

        indices_to_remove = []
        for i, agent in enumerate(self.data):
            # Build names dict from agent traits and attributes
            names = dict(agent.traits)
            if agent.name is not None:
                names["name"] = agent.name

            try:
                result = simple_eval(expression, names=names)
                if not result:
                    indices_to_remove.append(i)
            except Exception as e:
                raise AgentListError(
                    f"Error evaluating '{expression}' on agent {i}: {e}"
                )

        return RemoveRowsEvent(indices=tuple(indices_to_remove))

    def vibe_filter(
        self,
        criteria: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.1,
        show_expression: bool = False,
    ) -> "AgentList":
        """
        Filter the agent list using natural language criteria.

        This method uses an LLM to generate a filter expression based on
        natural language criteria, then applies it using the agent list's filter method.

        Parameters:
            criteria: Natural language description of the filtering criteria.
                Examples:
                - "Keep only people over 30"
                - "Only engineers"
                - "Agents in Boston"
                - "Remove anyone under 25"
            model: OpenAI model to use for generating the filter (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.1 for consistent logic)
            show_expression: If True, prints the generated filter expression

        Returns:
            AgentList: A new AgentList containing only agents that match the criteria

        Examples:
            >>> from edsl import Agent, AgentList
            >>> agents = AgentList([
            ...     Agent(name='Alice', traits={'age': 25, 'occupation': 'engineer'}),
            ...     Agent(name='Bob', traits={'age': 35, 'occupation': 'teacher'}),
            ... ])
            >>> filtered = agents.vibe_filter("Only people over 30")  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - The LLM generates a filter expression using trait names directly
            - Uses the agent list's built-in filter() method for safe evaluation
            - Use show_expression=True to see the generated filter logic
        """
        from edsl.dataset.vibes.vibe_filter import VibeFilter

        # Get trait names and sample data
        trait_names = self.all_traits

        # Get a few sample agents' traits to help the LLM understand the data structure
        sample_dicts = []
        for agent in self[:5]:  # First 5 agents
            sample_dicts.append(dict(agent.traits))

        # Create the filter generator
        filter_gen = VibeFilter(model=model, temperature=temperature)

        # Generate the filter expression
        filter_expr = filter_gen.create_filter(trait_names, sample_dicts, criteria)

        if show_expression:
            print(f"Generated filter expression: {filter_expr}")

        # Use the agent list's built-in filter method which returns AgentList
        return self.filter(filter_expr)

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
        source_type_or_data,
        *args,
        instructions: Optional[str] = None,
        codebook: Optional[dict[str, str]] = None,
        name_field: Optional[str] = None,
        **kwargs,
    ) -> "AgentList":
        """Create an AgentList from a specified source type or infer it automatically.

        This method serves as the main entry point for creating AgentList objects,
        providing a unified interface for various data sources.

        **Two modes of operation:**

        1. **Explicit source type** (2+ arguments): Specify the source type explicitly
           Example: AgentList.from_source('csv', 'data.csv')

        2. **Auto-detect source** (1 argument): Pass only the data and let it infer the type
           Example: AgentList.from_source('data.csv') or AgentList.from_source({'key': [1,2,3]})

        Args:
            source_type_or_data: Either:
                - A string specifying the source type ('csv', 'excel', 'pdf', etc.)
                  when using explicit mode with additional args
                - The actual data source (file path, URL, dict, DataFrame, etc.)
                  when using auto-detect mode
            *args: Positional arguments to pass to the source-specific method
                   (only used in explicit mode).
            instructions: Optional instructions to apply to all created agents.
            codebook: Optional dictionary mapping trait names to descriptions, or a path to a CSV file.
                     If a CSV file is provided, it should have 2 columns: original keys and descriptions.
                     Keys will be automatically converted to pythonic names.
            name_field: The name of the field to use as the agent name (for CSV/Excel sources).
            **kwargs: Additional keyword arguments to pass to the source-specific method.

        Returns:
            An AgentList object created from the specified source.

        Examples:
            >>> # Explicit source type (original behavior)
            >>> # agents = AgentList.from_source(
            >>> #     'csv', 'agents.csv',
            >>> #     instructions="Answer as if you were the person described"
            >>> # )
            >>> #
            >>> # Auto-detect source type (new behavior)
            >>> # agents = AgentList.from_source(
            >>> #     'agents.csv',
            >>> #     instructions="Answer as if you were the person described"
            >>> # )
            >>> #
            >>> # Auto-detect from dictionary
            >>> # agents = AgentList.from_source(
            >>> #     {'age': [25, 30], 'name': ['Alice', 'Bob']},
            >>> #     instructions="You are this person"
            >>> # )
        """
        from .agent_list_builder import AgentListBuilder

        return AgentListBuilder.from_source(
            source_type_or_data,
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

    @event
    def translate_traits(self, codebook: dict[str, str]) -> TranslateNestedValuesEvent:
        """Translate traits to a new codebook.

        :param codebook: The new codebook mapping trait names to value mappings.

        >>> al = AgentList.example()
        >>> codebook = {'hair': {'brown':'Secret word for green'}}
        >>> al = al.translate_traits(codebook)
        >>> al[0].traits['hair']
        'Secret word for green'
        """
        # Convert codebook to the event format: (field_name, ((old, new), ...))
        value_map = tuple(
            (trait_name, tuple(value_map.items()))
            for trait_name, value_map in codebook.items()
        )
        return TranslateNestedValuesEvent(parent_field="traits", value_map=value_map)

    @event
    def remove_trait(self, trait: str) -> DropNestedFieldsEvent:
        """Remove a trait from all agents.

        :param trait: The trait to remove.
        >>> from edsl import Agent
        >>> al = AgentList([Agent({'age': 22, 'hair': 'brown', 'height': 5.5}), Agent({'age': 22, 'hair': 'brown', 'height': 5.5})])
        >>> al = al.remove_trait('age')
        >>> al[0].traits
        {'hair': 'brown', 'height': 5.5}
        """
        return DropNestedFieldsEvent(parent_field="traits", fields=(trait,))

    @property
    def names(self) -> List[str]:
        """Returns the names of the agents in the AgentList."""
        return [agent.name for agent in self.data]

    @event
    def add_trait(self, trait: str, values: List[Any]) -> AddNestedFieldByIndexEvent:
        """Adds a new trait to every agent, with values taken from values.

        :param trait: The name of the trait.
        :param values: The values(s) of the trait. If a single value is passed, it is used for all agents.

        >>> al = AgentList.example()
        >>> al = al.add_trait('new_trait', 1)
        >>> al[0].traits['new_trait']
        1
        >>> al = AgentList.example()
        >>> al = al.add_trait('new_trait', [1, 2, 3])  # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
        ...
        AgentListError: The passed values have to be the same length as the agent list.
        """
        # Handle single value case
        if not isinstance(values, list):
            values = [values] * len(self.store.entries)

        if len(values) != len(self.store.entries):
            raise AgentListError(
                f"The passed values have to be the same length as the agent list. "
                f"Got {len(values)} values for {len(self.store.entries)} agents."
            )

        return AddNestedFieldByIndexEvent(
            parent_field="traits", field=trait, values=tuple(values)
        )

    @event
    def numberify(self) -> NumberifyNestedFieldsEvent:
        """Convert string traits to numeric types where possible.

        This method attempts to convert string values to integers or floats
        for all traits across all agents. It's particularly useful when loading
        data from CSV files where numeric fields may be stored as strings.

        Conversion rules:
        - None values remain None
        - Already numeric values (int, float) remain unchanged
        - String values that can be parsed as integers are converted to int
        - String values that can be parsed as floats are converted to float
        - String values that cannot be parsed remain as strings
        - Empty strings remain as empty strings

        Returns:
            AgentList: A new AgentList with numeric conversions applied.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([
            ...     Agent(name='Alice', traits={'age': '30', 'height': '5.5'}),
            ...     Agent(name='Bob', traits={'age': '25', 'height': '6.0'})
            ... ])
            >>> al = al.numberify()
            >>> al[0].traits
            {'age': 30, 'height': 5.5}
            >>> al[1].traits
            {'age': 25, 'height': 6.0}

            Works with None values and mixed types:

            >>> al = AgentList([Agent(traits={'count': '100', 'value': None, 'label': 'test'})])
            >>> al = al.numberify()
            >>> al[0].traits
            {'count': 100, 'value': None, 'label': 'test'}
        """

        def try_convert(val):
            if val is None or isinstance(val, (int, float)):
                return val
            if isinstance(val, str):
                if val == "":
                    return val
                try:
                    return int(val)
                except ValueError:
                    try:
                        return float(val)
                    except ValueError:
                        return val
            return val

        # Pre-compute all conversions as (entry_idx, field, new_value) tuples
        conversions = []
        for i, entry in enumerate(self.store.entries):
            if "traits" in entry:
                for key, value in entry["traits"].items():
                    converted = try_convert(value)
                    if converted != value:  # Only record actual changes
                        conversions.append((i, key, converted))

        return NumberifyNestedFieldsEvent(
            parent_field="traits", conversions=tuple(conversions)
        )

    @event
    def filter_na(self, fields: Union[str, List[str]] = "*") -> RemoveRowsEvent:
        """Remove agents where specified traits contain None or NaN values.

        This method filters out agents that have null/NaN values in the specified
        traits. It's similar to pandas' dropna() functionality. Values considered as
        NA include: None, float('nan'), and string representations like 'nan', 'none', 'null'.

        Args:
            fields: Trait name(s) to check for NA values. Can be:
                    - "*" (default): Check all traits in each agent
                    - A single trait name (str): Check only that trait
                    - A list of trait names: Check all specified traits

                    An agent is kept only if NONE of the specified traits contain NA values.

        Returns:
            AgentList: A new AgentList without agents containing NA values.

        Examples:
            Remove agents with any NA values in any trait:

            >>> from edsl import Agent, AgentList
            >>> al = AgentList([
            ...     Agent(traits={'a': 1, 'b': 2}),
            ...     Agent(traits={'a': None, 'b': 3}),
            ...     Agent(traits={'a': 4, 'b': 5})
            ... ])
            >>> al = al.filter_na()
            >>> len(al)
            2

            Remove agents with NA in specific trait:

            >>> al = AgentList([
            ...     Agent(name='Alice', traits={'age': 30}),
            ...     Agent(name='Bob', traits={'age': None}),
            ...     Agent(name='Charlie', traits={'age': 25})
            ... ])
            >>> al = al.filter_na('age')
            >>> len(al)
            2

            Remove agents with NA in multiple specific traits:

            >>> al = AgentList([
            ...     Agent(traits={'person_name': 'Alice', 'age': 30}),
            ...     Agent(traits={'person_name': None, 'age': 25}),
            ...     Agent(traits={'person_name': 'Bob', 'age': None})
            ... ])
            >>> al = al.filter_na(['person_name', 'age'])
            >>> len(al)
            1

            Handle float NaN values:

            >>> import math
            >>> al = AgentList([
            ...     Agent(traits={'x': 1.0, 'y': 2.0}),
            ...     Agent(traits={'x': float('nan'), 'y': 3.0}),
            ...     Agent(traits={'x': 4.0, 'y': 5.0})
            ... ])
            >>> al = al.filter_na('x')
            >>> len(al)
            2
        """
        import math

        def is_na(val):
            """Check if a value is considered NA (None or NaN)."""
            if val is None:
                return True
            if isinstance(val, float) and math.isnan(val):
                return True
            if hasattr(val, "__str__"):
                str_val = str(val).lower()
                if str_val in ["nan", "none", "null"]:
                    return True
            return False

        # Determine which fields to check
        if fields == "*":
            check_fields = set()
            for agent in self.data:
                check_fields.update(agent.traits.keys())
            check_fields = list(check_fields)
        elif isinstance(fields, str):
            check_fields = [fields]
        else:
            check_fields = list(fields)

        # Find indices of agents with NA values
        indices_to_remove = []
        for i, agent in enumerate(self.data):
            has_na = False
            for field in check_fields:
                if field in agent.traits:
                    if is_na(agent.traits[field]):
                        has_na = True
                        break
            if has_na:
                indices_to_remove.append(i)

        return RemoveRowsEvent(indices=tuple(indices_to_remove))

    @classmethod
    def from_results(
        cls, results: "Results", question_names: Optional[List[str]] = None
    ) -> "AgentList":
        """Create an AgentList from a Results object.

        Args:
            results: The Results object to convert
            question_names: Optional list of question names to include. If None, all questions are included.
                          Affects both answer.* columns (as traits) and prompt.* columns (as codebook).
                          Agent traits are always included.

        Returns:
            AgentList: A new AgentList created from the Results
        """
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.from_results(results, question_names)

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
        >>> isinstance(hash(al), int)
        True
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

        >>> d = AgentList.example().to_dict(add_edsl_version=False)
        >>> 'agent_list' in d and len(d['agent_list']) == 2
        True
        >>> 'traits_presentation_template' in d
        True
        >>> example_codebook = {'age': 'Age in years'}
        >>> al = AgentList.example().set_codebook(example_codebook)
        >>> result = al.to_dict(add_edsl_version=False)
        >>> 'codebook' in result
        True
        >>> result['codebook'] == example_codebook
        True
        >>> example_instruction = 'Answer as a test subject'
        >>> al = AgentList.example().set_instruction(example_instruction)
        >>> result = al.to_dict(add_edsl_version=False)
        >>> 'instruction' in result
        True
        >>> result['instruction'] == example_instruction
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
        """Return a string representation of the AgentList.

        Uses traditional repr format when running doctests, otherwise uses
        rich-based display for better readability. In Jupyter notebooks,
        returns a minimal string since _repr_html_ handles the display.
        """
        import os

        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            return self._eval_repr_()

        # Check if we're in a Jupyter notebook environment
        # If so, return minimal representation since _repr_html_ will handle display
        try:
            from IPython import get_ipython

            ipy = get_ipython()
            if ipy is not None and "IPKernelApp" in ipy.config:
                # We're in a Jupyter notebook/kernel, not IPython terminal
                return "AgentList(...)"
        except (NameError, ImportError):
            pass

        return self._summary_repr()

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the AgentList.

        This representation can be used with eval() to recreate the AgentList object.
        Used primarily for doctests and debugging.
        """
        return f"AgentList({self.data})"

    def _summary_repr(self, MAX_AGENTS: int = 10, MAX_TRAITS: int = 10) -> str:
        """Generate a summary representation of the AgentList with Rich formatting.

        Args:
            MAX_AGENTS: Maximum number of agents to show (default: 10)
            MAX_TRAITS: Maximum number of traits to show per agent (default: 10)
        """
        from rich.console import Console
        from rich.text import Text
        import io
        import shutil
        import textwrap

        # Get terminal width
        terminal_width = shutil.get_terminal_size().columns

        # Build the Rich text
        output = Text()
        output.append("AgentList(\n", style=RICH_STYLES["primary"])
        output.append(f"    num_agents={len(self)},\n", style=RICH_STYLES["default"])
        output.append("    agents=[\n", style=RICH_STYLES["default"])

        # Show the first MAX_AGENTS agents
        num_to_show = min(MAX_AGENTS, len(self))
        for i, agent in enumerate(self.data[:num_to_show]):
            # Get agent traits with limited fields
            agent_traits = dict(list(agent.traits.items())[:MAX_TRAITS])

            # Check if we need to indicate truncation
            num_traits = len(agent.traits)
            was_truncated = num_traits > MAX_TRAITS

            # Build agent repr with indentation
            output.append("        Agent(\n", style=RICH_STYLES["primary"])
            output.append(
                f"            num_traits={num_traits},\n", style=RICH_STYLES["default"]
            )

            # Add name if present
            if agent.name is not None:
                output.append(
                    f"            name={repr(agent.name)},\n",
                    style=RICH_STYLES["default"],
                )

            output.append("            traits={\n", style=RICH_STYLES["default"])

            # Show traits
            for key, value in agent_traits.items():
                # Format the value with wrapping if needed
                max_value_length = max(terminal_width - 30, 50)
                value_repr = repr(value)

                output.append("                ", style=RICH_STYLES["default"])
                output.append(f"'{key}'", style=RICH_STYLES["secondary"])
                output.append(": ", style=RICH_STYLES["default"])

                # Wrap long text values
                if len(value_repr) > max_value_length:
                    # Use textwrap to break into multiple lines
                    wrapped_lines = textwrap.wrap(
                        value_repr,
                        width=max_value_length,
                        break_long_words=True,
                        break_on_hyphens=False,
                    )
                    for line_idx, line in enumerate(wrapped_lines):
                        if line_idx == 0:
                            output.append(f"{line}\n", style=RICH_STYLES["default"])
                        else:
                            # Continuation lines are indented to align with the value
                            output.append(
                                f"                    {line}\n",
                                style=RICH_STYLES["default"],
                            )
                    # Remove the last newline and add comma
                    output._text[-1] = output._text[-1].rstrip("\n") + ",\n"
                else:
                    output.append(f"{value_repr},\n", style=RICH_STYLES["default"])

            if was_truncated:
                output.append(
                    f"                ... ({num_traits - MAX_TRAITS} more traits)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("            }\n", style=RICH_STYLES["default"])
            output.append("        )", style=RICH_STYLES["primary"])

            # Add comma and newline unless it's the last one
            if i < num_to_show - 1:
                output.append(",\n", style=RICH_STYLES["default"])
            else:
                output.append("\n", style=RICH_STYLES["default"])

        # Add ellipsis if there are more agents
        if len(self) > MAX_AGENTS:
            output.append(
                f"        ... ({len(self) - MAX_AGENTS} more agents)\n",
                style=RICH_STYLES["dim"],
            )

        output.append("    ],\n", style=RICH_STYLES["default"])

        # Show codebook if present
        if self.codebook:
            output.append("    codebook=", style=RICH_STYLES["default"])
            output.append(f"{self.codebook}", style=RICH_STYLES["secondary"])
            output.append(",\n", style=RICH_STYLES["default"])

        # Show traits_presentation_template if present
        if self.traits_presentation_template:
            template_repr = repr(self.traits_presentation_template)
            # Truncate if too long
            max_template_len = 60
            if len(template_repr) > max_template_len:
                template_repr = template_repr[: max_template_len - 3] + "...'"
            output.append(
                "    traits_presentation_template=", style=RICH_STYLES["default"]
            )
            output.append(f"{template_repr}", style=RICH_STYLES["secondary"])
            output.append(",\n", style=RICH_STYLES["default"])

        # Show instruction if present (and not the default)
        from .agent import Agent

        if self.instruction and self.instruction != Agent.default_instruction:
            instruction_repr = repr(self.instruction)
            # Truncate if too long
            max_instruction_len = 60
            if len(instruction_repr) > max_instruction_len:
                instruction_repr = instruction_repr[: max_instruction_len - 3] + "...'"
            output.append("    instruction=", style=RICH_STYLES["default"])
            output.append(f"{instruction_repr}", style=RICH_STYLES["secondary"])
            output.append(",\n", style=RICH_STYLES["default"])

        output.append(")", style=RICH_STYLES["primary"])

        # Render to string
        console = Console(file=io.StringIO(), force_terminal=True, width=terminal_width)
        console.print(output, end="")
        return console.file.getvalue()

    def _summary(self) -> dict:
        return {
            "agents": len(self),
        }

    @event
    def set_codebook(self, codebook: dict[str, str]) -> SetMetaEvent:
        """Set the codebook for all agents in the list.

        This updates the canonical codebook in store.meta. When agents are
        accessed via the data property, they will receive this codebook,
        ensuring all agents in the list have consistent codebook values.

        >>> from edsl import Agent
        >>> a = Agent(traits = {'hair': 'brown'})
        >>> al = AgentList([a, a])
        >>> al = al.set_codebook({'hair': "Color of hair on driver's license"})
        >>> al.codebook
        {'hair': "Color of hair on driver's license"}

        Args:
            codebook: Dictionary mapping trait names to descriptions.

        Returns:
            SetMetaEvent: Event that updates the codebook in store.meta.
        """
        return SetMetaEvent(key="codebook", value=codebook)

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
        >>> example_instruction = 'Answer as a test subject'
        >>> al = AgentList([Agent.example()]).set_instruction(example_instruction)
        >>> al2 = AgentList.from_dict(al.to_dict())
        >>> al2.instruction == example_instruction
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
        >>> len(al)
        2
        >>> al[0].traits['age']
        22
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

        >>> al = AgentList.from_list('age', [22, 23])
        >>> len(al)
        2
        >>> al[0].traits['age']
        22
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

    @property
    def codebook(self) -> dict[str, str]:
        """Return the codebook for the AgentList from store.meta."""
        return self.store.meta.get("codebook", {})

    @property
    def traits_presentation_template(self) -> Optional[str]:
        """Return the traits presentation template for the AgentList from store.meta.

        This template is applied to all agents in the list when they are accessed.
        All agents in the list must have the same traits_presentation_template.

        Returns:
            Optional[str]: The Jinja2 template for formatting traits, or None if using default.
        """
        return self.store.meta.get("traits_presentation_template")

    @property
    def instruction(self) -> Optional[str]:
        """Return the instruction for the AgentList from store.meta.

        This instruction is applied to all agents in the list when they are accessed.
        All agents in the list must have the same instruction.

        Returns:
            Optional[str]: The instruction text, or None if using default.
        """
        return self.store.meta.get("instruction")

    def code(self, string=True) -> Union[str, list[str]]:
        """Return code to construct an AgentList.

        >>> al = AgentList.example()
        >>> code = al.code()
        >>> 'from edsl import Agent' in code
        True
        >>> 'AgentList' in code
        True
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
            >>> len(al)
            1
            >>> al[0].traits['age']
            22
        """
        from .agent_list_factories import AgentListFactories

        return AgentListFactories.from_scenario_list(scenario_list)

    @classmethod
    def from_vibes(
        cls,
        description: str,
        *,
        num_agents: Optional[int] = None,
        traits: Optional[List[str]] = None,
        model: str = "gpt-4o",
        temperature: float = 0.8,
    ) -> "AgentList":
        """Generate an AgentList from a natural language description of a population.

        This method uses an LLM to generate a diverse population of agents with
        appropriate traits based on a description. It automatically creates realistic,
        varied individuals that represent the described population.

        Args:
            description: Natural language description of the population.
                Examples:
                - "College students studying computer science"
                - "Small business owners in the Midwest"
                - "Retired professionals interested in travel"
                - "Healthcare workers during the pandemic"
            num_agents: Optional number of agents to generate. If not provided,
                the LLM will decide based on the population (typically 5-10).
            traits: Optional list of specific trait names to include for each agent.
                If not provided, appropriate traits will be inferred from the description.
                Examples: ["age", "occupation", "education_level", "income_bracket"]
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.8 for diversity)

        Returns:
            AgentList: A new AgentList with generated agents

        Examples:
            Basic usage:

            >>> agents = AgentList.from_vibes("College students studying computer science")  # doctest: +SKIP

            With specific number of agents:

            >>> agents = AgentList.from_vibes(
            ...     "Small business owners in the Midwest",
            ...     num_agents=8
            ... )  # doctest: +SKIP

            With specific traits:

            >>> agents = AgentList.from_vibes(
            ...     "Voters in a swing state",
            ...     traits=["age", "political_affiliation", "education_level", "key_issue"],
            ...     num_agents=10
            ... )  # doctest: +SKIP

            Using a different model:

            >>> agents = AgentList.from_vibes(
            ...     "Retired professionals interested in travel",
            ...     model="gpt-4",
            ...     temperature=0.7
            ... )  # doctest: +SKIP

        Notes:
            - Requires OPENAI_API_KEY environment variable to be set
            - The generator creates diverse agents with realistic trait values
            - All agents will have the same set of trait names for consistency
            - Higher temperature (0.7-0.9) creates more diverse populations
            - The generator avoids stereotypes and creates nuanced individuals
        """
        from edsl.services import dispatch
        
        # Dispatch to agent_vibes service with 'generate' operation
        pending = dispatch("agent_vibes", {
            "operation": "generate",
            "description": description,
            "num_agents": num_agents,
            "traits": traits,
            "model": model,
            "temperature": temperature,
        })
        
        # Get result (which is already an AgentList)
        return pending.result()


if __name__ == "__main__":
    import doctest

    # Just run the standard doctests with verbose flag
    doctest.testmod(
        verbose=True, optionflags=doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
    )
