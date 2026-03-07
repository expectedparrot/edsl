"""
Representation utilities for ScenarioList.

This module contains methods that produce string, table, tree, and other
display representations of a ScenarioList, keeping ScenarioList itself
thin by delegating the implementation details here.
"""

from __future__ import annotations

import csv
import io
from typing import Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .scenario_list import ScenarioList


class ScenarioListRepresentation:
    """Collection of representation / display operations on a ScenarioList."""

    def __init__(self, scenario_list: "ScenarioList"):
        self._scenario_list = scenario_list

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the ScenarioList.

        This representation can be used with eval() to recreate the ScenarioList object.
        Used primarily for doctests and debugging.
        """
        return f"ScenarioList([{', '.join([x._eval_repr_() for x in self._scenario_list.data])}])"

    def _summary_repr(self, MAX_SCENARIOS: int = 10, MAX_FIELDS: int = 500) -> str:
        """Generate a summary representation of the ScenarioList with Rich formatting.

        Args:
            MAX_SCENARIOS: Maximum number of scenarios to show (default: 10)
            MAX_FIELDS: Maximum number of fields to show per scenario (default: 500)
        """
        from rich.console import Console
        from rich.text import Text
        import shutil
        from edsl.config import RICH_STYLES
        from ..utilities.display_utils import smart_truncate

        sl = self._scenario_list
        terminal_width = shutil.get_terminal_size().columns

        output = Text()
        output.append("ScenarioList(\n", style=RICH_STYLES["primary"])
        output.append(f"    num_scenarios={len(sl)},\n", style=RICH_STYLES["default"])
        output.append("    scenarios=[\n", style=RICH_STYLES["default"])

        num_to_show = min(MAX_SCENARIOS, len(sl))
        for i, scenario in enumerate(sl.data[:num_to_show]):
            scenario_data = dict(list(scenario.items())[:MAX_FIELDS])

            num_fields = len(scenario)
            was_truncated = num_fields > MAX_FIELDS

            output.append("        Scenario(\n", style=RICH_STYLES["primary"])
            output.append(
                f"            num_keys={num_fields},\n", style=RICH_STYLES["default"]
            )
            output.append("            data={\n", style=RICH_STYLES["default"])

            for key, value in scenario_data.items():
                max_value_length = max(terminal_width - 30, 50)
                value_repr = repr(value)
                if len(value_repr) > max_value_length:
                    value_repr = smart_truncate(value_repr, max_value_length)

                output.append("                ", style=RICH_STYLES["default"])
                output.append(f"'{key}'", style=RICH_STYLES["key"])
                output.append(f": {value_repr},\n", style=RICH_STYLES["default"])

            if was_truncated:
                output.append(
                    f"                ... ({num_fields - MAX_FIELDS} more fields)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("            }\n", style=RICH_STYLES["default"])
            output.append("        )", style=RICH_STYLES["primary"])

            if i < num_to_show - 1:
                output.append(",\n", style=RICH_STYLES["default"])
            else:
                output.append("\n", style=RICH_STYLES["default"])

        if len(sl) > MAX_SCENARIOS:
            output.append(
                f"        ... ({len(sl) - MAX_SCENARIOS} more scenarios)\n",
                style=RICH_STYLES["dim"],
            )

        output.append("    ]\n", style=RICH_STYLES["default"])
        output.append(")", style=RICH_STYLES["primary"])

        console = Console(file=io.StringIO(), force_terminal=True, width=terminal_width)
        console.print(output, end="")
        return console.file.getvalue()

    def _summary(self) -> dict:
        """Return a summary of the ScenarioList.

        >>> from edsl.scenarios import ScenarioList
        >>> ScenarioList.example()._summary()
        {'scenarios': 2, 'keys': ['persona']}
        """
        return {
            "scenarios": len(self._scenario_list),
            "keys": list(self._scenario_list.parameters),
        }

    def table(
        self,
        *fields: str,
        tablefmt: Optional[str] = "rich",
        pretty_labels: Optional[dict[str, str]] = None,
    ) -> str:
        """Return the ScenarioList as a table."""
        from ..dataset.display.table_display import SUPPORTED_TABLE_FORMATS

        if tablefmt is not None and tablefmt not in SUPPORTED_TABLE_FORMATS:
            raise ValueError(
                f"Invalid table format: {tablefmt}",
                f"Valid formats are: {list(SUPPORTED_TABLE_FORMATS)}",
            )
        return self._scenario_list.to_dataset().table(
            *fields, tablefmt=tablefmt, pretty_labels=pretty_labels
        )

    def tree(self, node_list: "list[str] | None" = None) -> str:
        """Return the ScenarioList as a tree.

        :param node_list: The list of nodes to include in the tree.
        """
        return self._scenario_list.to_dataset().tree(node_list)

    def code(self) -> list[str]:
        """Create the Python code representation of a ScenarioList."""
        header_lines = [
            "from edsl.scenarios import Scenario",
            "from edsl.scenarios import ScenarioList",
        ]
        lines = ["\n".join(header_lines)]
        names = []
        for index, scenario in enumerate(self._scenario_list):
            lines.append(f"scenario_{index} = " + repr(scenario))
            names.append(f"scenario_{index}")
        lines.append(f"scenarios = ScenarioList([{', '.join(names)}])")
        return lines

    def clipboard_data(self) -> str:
        """Return TSV representation of this ScenarioList for clipboard operations.

        This method is called by the clipboard() method in the base class to provide
        a custom format for copying ScenarioList objects to the system clipboard.

        Returns:
            str: Tab-separated values representation of the ScenarioList
        """
        csv_filestore = self._scenario_list.to_csv()
        csv_content = csv_filestore.text

        csv_reader = csv.reader(io.StringIO(csv_content))
        rows = list(csv_reader)

        tsv_lines = []
        for row in rows:
            tsv_lines.append("\t".join(row))

        return "\n".join(tsv_lines)
