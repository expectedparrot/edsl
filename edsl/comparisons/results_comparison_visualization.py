from __future__ import annotations

"""Altair/Vega-Lite visualisations for `ResultPairComparisonList` objects.

The functions in this module convert a `ResultPairComparisonList` into a tidy
DataFrame (via *pandas*) and then build interactive Altair charts.  The DataFrame
contains one row per agent with aggregated metric values (mean across
questions) and a *pareto* boolean flag indicating membership of the Pareto
frontier.

Example
-------
>>> df = to_dataframe(comparisons)
>>> pareto_scatter(comparisons, x_metric="exact_match", y_metric="cosine_similarity")

All functions return an `altair.Chart` which can be displayed in Jupyter/VSCode
or exported with ``chart.save("chart.html")``.
"""

from typing import List, Dict, Any

from .candidate_agent import ResultPairComparisonList  # type: ignore

__all__ = [
    "to_dataframe",
    "pareto_scatter",
    "metric_bar",
    "question_metric_bar",
    "all_question_metric_bars",
    "all_question_metric_bars_html",
]

# Optional dependencies -------------------------------------------------------
import pandas as pd  # type: ignore
import altair as alt  # type: ignore

# /// script
# dependencies = [
#   "pandas",
#   "altair",
# ]
# ///

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metric_names(comparisons: ResultPairComparisonList) -> List[str]:
    comp0 = comparisons[0]
    return [str(fn) for fn in comp0.comparison_factory.comparison_fns]  # type: ignore[attr-defined]


def _aggregated_metrics(
    comparisons: ResultPairComparisonList,
) -> List[Dict[str, float]]:
    """Mirror the aggregation logic used in `ResultPairComparisonList._aggregated_metrics`."""

    metric_names = _metric_names(comparisons)

    def mean(vals):
        numeric_vals = [float(v) for v in vals if isinstance(v, (int, float))]
        return (
            float("nan") if not numeric_vals else sum(numeric_vals) / len(numeric_vals)
        )

    rows: List[Dict[str, float]] = []
    for comp in comparisons:
        comp_dict = comp.compare()
        metric_to_vals: Dict[str, List[Any]] = {m: [] for m in metric_names}
        for ac in comp_dict.values():
            for m in metric_names:
                metric_to_vals[m].append(ac[m])
        rows.append({m: mean(metric_to_vals[m]) for m in metric_names})
    return rows


def to_dataframe(comparisons: ResultPairComparisonList):
    """Return a *pandas* DataFrame with one row per agent.

    Columns:
    - label:   Human-friendly label (info or truncated persona)
    - index:   Original index in the list
    - pareto:  bool, True if on Pareto frontier
    - <metric>: mean metric value across questions
    """
    if len(comparisons) == 0:
        raise ValueError("Empty ResultPairComparisonList")

    # Labels (reuse logic from ResultPairComparisonList.summary_table)
    labels: List[str] = []
    max_len = 60
    for idx, comp in enumerate(comparisons):
        try:
            persona_raw = comp.result_A["agent"].get("persona")  # type: ignore[index]
        except Exception:
            persona_raw = f"agent_{idx}"

        label = (
            persona_raw
            if len(str(persona_raw)) <= max_len
            else str(persona_raw)[: max_len - 3] + "..."
        )
        labels.append(label)

    # Aggregated metrics
    aggregated_rows = _aggregated_metrics(comparisons)

    # Pareto frontier indices (non-dominated)
    frontier_indices = {comparisons.index(comp) for comp in comparisons.nondominated()}

    records: List[Dict[str, Any]] = []
    for idx, metrics in enumerate(aggregated_rows):
        rec: Dict[str, Any] = {
            "index": idx,
            "label": labels[idx],
            "pareto": idx in frontier_indices,
        }
        rec.update(metrics)
        records.append(rec)

    return pd.DataFrame.from_records(records)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


