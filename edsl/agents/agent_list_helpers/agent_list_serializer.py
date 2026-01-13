"""AgentList serialization operations module."""

from __future__ import annotations
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ..agent_list import AgentList


class AgentListSerializer:
    """Handles serialization and deserialization operations for AgentList objects.

    This class provides functionality for converting AgentList objects to and from
    dictionary representations, supporting various serialization options like sorting,
    version information, and codebook handling.
    """

    @staticmethod
    def to_dict(
        agent_list: "AgentList",
        sorted: bool = False,
        add_edsl_version: bool = True,
        full_dict: bool = False,
    ) -> dict:
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
            >>> from edsl.agents.agent_list_helpers.agent_list_serializer import AgentListSerializer
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
                agent.to_dict(add_edsl_version=add_edsl_version, full_dict=full_dict)
                for agent in data
            ]
        }

        # Add codebook from store.meta if present
        codebook = agent_list.codebook
        if codebook:
            d["codebook"] = codebook

        # Add traits_presentation_template from store.meta if present
        template = agent_list.traits_presentation_template
        if template is not None:
            d["traits_presentation_template"] = template

        # Add instruction from store.meta if present
        instruction = agent_list.instruction
        if instruction is not None:
            d["instruction"] = instruction

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
            >>> from edsl.agents.agent_list_helpers.agent_list_serializer import AgentListSerializer
            >>> al = AgentList([Agent.example(), Agent.example()])
            >>> serialized = AgentListSerializer.to_dict(al)
            >>> al2 = AgentListSerializer.from_dict(serialized)
            >>> len(al2)
            2
        """
        from ..agent import Agent
        from ..agent_list import AgentList

        agent_data = data.get("agent_list", None)
        if agent_data is None:
            print("Current data is", data)
            raise ValueError("agent_list key not found in data")

        # Create AgentList with codebook, traits_presentation_template, and instruction if provided
        codebook = data.get("codebook")
        traits_presentation_template = data.get("traits_presentation_template")
        instruction = data.get("instruction")
        agents = [Agent.from_dict(agent_dict) for agent_dict in agent_data]
        agent_list = AgentList(
            agents,
            codebook=codebook,
            traits_presentation_template=traits_presentation_template,
            instruction=instruction,
        )

        return agent_list


if __name__ == "__main__":
    import doctest

    doctest.testmod()
