"""
Transformer utilities for ScenarioList.

This module contains operations that transform an entire `ScenarioList` into
another representation, keeping `ScenarioList` itself thin by delegating the
implementation details here.
"""

from __future__ import annotations

from typing import List, Optional, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario_list import ScenarioList
    from .scenario import Scenario
    from ..agents.agent import Agent


class ScenarioListTransformService:
    """Service class that provides transform operations on a ScenarioList instance.

    This class is used as a delegation target for transform methods on ScenarioList.
    It wraps a ScenarioList instance and delegates to ScenarioListTransformer static methods.
    """

    def __init__(self, sl: "ScenarioList"):
        self._sl = sl

    def pivot(self, id_vars=None, var_name="variable", value_name="value") -> "ScenarioList":
        """Pivot from long format back to wide columns.

        Groups rows by ``id_vars`` and spreads the values under ``var_name``
        into separate columns whose values come from ``value_name``.
        """
        return ScenarioListTransformer.pivot(self._sl, id_vars, var_name, value_name)

    def group_by(
        self, id_vars: List[str], variables: List[str], func: Callable
    ) -> "ScenarioList":
        """Group scenarios and aggregate variables with a custom function.

        Groups by the values of ``id_vars`` and passes lists of values for each
        field in ``variables`` to ``func``. The function must return a dict whose
        keys are added as fields on the aggregated Scenario.

        Args:
            id_vars: Field names to group by.
            variables: Field names to aggregate and pass to ``func`` as lists.
            func: Callable that accepts len(variables) lists and returns a dict.

        Returns:
            ScenarioList with one Scenario per group containing id_vars and aggregated fields.

        Raises:
            ScenarioError: If the function arity does not match variables or returns non-dict.

        Notes:
            Implementation is delegated to `ScenarioListTransformer.group_by`.
        """
        return ScenarioListTransformer.group_by(self._sl, id_vars, variables, func)

    def to_agent_traits(self, agent_name: Optional[str] = None) -> "Agent":
        """Convert all Scenario objects into traits of a single Agent.

        Aggregates each Scenario's key/value pairs into a single Agent's
        traits. If duplicate keys appear across scenarios, later occurrences
        are suffixed with an incrementing index (e.g., "key_1", "key_2").
        If a field named "name" is present, it is treated as "scenario_name"
        to avoid clobbering an Agent's own name.

        Args:
            agent_name: Optional custom agent name. Defaults to
                "Agent_from_{N}_scenarios" when not provided.

        Returns:
            Agent: An Agent instance whose traits include all fields from all scenarios.

        Notes:
            Implementation is delegated to `ScenarioListTransformer.to_agent_traits`.
        """
        return ScenarioListTransformer.to_agent_traits(self._sl, agent_name)

    def unpivot(
        self,
        id_vars: Optional[List[str]] = None,
        value_vars: Optional[List[str]] = None,
    ) -> "ScenarioList":
        """Convert wide-format fields into long format rows.

        For each Scenario, produces rows of (id_vars..., variable, value) where
        each original field listed in ``value_vars`` becomes a row with its
        field name under ``variable`` and its value under ``value``.

        Args:
            id_vars: Field names to preserve as identifiers on each output row.
            value_vars: Field names to unpivot. Defaults to all non-id_vars.

        Returns:
            ScenarioList: Long-format rows with columns: id_vars..., "variable", "value".

        Notes:
            Implementation is delegated to `ScenarioListTransformer.unpivot`.
        """
        return ScenarioListTransformer.unpivot(self._sl, id_vars, value_vars)

    def apply(
        self, func: Callable, field: str, new_name: Optional[str], replace: bool = False
    ) -> "ScenarioList":
        """Apply a function to a field across all scenarios.

        Evaluates ``func(scenario[field])`` for each Scenario and stores the result
        in ``new_name`` (or the original field name if ``new_name`` is None). If
        ``replace`` is True, the original field is removed.

        Args:
            func: Function to apply to each value in ``field``.
            field: Existing field name to read from.
            new_name: Optional output field name. Defaults to ``field``.
            replace: If True, delete the original ``field`` after writing.

        Returns:
            ScenarioList with updated scenarios.

        Notes:
            Implementation is delegated to `ScenarioListTransformer.apply`.
        """
        return ScenarioListTransformer.apply(self._sl, func, field, new_name, replace)

    def _concatenate(
        self,
        fields: List[str],
        output_type: str = "string",
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> "ScenarioList":
        """Concatenate fields into a new field as string/list/set."""
        return ScenarioListTransformer._concatenate(
            self._sl, fields, output_type, separator, prefix, postfix, new_field_name
        )

    def concatenate(
        self,
        fields: List[str],
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> "ScenarioList":
        """Concatenate fields into a single string field."""
        return ScenarioListTransformer.concatenate(
            self._sl, fields, separator, prefix, postfix, new_field_name
        )

    def concatenate_to_list(
        self,
        fields: List[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> "ScenarioList":
        """Concatenate fields into a single list field."""
        return ScenarioListTransformer.concatenate_to_list(
            self._sl, fields, prefix, postfix, new_field_name
        )

    def concatenate_to_set(
        self,
        fields: List[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: Optional[str] = None,
    ) -> "ScenarioList":
        """Concatenate fields into a single set field."""
        return ScenarioListTransformer.concatenate_to_set(
            self._sl, fields, prefix, postfix, new_field_name
        )

    def unpack_dict(
        self, field: str, prefix: Optional[str] = None, drop_field: bool = False
    ) -> "ScenarioList":
        """Unpack a dictionary field into separate fields."""
        return ScenarioListTransformer.unpack_dict(self._sl, field, prefix, drop_field)

    def transform(
        self, field: str, func: Callable, new_name: Optional[str] = None
    ) -> "ScenarioList":
        """Transform a field's value using a function."""
        return ScenarioListTransformer.transform(self._sl, field, func, new_name)

    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict] = None
    ) -> "ScenarioList":
        """Add a new field computed from an expression."""
        return ScenarioListTransformer.mutate(self._sl, new_var_string, functions_dict)

    def order_by(self, fields: List[str], reverse: bool = False) -> "ScenarioList":
        """Order scenarios by one or more fields."""
        return ScenarioListTransformer.order_by(self._sl, fields, reverse)

    def filter(self, expression: str) -> "ScenarioList":
        """Filter scenarios by evaluating an expression per row."""
        return ScenarioListTransformer.filter(self._sl, expression)

    def reorder_keys(self, new_order: List[str]) -> "ScenarioList":
        """Reorder keys in each Scenario according to the provided list."""
        return ScenarioListTransformer.reorder_keys(self._sl, new_order)

    def to_scenario_of_lists(self) -> "Scenario":
        """Collapse to a single Scenario with list-valued fields."""
        return ScenarioListTransformer.to_scenario_of_lists(self._sl)

    def unpack(
        self, field: str, new_names: Optional[List[str]] = None, keep_original: bool = True
    ) -> "ScenarioList":
        """Unpack a list-like field into multiple fields."""
        return ScenarioListTransformer.unpack(self._sl, field, new_names, keep_original)

    def collapse(
        self,
        field: str,
        separator: Optional[str] = None,
        prefix: str = "",
        postfix: str = "",
        add_count: bool = False,
    ) -> "ScenarioList":
        """Collapse rows by collecting values of one field."""
        return ScenarioListTransformer.collapse(
            self._sl, field, separator, prefix, postfix, add_count
        )

    def create_comparisons(
        self,
        bidirectional: bool = False,
        num_options: int = 2,
        option_prefix: str = "option_",
        use_alphabet: bool = False,
    ) -> "ScenarioList":
        """Generate pairwise or N-way comparison scenarios."""
        return ScenarioListTransformer.create_comparisons(
            self._sl, bidirectional, num_options, option_prefix, use_alphabet
        )


class ScenarioListTransformer:
    """Collection of transformations operating on a ScenarioList.

    Currently provides:
    - to_scenario_of_lists: Collapse a ScenarioList into a single Scenario with
      the same keys, where each value is the list of values across the list.
    - concatenate family: Concatenate fields across each Scenario into string/list/set
      on a new field, preserving streaming behavior and original API.
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

    @staticmethod
    def to_agent_traits(
        scenario_list: "ScenarioList", agent_name: "str | None" = None
    ) -> "Agent":
        """Convert all Scenario objects into traits of a single Agent.

        Mirrors ScenarioList.to_agent_traits behavior.
        """
        from ..agents import Agent

        all_traits: dict[str, object] = {}
        key_counts: dict[str, int] = {}

        for scenario in scenario_list.data:
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
            agent_name = f"Agent_from_{len(scenario_list)}_scenarios"

        return Agent(traits=all_traits, name=agent_name)

    @staticmethod
    def filter(scenario_list: "ScenarioList", expression: str) -> "ScenarioList":
        """Filter a ScenarioList based on an expression.

        Mirrors ScenarioList.filter behavior and errors.
        """
        from simpleeval import EvalWithCompoundTypes, NameNotDefined
        from .exceptions import ScenarioError
        import warnings as _warnings
        import re
        from .scenario_list import ScenarioList  # type: ignore

        try:
            first_item = scenario_list[0] if len(scenario_list) > 0 else None
            if first_item:
                sample_size = min(len(scenario_list), 100)
                base_keys = set(first_item.keys())
                keys = set()
                count = 0
                for scenario in scenario_list:
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

        new_sl = ScenarioList(data=[], codebook=getattr(scenario_list, "codebook", {}))

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
            for scenario in scenario_list:
                evaluator, eval_expression = create_evaluator(scenario)
                if evaluator.eval(eval_expression):
                    scenario_copy = scenario.copy()
                    new_sl.append(scenario_copy)
                    del scenario_copy
        except NameNotDefined as e:
            try:
                first_item = scenario_list[0] if len(scenario_list) > 0 else None
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

    @staticmethod
    def transform(
        scenario_list: "ScenarioList", field: str, func, new_name: "str | None" = None
    ) -> "ScenarioList":
        """Transform a field using a function for each Scenario in the list."""
        from .scenario_list import ScenarioList  # type: ignore

        new_scenarios = []
        for scenario in scenario_list:
            new_scenario = scenario.copy()
            new_scenario[new_name or field] = func(scenario[field])
            new_scenarios.append(new_scenario)
        return ScenarioList(new_scenarios)

    @staticmethod
    def apply(
        scenario_list: "ScenarioList",
        func,
        field: str,
        new_name: "str | None",
        replace: bool = False,
    ) -> "ScenarioList":
        """Apply a function to a field and return a new ScenarioList (original semantics)."""
        from .scenario_list import ScenarioList  # type: ignore

        new_list = ScenarioList(
            data=[], codebook=getattr(scenario_list, "codebook", {})
        )
        if new_name is None:
            new_name = field
        for scenario in scenario_list:
            scenario[new_name] = func(scenario[field])
            if replace:
                del scenario[field]
            new_list.append(scenario)
        return new_list

    @staticmethod
    def unpack_dict(
        scenario_list: "ScenarioList",
        field: str,
        prefix: "str | None" = None,
        drop_field: bool = False,
    ) -> "ScenarioList":
        """Unpack a dictionary field into separate fields for each Scenario."""
        from .scenario_list import ScenarioList  # type: ignore

        new_scenarios = []
        for scenario in scenario_list:
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

    @staticmethod
    def unpack(
        scenario_list: "ScenarioList",
        field: str,
        new_names: "list[str] | None" = None,
        keep_original: bool = True,
    ) -> "ScenarioList":
        """Unpack a field (list-like) into multiple fields across the list."""
        from .scenario_list import ScenarioList  # type: ignore

        new_names = new_names or [
            f"{field}_{i}" for i in range(len(scenario_list[0][field]))
        ]
        new_sl = ScenarioList(data=[], codebook=getattr(scenario_list, "codebook", {}))
        for scenario in scenario_list:
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

    @staticmethod
    def mutate(
        scenario_list: "ScenarioList",
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
            new_data = [_new_scenario(s, var_name) for s in scenario_list]
        except Exception as e:
            raise ScenarioError(f"Error in mutate. Exception:{e}")

        return ScenarioList(new_data)

    @staticmethod
    def unpivot(
        scenario_list: "ScenarioList",
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
                field for field in scenario_list[0].keys() if field not in id_vars
            ]

        new_scenarios = ScenarioList(data=[], codebook={})
        for scenario in scenario_list:
            for var in value_vars:
                new_scenario = {id_var: scenario[id_var] for id_var in id_vars}
                new_scenario["variable"] = var
                new_scenario["value"] = scenario[var]
                new_scenarios.append(Scenario(new_scenario))

        return new_scenarios

    @staticmethod
    def pivot(
        scenario_list: "ScenarioList",
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

        for scenario in scenario_list:
            id_key = tuple(scenario[id_var] for id_var in id_vars)
            if id_key not in pivoted_dict:
                pivoted_dict[id_key] = {id_var: scenario[id_var] for id_var in id_vars}
            variable = scenario[var_name]
            value = scenario[value_name]
            pivoted_dict[id_key][variable] = value

        new_sl = ScenarioList(data=[], codebook=getattr(scenario_list, "codebook", {}))
        for id_key, values in pivoted_dict.items():
            new_sl.append(Scenario(dict(zip(id_vars, id_key), **values)))
        return new_sl

    @staticmethod
    def group_by(
        scenario_list: "ScenarioList",
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
        for scenario in scenario_list:
            key = tuple(scenario[id_var] for id_var in id_vars)
            for var in variables:
                grouped[key][var].append(scenario[var])

        new_sl = ScenarioList(data=[], codebook=getattr(scenario_list, "codebook", {}))
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

    @staticmethod
    def order_by(
        scenario_list: "ScenarioList", fields: list[str], reverse: bool = False
    ) -> "ScenarioList":
        """Order scenarios by one or more fields."""
        from .scenario_list import ScenarioList  # type: ignore

        def get_sort_key(scenario: object) -> tuple:
            return tuple(scenario[field] for field in fields)

        return ScenarioList(
            sorted(scenario_list.data, key=get_sort_key, reverse=reverse)
        )

    @staticmethod
    def reorder_keys(
        scenario_list: "ScenarioList", new_order: list[str]
    ) -> "ScenarioList":
        """Reorder keys in each Scenario according to provided order."""
        from .scenario_list import ScenarioList  # type: ignore
        from .scenario import Scenario

        assert set(new_order) == set(scenario_list.parameters)

        new_sl = ScenarioList(data=[], codebook=getattr(scenario_list, "codebook", {}))
        for scenario in scenario_list:
            new_scenario = Scenario({key: scenario[key] for key in new_order})
            new_sl.append(new_scenario)
        return new_sl

    @staticmethod
    def create_comparisons(
        scenario_list: "ScenarioList",
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
        if num_options > len(scenario_list):
            raise ValueScenarioError(
                f"num_options ({num_options}) cannot exceed the number of scenarios ({len(scenario_list)})"
            )
        if use_alphabet and num_options > 26:
            raise ValueScenarioError(
                "When using alphabet labels, num_options cannot exceed 26 (the number of letters in the English alphabet)"
            )

        scenario_dicts = [s.to_dict(add_edsl_version=False) for s in scenario_list]

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

    @staticmethod
    def collapse(
        scenario_list: "ScenarioList",
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

        if not scenario_list:
            return ScenarioList([])

        id_vars = [key for key in scenario_list[0].keys() if key != field]

        grouped: dict[tuple, list] = defaultdict(list)
        for scenario in scenario_list:
            key = tuple(scenario[id_var] for id_var in id_vars)
            grouped[key].append(scenario[field])

        new_sl = ScenarioList(data=[], codebook=getattr(scenario_list, "codebook", {}))
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

    @staticmethod
    def _concatenate(
        scenario_list: "ScenarioList",
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
        for scenario in scenario_list:
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

    @staticmethod
    def concatenate(
        scenario_list: "ScenarioList",
        fields: list[str],
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: "str | None" = None,
    ) -> "ScenarioList":
        return ScenarioListTransformer._concatenate(
            scenario_list,
            fields,
            output_type="string",
            separator=separator,
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    @staticmethod
    def concatenate_to_list(
        scenario_list: "ScenarioList",
        fields: list[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: "str | None" = None,
    ) -> "ScenarioList":
        return ScenarioListTransformer._concatenate(
            scenario_list,
            fields,
            output_type="list",
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )

    @staticmethod
    def concatenate_to_set(
        scenario_list: "ScenarioList",
        fields: list[str],
        prefix: str = "",
        postfix: str = "",
        new_field_name: "str | None" = None,
    ) -> "ScenarioList":
        return ScenarioListTransformer._concatenate(
            scenario_list,
            fields,
            output_type="set",
            prefix=prefix,
            postfix=postfix,
            new_field_name=new_field_name,
        )
