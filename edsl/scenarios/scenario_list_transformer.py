"""
Transformer utilities for ScenarioList.

This module contains operations that transform an entire `ScenarioList` into
another representation, keeping `ScenarioList` itself thin by delegating the
implementation details here.
"""

from __future__ import annotations

from typing import List


class ScenarioListTransformer:
    """Collection of transformations operating on a ScenarioList.

    Currently provides:
    - to_scenario_of_lists: Collapse a ScenarioList into a single Scenario with
      the same keys, where each value is the list of values across the list.
    """

    @staticmethod
    def to_scenario_of_lists(scenario_list: "ScenarioList") -> "Scenario":
        """Collapse a ScenarioList to a single Scenario with list-valued fields.

        The resulting Scenario has one entry per field appearing anywhere in the
        input. Each field maps to a list whose elements are taken from the
        corresponding field in each Scenario (row-wise). Missing values are
        represented as None, and key order is preserved by first encountering order.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({"a": 1, "b": 10}),
            ...     Scenario({"a": 2, "b": 20}),
            ... ])
            >>> ScenarioListTransformer.to_scenario_of_lists(sl)
            Scenario({'a': [1, 2], 'b': [10, 20]})

            >>> sl_ragged = ScenarioList([
            ...     Scenario({"a": 1}),
            ...     Scenario({"b": 2}),
            ... ])
            >>> ScenarioListTransformer.to_scenario_of_lists(sl_ragged)
            Scenario({'a': [1, None], 'b': [None, 2]})
        """
        from .scenario import Scenario

        # Empty input -> empty Scenario
        if len(scenario_list) == 0:
            return Scenario({})

        # Preserve field order: start with the first row's keys, then add any new
        # keys as they are first encountered across subsequent rows.
        keys: List[str] = list(scenario_list[0].keys())
        seen = set(keys)
        for row in scenario_list:
            for key in row.keys():
                if key not in seen:
                    keys.append(key)
                    seen.add(key)

        # Build dict of lists, padding missing keys with None
        collapsed: dict[str, list] = {}
        for key in keys:
            collapsed[key] = [s.get(key, None) for s in scenario_list]

        return Scenario(collapsed)


