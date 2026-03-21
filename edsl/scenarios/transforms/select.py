"""Select transforms: select, drop, keep, rename, snakify, replace_names, reorder_keys."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class SelectMixin:
    """Mixin providing selection and renaming operations on ScenarioList."""

    def select(self, *fields: str) -> "ScenarioList":
        """Select only specified fields from all scenarios in the list.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
            >>> s.select('a')
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        from ..scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            try:
                new_sl.append(scenario.select(*fields))
            except KeyError:
                from ..exceptions import KeyScenarioError

                raise KeyScenarioError(
                    f"Key {fields} not found in scenario {scenario.keys()}"
                )
        return new_sl

    def drop(self, *fields: str) -> "ScenarioList":
        """Drop fields from the scenarios.

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
            >>> s.drop('a')
            ScenarioList([Scenario({'b': 1}), Scenario({'b': 2})])
        """
        from ..scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            new_sl.append(scenario.drop(fields))
        return new_sl

    def keep(self, *fields: str) -> "ScenarioList":
        """Keep only the specified fields in the scenarios.

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
            >>> s.keep('a')
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        from ..scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            new_sl.append(scenario.keep(fields))
        return new_sl

    def rename(self, replacement_dict: dict) -> "ScenarioList":
        """Rename the fields in the scenarios.

        Example:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
            >>> s.rename({'name': 'first_name', 'age': 'years'})
            ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])
        """
        from ..scenario_list import ScenarioList
        from ..exceptions import KeyScenarioError

        all_keys = set()
        for scenario in self._scenario_list:
            all_keys.update(scenario.keys())

        missing_keys = [key for key in replacement_dict.keys() if key not in all_keys]
        if missing_keys:
            raise KeyScenarioError(
                f"The following keys in replacement_dict are not present in any scenario: {', '.join(missing_keys)}"
            )

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            new_scenario = scenario.rename(replacement_dict)
            new_sl.append(new_scenario)
        return new_sl

    def snakify(self) -> "ScenarioList":
        """Convert all scenario keys to valid Python identifiers (snake_case).

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'First Name': 'Alice', 'Age Group': '30s'})])
            >>> result = s.snakify()
            >>> sorted(result[0].keys())
            ['age_group', 'first_name']
        """
        from ..scenario_snakifier import ScenarioSnakifier

        return ScenarioSnakifier(self._scenario_list).snakify()

    def replace_names(self, new_names: list) -> "ScenarioList":
        """Replace the field names in the scenarios with a new list of names.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
            >>> s.replace_names(['first_name', 'years'])
            ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])
        """
        from ..scenario_list import ScenarioList
        from ..exceptions import ScenarioError

        if not self._scenario_list:
            return ScenarioList([])

        if len(new_names) != len(self._scenario_list[0].keys()):
            raise ScenarioError(
                f"Length of new names ({len(new_names)}) does not match number of fields ({len(self._scenario_list[0].keys())})"
            )

        old_names = list(self._scenario_list[0].keys())
        replacement_dict = dict(zip(old_names, new_names))
        return self.rename(replacement_dict)

    def reorder_keys(
        self, new_order: list[str]
    ) -> "ScenarioList":
        """Reorder keys in each Scenario according to provided order."""
        from ..scenario_list import ScenarioList  # type: ignore
        from ..scenario import Scenario

        assert set(new_order) == set(self._scenario_list.parameters)

        new_sl = ScenarioList(data=[], codebook=getattr(self._scenario_list, "codebook", {}))
        for scenario in self._scenario_list:
            new_scenario = Scenario({key: scenario[key] for key in new_order})
            new_sl.append(new_scenario)
        return new_sl
