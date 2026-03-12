"""AgentList representation operations module."""

from __future__ import annotations

import os
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

        result = self.summary_repr()
        info = self._agent_list._store_info_line()
        if info:
            result = result.rstrip() + "\n" + info
        return result

    def eval_repr(self) -> str:
        """Return an eval-able string representation of the AgentList.

        This representation can be used with eval() to recreate the AgentList object.
        Used primarily for doctests and debugging.
        """
        return f"AgentList({self._agent_list.data})"

    def summary_repr(self, MAX_AGENTS: int = 500, MAX_TRAITS: int = 500) -> str:
        """Generate a summary representation of the AgentList as a Rich table.

        One column per trait key, one row per agent.

        Args:
            MAX_AGENTS: Maximum number of agent rows to show (default: 10).
            MAX_TRAITS: (unused, kept for API compat)
        """
        from ..utilities.summary_table import ColumnDef, render_summary_table

        al = self._agent_list
        num_agents = len(al)
        title = f"AgentList ({num_agents} agent{'s' if num_agents != 1 else ''})"

        all_keys = sorted(al.trait_keys)

        has_names = any(agent.name is not None for agent in al.data)

        columns: list[ColumnDef] = [
            ColumnDef("#", style="dim", no_wrap=True, justify="right"),
        ]
        if has_names:
            columns.append(ColumnDef("Name", style="bold cyan", no_wrap=True))
        columns.extend(ColumnDef(k, style="bold green") for k in all_keys)

        rows = []
        for idx, agent in enumerate(al.data):
            row: list[str] = [str(idx)]
            if has_names:
                row.append(repr(agent.name) if agent.name is not None else "")
            row.extend(repr(agent.traits.get(k, "")) for k in all_keys)
            rows.append(tuple(row))

        caption_parts: list[str] = []
        if al._codebook:
            caption_parts.append(f"codebook: {len(al._codebook)} entries")
        if al._traits_presentation_template:
            caption_parts.append("custom traits template")

        return render_summary_table(
            title=title,
            columns=columns,
            rows=rows,
            caption=", ".join(caption_parts) if caption_parts else None,
            max_rows=MAX_AGENTS,
        )

    def summary(self) -> dict:
        """Return a brief summary dict of the AgentList."""
        return {
            "agents": len(self._agent_list),
        }
