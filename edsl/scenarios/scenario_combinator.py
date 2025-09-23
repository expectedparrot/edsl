from __future__ import annotations

from typing import Iterator, TYPE_CHECKING

from itertools import combinations, permutations

from .scenario import Scenario
from .exceptions import ScenarioError

if TYPE_CHECKING:
    from .scenario_list import ScenarioList


class ScenarioCombinator:
    """Utilities for generating combinatorial Scenario structures.

    This module centralizes generator-based combinatorial logic so that
    `ScenarioList` can delegate without carrying implementation details.
    """

    @staticmethod
    def iter_choose_k(
        scenario_list: "ScenarioList",
        k: int,
        order_matters: bool = False,
    ) -> Iterator[Scenario]:
        """Yield scenarios formed by choosing k items from a single-key ScenarioList.

        Each emitted scenario replaces the sole key with suffixed keys
        `<key>_1`, `<key>_2`, ..., `<key>_k`.

        Args:
            scenario_list: The source `ScenarioList` with exactly one key per scenario.
            k: Number of items to choose for each emitted scenario.
            order_matters: If True, generate permutations; otherwise combinations.

        Yields:
            Scenario objects with suffixed keys holding chosen values.

        Raises:
            ScenarioError: If the input is empty, ragged, not single-key, or k is invalid.
        """
        if len(scenario_list) == 0:
            raise ScenarioError("Cannot choose_k from an empty ScenarioList.")

        base_keys = list(scenario_list[0].keys())
        if len(base_keys) != 1:
            raise ScenarioError(
                "choose_k requires scenarios with exactly one key each."
            )
        base_key = base_keys[0]

        for scenario in scenario_list:
            if list(scenario.keys()) != base_keys:
                raise ScenarioError(
                    "Ragged ScenarioList detected. All scenarios must share the same single key for choose_k."
                )

        if k < 1:
            raise ScenarioError("k must be at least 1")
        if k > len(scenario_list):
            raise ScenarioError(
                f"k ({k}) cannot exceed the number of scenarios ({len(scenario_list)})."
            )

        values = [scenario[base_key] for scenario in scenario_list]
        groups = permutations(values, k) if order_matters else combinations(values, k)

        for group in groups:
            new_data = {f"{base_key}_{i+1}": value for i, value in enumerate(group)}
            yield Scenario(new_data)


