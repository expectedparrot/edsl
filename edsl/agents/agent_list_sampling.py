"""AgentList sampling and splitting operations module."""

from __future__ import annotations

import random
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_list import AgentList


class AgentListSampling:
    """Handles sampling, shuffling, splitting, and duplication for AgentList objects.

    Instantiated with a reference to an AgentList; provides methods for
    random sampling, shuffling, train/test splitting, and deep copying.
    """

    def __init__(self, agent_list: "AgentList") -> None:
        self._agent_list = agent_list

    def shuffle(self, seed: Optional[str] = None) -> "AgentList":
        """Randomly shuffle the agents in place.

        Args:
            seed: Optional seed for the random number generator to ensure reproducibility.

        Returns:
            The shuffled AgentList (self).
        """
        if seed is not None:
            random.seed(seed)
        random.shuffle(self._agent_list.data)
        return self._agent_list

    def sample(self, n: int, seed: Optional[str] = None) -> "AgentList":
        """Return a random sample of agents.

        Args:
            n: The number of agents to sample.
            seed: Optional seed for the random number generator to ensure reproducibility.

        Returns:
            A new AgentList containing the sampled agents.
        """
        from .agent_list import AgentList

        if seed:
            random.seed(seed)
        return AgentList(random.sample(self._agent_list.data, n))

    def split(
        self, frac_left: float, seed: Optional[int] = None
    ) -> tuple["AgentList", "AgentList"]:
        """Split the AgentList into two random groups.

        Randomly assigns agents to two groups (left and right) based on the specified
        fraction. Useful for creating train/test splits or other random partitions.

        Args:
            frac_left: Fraction (0-1) of agents to assign to the left group.
            seed: Optional random seed for reproducibility.

        Returns:
            A tuple containing (left, right) AgentLists.

        Raises:
            ValueError: If frac_left is not between 0 and 1.

        Examples:
            >>> from edsl import Agent, AgentList
            >>> al = AgentList([Agent(traits={'id': i}) for i in range(10)])
            >>> left, right = al.split(0.7, seed=42)
            >>> len(left)
            7
            >>> len(right)
            3

            >>> al = AgentList([Agent(traits={'id': i}) for i in range(5)])
            >>> left1, right1 = al.split(0.6, seed=123)
            >>> left2, right2 = al.split(0.6, seed=123)
            >>> len(left1) == len(left2) and len(right1) == len(right2)
            True
        """
        from ..utilities import list_split

        return list_split(self._agent_list, frac_left, seed)

    def duplicate(self) -> "AgentList":
        """Create a deep copy of the AgentList.

        Returns:
            A new AgentList containing copies of all agents.

        Examples:
            >>> from edsl import AgentList
            >>> al = AgentList.example()
            >>> al2 = al.duplicate()
            >>> al2 == al
            True
            >>> id(al2) == id(al)
            False
        """
        from .agent_list import AgentList

        return AgentList([a.duplicate() for a in self._agent_list.data])
