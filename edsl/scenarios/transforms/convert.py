"""Conversion transforms: collapse / expand between Scenario and ScenarioList."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList
    from ..scenario import Scenario
    from ...agents.agent import Agent


class ConvertMixin:
    """Mixin providing ScenarioList <-> Scenario conversion methods."""

    def to_scenario_of_lists(self) -> "Scenario":
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
            >>> sl.to_scenario_of_lists()
            Scenario({'a': [1, 2], 'b': [10, 20]})

            >>> sl_ragged = ScenarioList([
            ...     Scenario({"a": 1}),
            ...     Scenario({"b": 2}),
            ... ])
            >>> sl_ragged.to_scenario_of_lists()
            Scenario({'a': [1, None], 'b': [None, 2]})
        """
        from ..scenario import Scenario

        # Empty input -> empty Scenario
        if len(self._scenario_list) == 0:
            return Scenario({})

        # Preserve field order: start with the first row's keys, then add any new
        # keys as they are first encountered across subsequent rows.
        keys: List[str] = list(self._scenario_list[0].keys())
        seen = set(keys)
        for row in self._scenario_list:
            for key in row.keys():
                if key not in seen:
                    keys.append(key)
                    seen.add(key)

        # Build dict of lists, padding missing keys with None
        collapsed: dict[str, list] = {}
        for key in keys:
            collapsed[key] = [s.get(key, None) for s in self._scenario_list]

        return Scenario(collapsed)

    def to_agent_traits(self, agent_name: "str | None" = None) -> "Agent":
        """Convert all Scenario objects into traits of a single Agent.

        Mirrors ScenarioList.to_agent_traits behavior.
        """
        from ...agents import Agent

        all_traits: dict[str, object] = {}
        key_counts: dict[str, int] = {}

        for scenario in self._scenario_list.data:
            scenario_dict = scenario.to_dict(add_edsl_version=False)

            for key, value in scenario_dict.items():
                if key in ["edsl_version", "edsl_class_name"]:
                    continue

                if key == "name":
                    key = "scenario_name"

                if key in all_traits:
                    key_counts[key] = key_counts.get(key, 0) + 1
                    new_key = f"{key}_{key_counts[key]}"
                else:
                    key_counts[key] = 0
                    new_key = key

                all_traits[new_key] = value

        if agent_name is None:
            agent_name = f"Agent_from_{len(self._scenario_list)}_scenarios"

        return Agent(traits=all_traits, name=agent_name)
