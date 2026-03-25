"""Combine transforms: concatenate family."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..scenario_list import ScenarioList


class CombineMixin:
    """Mixin providing concatenation operations on ScenarioList."""

    def _concatenate(
        self,
        fields: list[str],
        output_type: str = "string",
        separator: str = ";",
        prefix: str = "",
        postfix: str = "",
        new_field_name: "str | None" = None,
    ) -> "ScenarioList":
        """Core implementation for the concatenate family."""
        from ..scenario_list import ScenarioList  # type: ignore

        if isinstance(fields, str):
            from ..exceptions import ScenarioError

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
                from ..exceptions import ValueScenarioError

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
