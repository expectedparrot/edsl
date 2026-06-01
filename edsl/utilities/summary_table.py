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
from dataclasses import dataclass
from typing import Optional, Sequence, Union

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


MAX_TERMINAL_LINES = 2000


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


_WRAP_STYLE = "font-family: sans-serif; font-size: 13px; overflow-x: auto;"
_TITLE_STYLE = "font-weight: bold; color: #2c7be5; margin-bottom: 4px;"
_CAPTION_STYLE = "color: #888; font-style: italic; font-size: 12px; margin-top: 4px;"
_TABLE_STYLE = "border-collapse: collapse; width: auto;"
_TH_STYLE = (
    "background: #f0f4f8; color: #333; font-weight: bold;"
    " text-align: left; vertical-align: top;"
    " padding: 5px 10px; border: 1px solid #ccc;"
)
_TD_STYLE = (
    "text-align: left; vertical-align: top;"
    " padding: 5px 10px; border: 1px solid #ddd;"
    " white-space: pre-wrap; word-break: break-word;"
)
_TD_EVEN_STYLE = _TD_STYLE + " background: #f9f9f9;"


def render_summary_table_html(
    title: str,
    columns: Sequence[ColumnDef],
    rows: Sequence[Sequence[CellValue]],
    caption: Optional[str] = None,
    max_rows: Optional[int] = None,
) -> str:
    """Render a summary table as a styled HTML string for Jupyter notebooks."""

    def _cell(value: CellValue) -> str:
        text = value.plain if isinstance(value, Text) else str(value)
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    visible_rows = rows
    overflow = 0
    if max_rows is not None and len(rows) > max_rows:
        visible_rows = rows[:max_rows]
        overflow = len(rows) - max_rows

    header_html = "".join(
        f'<th style="{_TH_STYLE}">{_cell(col.name)}</th>' for col in columns
    )
    rows_html = ""
    for i, row in enumerate(visible_rows):
        td_style = _TD_EVEN_STYLE if i % 2 == 1 else _TD_STYLE
        cells = "".join(f'<td style="{td_style}">{_cell(v)}</td>' for v in row)
        rows_html += f"<tr>{cells}</tr>"

    if overflow:
        filler_cells = (
            f'<td style="{_TD_STYLE}">… +{overflow} more</td>'
            + f'<td style="{_TD_STYLE}"></td>' * (len(columns) - 1)
        )
        rows_html += f"<tr>{filler_cells}</tr>"

    title_html = f'<div style="{_TITLE_STYLE}">{title}</div>' if title else ""
    caption_html = f'<div style="{_CAPTION_STYLE}">{caption}</div>' if caption else ""

    table_html = (
        f'<table style="{_TABLE_STYLE}">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table>"
    )

    return (
        f'<div style="{_WRAP_STYLE}">'
        + title_html
        + table_html
        + caption_html
        + "</div>"
    )


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
        max_lines: Safety limit on rendered output height (default 2000).
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
