from __future__ import annotations

"""Rich-based pretty printer for EDSL BaseDiff objects (package-local).

Moved into ``edsl.base`` so we can rely on relative imports and avoid top-level
package references.
"""

from typing import Any, Optional

from rich.console import Console, ConsoleRenderable, Group
from rich.table import Table
from rich.panel import Panel
from rich import box


class DiffRenderer:
    """Render a :class:`BaseDiff` instance with Rich."""

    def __init__(self, diff: "BaseDiff", *, console: Optional[Console] = None):
        # Local relative import to avoid circular deps
        from .base_class import BaseDiff  # pylint: disable=import-outside-toplevel

        if not isinstance(diff, BaseDiff):
            raise TypeError("DiffRenderer expects a BaseDiff instance")

        self.diff: "BaseDiff" = diff
        self.console: Console = console or Console()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def display(self) -> None:  # noqa: D401
        """Pretty-print the diff to *self.console*."""
        self.console.print(self._build_renderable())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_renderable(self) -> ConsoleRenderable:  # type: ignore[override]
        sections = []
        if self.diff.added:
            sections.append(self._panel_added())
        if self.diff.removed:
            sections.append(self._panel_removed())
        if self.diff.modified:
            sections.append(self._panel_modified())

        if not sections:
            return Panel("[green]No differences[/green]", title="Diff Result", style="green", padding=(0, 1))

        # Group stacks renderables without extra spacing
        return Group(*sections)

    # ------------------------------------------------------------------
    # Panel builders
    # ------------------------------------------------------------------
    def _panel_added(self) -> Panel:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold green")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        for key, val in self.diff.added.items():
            table.add_row(str(key), self._safe_repr(val))

        return Panel(table, title="[bold green]Added", border_style="green", padding=(0, 1))

    def _panel_removed(self) -> Panel:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold red")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        for key, val in self.diff.removed.items():
            table.add_row(str(key), self._safe_repr(val))

        return Panel(table, title="[bold red]Removed", border_style="red", padding=(0, 1))

    def _panel_modified(self) -> Panel:
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold yellow")
        table.add_column("Key", style="cyan")
        table.add_column("Old", style="white")
        table.add_column("New", style="white")

        for key, (old, new, _details) in self.diff.modified.items():
            table.add_row(str(key), self._safe_repr(old), self._safe_repr(new))

        return Panel(table, title="[bold yellow]Modified", border_style="yellow", padding=(0, 1))

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_repr(value: Any, max_len: int = 80) -> str:
        text = repr(value)
        if len(text) > max_len:
            half = (max_len - 3) // 2
            text = text[:half] + "..." + text[-half:]
        return text


# ----------------------------------------------------------------------
# Public convenience function
# ----------------------------------------------------------------------

def pretty_print(diff: "BaseDiff", *, console: Optional[Console] = None) -> None:  # noqa: ANN001
    """Print *diff* using Rich-based formatting."""

    renderer = DiffRenderer(diff, console=console)
    renderer.display() 