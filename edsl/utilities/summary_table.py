"""Central renderer for Rich summary tables used by _summary_repr across EDSL.

All visual styling decisions (box style, borders, colors, padding, terminal
width, overflow rows) live here so that every EDSL object renders with a
consistent look. Classes supply the *data* (title, columns, rows, caption);
this module supplies the *presentation*.

Cell values may be plain ``str`` or ``rich.text.Text`` objects for cases
that need custom inline markup (e.g. Jinja2 highlighting).
"""

from __future__ import annotations

import io
import shutil
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, Union

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text


@dataclass(frozen=True)
class ColumnDef:
    """Descriptor for a single table column."""

    name: str
    style: str = ""
    no_wrap: bool = False
    justify: str = "left"


CellValue = Union[str, Text]


MAX_TERMINAL_LINES = 200


def _build_table(
    title: str,
    columns: Sequence[ColumnDef],
    rows: Sequence[Sequence[CellValue]],
    caption: Optional[str],
    max_rows: Optional[int],
) -> str:
    terminal_width = shutil.get_terminal_size().columns
    num_cols = len(columns)

    table = Table(
        title=title,
        box=box.ROUNDED,
        show_lines=True,
        title_style="bold blue",
        border_style="dim",
        caption=caption,
        caption_style="dim italic",
        padding=(0, 1),
        expand=False,
    )

    for col in columns:
        table.add_column(
            col.name,
            style=col.style or None,
            no_wrap=col.no_wrap,
            justify=col.justify,
        )

    visible_rows = rows
    overflow = 0
    if max_rows is not None and len(rows) > max_rows:
        visible_rows = rows[:max_rows]
        overflow = len(rows) - max_rows

    for row in visible_rows:
        table.add_row(*row)

    if overflow:
        filler: list[CellValue] = [
            Text(f"… +{overflow} more", style="dim italic")
        ] + [""] * (num_cols - 1)
        table.add_row(*filler)

    console = Console(file=io.StringIO(), force_terminal=True, width=terminal_width)
    console.print(table, end="")
    return console.file.getvalue()


def render_summary_table(
    title: str,
    columns: Sequence[ColumnDef],
    rows: Sequence[Sequence[CellValue]],
    caption: Optional[str] = None,
    max_rows: Optional[int] = None,
    max_lines: int = MAX_TERMINAL_LINES,
) -> str:
    """Render a Rich table to a string with the standard EDSL style.

    Args:
        title: Bold blue title displayed above the table.
        columns: Column definitions controlling header names and per-column
            styling.
        rows: Row data.  Each inner sequence must have the same length as
            *columns*.  Values can be ``str`` or ``rich.text.Text``.
        caption: Optional dim italic caption displayed below the table.
        max_rows: If set and ``len(rows)`` exceeds this, only the first
            *max_rows* rows are shown followed by an overflow indicator.
        max_lines: Safety limit on rendered output height (default 200).
            If the table exceeds this many lines it is automatically
            re-rendered with fewer rows to fit.

    Returns:
        The rendered table as an ANSI string sized to the current terminal.
    """
    effective_max = max_rows

    result = _build_table(title, columns, rows, caption, effective_max)
    line_count = result.count("\n")

    if line_count > max_lines and len(rows) > 1:
        overhead = 6
        lines_per_row = max(line_count / max(len(rows), 1), 1)
        safe_rows = max(int((max_lines - overhead) / lines_per_row), 1)
        if effective_max is None or safe_rows < effective_max:
            effective_max = safe_rows
        result = _build_table(title, columns, rows, caption, effective_max)

    return result
