"""AgentList joining operations module."""

from __future__ import annotations
import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_list import AgentList


class AgentListJoiner:
    """Handles joining operations for AgentList objects.
    
    This class provides functionality for combining multiple AgentList objects
    based on agent names, supporting different join types (inner, left, right).
    """

    @staticmethod
    def _join_two(left: "AgentList", right: "AgentList", join_type: str = "inner") -> "AgentList":
        """Join two AgentLists (private method).
        
        Args:
            left: The left AgentList to join
            right: The right AgentList to join
            join_type: The type of join to perform ("inner", "left", or "right")
            
        Returns:
            AgentList: A new AgentList containing the joined results
            
        Raises:
            AssertionError: If agents don't have names
            ValueError: If join_type is invalid
        """
        from .agent_list import AgentList
        
        assert all([agent.name is not None for agent in left.data]), "Agents must have names to join."
        assert all([agent.name is not None for agent in right.data]), "Other agents must have names to join."
        
        inner_list = []
        left_list = []
        right_list = []
        
        for agent in left.data:
            for other_agent in right.data:
                if agent.name == other_agent.name:
                    new_agent = agent + other_agent
                    inner_list.append(new_agent)
                    left_list.append(agent)
                    right_list.append(other_agent)
                else:
                    right_list.append(other_agent)
                    left_list.append(agent)

        if len(inner_list) != len(right_list) and len(inner_list) != len(left_list):
            warnings.warn(f"The number of agents in the left list is {len(left_list)} and the number of agents in the right list is {len(right_list)}.")
            warnings.warn(f"The number of agents in the inner list is {len(inner_list)}.")
            warnings.warn(f"The number of agents in the left list is {len(left_list)} and the number of agents in the right list is {len(right_list)}.")
        
        if join_type == "inner":
            return AgentList(inner_list)
        elif join_type == "left":
            return AgentList(left_list)
        elif join_type == "right":
            return AgentList(right_list)
        else:
            raise ValueError(f"Invalid join type: {join_type}")

    @staticmethod
    def join_two(left: "AgentList", right: "AgentList", join_type: str = "inner") -> "AgentList":
        """Join two AgentLists.
        
        Args:
            left: The left AgentList to join
            right: The right AgentList to join with
            join_type: The type of join to perform ("inner", "left", or "right")
            
        Returns:
            AgentList: A new AgentList containing the joined results
            
        Examples:
            >>> from edsl import Agent, AgentList
            >>> from edsl.agents.agent_list_joiner import AgentListJoiner
            >>> al1 = AgentList([Agent(name="John", traits={"age": 30})])
            >>> al2 = AgentList([Agent(name="John", traits={"height": 180})])
            >>> joined = AgentListJoiner.join_two(al1, al2)
            >>> joined[0].traits
            {'age': 30, 'height': 180}
        """
        return AgentListJoiner._join_two(left, right, join_type=join_type)

    @staticmethod
    def join_multiple(*agent_lists: "AgentList", join_type: str = "inner") -> "AgentList":
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
            >>> from edsl.agents.agent_list_joiner import AgentListJoiner
            >>> al1 = AgentList([Agent(name="John", traits={"age": 30})])
            >>> al2 = AgentList([Agent(name="John", traits={"height": 180})])
            >>> al3 = AgentList([Agent(name="John", traits={"weight": 75})])
            >>> joined = AgentListJoiner.join_multiple(al1, al2, al3)
            >>> len(joined)
            1
            >>> joined[0].traits
            {'age': 30, 'height': 180, 'weight': 75}
        """
        if len(agent_lists) < 2:
            raise ValueError("At least 2 AgentLists are required for joining")
        
        # Start with the first AgentList
        result = agent_lists[0]
        
        # Sequentially join with each subsequent AgentList
        for agent_list in agent_lists[1:]:
            result = AgentListJoiner._join_two(result, agent_list, join_type=join_type)
            
        return result 