"""AgentList trait operations module."""

from __future__ import annotations
import sys
from typing import Union, List, Any, TYPE_CHECKING
from collections.abc import Iterable

from ..utilities import is_notebook

if TYPE_CHECKING:
    from .agent_list import AgentList


def is_iterable(obj):
    return isinstance(obj, Iterable)


class AgentListTraitOperations:
    """Handles trait manipulation operations for AgentList objects.
    
    This class provides functionality for modifying, selecting, and managing
    traits across collections of Agent objects, including operations like
    dropping, keeping, selecting, renaming, adding, removing, and translating traits.
    """

    @staticmethod
    def drop(agent_list: "AgentList", *field_names: Union[str, List[str]]) -> "AgentList":
        """Drop field(s) from all agents in the AgentList.

        Args:
            agent_list: The AgentList to operate on
            *field_names: The name(s) of the field(s) to drop. Can be:
                - Single field name: drop("age")
                - Multiple field names: drop("age", "height")
                - List of field names: drop(["age", "height"])

        Returns:
            AgentList: A new AgentList with the specified fields dropped from all agents.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_trait_operations import AgentListTraitOperations
            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al_dropped = AgentListTraitOperations.drop(al, "age")
            >>> al_dropped[0].traits
            {'hair': 'brown', 'height': 5.5}
        """
        from .agent_list import AgentList
        return AgentList([a.drop(*field_names) for a in agent_list.data])

    @staticmethod
    def keep(agent_list: "AgentList", *field_names: Union[str, List[str]]) -> "AgentList":
        """Keep only the specified fields from all agents in the AgentList.

        Args:
            agent_list: The AgentList to operate on
            *field_names: The name(s) of the field(s) to keep. Can be:
                - Single field name: keep("age")
                - Multiple field names: keep("age", "height")
                - List of field names: keep(["age", "height"])

        Returns:
            AgentList: A new AgentList with only the specified fields kept for all agents.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_trait_operations import AgentListTraitOperations
            >>> al = AgentList([Agent(traits={"age": 30, "hair": "brown", "height": 5.5})])
            >>> al_kept = AgentListTraitOperations.keep(al, "age")
            >>> al_kept[0].traits
            {'age': 30}
        """
        from .agent_list import AgentList
        return AgentList([a.keep(*field_names) for a in agent_list.data])

    @staticmethod
    def rename(agent_list: "AgentList", old_name: str, new_name: str) -> "AgentList":
        """Rename a trait across all agents in the list.

        Args:
            agent_list: The AgentList to operate on
            old_name: The current name of the trait.
            new_name: The new name to assign to the trait.

        Returns:
            AgentList: A new AgentList with the renamed trait.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_trait_operations import AgentListTraitOperations
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1})])
            >>> al2 = AgentListTraitOperations.rename(al, 'a', 'c')
            >>> al2[0].traits
            {'c': 1, 'b': 1}
        """
        from .agent_list import AgentList
        newagents = []
        for agent in agent_list:
            newagents.append(agent.rename(old_name, new_name))
        return AgentList(newagents)

    @staticmethod
    def select(agent_list: "AgentList", *traits) -> "AgentList":
        """Create a new AgentList with only the specified traits.

        Args:
            agent_list: The AgentList to operate on
            *traits: Variable number of trait names to keep.

        Returns:
            AgentList: A new AgentList containing agents with only the selected traits.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_trait_operations import AgentListTraitOperations
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1})])
            >>> selected = AgentListTraitOperations.select(al, 'a')
            >>> selected[0].traits
            {'a': 1}
        """
        from .agent_list import AgentList
        if len(traits) == 1:
            traits_to_select = [list(traits)[0]]
        else:
            traits_to_select = list(traits)

        return AgentList([agent.select(*traits_to_select) for agent in agent_list.data])

    @staticmethod
    def get_all_traits(agent_list: "AgentList") -> list[str]:
        """Return all traits in the AgentList.
        
        Args:
            agent_list: The AgentList to get traits from
            
        Returns:
            list[str]: List of all unique trait names across all agents
            
        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_trait_operations import AgentListTraitOperations
            >>> agent_1 = Agent(traits = {'age': 22})
            >>> agent_2 = Agent(traits = {'hair': 'brown'})
            >>> al = AgentList([agent_1, agent_2])
            >>> AgentListTraitOperations.get_all_traits(al)
            ['age', 'hair']
        """
        d = {}
        for agent in agent_list:
            d.update(agent.traits)
        return list(d.keys())

    @staticmethod
    def translate_traits(agent_list: "AgentList", codebook: dict[str, str]) -> "AgentList":
        """Translate traits to a new codebook.

        Args:
            agent_list: The AgentList to operate on
            codebook: The new codebook for translation

        Returns:
            AgentList: A new AgentList with translated traits

        Examples:
            >>> from edsl import AgentList
            >>> from edsl.agents.agent_list_trait_operations import AgentListTraitOperations
            >>> al = AgentList.example()
            >>> codebook = {'hair': {'brown':'Secret word for green'}}
            >>> translated = AgentListTraitOperations.translate_traits(al, codebook)
            >>> len(translated)
            2
        """
        from .agent_list import AgentList
        new_agents = []
        for agent in agent_list.data:
            new_agents.append(agent.translate_traits(codebook))
        return AgentList(new_agents)

    @staticmethod
    def remove_trait(agent_list: "AgentList", trait: str) -> "AgentList":
        """Remove traits from the AgentList.

        Args:
            agent_list: The AgentList to operate on
            trait: The trait to remove

        Returns:
            AgentList: A new AgentList with the trait removed from all agents

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_trait_operations import AgentListTraitOperations
            >>> al = AgentList([Agent({'age': 22, 'hair': 'brown', 'height': 5.5})])
            >>> result = AgentListTraitOperations.remove_trait(al, 'age')
            >>> result[0].traits
            {'hair': 'brown', 'height': 5.5}
        """
        from .agent_list import AgentList
        agents = []
        new_al = agent_list.duplicate()
        for agent in new_al.data:
            agents.append(agent.remove_trait(trait))
        return AgentList(agents)

    @staticmethod
    def add_trait(agent_list: "AgentList", trait: str, values: List[Any]) -> "AgentList":
        """Adds a new trait to every agent, with values taken from values.

        Args:
            agent_list: The AgentList to operate on
            trait: The name of the trait.
            values: The value(s) of the trait. If a single value is passed, it is used for all agents.

        Returns:
            AgentList: A new AgentList with the trait added to all agents

        Examples:
            >>> from edsl import AgentList
            >>> from edsl.agents.agent_list_trait_operations import AgentListTraitOperations
            >>> al = AgentList.example()
            >>> new_al = AgentListTraitOperations.add_trait(al, 'new_trait', 1)
            >>> len(new_al)
            2
        """
        from .agent_list import AgentList
        from .exceptions import AgentListError
        
        if not is_iterable(values):
            new_agents = []
            value = values
            for agent in agent_list.data:
                new_agents.append(agent.add_trait(trait, value))
            return AgentList(new_agents)

        if len(values) != len(agent_list):
            e = AgentListError(
                "The passed values have to be the same length as the agent list."
            )
            if is_notebook():
                print(e, file=sys.stderr)
            else:
                raise e
        new_agents = []
        for agent, value in zip(agent_list.data, values):
            new_agents.append(agent.add_trait(trait, value))
        return AgentList(new_agents) 