"""
Joiner utilities for ScenarioList.

This module provides join operations for ScenarioList, delegating the
implementation details to ScenarioJoin while keeping ScenarioList thin.
"""

from __future__ import annotations

from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.scenarios.scenario_list import ScenarioList


class ScenarioListJoiner:
    """Handles join operations for a ScenarioList.

    This class wraps a ScenarioList and provides left, inner, and right join
    operations that combine with another ScenarioList.
    """

    def __init__(self, scenario_list: "ScenarioList"):
        """Initialize with a reference to the ScenarioList.

        Args:
            scenario_list: The ScenarioList instance to operate on.
        """
        self._scenario_list = scenario_list

    def left_join(
        self, other: "ScenarioList", by: Union[str, list[str]]
    ) -> "ScenarioList":
        """Perform a left join with another ScenarioList, following SQL join semantics.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on. Cannot be empty.

        Returns:
            A new ScenarioList containing all left scenarios with matching right data added.
            Unmatched right scenarios are excluded; unmatched left scenarios have None for
            right-only fields.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s1 = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
            >>> s2 = ScenarioList([Scenario({'name': 'Alice', 'location': 'New York'}), Scenario({'name': 'Charlie', 'location': 'Los Angeles'})])
            >>> s3 = s1.left_join(s2, 'name')
            >>> s3 == ScenarioList([Scenario({'age': 30, 'location': 'New York', 'name': 'Alice'}), Scenario({'age': 25, 'location': None, 'name': 'Bob'})])
            True
        """
        from edsl.scenarios.join.scenario_join import ScenarioJoin

        sj = ScenarioJoin(self._scenario_list, other)
        return sj.left_join(by)

    def inner_join(
        self, other: "ScenarioList", by: Union[str, list[str]]
    ) -> "ScenarioList":
        """Perform an inner join with another ScenarioList, following SQL join semantics.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on. Cannot be empty.

        Returns:
            A new ScenarioList containing only scenarios that have matches in both ScenarioLists

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s1 = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
            >>> s2 = ScenarioList([Scenario({'name': 'Alice', 'location': 'New York'}), Scenario({'name': 'Charlie', 'location': 'Los Angeles'})])
            >>> s4 = s1.inner_join(s2, 'name')
            >>> s4 == ScenarioList([Scenario({'age': 30, 'location': 'New York', 'name': 'Alice'})])
            True
        """
        from edsl.scenarios.join.scenario_join import ScenarioJoin

        sj = ScenarioJoin(self._scenario_list, other)
        return sj.inner_join(by)

    def right_join(
        self, other: "ScenarioList", by: Union[str, list[str]]
    ) -> "ScenarioList":
        """Perform a right join with another ScenarioList, following SQL join semantics.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on. Cannot be empty.

        Returns:
            A new ScenarioList containing all right scenarios with matching left data added.
            Unmatched left scenarios are excluded; unmatched right scenarios have None for
            left-only fields.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s1 = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
            >>> s2 = ScenarioList([Scenario({'name': 'Alice', 'location': 'New York'}), Scenario({'name': 'Charlie', 'location': 'Los Angeles'})])
            >>> s5 = s1.right_join(s2, 'name')
            >>> s5 == ScenarioList([Scenario({'age': 30, 'location': 'New York', 'name': 'Alice'}), Scenario({'age': None, 'location': 'Los Angeles', 'name': 'Charlie'})])
            True
        """
        from edsl.scenarios.join.scenario_join import ScenarioJoin

        sj = ScenarioJoin(self._scenario_list, other)
        return sj.right_join(by)