def pareto_scatter(
    comparisons: ResultPairComparisonList,
    x_metric: str,
    y_metric: str,
    title: str | None = None,
):
    """Return an Altair scatter plot of two metrics with Pareto front highlight."""

    df = to_dataframe(comparisons)
    title = title or f"{x_metric} vs {y_metric}"

    chart = (
        alt.Chart(df)
        .mark_point(filled=True, size=100)
        .encode(
            x=alt.X(x_metric, title=x_metric.replace("_", " ").title()),
            y=alt.Y(y_metric, title=y_metric.replace("_", " ").title()),
            color=alt.condition("datum.pareto", alt.value("red"), alt.value("grey")),
            shape=alt.condition("datum.pareto", alt.value("star"), alt.value("circle")),
            tooltip=["label", x_metric, y_metric, "pareto"],
        )
        .properties(title=title, width=400, height=400)
    )

    # Add text labels for Pareto points
    text = (
        alt.Chart(df[df["pareto"]])
        .mark_text(align="left", dx=5, dy=-5)
        .encode(
            x=x_metric,
            y=y_metric,
            text="label",
        )
    )

    return chart + text


def metric_bar(
    comparisons: ResultPairComparisonList,
    metric_name: str,
    title: str | None = None,
):
    """Return a horizontal bar chart for a single metric with Pareto highlight."""

    df = to_dataframe(comparisons)
    df_sorted = df.sort_values(metric_name, ascending=False)
    title = title or metric_name.replace("_", " ").title()

    chart = (
        alt.Chart(df_sorted)
        .mark_bar()
        .encode(
            x=alt.X(metric_name, title=title),
            y=alt.Y("label", sort="-x"),
            color=alt.condition(
                "datum.pareto", alt.value("red"), alt.value("steelblue")
            ),
            tooltip=["label", metric_name, "pareto"],
        )
        .properties(height=max(200, 20 * len(df)), width=500)
    )
    return chart


# ---------------------------------------------------------------------------
# Question-specific chart
# ---------------------------------------------------------------------------


def question_metric_bar(
    comparisons: ResultPairComparisonList,
    question_name: str,
    metric_name: str,
    title: str | None = None,
):
    """Return a horizontal bar chart of *metric_name* values for *question_name*.

    Parameters
    ----------
    comparisons
        List of ResultPairComparison objects – one per agent.
    question_name
        Identifier of the question as present in ``ResultPairComparison.compare()``.
    metric_name
        Name of the metric to plot (must be produced by the comparison factory).
    title
        Optional chart title.  If *None* a default title is generated.
    """

    if len(comparisons) == 0:
        raise ValueError("Empty ResultPairComparisonList")

    # Build agent labels (reuse logic from to_dataframe)
    labels: List[str] = []
    full_labels: List[str] = []
    max_len = 60
    for idx, comp in enumerate(comparisons):
        try:
            persona_raw = comp.result_A["agent"].get("persona")  # type: ignore[index]
        except Exception:
            persona_raw = f"agent_{idx}"

        label = (
            persona_raw
            if len(str(persona_raw)) <= max_len
            else str(persona_raw)[: max_len - 3] + "..."
        )
        full_label = str(persona_raw)
        labels.append(label)
        full_labels.append(full_label)

    # Extract metric values for the specified question -----------------------
    values: List[float] = []
    for comp in comparisons:
        comp_dict = comp.compare()
        if question_name not in comp_dict:
            raise ValueError(
                f"Question '{question_name}' not found in comparison results."
            )

        ac = comp_dict[question_name]
        val = ac[metric_name]
        if val is None:
            raise ValueError(
                f"Metric '{metric_name}' is None for question '{question_name}'. "
                "Ensure the metric exists and was computed. Available metrics: "
                + ", ".join(ac._metrics.keys())
            )
        values.append(val)

    # Determine Pareto frontier ---------------------------------------------
    frontier_indices = {comparisons.index(comp) for comp in comparisons.nondominated()}
    pareto_flags = [idx in frontier_indices for idx in range(len(comparisons))]

    # Build DataFrame ---------------------------------------------------------
    df = pd.DataFrame(
        {
            "label": labels,
            "full_label": full_labels,
            "pareto": pareto_flags,
            metric_name: values,
        }
    )

    # Ensure numeric axis
    df[metric_name] = pd.to_numeric(df[metric_name], errors="coerce")

    title = title or f"{metric_name.replace('_', ' ').title()} – {question_name}"

    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X(metric_name, title=metric_name.replace("_", " ").title()),
            y=alt.Y("label", sort="-x"),
            color=alt.condition(
                "datum.pareto", alt.value("red"), alt.value("steelblue")
            ),
            tooltip=["full_label", metric_name, "pareto"],
        )
        .properties(height=max(200, 20 * len(df)), width=500, title=title)
    )

    return chart


