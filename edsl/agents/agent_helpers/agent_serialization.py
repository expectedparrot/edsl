"""Agent serialization functionality.

This module provides the AgentSerialization class that handles serialization and
deserialization of Agent instances to/from dictionary representations.
"""

from __future__ import annotations
import copy
import inspect
from typing import Union, TYPE_CHECKING

from edsl.utilities import remove_edsl_version

if TYPE_CHECKING:
    from ..agent import Agent


class AgentSerialization:
    """Handles serialization and deserialization of Agent instances.

    This class provides methods to convert Agent instances to dictionary
    representations and create Agent instances from dictionaries, supporting
    various serialization options and backward compatibility.
    """

    @staticmethod
    def to_dict(
        agent: "Agent", add_edsl_version: bool = True, full_dict: bool = False
    ) -> dict[str, Union[dict, bool, str]]:
        """Serialize an agent to a dictionary with EDSL info.

        Args:
            agent: The agent instance to serialize
            add_edsl_version: Whether to include EDSL version information
            full_dict: Whether to include all attributes even if they have default values

        Returns:
            A dictionary representation of the agent

        Example:
            >>> from edsl.agents import Agent
            >>> a = Agent(name = "Steve", traits = {"age": 10, "hair": "brown", "height": 5.5})
            >>> d = AgentSerialization.to_dict(a)
            >>> d['traits']
            {'age': 10, 'hair': 'brown', 'height': 5.5}
            >>> d['name']
            'Steve'
            >>> d['edsl_class_name']
            'Agent'
        """
        d = {}
        d["traits"] = copy.deepcopy(dict(agent._traits))
        if agent.name:
            d["name"] = agent.name
        if agent.set_instructions or full_dict:
            d["instruction"] = agent.instruction
        if agent.set_traits_presentation_template or full_dict:
            d["traits_presentation_template"] = agent.traits_presentation_template
        if agent.codebook or full_dict:
            d["codebook"] = agent.codebook
        if agent.trait_categories or full_dict:
            d["trait_categories"] = agent.trait_categories
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = agent.__class__.__name__

        return d

    @classmethod
    @remove_edsl_version
    def from_dict(cls, agent_dict: dict[str, Union[dict, bool, str]]) -> "Agent":
        """Deserialize from a dictionary.

        Args:
            agent_dict: Dictionary containing agent data

        Returns:
            An Agent instance created from the dictionary

        Example:
            >>> agent_dict = {'name': "Steve", 'traits': {'age': 10, 'hair': 'brown', 'height': 5.5}}
            >>> agent = AgentSerialization.from_dict(agent_dict)
            >>> agent.name
            'Steve'
            >>> agent.traits
            {'age': 10, 'hair': 'brown', 'height': 5.5}
        """
        # Import locally to avoid circular imports
        from ..agent import Agent

        if "traits" in agent_dict:
            if "trait_categories" in agent_dict:
                trait_categories = agent_dict.pop("trait_categories", {})
            else:
                trait_categories = {}
            return Agent(
                traits=agent_dict["traits"],
                name=agent_dict.get("name", None),
                instruction=agent_dict.get("instruction", None),
                traits_presentation_template=agent_dict.get(
                    "traits_presentation_template", None
                ),
                codebook=agent_dict.get("codebook", None),
                trait_categories=trait_categories,
            )
        else:  # old-style agent - we used to only store the traits
            return Agent(**agent_dict)

    @staticmethod
    def data(agent: "Agent") -> dict:
        """Format the agent data for serialization.

        Returns:
            A dictionary containing the agent's serializable data

        Todo:
            * Warn if has dynamic traits function or direct answer function that cannot be serialized
            * Add ability to have coop-hosted functions that are serializable

        Example:
            >>> from edsl.agents import Agent
            >>> agent = Agent(traits={'age': 30}, name='John')
            >>> data = AgentSerialization.data(agent)
            >>> 'traits' in data
            True
        """

        raw_data = {
            k.replace("_", "", 1): v
            for k, v in agent.__dict__.items()
            if k.startswith("_")
        }

        # Remove internal cache attributes that should not be serialized
        raw_data.pop("cached_hash", None)

        if hasattr(agent, "set_instructions"):
            if not agent.set_instructions:
                raw_data.pop("instruction")
        if hasattr(agent, "set_traits_presentation_template"):
            if not agent.set_traits_presentation_template:
                raw_data.pop("traits_presentation_template", None)
        if agent.codebook == {}:
            raw_data.pop("codebook")
        if agent.name is None:
            raw_data.pop("name")

        if hasattr(agent, "dynamic_traits_function"):
            raw_data.pop(
                "dynamic_traits_function", None
            )  # in case dynamic_traits_function will appear with _ in agent.__dict__
            dynamic_traits_func = agent.dynamic_traits_function
            if dynamic_traits_func:
                func = inspect.getsource(dynamic_traits_func)
                raw_data["dynamic_traits_function_source_code"] = func
                raw_data["dynamic_traits_function_name"] = (
                    agent.dynamic_traits_function_name
                )
        if hasattr(agent, "answer_question_directly"):
            raw_data.pop(
                "answer_question_directly", None
            )  # in case answer_question_directly will appear with _ in agent.__dict__
            answer_question_directly_func = agent.answer_question_directly

            if answer_question_directly_func:
                try:
                    raw_data["answer_question_directly_source_code"] = (
                        inspect.getsource(answer_question_directly_func)
                    )
                    raw_data["answer_question_directly_function_name"] = (
                        agent.answer_question_directly_function_name
                    )
                except (OSError, TypeError):
                    # Can't get source for closures, lambdas, or dynamically defined functions
                    # The method won't survive serialization
                    pass
        raw_data["traits"] = dict(raw_data["traits"])

        if hasattr(agent, "trait_categories"):
            if agent.trait_categories:
                raw_data["trait_categories"] = agent.trait_categories

        return raw_data
