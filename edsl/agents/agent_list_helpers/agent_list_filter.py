"""AgentList filtering operations module."""

from __future__ import annotations
import sys
from typing import TYPE_CHECKING

from simpleeval import EvalWithCompoundTypes, NameNotDefined
from edsl.utilities import is_notebook

if TYPE_CHECKING:
    from ..agent_list import AgentList
    from ..agent import Agent


class EmptyAgentList:
    """Represents an empty AgentList result from filtering operations."""

    def __repr__(self):
        return "Empty AgentList"

    def __len__(self):
        return 0


class AgentListFilter:
    """Handles filtering operations for AgentList objects.

    This class provides functionality for filtering AgentList objects based on
    boolean expressions that can reference agent traits and names.
    """

    @staticmethod
    def filter(agent_list: "AgentList", expression: str) -> "AgentList":
        """Filter agents based on a boolean expression.

        Args:
            agent_list: The AgentList to filter
            expression: A string containing a boolean expression to evaluate against
                each agent's traits.

        Returns:
            AgentList or EmptyAgentList: A new AgentList containing only agents that
                satisfy the expression, or EmptyAgentList if no matches or error.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_helpers.agent_list_filter import AgentListFilter
            >>> al = AgentList([Agent(traits = {'a': 1, 'b': 1}),
            ...                Agent(traits = {'a': 1, 'b': 2})])
            >>> filtered = AgentListFilter.filter(al, "b == 2")
            >>> len(filtered)
            1
            >>> filtered[0].traits
            {'a': 1, 'b': 2}
        """
        from ..agent_list import AgentList
        from ..exceptions import AgentListError

        def create_evaluator(agent: "Agent"):
            """Create an evaluator for the given agent."""
            return EvalWithCompoundTypes(names={**agent.traits, "name": agent.name})

        try:
            new_data = [
                agent
                for agent in agent_list.data
                if create_evaluator(agent).eval(expression)
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