# ---------------------------------------------------------------------------
# Facet grid: all questions × metrics
# ---------------------------------------------------------------------------


def all_question_metric_bars(
    comparisons: ResultPairComparisonList,
    title: str | None = None,
):
    """Return a facet grid of bar charts covering all questions and metrics.

    The grid has one **row per question** and one **column per metric**.  Within
    each cell agents are displayed on the y-axis (sorted by the metric value)
    and metric values on the x-axis.
    """

    if len(comparisons) == 0:
        raise ValueError("Empty ResultPairComparisonList")

    # Determine list of questions and metric names ---------------------------
    first_comp_dict = comparisons[0].compare()
    question_names = list(first_comp_dict.keys())

    metric_names = [
        str(fn) for fn in comparisons[0].comparison_factory.comparison_fns  # type: ignore[attr-defined]
    ]

    # Build agent labels (reusing logic from to_dataframe) --------------------
    labels: List[str] = []
    full_labels: List[str] = []
    max_len = 60
    for idx, comp in enumerate(comparisons):
        try:
            persona_raw = comp.result_A["agent"].get("persona")  # type: ignore[index]
        except Exception:
            persona_raw = f"agent_{idx}"

        label = (
            persona_raw
            if len(str(persona_raw)) <= max_len
            else str(persona_raw)[: max_len - 3] + "..."
        )
        full_label = str(persona_raw)
        labels.append(label)
        full_labels.append(full_label)

    # Pareto frontier indices -----------------------------------------------
    frontier_indices = {comparisons.index(comp) for comp in comparisons.nondominated()}

    # Build long-form DataFrame ---------------------------------------------
    records: List[Dict[str, Any]] = []
    for comp_idx, comp in enumerate(comparisons):
        comp_dict = comp.compare()
        for q in question_names:
            ac = comp_dict[q]
            for m in metric_names:
                val = ac[m]
                records.append(
                    {
                        "label": labels[comp_idx],
                        "full_label": full_labels[comp_idx],
                        "pareto": comp_idx in frontier_indices,
                        "question": q,
                        "metric": m,
                        "value": val,
                    }
                )

    df = pd.DataFrame.from_records(records)

    # Ensure the 'value' column is numeric so Altair treats it as quantitative
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    base = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            x=alt.X("value:Q", title="Value"),
            y=alt.Y("label", sort="-x"),
            color=alt.condition(
                "datum.pareto", alt.value("red"), alt.value("steelblue")
            ),
            tooltip=["full_label", "value", "pareto"],
        )
        .properties(width=200, height=max(200, 20 * len(comparisons)))
    )

    chart = base.facet(row="question:N", column="metric:N").properties(
        title=title or "Metrics per Question – Candidate Agents",
        spacing=5,
    )

    return chart


# ---------------------------------------------------------------------------
# Helper: full HTML with traits table
# ---------------------------------------------------------------------------


def _agent_traits_dataframe(comparisons: ResultPairComparisonList) -> pd.DataFrame:
    """Return a pandas DataFrame with one row per agent and each trait in its own column."""

    rows: list[dict[str, Any]] = []
    all_keys: set[str] = set()
    for idx, comp in enumerate(comparisons):
        try:
            traits = dict(comp.result_A.agent.traits)  # type: ignore[attr-defined]
        except Exception:
            try:
                traits = dict(comp.result_A["agent"])  # type: ignore[index]
            except Exception:
                traits = {}

        row = {"Agent": f"agent_{idx + 1}", **traits}
        rows.append(row)
        all_keys.update(traits.keys())

    columns = ["Agent"] + sorted(all_keys)
    return pd.DataFrame(rows, columns=columns).fillna("")


def all_question_metric_bars_html(
    comparisons: ResultPairComparisonList,
    title: str | None = None,
):
    """Return an HTML string with the facet grid and a traits table appended."""

    chart = all_question_metric_bars(comparisons, title=title)
    grid_html = chart.to_html()

    df_traits = _agent_traits_dataframe(comparisons)
    table_html = df_traits.to_html(index=False, escape=True)

    return grid_html + "<hr><h2>Agent Traits</h2>" + table_html
