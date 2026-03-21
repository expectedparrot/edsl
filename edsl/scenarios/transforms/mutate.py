"""Mutate / transform operations for ScenarioList."""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class MutateMixin:
    """Mixin providing mutation and field-level transform operations."""

    def transform(
        self, field: str, func, new_name: "str | None" = None
    ) -> "ScenarioList":
        """Transform a field using a function for each Scenario in the list."""
        from ..scenario_list import ScenarioList  # type: ignore

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
        from ..scenario_list import ScenarioList  # type: ignore

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
        from ..scenario_list import ScenarioList  # type: ignore

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
        from ..scenario_list import ScenarioList  # type: ignore

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
        from ..scenario_list import ScenarioList  # type: ignore
        from ..exceptions import ScenarioError
        from ...utilities import is_valid_variable_name
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

    def numberify(self) -> "ScenarioList":
        """Convert string values to numeric types where possible.

        Examples:
            >>> from edsl.scenarios import Scenario, ScenarioList
            >>> sl = ScenarioList([
            ...     Scenario({'age': '30', 'height': '5.5', 'name': 'Alice'}),
            ...     Scenario({'age': '25', 'height': '6.0', 'name': 'Bob'})
            ... ])
            >>> sl_numeric = sl.numberify()
            >>> sl_numeric[0]
            Scenario({'age': 30, 'height': 5.5, 'name': 'Alice'})
        """
        from ..scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            new_sl.append(scenario.numberify())
        return new_sl

    def fillna(self, value: Any = "", inplace: bool = False) -> "ScenarioList":
        """Fill None/NaN values in all scenarios with a specified value.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': None, 'b': 1, 'c': 'hello'}),
            ...     Scenario({'a': 2, 'b': None, 'c': None}),
            ...     Scenario({'a': None, 'b': 3, 'c': 'world'})
            ... ])
            >>> filled = scenarios.fillna()
            >>> print(filled)
            ScenarioList([Scenario({'a': '', 'b': 1, 'c': 'hello'}), Scenario({'a': 2, 'b': '', 'c': ''}), Scenario({'a': '', 'b': 3, 'c': 'world'})])
        """
        from ..scenario_list import ScenarioList
        from ..scenario import Scenario

        def is_null(val):
            """Check if a value is considered null/None."""
            return val is None or (
                hasattr(val, "__str__")
                and str(val).lower() in ["nan", "none", "null", ""]
            )

        if inplace:
            for scenario in self._scenario_list:
                for key in scenario:
                    if is_null(scenario[key]):
                        scenario[key] = value
            return self._scenario_list
        else:
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

    def replace_values(self, replacements: dict) -> "ScenarioList":
        """Create new scenarios with values replaced according to the provided replacement dictionary.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> scenarios = ScenarioList([
            ...     Scenario({'a': 'nan', 'b': 1}),
            ...     Scenario({'a': 2, 'b': 'nan'})
            ... ])
            >>> replaced = scenarios.replace_values({'nan': None})
            >>> print(replaced)
            ScenarioList([Scenario({'a': None, 'b': 1}), Scenario({'a': 2, 'b': None})])
        """
        from ..scenario_list import ScenarioList
        from ..scenario import Scenario

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

    def add_list(self, name: str, values: list) -> "ScenarioList":
        """Add a list of values to a ScenarioList.

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
            >>> s.add_list('age', [30, 25])
            ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 25})])
        """
        from ..scenario_list import ScenarioList
        from ..exceptions import ScenarioError

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

        Examples:
            >>> from edsl import ScenarioList, Scenario
            >>> s = ScenarioList([Scenario({'name': 'Alice'}), Scenario({'name': 'Bob'})])
            >>> s.add_value('age', 30)
            ScenarioList([Scenario({'name': 'Alice', 'age': 30}), Scenario({'name': 'Bob', 'age': 30})])
        """
        from ..scenario_list import ScenarioList

        new_sl = ScenarioList(data=[], codebook=self._scenario_list.codebook)
        for scenario in self._scenario_list:
            scenario[name] = value
            new_sl.append(scenario)
        return new_sl

    def tack_on(self, replacements: "dict[str, Any]", index: int = -1) -> "ScenarioList":
        """Add a duplicate of an existing scenario with optional value replacements."""
        from ..exceptions import ScenarioError

        if len(self._scenario_list) == 0:
            raise ScenarioError("Cannot tack_on to an empty ScenarioList.")

        if index < 0:
            index = len(self._scenario_list) + index
        if index < 0 or index >= len(self._scenario_list):
            raise ScenarioError(
                f"Index {index} is out of range for ScenarioList of length {len(self._scenario_list)}."
            )

        reference = self._scenario_list[index]

        missing_keys = [key for key in replacements if key not in reference]
        if missing_keys:
            raise ScenarioError(
                f"Replacement keys not found in scenario: {', '.join(missing_keys)}"
            )

        new_scenario = reference.copy()
        for key, value in replacements.items():
            new_scenario[key] = value

        new_sl = self._scenario_list.duplicate()
        new_sl.append(new_scenario)
        return new_sl
