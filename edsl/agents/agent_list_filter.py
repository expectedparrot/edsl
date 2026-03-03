"""AgentList filtering operations module."""

from __future__ import annotations
import sys
from typing import TYPE_CHECKING

from simpleeval import EvalWithCompoundTypes, NameNotDefined
from ..utilities import is_notebook

if TYPE_CHECKING:
    from .agent_list import AgentList
    from .agent import Agent


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

    def __init__(self, agent_list: "AgentList"):
        """Initialize with a reference to the AgentList.

        Args:
            agent_list: The AgentList instance to operate on.
        """
        self._agent_list = agent_list

    def filter(self, expression: str) -> "AgentList":
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
        from .agent_list import AgentList
        from .exceptions import AgentListError

        def create_evaluator(agent: "Agent"):
            """Create an evaluator for the given agent."""
            return EvalWithCompoundTypes(names={**agent.traits, "name": agent.name})

        try:
            new_data = [
                agent
                for agent in self._agent_list.data
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
