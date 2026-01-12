from __future__ import annotations

"""Rendering helpers: rich tables."""

from typing import Sequence, List, Optional, TYPE_CHECKING
from rich.table import Table

from .metrics.metrics_abc import ComparisonFunction
from .answer_comparison import AnswerComparison

__all__ = ["render_comparison_table"]


# ---------------------------------------------------------------------------
# Rich table
# ---------------------------------------------------------------------------


def render_comparison_table(
    comparison: dict[str, AnswerComparison],
    comparison_fns: Sequence[ComparisonFunction],
    title: Optional[str] = None,
) -> Table:
    if title is None:
        title = "Answer Comparison"
    table = Table(title=title, show_lines=True)
    table.add_column("Question", style="bold")

    metric_names: List[str] = [str(fn) for fn in comparison_fns]
    for m in metric_names:
        pretty = m.replace("_", " ").title()
        header = f"{pretty}\n({m})"
        table.add_column(header, justify="right")
    table.add_column("Answer A", overflow="fold")
    table.add_column("Answer B", overflow="fold")

    for q, metrics in comparison.items():
        q_cell = str(q)
        if metrics["question_type"]:
            q_cell += f"\n({metrics['question_type']})"
        row: List[str] = [q_cell]
        for m in metric_names:
            val = metrics[m]
            if isinstance(val, (int, float)):
                row.append(f"{val:.3f}")
            else:
                row.append(str(val))
        row.extend(
            [
                AnswerComparison._truncate(metrics.answer_a, 100),
                AnswerComparison._truncate(metrics.answer_b, 100),
            ]
        )
        table.add_row(*row)
    return table
