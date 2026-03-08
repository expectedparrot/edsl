"""AgentList representation operations module."""

from __future__ import annotations

import io
import os
import shutil
import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .agent_list import AgentList


class AgentListRepresentation:
    """Handles string representation operations for AgentList objects.

    Instantiated with a reference to an AgentList; provides __repr__
    dispatch, eval-safe repr, and rich summary formatting.
    """

    def __init__(self, agent_list: "AgentList") -> None:
        self._agent_list = agent_list

    def repr(self) -> str:
        """Return a string representation of the AgentList.

        Uses traditional repr format when running doctests, otherwise uses
        rich-based display for better readability. In Jupyter notebooks,
        returns a minimal string since _repr_html_ handles the display.
        """
        if os.environ.get("EDSL_RUNNING_DOCTESTS") == "True":
            return self.eval_repr()

        try:
            from IPython import get_ipython

            ipy = get_ipython()
            if ipy is not None and "IPKernelApp" in ipy.config:
                return "AgentList(...)"
        except (NameError, ImportError):
            pass

        return self.summary_repr()

    def eval_repr(self) -> str:
        """Return an eval-able string representation of the AgentList.

        This representation can be used with eval() to recreate the AgentList object.
        Used primarily for doctests and debugging.
        """
        return f"AgentList({self._agent_list.data})"

    def summary_repr(self, MAX_AGENTS: int = 10, MAX_TRAITS: int = 10) -> str:
        """Generate a summary representation of the AgentList with Rich formatting.

        Args:
            MAX_AGENTS: Maximum number of agents to show (default: 10).
            MAX_TRAITS: Maximum number of traits to show per agent (default: 10).
        """
        from rich.console import Console
        from rich.text import Text
        from ..config import RICH_STYLES

        terminal_width = shutil.get_terminal_size().columns

        output = Text()
        output.append("AgentList(\n", style=RICH_STYLES["primary"])
        output.append(
            f"    num_agents={len(self._agent_list)},\n",
            style=RICH_STYLES["default"],
        )
        output.append("    agents=[\n", style=RICH_STYLES["default"])

        num_to_show = min(MAX_AGENTS, len(self._agent_list))
        for i, agent in enumerate(self._agent_list.data[:num_to_show]):
            agent_traits = dict(list(agent.traits.items())[:MAX_TRAITS])
            num_traits = len(agent.traits)
            was_truncated = num_traits > MAX_TRAITS

            output.append("        Agent(\n", style=RICH_STYLES["primary"])
            output.append(
                f"            num_traits={num_traits},\n",
                style=RICH_STYLES["default"],
            )

            if agent.name is not None:
                output.append(
                    f"            name={repr(agent.name)},\n",
                    style=RICH_STYLES["default"],
                )

            output.append("            traits={\n", style=RICH_STYLES["default"])

            for key, value in agent_traits.items():
                max_value_length = max(terminal_width - 30, 50)
                value_repr = repr(value)

                output.append("                ", style=RICH_STYLES["default"])
                output.append(f"'{key}'", style=RICH_STYLES["secondary"])
                output.append(": ", style=RICH_STYLES["default"])

                if len(value_repr) > max_value_length:
                    wrapped_lines = textwrap.wrap(
                        value_repr,
                        width=max_value_length,
                        break_long_words=True,
                        break_on_hyphens=False,
                    )
                    for line_idx, line in enumerate(wrapped_lines):
                        if line_idx == 0:
                            output.append(f"{line}\n", style=RICH_STYLES["default"])
                        else:
                            output.append(
                                f"                    {line}\n",
                                style=RICH_STYLES["default"],
                            )
                    output._text[-1] = output._text[-1].rstrip("\n") + ",\n"
                else:
                    output.append(f"{value_repr},\n", style=RICH_STYLES["default"])

            if was_truncated:
                output.append(
                    f"                ... ({num_traits - MAX_TRAITS} more traits)\n",
                    style=RICH_STYLES["dim"],
                )

            output.append("            }\n", style=RICH_STYLES["default"])
            output.append("        )", style=RICH_STYLES["primary"])

            if i < num_to_show - 1:
                output.append(",\n", style=RICH_STYLES["default"])
            else:
                output.append("\n", style=RICH_STYLES["default"])

        if len(self._agent_list) > MAX_AGENTS:
            output.append(
                f"        ... ({len(self._agent_list) - MAX_AGENTS} more agents)\n",
                style=RICH_STYLES["dim"],
            )

        output.append("    ]\n", style=RICH_STYLES["default"])
        output.append(")", style=RICH_STYLES["primary"])

        console = Console(
            file=io.StringIO(), force_terminal=True, width=terminal_width
        )
        console.print(output, end="")
        return console.file.getvalue()

    def summary(self) -> dict:
        """Return a brief summary dict of the AgentList."""
        return {
            "agents": len(self._agent_list),
        }
