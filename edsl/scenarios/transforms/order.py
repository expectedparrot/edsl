"""Order transforms: order_by, shuffle, sample."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class OrderMixin:
    """Mixin providing ordering operations on ScenarioList."""

    def order_by(
        self, fields: list[str], reverse: bool = False
    ) -> "ScenarioList":
        """Order scenarios by one or more fields."""
        from ..scenario_list import ScenarioList  # type: ignore

        def get_sort_key(scenario: object) -> tuple:
            return tuple(scenario[field] for field in fields)

        return ScenarioList(
            sorted(self._scenario_list.data, key=get_sort_key, reverse=reverse)
        )

    def shuffle(self, seed: "str | None" = None) -> "ScenarioList":
        """Shuffle the ScenarioList.

        Examples:
            >>> from edsl import ScenarioList
            >>> s = ScenarioList.from_list("a", [1,2,3,4])
            >>> s.shuffle(seed = "1234")
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 4}), Scenario({'a': 3}), Scenario({'a': 2})])
        """
        import random

        sl = self._scenario_list.duplicate()
        if seed:
            random.seed(seed)
        random.shuffle(sl.data)
        return sl

    def sample(self, n: int, seed: "str | None" = None) -> "ScenarioList":
        """Return a random sample from the ScenarioList.

        Examples:
            >>> from edsl import ScenarioList
            >>> s = ScenarioList.from_list("a", [1,2,3,4,5,6])
            >>> s.sample(3, seed = "edsl")  # doctest: +SKIP
            ScenarioList([Scenario({'a': 2}), Scenario({'a': 1}), Scenario({'a': 3})])
        """
        import random
        from ..scenario_list import ScenarioList

        if seed:
            random.seed(seed)

        sl = self._scenario_list.duplicate()
        data_list = list(sl.data)
        return ScenarioList(random.sample(data_list, n))
