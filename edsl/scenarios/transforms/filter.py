"""Filter transforms for ScenarioList."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class FilterMixin:
    """Mixin providing filter operations on ScenarioList."""

    def filter(self, expression: str) -> "ScenarioList":
        """Filter a ScenarioList based on an expression.

        Mirrors ScenarioList.filter behavior and errors.
        """
        from simpleeval import EvalWithCompoundTypes, NameNotDefined
        from ..exceptions import ScenarioError
        import warnings as _warnings
        import re
        from ..scenario_list import ScenarioList  # type: ignore

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

    def filter_na(self, fields: "str | list[str]" = "*") -> "ScenarioList":
        """Remove scenarios where specified fields contain None or NaN values.

        Args:
            fields: Field name(s) to check for NA values. Can be:
                    - "*" (default): Check all fields in each scenario
                    - A single field name (str): Check only that field
                    - A list of field names: Check all specified fields
        """
        import math
        from ..scenario_list import ScenarioList

        def is_na(val):
            """Check if a value is considered NA (None or NaN)."""
            if val is None:
                return True
            if isinstance(val, float) and math.isnan(val):
                return True
            if hasattr(val, "__str__"):
                str_val = str(val).lower()
                if str_val in ["nan", "none", "null"]:
                    return True
            return False

        # Determine which fields to check
        if fields == "*":
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
            has_na = False
            for field in check_fields:
                if field in scenario:
                    if is_na(scenario[field]):
                        has_na = True
                        break
            if not has_na:
                new_sl.append(scenario)

        return new_sl

    def unique(self) -> "ScenarioList":
        """Return a new ScenarioList containing only unique Scenario objects.

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
        """
        from ..scenario_list import ScenarioList

        seen_hashes = set()
        result = ScenarioList()

        for scenario in self._scenario_list.data:
            scenario_hash = hash(scenario)
            if scenario_hash not in seen_hashes:
                seen_hashes.add(scenario_hash)
                result.append(scenario)

        return result

    def uniquify(self, field: str) -> "ScenarioList":
        """Make all values of a field unique by appending suffixes (_1, _2, etc.) as needed.

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
        """
        from ..scenario_list import ScenarioList
        from ..scenario import Scenario
        from ..exceptions import ScenarioError

        if not any(field in scenario for scenario in self._scenario_list.data):
            raise ScenarioError(f"Field '{field}' not found in any scenario")

        seen_values = {}
        result = ScenarioList(codebook=self._scenario_list.codebook)

        for scenario in self._scenario_list.data:
            if field not in scenario:
                result.append(scenario)
                continue

            original_value = scenario[field]

            if original_value not in seen_values:
                new_value = original_value
                seen_values[original_value] = 1
            else:
                suffix_num = seen_values[original_value]
                new_value = f"{original_value}_{suffix_num}"
                seen_values[original_value] += 1

            new_scenario_dict = dict(scenario)
            new_scenario_dict[field] = new_value
            result.append(Scenario(new_scenario_dict))

        return result
