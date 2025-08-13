"""AgentList serialization operations module."""

from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .agent_list import AgentList


class AgentListSerializer:
    """Handles serialization and deserialization operations for AgentList objects.
    
    This class provides functionality for converting AgentList objects to and from
    dictionary representations, supporting various serialization options like sorting,
    version information, and codebook handling.
    """

    @staticmethod
    def to_dict(agent_list: "AgentList", sorted: bool = False, add_edsl_version: bool = True, full_dict: bool = False) -> dict:
        """Serialize the AgentList to a dictionary.

        Args:
            agent_list: The AgentList to serialize
            sorted: Whether to sort agents before serialization
            add_edsl_version: Whether to include EDSL version information
            full_dict: Whether to include full dictionary representation

        Returns:
            dict: A dictionary representation of the AgentList

        Examples:
            >>> from edsl import AgentList
            >>> from edsl.agents.agent_list_serializer import AgentListSerializer
            >>> al = AgentList.example()
            >>> result = AgentListSerializer.to_dict(al, add_edsl_version=False)
            >>> 'agent_list' in result
            True
            >>> len(result['agent_list'])
            2
        """
        if sorted:
            data = agent_list.data[:]
            data.sort(key=lambda x: hash(x))
        else:
            data = agent_list.data

        d = {
            "agent_list": [
                agent.to_dict(add_edsl_version=add_edsl_version, full_dict=full_dict) for agent in data
            ]
        }

        # Add codebook if all agents have the same codebook
        if len(agent_list.data) > 0:
            # Get the first agent's codebook
            first_codebook = agent_list.data[0].codebook

            # Check if all agents have the same codebook
            all_same = all(agent.codebook == first_codebook for agent in agent_list.data)

            # Only include codebook if it's non-empty and consistent across all agents
            if all_same and first_codebook:
                d["codebook"] = first_codebook

        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "AgentList"

        return d

    @staticmethod
    def from_dict(data: dict) -> "AgentList":
        """Deserialize the dictionary back to an AgentList object.

        Args:
            data: A dictionary representing an AgentList

        Returns:
            AgentList: A new AgentList object created from the dictionary

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_serializer import AgentListSerializer
            >>> al = AgentList([Agent.example(), Agent.example()])
            >>> serialized = AgentListSerializer.to_dict(al)
            >>> al2 = AgentListSerializer.from_dict(serialized)
            >>> len(al2)
            2
        """
        from .agent import Agent
        from .agent_list import AgentList

        agents = [Agent.from_dict(agent_dict) for agent_dict in data["agent_list"]]
        agent_list = AgentList(agents)

        # Apply codebook if present in the dictionary
        if "codebook" in data and data["codebook"]:
            agent_list.set_codebook(data["codebook"])

        return agent_list 