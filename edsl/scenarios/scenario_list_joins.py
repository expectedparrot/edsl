"""
Namespace class for ScenarioList join methods.

This module provides the `ScenarioListJoin` class which is accessed via
the `.join` property on ScenarioList instances, enabling a clean namespace
for join operations:

    sl.join.left(other, by='key')
    sl.join.inner(other, by='key')
    sl.join.right(other, by='key')

Created: 2026-01-08
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .scenario_list import ScenarioList


class ScenarioListJoin:
    """Namespace for ScenarioList join methods.
    
    Access via the `.join` property on ScenarioList:
    
        >>> from edsl import ScenarioList, Scenario
        >>> s1 = ScenarioList([Scenario({'name': 'Alice', 'age': 30})])
        >>> s2 = ScenarioList([Scenario({'name': 'Alice', 'city': 'NYC'})])
        >>> result = s1.join.left(s2, by='name')
    """
    
    def __init__(self, scenario_list: "ScenarioList"):
        self._sl = scenario_list
    
    def left(self, other: "ScenarioList", by: Union[str, list[str]]) -> "ScenarioList":
        """Perform a left join with another ScenarioList, following SQL join semantics.

        All rows from this ScenarioList are kept, with matching data from `other`
        added where available. Non-matching rows get None for the other's fields.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on.

        Returns:
            A new ScenarioList with left join results.

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> s1 = ScenarioList([
            ...     Scenario({'name': 'Alice', 'age': 30}),
            ...     Scenario({'name': 'Bob', 'age': 25})
            ... ])
            >>> s2 = ScenarioList([
            ...     Scenario({'name': 'Alice', 'location': 'New York'}),
            ...     Scenario({'name': 'Charlie', 'location': 'Los Angeles'})
            ... ])
            >>> s3 = s1.join.left(s2, by='name')
            >>> len(s3)
            2
            >>> s3[0]['location']
            'New York'
            >>> s3[1]['location'] is None
            True
        """
        from .scenario_join import ScenarioJoin
        sj = ScenarioJoin(self._sl, other)
        return sj.left_join(by)
    
    def inner(self, other: "ScenarioList", by: Union[str, list[str]]) -> "ScenarioList":
        """Perform an inner join with another ScenarioList, following SQL join semantics.

        Only rows that have matches in both ScenarioLists are included.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on.

        Returns:
            A new ScenarioList containing only scenarios that have matches in both.

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> s1 = ScenarioList([
            ...     Scenario({'name': 'Alice', 'age': 30}),
            ...     Scenario({'name': 'Bob', 'age': 25})
            ... ])
            >>> s2 = ScenarioList([
            ...     Scenario({'name': 'Alice', 'location': 'New York'}),
            ...     Scenario({'name': 'Charlie', 'location': 'Los Angeles'})
            ... ])
            >>> s4 = s1.join.inner(s2, by='name')
            >>> len(s4)
            1
            >>> s4[0]['name']
            'Alice'
        """
        from .scenario_join import ScenarioJoin
        sj = ScenarioJoin(self._sl, other)
        return sj.inner_join(by)
    
    def right(self, other: "ScenarioList", by: Union[str, list[str]]) -> "ScenarioList":
        """Perform a right join with another ScenarioList, following SQL join semantics.

        All rows from `other` are kept, with matching data from this ScenarioList
        added where available. Non-matching rows get None for this list's fields.

        Args:
            other: The ScenarioList to join with
            by: String or list of strings representing the key(s) to join on.

        Returns:
            A new ScenarioList containing all right scenarios with matching left data.

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> s1 = ScenarioList([
            ...     Scenario({'name': 'Alice', 'age': 30}),
            ...     Scenario({'name': 'Bob', 'age': 25})
            ... ])
            >>> s2 = ScenarioList([
            ...     Scenario({'name': 'Alice', 'location': 'New York'}),
            ...     Scenario({'name': 'Charlie', 'location': 'Los Angeles'})
            ... ])
            >>> s5 = s1.join.right(s2, by='name')
            >>> len(s5)
            2
            >>> s5[1]['name']
            'Charlie'
            >>> s5[1]['age'] is None
            True
        """
        from .scenario_join import ScenarioJoin
        sj = ScenarioJoin(self._sl, other)
        return sj.right_join(by)

