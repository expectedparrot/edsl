"""
Transformer utilities for ScenarioList.

This module contains operations that transform an entire `ScenarioList` into
another representation, keeping `ScenarioList` itself thin by delegating the
implementation details here.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario_list import ScenarioList
    from .scenario import Scenario
    from ..agents.agent import Agent


class ScenarioListTransformer:
    """Collection of transformations operating on a ScenarioList.

    Currently provides:
    - to_scenario_of_lists: Collapse a ScenarioList into a single Scenario with
      the same keys, where each value is the list of values across the list.
    - concatenate family: Concatenate fields across each Scenario into string/list/set
      on a new field, preserving streaming behavior and original API.
    """

    def __init__(self, scenario_list: "ScenarioList"):
        """Initialize with a reference to the ScenarioList.

        Args:
            scenario_list: The ScenarioList instance to operate on.
        """
        self._scenario_list = scenario_list

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
        from .scenario import Scenario

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
        from ..agents import Agent

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

    def filter(self, expression: str) -> "ScenarioList":
        """Filter a ScenarioList based on an expression.

        Mirrors ScenarioList.filter behavior and errors.
        """
        from simpleeval import EvalWithCompoundTypes, NameNotDefined
        from .exceptions import ScenarioError
        import warnings as _warnings
        import re
        from .scenario_list import ScenarioList  # type: ignore

        try:
            first_item = self._scenario_list[0] if len(self._scenario_list) > 0 else None
            if first_item:
                sample_size = min(len(self._scenario_list), 100)
                base_keys = set(first_item.keys())
                keys = set()
                count = 0
                for scenario in self._scenario_list:
                    keys.update(scenario.keys())
                    count += 1
                    if count >= sample_size:
                        break
                if keys != base_keys:
                    _warnings.warn(
                        "Ragged ScenarioList detected (different keys for different scenario entries). This may cause unexpected behavior."
                    )
        except IndexError:
            pass

        new_sl = ScenarioList(data=[], codebook=getattr(self._scenario_list, "codebook", {}))

        def create_evaluator(scenario):
            # Handle field names containing dots by creating safe aliases
            scenario_names = dict(scenario)
            modified_expression = expression

            # Find all field names with dots that exist in the scenario
            dot_fields = [key for key in scenario.keys() if "." in key]

            if dot_fields:
                # Create safe aliases for fields with dots
                field_mapping = {}
                for field in dot_fields:
                    # Create a safe alias by replacing dots with underscores and adding prefix
                    safe_alias = f"__dot_field_{field.replace('.', '_dot_')}"
                    field_mapping[field] = safe_alias
                    scenario_names[safe_alias] = scenario[field]

                    # Replace field references in the expression with safe aliases
                    # Use word boundaries to avoid partial replacements
                    pattern = r"\b" + re.escape(field) + r"\b"
                    modified_expression = re.sub(
                        pattern, safe_alias, modified_expression
                    )

            return EvalWithCompoundTypes(names=scenario_names), modified_expression

        try:
            for scenario in self._scenario_list:
                evaluator, eval_expression = create_evaluator(scenario)
                if evaluator.eval(eval_expression):
                    scenario_copy = scenario.copy()
                    new_sl.append(scenario_copy)
                    del scenario_copy
        except NameNotDefined as e:
            try:
                first_item = self._scenario_list[0] if len(self._scenario_list) > 0 else None
                available_fields = ", ".join(first_item.keys() if first_item else [])
            except Exception:
                available_fields = "unknown"

            raise ScenarioError(
                f"Error in filter: '{e}'\n"
                f"The expression '{expression}' refers to a field that does not exist.\n"
                f"Available fields: {available_fields}\n"
                "Check your filter expression or consult the documentation: "
                "https://docs.expectedparrot.com/en/latest/scenarios.html#module-edsl.scenarios.Scenario"
            ) from None
        except Exception as e:
            raise ScenarioError(f"Error in filter. Exception:{e}")

        return new_sl

    def transform(
        self, field: str, func, new_name: "str | None" = None
    ) -> "ScenarioList":
        """Transform a field using a function for each Scenario in the list."""
        from .scenario_list import ScenarioList  # type: ignore

        new_scenarios = []
        for scenario in self._scenario_list:
            new_scenario = scenario.copy()
            new_scenario[new_name or field] = func(scenario[field])
            new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    def apply(
        self,
        func,
        field: str,
        new_name: "str | None",
        replace: bool = False,
    ) -> "ScenarioList":
        """Apply a function to a field and return a new ScenarioList (original semantics)."""
        from .scenario_list import ScenarioList  # type: ignore

        new_list = ScenarioList(
            data=[], codebook=getattr(self._scenario_list, "codebook", {})
        )
        if new_name is None:
            new_name = field
        for scenario in self._scenario_list:
            scenario[new_name] = func(scenario[field])
            if replace:
                del scenario[field]
            new_list.append(scenario)
        return new_list

    def unpack_dict(
        self,
        field: str,
        prefix: "str | None" = None,
        drop_field: bool = False,
    ) -> "ScenarioList":
        """Unpack a dictionary field into separate fields for each Scenario."""
        from .scenario_list import ScenarioList  # type: ignore

        new_scenarios = []
        for scenario in self._scenario_list:
            new_scenario = scenario.copy()
            for key, value in scenario[field].items():
                if prefix:
                    new_scenario[prefix + key] = value
                else:
                    new_scenario[key] = value
            if drop_field:
                new_scenario.pop(field)
            new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    def unpack(
        self,
        field: str,
        new_names: "list[str] | None" = None,
        keep_original: bool = True,
    ) -> "ScenarioList":
        """Unpack a field (list-like) into multiple fields across the list."""
        from .scenario_list import ScenarioList  # type: ignore

        new_names = new_names or [
            f"{field}_{i}" for i in range(len(self._scenario_list[0][field]))
        ]
        new_sl = ScenarioList(data=[], codebook=getattr(self._scenario_list, "codebook", {}))
        for scenario in self._scenario_list:
            new_scenario = scenario.copy()
            if len(new_names) == 1:
                new_scenario[new_names[0]] = scenario[field]
            else:
                for i, new_name in enumerate(new_names):
                    new_scenario[new_name] = scenario[field][i]

            if not keep_original:
                del new_scenario[field]
            new_sl.append(new_scenario)
        return new_sl

    def mutate(
        self,
        new_var_string: str,
        functions_dict: "dict[str, callable] | None" = None,
    ) -> "ScenarioList":
        """Return a new ScenarioList with a new variable added via expression eval."""
        from .scenario_list import ScenarioList  # type: ignore
        from .exceptions import ScenarioError
        from ..utilities import is_valid_variable_name
        from simpleeval import EvalWithCompoundTypes

        if "=" not in new_var_string:
            raise ScenarioError(
                f"Mutate requires an '=' in the string, but '{new_var_string}' doesn't have one."
            )
        raw_var_name, expression = new_var_string.split("=", 1)
        var_name = raw_var_name.strip()

        if not is_valid_variable_name(var_name):
            raise ScenarioError(f"{var_name} is not a valid variable name.")

        functions_dict = functions_dict or {}

        def create_evaluator(scenario) -> EvalWithCompoundTypes:
            return EvalWithCompoundTypes(names=scenario, functions=functions_dict)

        def _new_scenario(old_scenario, var_name: str):
            evaluator = create_evaluator(old_scenario)
            value = evaluator.eval(expression)
            new_s = old_scenario.copy()
            new_s[var_name] = value
            return new_s

        try:
            new_data = [_new_scenario(s, var_name) for s in self._scenario_list]
        except Exception as e:
            raise ScenarioError(f"Error in mutate. Exception:{e}")

        return ScenarioList(new_data)

    def unpivot(
        self,
        id_vars: "list[str] | None" = None,
        value_vars: "list[str] | None" = None,
    ) -> "ScenarioList":
        """Unpivot the ScenarioList, allowing for id variables to be specified."""
        from .scenario_list import ScenarioList  # type: ignore
        from .scenario import Scenario

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
        from .scenario_list import ScenarioList  # type: ignore
        from .scenario import Scenario

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
        from .scenario_list import ScenarioList  # type: ignore
        from .exceptions import ScenarioError
        from collections import defaultdict
        import inspect
        from .scenario import Scenario

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

    def order_by(
        self, fields: list[str], reverse: bool = False
    ) -> "ScenarioList":
        """Order scenarios by one or more fields."""
        from .scenario_list import ScenarioList  # type: ignore

        def get_sort_key(scenario: object) -> tuple:
            return tuple(scenario[field] for field in fields)

        return ScenarioList(
            sorted(self._scenario_list.data, key=get_sort_key, reverse=reverse)
        )

    def reorder_keys(
        self, new_order: list[str]
    ) -> "ScenarioList":
        """Reorder keys in each Scenario according to provided order."""
        from .scenario_list import ScenarioList  # type: ignore
        from .scenario import Scenario

        assert set(new_order) == set(self._scenario_list.parameters)

        new_sl = ScenarioList(data=[], codebook=getattr(self._scenario_list, "codebook", {}))
        for scenario in self._scenario_list:
            new_scenario = Scenario({key: scenario[key] for key in new_order})
            new_sl.append(new_scenario)
        return new_sl

    def create_comparisons(
        self,
        bidirectional: bool = False,
        num_options: int = 2,
        option_prefix: str = "option_",
        use_alphabet: bool = False,
    ) -> "ScenarioList":
        """Create a ScenarioList with comparisons between scenarios.

        Mirrors ScenarioList.create_comparisons behavior.
        """
        from .scenario_list import ScenarioList  # type: ignore
        from .scenario import Scenario
        from .exceptions import ValueScenarioError
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
        """Collapse by grouping on all fields except the specified one, collecting values.

        Mirrors ScenarioList.collapse behavior.
        """
        from .scenario_list import ScenarioList  # type: ignore
        from .scenario import Scenario
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

    def _concatenate(
        self,
        fields: list[str],
        output_type: str = "string",
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: "str | None" = None,
    ) -> "ScenarioList":
        """Core implementation for the concatenate family.

        Mirrors the previous `ScenarioList._concatenate` semantics.
        """
        # Lazy import to avoid circular import at module import time
        from .scenario_list import ScenarioList  # type: ignore

        if isinstance(fields, str):
            from .exceptions import ScenarioError

            raise ScenarioError(
                f"The 'fields' parameter must be a list of field names, not a string. Got '{fields}'."
            )

        new_scenarios = []
        for scenario in self._scenario_list:
            new_scenario = scenario.copy()
            values = []
            for field in fields:
                if field in new_scenario:
                    values.append(new_scenario[field])
                    del new_scenario[field]

            field_name = (
                new_field_name
                if new_field_name is not None
                else f"concat_{'_'.join(fields)}"
            )

            if output_type == "string":
                formatted_values = [f"{prefix}{str(v)}{postfix}" for v in values]
                new_scenario[field_name] = separator.join(formatted_values)
            elif output_type == "list":
                if prefix or postfix:
                    formatted_values = [f"{prefix}{str(v)}{postfix}" for v in values]
                    new_scenario[field_name] = formatted_values
                else:
                    new_scenario[field_name] = values
            elif output_type == "set":
                if prefix or postfix:
                    formatted_values = [f"{prefix}{str(v)}{postfix}" for v in values]
                    new_scenario[field_name] = set(formatted_values)
                else:
                    new_scenario[field_name] = set(values)
            else:
                from .exceptions import ValueScenarioError

                raise ValueScenarioError(
                    "Invalid output_type: {output_type}. Must be 'string', 'list', or 'set'."
                )

            new_scenarios.append(new_scenario)

        return ScenarioList(new_scenarios)

    def concatenate(
        self,
        fields: list[str],
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: "str | None" = None,
    ) -> "ScenarioList":
        return self._concatenate(
            fields,
            output_type="string",
            separator=separator,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    def concatenate_to_list(
        self,
        fields: list[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: "str | None" = None,
    ) -> "ScenarioList":
        return self._concatenate(
            fields,
            output_type="list",
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    def concatenate_to_set(
        self,
        fields: list[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: "str | None" = None,
    ) -> "ScenarioList":
        return self._concatenate(
            fields,
            output_type="set",
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    def expand(self, *expand_fields: str, number_field: bool = False) -> "ScenarioList":
        """Expand the ScenarioList by one or more fields.

        - When a single field is provided, behavior is unchanged: expand rows by that field.
        - When multiple fields are provided, they are expanded in lockstep (aligned). Each
          field must be an iterable (strings are treated as scalars) of equal length; the
          i-th elements across all fields are combined into one expanded row.

        Args:
            *expand_fields: One or more field names to expand. When multiple, lengths must match.
            number_field: Whether to add a per-field index (1-based) for expanded values as
                ``<field>_number``.

        Examples:

            Single-field (unchanged):
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'a': 1, 'b': [1, 2]})])
            >>> s.expand('b')
            ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
            >>> s.expand('b', number_field=True)
            ScenarioList([Scenario({'a': 1, 'b': 1, 'b_number': 1}), Scenario({'a': 1, 'b': 2, 'b_number': 2})])

            Multi-field aligned expansion:
            >>> s2 = ScenarioList([Scenario({'a': 1, 'b': [1, 2], 'c': ['x', 'y']})])
            >>> s2.expand('b', 'c')
            ScenarioList([Scenario({'a': 1, 'b': 1, 'c': 'x'}), Scenario({'a': 1, 'b': 2, 'c': 'y'})])
            >>> s2.expand('b', 'c', number_field=True)  # doctest: +ELLIPSIS
            ScenarioList([Scenario({'a': 1, 'b': 1, 'c': 'x', 'b_number': 1, 'c_number': 1}), ...])
        """
        from .scenario_list import ScenarioList
        from .exceptions import ScenarioError

        if not expand_fields:
            raise ScenarioError("expand() requires at least one field name")

        # Preserve original behavior for the single-field case
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

    def select(self, *fields: str) -> "ScenarioList":
        """Select only specified fields from all scenarios in the list.

        This method applies the select operation to each scenario in the list,
        returning a new ScenarioList where each scenario contains only the
        specified fields.

        Args:
            *fields: Field names to select from each scenario.

        Returns:
            A new ScenarioList with each scenario containing only the selected fields.

        Raises:
            KeyError: If any specified field doesn't exist in any scenario.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
            >>> s.select('a')
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        from .scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            try:
                new_sl.append(scenario.select(*fields))
            except KeyError:
                from .exceptions import KeyScenarioError

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
        from .scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            new_sl.append(scenario.drop(fields))
        return new_sl

    def keep(self, *fields: str) -> "ScenarioList":
        """Keep only the specified fields in the scenarios.

        :param fields: The fields to keep.

        Example:

        >>> from edsl import ScenarioList, Scenario
        >>> s = ScenarioList([Scenario({'a': 1, 'b': 1}), Scenario({'a': 1, 'b': 2})])
        >>> s.keep('a')
        ScenarioList([Scenario({'a': 1}), Scenario({'a': 1})])
        """
        from .scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            new_sl.append(scenario.keep(fields))
        return new_sl

    def numberify(self) -> "ScenarioList":
        """Convert string values to numeric types where possible.

        This method attempts to convert string values to integers or floats
        for all fields across all scenarios. It's particularly useful when loading
        data from CSV files where numeric fields may be stored as strings.

        Conversion rules:
        - None values remain None
        - Already numeric values (int, float) remain unchanged
        - String values that can be parsed as integers are converted to int
        - String values that can be parsed as floats are converted to float
        - String values that cannot be parsed remain as strings
        - Empty strings remain as empty strings

        Returns:
            ScenarioList: A new ScenarioList with numeric conversions applied

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({'age': '30', 'height': '5.5', 'name': 'Alice'}),
            ...     Scenario({'age': '25', 'height': '6.0', 'name': 'Bob'})
            ... ])
            >>> sl_numeric = sl.numberify()
            >>> sl_numeric[0]
            Scenario({'age': 30, 'height': 5.5, 'name': 'Alice'})
            >>> sl_numeric[1]
            Scenario({'age': 25, 'height': 6.0, 'name': 'Bob'})

            Works with None values and mixed types:

            >>> sl = ScenarioList([Scenario({'count': '100', 'value': None, 'label': 'test'})])
            >>> sl_numeric = sl.numberify()
            >>> sl_numeric[0]
            Scenario({'count': 100, 'value': None, 'label': 'test'})
        """
        from .scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            new_sl.append(scenario.numberify())
        return new_sl

    def tack_on(self, replacements: "dict[str, Any]", index: int = -1) -> "ScenarioList":
        """Add a duplicate of an existing scenario with optional value replacements.

        This method duplicates the scenario at *index* (default ``-1`` which refers to the
        last scenario), applies the key/value pairs provided in *replacements*, and
        returns a new ScenarioList with the modified scenario appended.

        Args:
            replacements: Mapping of field names to new values to overwrite in the cloned
                scenario.
            index: Index of the scenario to duplicate. Supports negative indexing just
                like normal Python lists (``-1`` is the last item).

        Returns:
            ScenarioList: A new ScenarioList containing all original scenarios plus the
            newly created one.

        Raises:
            ScenarioError: If the ScenarioList is empty, *index* is out of range, or if
                any key in *replacements* does not exist in the reference scenario.
        """
        from .exceptions import ScenarioError

        # Ensure there is at least one scenario to duplicate
        if len(self._scenario_list) == 0:
            raise ScenarioError("Cannot tack_on to an empty ScenarioList.")

        # Resolve negative indices and validate range
        if index < 0:
            index = len(self._scenario_list) + index
        if index < 0 or index >= len(self._scenario_list):
            raise ScenarioError(
                f"Index {index} is out of range for ScenarioList of length {len(self._scenario_list)}."
            )

        # Reference scenario to clone
        reference = self._scenario_list[index]

        # Verify that all replacement keys are present in the scenario
        missing_keys = [key for key in replacements if key not in reference]
        if missing_keys:
            raise ScenarioError(
                f"Replacement keys not found in scenario: {', '.join(missing_keys)}"
            )

        # Create a modified copy of the scenario
        new_scenario = reference.copy()
        for key, value in replacements.items():
            new_scenario[key] = value

        # Duplicate the ScenarioList and append the modified scenario
        new_sl = self._scenario_list.duplicate()
        new_sl.append(new_scenario)
        return new_sl

    def rename(self, replacement_dict: dict) -> "ScenarioList":
        """Rename the fields in the scenarios.

        :param replacement_dict: A dictionary with the old names as keys and the new names as values.

        Raises:
            KeyScenarioError: If any key in replacement_dict is not present in any scenario.

        Example:

        >>> from edsl import ScenarioList, Scenario
        >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        >>> s.rename({'name': 'first_name', 'age': 'years'})
        ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])

        """
        from .scenario_list import ScenarioList
        from .exceptions import KeyScenarioError

        # Collect all keys present across all scenarios
        all_keys = set()
        for scenario in self._scenario_list:
            all_keys.update(scenario.keys())

        # Check for keys in replacement_dict that are not present in any scenario
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

        This method delegates to ScenarioSnakifier to transform all keys to lowercase,
        replace spaces and special characters with underscores, and ensure all keys are
        valid Python identifiers. If multiple keys would map to the same snakified name,
        numbers are appended to ensure uniqueness.

        Returns:
            ScenarioList: A new ScenarioList with snakified keys.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'First Name': 'Alice', 'Age Group': '30s'})])
            >>> result = s.snakify()
            >>> sorted(result[0].keys())
            ['age_group', 'first_name']
            >>> result[0]['first_name']
            'Alice'
            >>> result[0]['age_group']
            '30s'

            >>> s = ScenarioList([Scenario({'name': 'Alice', 'Name': 'Bob', 'NAME': 'Charlie'})])
            >>> result = s.snakify()
            >>> sorted(result[0].keys())
            ['name', 'name_1', 'name_2']

            >>> s = ScenarioList([Scenario({'User-Name': 'Alice', '123field': 'test', 'valid_key': 'keep'})])
            >>> result = s.snakify()
            >>> sorted(result[0].keys())
            ['_123field', 'user_name', 'valid_key']
        """
        from .scenario_snakifier import ScenarioSnakifier

        return ScenarioSnakifier(self._scenario_list).snakify()

    def replace_values(self, replacements: dict) -> "ScenarioList":
        """
        Create new scenarios with values replaced according to the provided replacement dictionary.

        Args:
            replacements (dict): Dictionary of values to replace {old_value: new_value}

        Returns:
            ScenarioList: A new ScenarioList with replaced values

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': 'nan', 'b': 1}),
            ...     Scenario({'a': 2, 'b': 'nan'})
            ... ])
            >>> replaced = scenarios.replace_values({'nan': None})
            >>> print(replaced)
            ScenarioList([Scenario({'a': None, 'b': 1}), Scenario({'a': 2, 'b': None})])
            >>> # Original scenarios remain unchanged
            >>> print(scenarios)
            ScenarioList([Scenario({'a': 'nan', 'b': 1}), Scenario({'a': 2, 'b': 'nan'})])
        """
        from .scenario_list import ScenarioList
        from .scenario import Scenario

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            new_scenario = {}
            for key, value in scenario.items():
                if str(value) in replacements:
                    new_scenario[key] = replacements[str(value)]
                else:
                    new_scenario[key] = value
            new_sl.append(Scenario(new_scenario))
        return new_sl

    def unique(self) -> "ScenarioList":
        """
        Return a new ScenarioList containing only unique Scenario objects.

        This method removes duplicate Scenario objects based on their hash values,
        which are determined by their content. Two Scenarios with identical key-value
        pairs will have the same hash and be considered duplicates.

        Returns:
            A new ScenarioList containing only unique Scenario objects.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> s1 = Scenario({"a": 1})
            >>> s2 = Scenario({"a": 1})  # Same content as s1
            >>> s3 = Scenario({"a": 2})
            >>> sl = ScenarioList([s1, s2, s3])
            >>> unique_sl = sl.unique()
            >>> len(unique_sl)
            2
            >>> unique_sl
            ScenarioList([Scenario({'a': 1}), Scenario({'a': 2})])

        Notes:
            - The order of scenarios in the result is not guaranteed due to the use of sets
            - Uniqueness is determined by the Scenario's __hash__ method
            - The original ScenarioList is not modified
            - This implementation is memory efficient as it processes scenarios one at a time
        """
        from .scenario_list import ScenarioList

        seen_hashes = set()
        result = ScenarioList()

        for scenario in self._scenario_list.data:
            scenario_hash = hash(scenario)
            if scenario_hash not in seen_hashes:
                seen_hashes.add(scenario_hash)
                result.append(scenario)

        return result

    def uniquify(self, field: str) -> "ScenarioList":
        """
        Make all values of a field unique by appending suffixes (_1, _2, etc.) as needed.

        This method ensures that all values for the specified field are unique across
        all scenarios in the list. When duplicate values are encountered, they are made
        unique by appending suffixes like "_1", "_2", "_3", etc. The first occurrence
        of a value remains unchanged.

        Args:
            field: The name of the field whose values should be made unique.

        Returns:
            A new ScenarioList with unique field values.

        Raises:
            ScenarioError: If the field does not exist in any scenario.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({"id": "item", "value": 1}),
            ...     Scenario({"id": "item", "value": 2}),
            ...     Scenario({"id": "item", "value": 3}),
            ...     Scenario({"id": "other", "value": 4})
            ... ])
            >>> unique_sl = sl.uniquify("id")
            >>> [s["id"] for s in unique_sl]
            ['item', 'item_1', 'item_2', 'other']

        Notes:
            - The original ScenarioList is not modified
            - Scenarios without the specified field are left unchanged
            - The codebook is preserved in the result
            - Suffixes are numbered sequentially starting from 1
        """
        from .scenario_list import ScenarioList
        from .scenario import Scenario
        from .exceptions import ScenarioError

        # Check if field exists in at least one scenario
        if not any(field in scenario for scenario in self._scenario_list.data):
            raise ScenarioError(f"Field '{field}' not found in any scenario")

        seen_values = {}  # Maps original value to count of occurrences
        result = ScenarioList(codebook=self._scenario_list.codebook)

        for scenario in self._scenario_list.data:
            # Skip scenarios that don't have this field
            if field not in scenario:
                result.append(scenario)
                continue

            original_value = scenario[field]

            # Determine the new unique value
            if original_value not in seen_values:
                # First occurrence - use original value
                new_value = original_value
                seen_values[original_value] = 1
            else:
                # Duplicate - append suffix
                suffix_num = seen_values[original_value]
                new_value = f"{original_value}_{suffix_num}"
                seen_values[original_value] += 1

            # Create new scenario with updated field value
            new_scenario_dict = dict(scenario)
            new_scenario_dict[field] = new_value
            result.append(Scenario(new_scenario_dict))

        return result

    def shuffle(self, seed: "str | None" = None) -> "ScenarioList":
        """Shuffle the ScenarioList.

        Args:
            seed: Optional random seed for reproducibility.

        Returns:
            A new shuffled ScenarioList.

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

        Args:
            n: Number of scenarios to sample.
            seed: Optional random seed for reproducibility.

        Returns:
            A new ScenarioList with n randomly sampled scenarios.

        Examples:
            >>> from edsl import ScenarioList
            >>> s = ScenarioList.from_list("a", [1,2,3,4,5,6])
            >>> s.sample(3, seed = "edsl")  # doctest: +SKIP
            ScenarioList([Scenario({'a': 2}), Scenario({'a': 1}), Scenario({'a': 3})])
        """
        import random
        from .scenario_list import ScenarioList

        if seed:
            random.seed(seed)

        sl = self._scenario_list.duplicate()
        # Convert to list if necessary for random.sample
        data_list = list(sl.data)
        return ScenarioList(random.sample(data_list, n))

    def split(
        self, frac_left: float = 0.5, seed: "int | None" = None
    ) -> "tuple[ScenarioList, ScenarioList]":
        """Split the ScenarioList into two random groups.

        Randomly assigns scenarios to two groups (left and right) based on the specified
        fraction. Useful for creating train/test splits or other random partitions.

        Args:
            frac_left: Fraction (0-1) of scenarios to assign to the left group. Defaults to 0.5.
            seed: Optional random seed for reproducibility.

        Returns:
            tuple[ScenarioList, ScenarioList]: A tuple containing (left, right) ScenarioLists.

        Raises:
            ValueError: If frac_left is not between 0 and 1.

        Examples:
            Split a scenario list 50/50 (default):

            >>> from edsl import Scenario, ScenarioList
            >>> sl = ScenarioList([Scenario({'id': i}) for i in range(10)])
            >>> left, right = sl.split(seed=42)
            >>> len(left)
            5
            >>> len(right)
            5

            Split a scenario list 70/30:

            >>> sl = ScenarioList([Scenario({'id': i}) for i in range(10)])
            >>> left, right = sl.split(0.7, seed=42)
            >>> len(left)
            7
            >>> len(right)
            3

            Create reproducible splits:

            >>> sl = ScenarioList([Scenario({'id': i}) for i in range(5)])
            >>> left1, right1 = sl.split(0.6, seed=123)
            >>> left2, right2 = sl.split(0.6, seed=123)
            >>> len(left1) == len(left2) and len(right1) == len(right2)
            True
        """
        from edsl.utilities.list_split import list_split

        return list_split(self._scenario_list, frac_left, seed)

    def fillna(self, value: Any = "", inplace: bool = False) -> "ScenarioList":
        """
        Fill None/NaN values in all scenarios with a specified value.

        This method is equivalent to pandas' df.fillna() functionality, allowing you to
        replace None, NaN, or other null-like values across all scenarios in the list.

        Args:
            value: The value to use for filling None/NaN values. Defaults to empty string "".
            inplace: If True, modify the original ScenarioList. If False (default),
                    return a new ScenarioList with filled values.

        Returns:
            ScenarioList: A new ScenarioList with filled values, or self if inplace=True

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': None, 'b': 1, 'c': 'hello'}),
            ...     Scenario({'a': 2, 'b': None, 'c': None}),
            ...     Scenario({'a': None, 'b': 3, 'c': 'world'})
            ... ])
            >>> # Fill None values with empty string (default)
            >>> filled = scenarios.fillna()
            >>> print(filled)
            ScenarioList([Scenario({'a': '', 'b': 1, 'c': 'hello'}), Scenario({'a': 2, 'b': '', 'c': ''}), Scenario({'a': '', 'b': 3, 'c': 'world'})])
            >>> # Fill with custom value
            >>> filled_custom = scenarios.fillna(value="N/A")
            >>> print(filled_custom)
            ScenarioList([Scenario({'a': 'N/A', 'b': 1, 'c': 'hello'}), Scenario({'a': 2, 'b': 'N/A', 'c': 'N/A'}), Scenario({'a': 'N/A', 'b': 3, 'c': 'world'})])
        """
        from .scenario_list import ScenarioList
        from .scenario import Scenario

        def is_null(val):
            """Check if a value is considered null/None."""
            return val is None or (
                hasattr(val, "__str__")
                and str(val).lower() in ["nan", "none", "null", ""]
            )

        if inplace:
            # Modify the original scenarios
            for scenario in self._scenario_list:
                for key in scenario:
                    if is_null(scenario[key]):
                        scenario[key] = value
            return self._scenario_list
        else:
            # Create new scenarios with filled values
            new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
            for scenario in self._scenario_list:
                new_scenario = {}
                for key, val in scenario.items():
                    if is_null(val):
                        new_scenario[key] = value
                    else:
                        new_scenario[key] = val
                new_sl.append(Scenario(new_scenario))
            return new_sl

    def filter_na(self, fields: "str | list[str]" = "*") -> "ScenarioList":
        """
        Remove scenarios where specified fields contain None or NaN values.

        This method filters out scenarios that have null/NaN values in the specified
        fields. It's similar to pandas' dropna() functionality. Values considered as
        NA include: None, float('nan'), and string representations like 'nan', 'none', 'null'.

        Args:
            fields: Field name(s) to check for NA values. Can be:
                    - "*" (default): Check all fields in each scenario
                    - A single field name (str): Check only that field
                    - A list of field names: Check all specified fields

                    A scenario is kept only if NONE of the specified fields contain NA values.

        Returns:
            ScenarioList: A new ScenarioList containing only scenarios without NA values
                         in the specified fields.

        Examples:
            Remove scenarios with any NA values in any field:
            >>> from edsl import ScenarioList, Scenario
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': 1, 'b': 2}),
            ...     Scenario({'a': None, 'b': 3}),
            ...     Scenario({'a': 4, 'b': 5})
            ... ])
            >>> filtered = scenarios.filter_na()
            >>> len(filtered)
            2
            >>> filtered[0]['a']
            1

            Remove scenarios with NA in specific field:
            >>> scenarios = ScenarioList([
            ...     Scenario({'name': 'Alice', 'age': 30}),
            ...     Scenario({'name': None, 'age': 25}),
            ...     Scenario({'name': 'Bob', 'age': None})
            ... ])
            >>> filtered = scenarios.filter_na('name')
            >>> len(filtered)
            2
            >>> filtered[0]['name']
            'Alice'
            >>> filtered[1]['name']
            'Bob'

            Remove scenarios with NA in multiple specific fields:
            >>> filtered = scenarios.filter_na(['name', 'age'])
            >>> len(filtered)
            1
            >>> filtered[0]['name']
            'Alice'

            Handle float NaN values:
            >>> import math
            >>> scenarios = ScenarioList([
            ...     Scenario({'x': 1.0, 'y': 2.0}),
            ...     Scenario({'x': float('nan'), 'y': 3.0}),
            ...     Scenario({'x': 4.0, 'y': 5.0})
            ... ])
            >>> filtered = scenarios.filter_na('x')
            >>> len(filtered)
            2
        """
        import math
        from .scenario_list import ScenarioList

        def is_na(val):
            """Check if a value is considered NA (None or NaN)."""
            if val is None:
                return True
            # Check for float NaN
            if isinstance(val, float) and math.isnan(val):
                return True
            # Check for string representations of null values
            if hasattr(val, "__str__"):
                str_val = str(val).lower()
                if str_val in ["nan", "none", "null"]:
                    return True
            return False

        # Determine which fields to check
        if fields == "*":
            # Check all fields - need to collect all unique keys across scenarios
            check_fields = set()
            for scenario in self._scenario_list:
                check_fields.update(scenario.keys())
            check_fields = list(check_fields)
        elif isinstance(fields, str):
            check_fields = [fields]
        else:
            check_fields = list(fields)

        # Filter scenarios
        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            # Check if any of the specified fields contain NA
            has_na = False
            for field in check_fields:
                # Only check fields that exist in this scenario
                if field in scenario:
                    if is_na(scenario[field]):
                        has_na = True
                        break

            # Keep scenario only if it has no NA values in checked fields
            if not has_na:
                new_sl.append(scenario)

        return new_sl

    def add_list(self, name: str, values: list) -> "ScenarioList":
        """Add a list of values to a ScenarioList.

        Each value in the list is added to the corresponding scenario by index.

        Args:
            name: The field name to add.
            values: List of values to add, must match length of ScenarioList.

        Returns:
            A new ScenarioList with the added field.

        Raises:
            ScenarioError: If length of values doesn't match length of ScenarioList.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
            >>> s.add_list('age', [30, 25])
            ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        """
        from .scenario_list import ScenarioList
        from .exceptions import ScenarioError

        if len(values) != len(self._scenario_list.data):
            raise ScenarioError(
                f"Length of values ({len(values)}) does not match length of ScenarioList ({len(self._scenario_list)})"
            )
        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for i, value in enumerate(values):
            scenario = self._scenario_list.data[i]
            scenario[name] = value
            new_sl.append(scenario)
        return new_sl

    def add_value(self, name: str, value: Any) -> "ScenarioList":
        """Add a value to all scenarios in a ScenarioList.

        Args:
            name: The field name to add.
            value: The value to add to all scenarios.

        Returns:
            A new ScenarioList with the added field.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
            >>> s.add_value('age', 30)
            ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 30})])
        """
        from .scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            scenario[name] = value
            new_sl.append(scenario)
        return new_sl

    def replace_names(self, new_names: list) -> "ScenarioList":
        """Replace the field names in the scenarios with a new list of names.

        Args:
            new_names: A list of new field names to use, in order.

        Returns:
            A new ScenarioList with renamed fields.

        Raises:
            ScenarioError: If length of new_names doesn't match number of fields.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
            >>> s.replace_names(['first_name', 'years'])
            ScenarioList([Scenario({'first_name': 'Alice', 'years': 30}), Scenario({'first_name': 'Bob', 'years': 25})])
        """
        from .scenario_list import ScenarioList
        from .exceptions import ScenarioError

        if not self._scenario_list:
            return ScenarioList([])

        if len(new_names) != len(self._scenario_list[0].keys()):
            raise ScenarioError(
                f"Length of new names ({len(new_names)}) does not match number of fields ({len(self._scenario_list[0].keys())})"
            )

        old_names = list(self._scenario_list[0].keys())
        replacement_dict = dict(zip(old_names, new_names))
        return self.rename(replacement_dict)

    def chunk(
        self,
        field: str,
        num_words: "int | None" = None,
        num_lines: "int | None" = None,
        include_original: bool = False,
        hash_original: bool = False,
    ) -> "ScenarioList":
        """Chunk the scenarios based on a field.

        Breaks up text in the specified field into smaller chunks based on
        word count or line count.

        Args:
            field: The field containing text to chunk.
            num_words: Maximum number of words per chunk.
            num_lines: Maximum number of lines per chunk.
            include_original: Whether to include the original text.
            hash_original: Whether to hash the original text.

        Returns:
            A new ScenarioList with chunked scenarios.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'text': 'The quick brown fox jumps over the lazy dog.'})])
            >>> s.chunk('text', num_words=3)
            ScenarioList([Scenario({'text': 'The quick brown', 'text_chunk': 0, 'text_char_count': 15, 'text_word_count': 3}), Scenario({'text': 'fox jumps over', 'text_chunk': 1, 'text_char_count': 14, 'text_word_count': 3}), Scenario({'text': 'the lazy dog.', 'text_chunk': 2, 'text_char_count': 13, 'text_word_count': 3})])
        """
        from .scenario_list import ScenarioList

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

        The input must be a ScenarioList where each scenario has exactly one key, e.g.:
        ``ScenarioList.from_list('item', ['a', 'b', 'c'])``.

        Args:
            k: Number of items to choose for each scenario.
            order_matters: If True, use ordered selections (permutations). If False, use
                unordered selections (combinations).

        Returns:
            ScenarioList: A new list containing all generated scenarios.

        Examples:
            >>> from edsl import ScenarioList
            >>> s = ScenarioList.from_list('x', ['a', 'b', 'c'])
            >>> s.choose_k(2)
            ScenarioList([Scenario({'x_1': 'a', 'x_2': 'b'}), Scenario({'x_1': 'a', 'x_2': 'c'}), Scenario({'x_1': 'b', 'x_2': 'c'})])
            >>> s.choose_k(2, order_matters=True)  # doctest: +ELLIPSIS
            ScenarioList([...])
        """
        from .scenario_list import ScenarioList

        return ScenarioList(list(self._iter_choose_k(k=k, order_matters=order_matters)))

    def _iter_choose_k(self, k: int, order_matters: bool = False):
        """Delegate generator for choose-k to the ScenarioCombinator module.

        Returns a generator yielding `Scenario` instances.
        """
        from importlib import import_module

        ScenarioCombinator = import_module(
            "edsl.scenarios.scenario_combinator"
        ).ScenarioCombinator
        return ScenarioCombinator.iter_choose_k(
            self._scenario_list, k=k, order_matters=order_matters
        )
