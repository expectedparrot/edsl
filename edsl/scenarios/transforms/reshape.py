"""Reshape transforms: pivot, unpivot, group_by, collapse, expand, chunk, choose_k, split."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class ReshapeMixin:
    """Mixin providing reshape operations on ScenarioList."""

    def unpivot(
        self,
        id_vars: "list[str] | None" = None,
        value_vars: "list[str] | None" = None,
    ) -> "ScenarioList":
        """Unpivot the ScenarioList, allowing for id variables to be specified."""
        from ..scenario_list import ScenarioList  # type: ignore
        from ..scenario import Scenario

        if id_vars is None:
            id_vars = []
        if value_vars is None:
            value_vars = [
                field for field in self._scenario_list[0].keys() if field not in id_vars
            ]

        new_scenarios = ScenarioList(data=[], codebook={})
        for scenario in self._scenario_list:
            for var in value_vars:
                new_scenario = {id_var: scenario[id_var] for id_var in id_vars}
                new_scenario["variable"] = var
                new_scenario["value"] = scenario[var]
                new_scenarios.append(Scenario(new_scenario))

        return new_scenarios

    def pivot(
        self,
        id_vars: "list[str] | None" = None,
        var_name: str = "variable",
        value_name: str = "value",
    ) -> "ScenarioList":
        """Pivot the ScenarioList from long to wide format."""
        from ..scenario_list import ScenarioList  # type: ignore
        from ..scenario import Scenario

        if id_vars is None:
            id_vars = []

        pivoted_dict: dict[tuple, dict] = {}

        for scenario in self._scenario_list:
            id_key = tuple(scenario[id_var] for id_var in id_vars)
            if id_key not in pivoted_dict:
                pivoted_dict[id_key] = {id_var: scenario[id_var] for id_var in id_vars}
            variable = scenario[var_name]
            value = scenario[value_name]
            pivoted_dict[id_key][variable] = value

        new_sl = ScenarioList(data=[], codebook=getattr(self._scenario_list, "codebook", {}))
        for id_key, values in pivoted_dict.items():
            new_sl.append(Scenario(dict(zip(id_vars, id_key), **values)))
        return new_sl

    def group_by(
        self,
        id_vars: list[str],
        variables: list[str],
        func,
    ) -> "ScenarioList":
        """Group the ScenarioList by id_vars and apply a function to variables."""
        from ..scenario_list import ScenarioList  # type: ignore
        from ..exceptions import ScenarioError
        from collections import defaultdict
        import inspect
        from ..scenario import Scenario

        func_params = inspect.signature(func).parameters
        if len(func_params) != len(variables):
            raise ScenarioError(
                f"Function {getattr(func, '__name__', 'fn')} expects {len(func_params)} arguments, but {len(variables)} variables were provided"
            )

        grouped: dict[tuple, dict[str, list]] = defaultdict(lambda: defaultdict(list))
        for scenario in self._scenario_list:
            key = tuple(scenario[id_var] for id_var in id_vars)
            for var in variables:
                grouped[key][var].append(scenario[var])

        new_sl = ScenarioList(data=[], codebook=getattr(self._scenario_list, "codebook", {}))
        for key, group in grouped.items():
            try:
                aggregated = func(*[group[var] for var in variables])
            except Exception as e:
                raise ScenarioError(f"Error applying function to group {key}: {str(e)}")

            if not isinstance(aggregated, dict):
                raise ScenarioError(
                    f"Function {getattr(func, '__name__', 'fn')} must return a dictionary"
                )

            new_scenario = dict(zip(id_vars, key))
            new_scenario.update(aggregated)
            new_sl.append(Scenario(new_scenario))

        return new_sl

    def create_comparisons(
        self,
        bidirectional: bool = False,
        num_options: int = 2,
        option_prefix: str = "option_",
        use_alphabet: bool = False,
    ) -> "ScenarioList":
        """Create a ScenarioList with comparisons between scenarios."""
        from ..scenario_list import ScenarioList  # type: ignore
        from ..scenario import Scenario
        from ..exceptions import ValueScenarioError
        from itertools import combinations, permutations
        import string

        if num_options < 2:
            raise ValueScenarioError("num_options must be at least 2")
        if num_options > len(self._scenario_list):
            raise ValueScenarioError(
                f"num_options ({num_options}) cannot exceed the number of scenarios ({len(self._scenario_list)})"
            )
        if use_alphabet and num_options > 26:
            raise ValueScenarioError(
                "When using alphabet labels, num_options cannot exceed 26 (the number of letters in the English alphabet)"
            )

        scenario_dicts = [s.to_dict(add_edsl_version=False) for s in self._scenario_list]

        if bidirectional:
            if num_options == 2:
                scenario_groups = permutations(scenario_dicts, 2)
            else:
                scenario_groups = permutations(scenario_dicts, num_options)
        else:
            scenario_groups = combinations(scenario_dicts, num_options)

        result = []
        for group in scenario_groups:
            new_scenario: dict[str, dict] = {}
            for i, scenario_dict in enumerate(group):
                if use_alphabet:
                    key = string.ascii_uppercase[i]
                else:
                    key = f"{option_prefix}{i+1}"
                new_scenario[key] = scenario_dict
            result.append(Scenario(new_scenario))

        return ScenarioList(result)

    def collapse(
        self,
        field: str,
        separator: "str | None" = None,
        prefix: str = "",
        postfix: str = "",
        add_count: bool = False,
    ) -> "ScenarioList":
        """Collapse by grouping on all fields except the specified one, collecting values."""
        from ..scenario_list import ScenarioList  # type: ignore
        from ..scenario import Scenario
        from collections import defaultdict

        if not self._scenario_list:
            return ScenarioList([])

        id_vars = [key for key in self._scenario_list[0].keys() if key != field]

        grouped: dict[tuple, list] = defaultdict(list)
        for scenario in self._scenario_list:
            key = tuple(scenario[id_var] for id_var in id_vars)
            grouped[key].append(scenario[field])

        new_sl = ScenarioList(data=[], codebook=getattr(self._scenario_list, "codebook", {}))
        for key, values in grouped.items():
            new_scenario = dict(zip(id_vars, key))
            if separator:
                formatted_values = [f"{prefix}{str(v)}{postfix}" for v in values]
                new_scenario[field] = separator.join(formatted_values)
            else:
                new_scenario[field] = values
            if add_count:
                new_scenario["num_collapsed_rows"] = len(values)
            new_sl.append(Scenario(new_scenario))

        return new_sl

    def expand(self, *expand_fields: str, number_field: bool = False) -> "ScenarioList":
        """Expand the ScenarioList by one or more fields.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'a': 1, 'b': [1, 2]})])
            >>> s.expand('b')
            ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        """
        from ..scenario_list import ScenarioList
        from ..exceptions import ScenarioError

        if not expand_fields:
            raise ScenarioError("expand() requires at least one field name")

        # Single-field case
        if len(expand_fields) == 1:
            expand_field = expand_fields[0]
            new_scenarios = []
            for scenario in self._scenario_list:
                values = scenario[expand_field]
                if not isinstance(values, Iterable) or isinstance(values, str):
                    values = [values]
                for index, value in enumerate(values):
                    new_scenario = scenario.copy()
                    new_scenario[expand_field] = value
                    if number_field:
                        new_scenario[expand_field + "_number"] = index + 1
                    new_scenarios.append(new_scenario)
            return ScenarioList(new_scenarios)

        # Multi-field aligned expansion
        fields = list(expand_fields)
        new_scenarios = []
        for scenario in self._scenario_list:
            value_lists = []
            for field in fields:
                vals = scenario[field]
                if not isinstance(vals, Iterable) or isinstance(vals, str):
                    vals = [vals]
                value_lists.append(list(vals))

            lengths = {len(v) for v in value_lists}
            if len(lengths) != 1:
                lengths_str = ", ".join(
                    f"{fld}:{len(v)}" for fld, v in zip(fields, value_lists)
                )
                raise ScenarioError(
                    f"All fields must have equal lengths for aligned expansion; got {lengths_str}"
                )

            for index, tuple_vals in enumerate(zip(*value_lists)):
                new_scenario = scenario.copy()
                for field, val in zip(fields, tuple_vals):
                    new_scenario[field] = val
                    if number_field:
                        new_scenario[field + "_number"] = index + 1
                new_scenarios.append(new_scenario)

        return ScenarioList(new_scenarios)

    def chunk(
        self,
        field: str,
        num_words: "int | None" = None,
        num_lines: "int | None" = None,
        include_original: bool = False,
        hash_original: bool = False,
    ) -> "ScenarioList":
        """Chunk the scenarios based on a field.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'text': 'The quick brown fox jumps over the lazy dog.'})])
            >>> s.chunk('text', num_words=3)
            ScenarioList([Scenario({'text': 'The quick brown', 'text_chunk': 0, 'text_char_count': 15, 'text_word_count': 3}), Scenario({'text': 'fox jumps over', 'text_chunk': 1, 'text_char_count': 14, 'text_word_count': 3}), Scenario({'text': 'the lazy dog.', 'text_chunk': 2, 'text_char_count': 13, 'text_word_count': 3})])
        """
        from ..scenario_list import ScenarioList

        new_scenarios = []
        for scenario in self._scenario_list:
            replacement_scenarios = scenario.chunk(
                field,
                num_words=num_words,
                num_lines=num_lines,
                include_original=include_original,
                hash_original=hash_original,
            )
            new_scenarios.extend(replacement_scenarios)
        return ScenarioList(new_scenarios)

    def choose_k(self, k: int, order_matters: bool = False) -> "ScenarioList":
        """Create a ScenarioList of all choose-k selections with suffixed keys.

        Examples:
            >>> from edsl import ScenarioList
            >>> s = ScenarioList.from_list('x', ['a', 'b', 'c'])
            >>> s.choose_k(2)
            ScenarioList([Scenario({'x_1': 'a', 'x_2': 'b'}), Scenario({'x_1': 'a', 'x_2': 'c'}), Scenario({'x_1': 'b', 'x_2': 'c'})])
        """
        from ..scenario_list import ScenarioList

        return ScenarioList(list(self._iter_choose_k(k=k, order_matters=order_matters)))

    def _iter_choose_k(self, k: int, order_matters: bool = False):
        """Delegate generator for choose-k to the ScenarioCombinator module."""
        from importlib import import_module

        ScenarioCombinator = import_module(
            "edsl.scenarios.scenario_combinator"
        ).ScenarioCombinator
        return ScenarioCombinator.iter_choose_k(
            self._scenario_list, k=k, order_matters=order_matters
        )

    def split(
        self, frac_left: float = 0.5, seed: "int | None" = None
    ) -> "tuple[ScenarioList, ScenarioList]":
        """Split the ScenarioList into two random groups.

        Examples:
            >>> from edsl import Scenario, ScenarioList
            >>> sl = ScenarioList([Scenario({'id': i}) for i in range(10)])
            >>> left, right = sl.split(seed=42)
            >>> len(left)
            5
        """
        from edsl.utilities.list_split import list_split

        return list_split(self._scenario_list, frac_left, seed)
