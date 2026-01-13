"""AgentList code generation operations module."""

from __future__ import annotations
from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..agent_list import AgentList


class AgentListCodeGenerator:
    """Handles code generation operations for AgentList objects.

    This class provides functionality for generating Python code that can
    recreate AgentList objects, useful for debugging, documentation, and
    code generation workflows.
    """

    @staticmethod
    def generate_code(
        agent_list: "AgentList", string: bool = True
    ) -> Union[str, list[str]]:
        """Return code to construct an AgentList.

        Args:
            agent_list: The AgentList to generate code for
            string: Whether to return code as a string (True) or list of lines (False)

        Returns:
            Union[str, list[str]]: Python code to recreate the AgentList

        Examples:
            >>> from edsl import AgentList
            >>> from edsl.agents.agent_list_helpers.agent_list_code_generator import AgentListCodeGenerator
            >>> al = AgentList.example()
            >>> code_lines = AgentListCodeGenerator.generate_code(al, string=False)
            >>> len(code_lines)
            3
            >>> code_lines[0]
            'from edsl import Agent'
            >>> code_lines[1]
            'from edsl import AgentList'
            >>> 'agent_list = AgentList([' in code_lines[2]
            True
        """
        lines = [
            "from edsl import Agent",
            "from edsl import AgentList",
        ]
        lines.append(f"agent_list = AgentList({agent_list.data})")

        if string:
            return "\n".join(lines)
        return lines
