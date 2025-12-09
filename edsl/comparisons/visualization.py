from __future__ import annotations

"""Rendering helpers: rich tables and Matplotlib heat-maps."""

from typing import Sequence, List, Callable, Optional, Any
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from rich.table import Table

from .metrics.metrics_abc import ComparisonFunction
from .answer_comparison import AnswerComparison
from .factory import ComparisonFactory

__all__ = ["render_comparison_table", "render_metric_heatmap"]


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


# ---------------------------------------------------------------------------
# Heat-map
# ---------------------------------------------------------------------------


def render_metric_heatmap(
    results: Sequence,
    metric_name: str,
    comparison_factory: ComparisonFactory | None = None,
    agg_func: Callable[[List[float]], float] | None = None,
    title: str | None = None,
    ax: Optional[Any] = None,
):
    if comparison_factory is None:
        comparison_factory = ComparisonFactory()

    if agg_func is None:

        def agg_func(vals: List[float]):
            arr = np.array([v for v in vals if v is not None], dtype=float)
            return float(np.nan) if arr.size == 0 else float(np.mean(arr))

    n = len(results)
    labels = [getattr(r.model, "model", f"model_{i}") for i, r in enumerate(results)]
    matrix = np.full((n, n), np.nan, dtype=float)

    for i in range(n):
        for j in range(i, n):
            if i == j:
                matrix[i, j] = 0.0
            else:
                comp = comparison_factory.compare_results(
                    results[i], results[j]
                ).comparisons
                vals: List[float] = [
                    float(ac[metric_name])
                    for ac in comp.values()
                    if ac[metric_name] is not None
                ]
                matrix[i, j] = matrix[j, i] = agg_func(vals)

    if ax is None:
        _, ax = plt.subplots(figsize=(1 + n, 0.8 + n))

    sns.heatmap(
        matrix,
        annot=True,
        fmt=".2f",
        cmap="viridis",
        square=True,
        xticklabels=labels,
        yticklabels=labels,
        ax=ax,
    )
    ax.set_title(title or metric_name.replace("_", " ").title())
    plt.tight_layout()
    return ax
