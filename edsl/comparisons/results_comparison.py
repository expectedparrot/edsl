from __future__ import annotations

"""High-level wrapper around two `edsl.Results` objects."""

from typing import Sequence, Optional, Dict, Any, List, Callable
from rich.console import Console
from rich.table import Table
from typing import TYPE_CHECKING

from .factory import ComparisonFactory
from .answer_comparison import AnswerComparison
from .visualization import render_comparison_table, render_metric_heatmap

# Public API -----------------------------------------------------------

__all__ = [
    "ResultPairComparison",
    "example_metric_weighting_dict",
    "example_question_weighting_dict",
    "single_metric_weighting_dict",
    "single_question_weighting_dict",
]

# ---------------------------------------------------------------------
# Helper to build a default weighting dictionary (defined early for reuse)
# ---------------------------------------------------------------------


def example_metric_weighting_dict(
    comparison_factory: ComparisonFactory | None = None,
    weight: float = 1.0,
) -> Dict[str, float]:
    """Return a mapping *metric_name* -> *weight* for the given factory.

    Parameters
    ----------
    comparison_factory
        Factory whose metric functions should be considered.  If *None*, a
        :class:`ComparisonFactory` with the default metrics is instantiated.
    weight
        Value assigned to **every** metric (default: 1.0).

    Examples
    --------
    >>> from edsl.comparisons import ResultPairComparison, example_metric_weighting_dict
    >>> rc = ResultPairComparison.example()
    >>> weights = example_metric_weighting_dict(rc.comparison_factory)
    >>> all(isinstance(w, float) for w in weights.values())
    True
    """

    if comparison_factory is None:
        comparison_factory = ComparisonFactory.with_defaults()

    return {str(fn): float(weight) for fn in comparison_factory.comparison_fns}


# ---------------------------------------------------------------------
# Example question weighting helper
# ---------------------------------------------------------------------


def example_question_weighting_dict(
    results_comparison: "ResultPairComparison",
    weight: float = 1.0,
) -> Dict[str, float]:
    """Return a mapping *question_name* -> *weight* for the given comparison.

    Examples
    --------
    >>> from edsl.comparisons import ResultPairComparison, example_question_weighting_dict
    >>> rc = ResultPairComparison.example()
    >>> qw = example_question_weighting_dict(rc)
    >>> set(qw) == set(rc.comparison.keys())
    True
    """

    return {qname: float(weight) for qname in results_comparison.comparison.keys()}


# ---------------------------------------------------------------------
# Helpers for *focused* weighting on a single metric/question
# ---------------------------------------------------------------------


def single_metric_weighting_dict(
    comparison_factory: ComparisonFactory,
    target_metric_name: str,
    weight: float = 1.0,
    default: float = 0.0,
) -> Dict[str, float]:
    """Return weights with *target_metric_name* set to *weight*, others to *default*.

    Raises
    ------
    ValueError
        If *target_metric_name* is not produced by *comparison_factory*.
    """

    names = [str(fn) for fn in comparison_factory.comparison_fns]
    if target_metric_name not in names:
        raise ValueError(f"Metric '{target_metric_name}' not found in factory metrics.")
    return {name: (weight if name == target_metric_name else default) for name in names}


def single_question_weighting_dict(
    results_comparison: "ResultPairComparison",
    target_question_name: str,
    weight: float = 1.0,
    default: float = 0.0,
) -> Dict[str, float]:
    """Return weights with *target_question_name* set to *weight*, others to *default*.

    Raises
    ------
    ValueError
        If *target_question_name* is not among the compared questions.
    """

    qnames = list(results_comparison.comparison.keys())
    if target_question_name not in qnames:
        raise ValueError(f"Question '{target_question_name}' not found in comparison.")
    return {q: (weight if q == target_question_name else default) for q in qnames}


if TYPE_CHECKING:
    from edsl import Results  # pragma: no cover – only for type hints
    from edsl.scenarios import (
        Scenario,
        ScenarioList,
    )  # pragma: no cover – only for type hints


class ResultPairComparison:
    """Pair-wise result comparison and visualisation."""

    def __init__(
        self,
        result_A: Any,
        result_B: Any,
        comparison_factory: ComparisonFactory | None = None,
        diff_keys: Sequence[str] | None = None,
    ) -> None:
        self.result_A = result_A
        self.result_B = result_B
        self.comparison_factory = (
            comparison_factory or ComparisonFactory.with_defaults()
        )
        self.diff_keys: Sequence[str] = diff_keys or ("scenario", "agent", "model")

        # Optional cache for previous weighted score calculations
        self._cached_scores: Dict[tuple[frozenset, frozenset], float] = {}

        # self._comparison: Optional[Dict[str, AnswerComparison]] = None
        self._diffs: Dict[str, Any] = {}

        for key in self.diff_keys:
            try:
                self._diffs[key] = result_A[key] - result_B[key]
            except Exception:
                self._diffs[key] = None

        self.comparison = self.comparison_factory.compare_results(
            self.result_A, self.result_B
        ).comparisons

    def to_table(self, title: Optional[str] = None) -> Table:
        if title is None:
            title = "Answer Comparison"
        return render_comparison_table(
            self.comparison, self.comparison_factory.comparison_fns, title=title
        )

    def print_table(self, console: Optional[Console] = None) -> None:
        if console is None:
            console = Console()
        console.print(self.to_table())

    def to_scenario_list(self) -> "ScenarioList":
        """Convert comparison results to a ScenarioList with codebook.

        Returns a ScenarioList where each row represents a question comparison
        with short column names as keys and a codebook mapping short names to
        descriptive names.

        Returns:
            ScenarioList: Collection of scenarios with comparison data and codebook

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> sl = rc.to_scenario_list()
            >>> len(sl) > 0
            True
            >>> len(sl.codebook) > 0
            True
        """
        from edsl.scenarios import Scenario, ScenarioList

        metric_names = [str(fn) for fn in self.comparison_factory.comparison_fns]

        # Build the data rows and codebook
        scenarios = []
        codebook = {}

        # Define column names and their descriptions
        codebook["question"] = "Question"
        codebook["question_text"] = "Question Text"
        codebook["answer_a"] = "Answer A"
        codebook["answer_b"] = "Answer B"

        for m in metric_names:
            # Short name is the metric name itself
            # Pretty name is the formatted version
            pretty = m.replace("_", " ").title()
            codebook[m] = pretty

        codebook["question_type"] = "Question Type"

        # Build rows
        for q, metrics in self.comparison.items():
            row = {}
            row["question"] = str(q)
            row["question_text"] = metrics["question_text"]
            row["answer_a"] = metrics.answer_a
            row["answer_b"] = metrics.answer_b

            # Add metric values
            for m in metric_names:
                val = metrics[m]
                if isinstance(val, (int, float)):
                    row[m] = val
                else:
                    row[m] = str(val) if val is not None else None

            row["question_type"] = metrics["question_type"]

            scenarios.append(Scenario(row))

        return ScenarioList(scenarios, codebook=codebook)

    def differences(
        self,
        question_names: Optional[Sequence[str]] = None,
        template: Optional[str] = None,
    ) -> str:
        """Format and display differences for questions.

        Shows formatted comparison data for all questions or specific questions.
        Uses the ComparisonFormatter to render the output.

        Args:
            question_names: Optional sequence of question names to show.
                          If None, shows all questions.
            template: Optional Jinja2 template string. If None, uses default template.

        Returns:
            Formatted string with question comparisons separated by newlines

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> output = rc.differences()
            >>> "<question_text>" in output
            True

            Show specific questions:
            >>> output = rc.differences(question_names=["how_feeling"])
            >>> "<question_text>" in output
            True
        """
        from .comparison_formatter import ComparisonFormatter

        # Get the scenario list
        sl = self.to_scenario_list()

        # Create formatter
        formatter = ComparisonFormatter(sl, template=template)

        # Determine which questions to format
        if question_names is None:
            # Format all questions
            formatted_parts = formatter.format_all_questions()
        else:
            # Format specific questions
            formatted_parts = []
            for qname in question_names:
                try:
                    formatted_parts.append(formatter.format_question(qname))
                except KeyError:
                    # Question not found, skip it
                    pass

        # Join with double newlines
        return "\n\n".join(formatted_parts)

    @property
    def diffs(self) -> Dict[str, Any]:
        return self._diffs

    def print_diffs(self, console: Optional[Console] = None) -> None:
        if console is None:
            console = Console()
        for key in self.diff_keys:
            diff_obj = self._diffs.get(key)
            if diff_obj is None:
                console.print(f"[red]No diff available for '{key}'[/red]")
            else:
                console.print(f"[bold]{key.title()} difference:[/bold]")
                if hasattr(diff_obj, "pretty_print"):
                    diff_obj.pretty_print()
                else:
                    console.print(str(diff_obj))

    def to_diffs_html(self) -> str:
        """Generate HTML representation of the diffs."""
        import html

        html_parts = ['<div style="font-family: monospace;">']

        for key in self.diff_keys:
            diff_obj = self._diffs.get(key)
            html_parts.append(
                f'<h3 style="color: #333; margin-top: 20px;">{key.title()} Difference:</h3>'
            )

            if diff_obj is None:
                html_parts.append(
                    '<p style="color: #d32f2f;">No diff available for this key</p>'
                )
            else:
                html_parts.append(
                    '<div style="background-color: #f5f5f5; padding: 10px; border-left: 4px solid #2196f3; margin: 10px 0;">'
                )

                # Check if diff_obj has a string representation we can use
                if hasattr(diff_obj, "__str__"):
                    diff_str = str(diff_obj)
                    escaped_diff = html.escape(diff_str)
                    # Replace newlines with <br> for HTML display
                    formatted_diff = escaped_diff.replace("\n", "<br>")
                    html_parts.append(
                        f'<pre style="margin: 0; white-space: pre-wrap;">{formatted_diff}</pre>'
                    )
                else:
                    html_parts.append("<p>Unable to display diff</p>")

                html_parts.append("</div>")

        html_parts.append("</div>")
        return "\n".join(html_parts)

    def _validate_metric_weights(self, metric_weights: Dict[str, float]) -> None:
        """Ensure provided *metric_weights* match the metrics produced by the factory.

        Raises
        ------
        ValueError
            If a metric defined by the factory has no corresponding weight or
            an unknown metric is specified in *metric_weights*.
        """

        if metric_weights is None:
            return

        # Expected metric names (string representation of comparison functions)
        expected_metrics = {str(fn) for fn in self.comparison_factory.comparison_fns}

        provided_metrics = set(metric_weights.keys())

        missing = expected_metrics - provided_metrics
        extra = provided_metrics - expected_metrics

        if missing or extra:
            messages: List[str] = []
            if missing:
                messages.append(
                    "Missing weights for metrics: " + ", ".join(sorted(missing))
                )
            if extra:
                messages.append(
                    "Unexpected metrics provided: " + ", ".join(sorted(extra))
                )
            raise ValueError("; ".join(messages))

    def _validate_question_weights(
        self, question_weights: Dict[str, float], questions: Sequence[str]
    ) -> None:
        """Validate *question_weights* covers each question exactly once."""

        expected = set(questions)
        provided = set(question_weights.keys())

        missing = expected - provided
        extra = provided - expected

        if missing or extra:
            msgs: List[str] = []
            if missing:
                msgs.append(
                    "Missing weights for questions: " + ", ".join(sorted(missing))
                )
            if extra:
                msgs.append(
                    "Unexpected questions provided: " + ", ".join(sorted(extra))
                )
            raise ValueError("; ".join(msgs))

    def weighted_score(
        self,
        metric_weights: Optional[Dict[str, float]] = None,
        question_weights: Optional[Dict[str, float]] = None,
    ) -> float:
        """Compute a weighted score using metric and question weights.

        Parameters
        ----------
        metric_weights
            Mapping *metric_name* -> *weight* used for aggregation.
            The argument is required; omitting it raises a ``ValueError``.
        question_weights
            Mapping *question_name* -> *weight* used for aggregation.
            The argument is optional; if omitted, all questions are weighted equally.
        """

        if metric_weights is None:
            raise ValueError("metric_weights must be provided for weighted_score().")

        # Default question weights equal for all questions if not provided        comparison = self.compare()

        if question_weights is None:
            question_weights = {q: 1.0 for q in self.comparison.keys()}
        else:
            self._validate_question_weights(question_weights, self.comparison.keys())

        cache_key = (
            frozenset(metric_weights.items()),
            frozenset(question_weights.items()),
        )
        if cache_key in self._cached_scores:
            return self._cached_scores[cache_key]

        # Validate provided weights
        self._validate_metric_weights(metric_weights)

        total = 0.0
        for metric_name, weight in metric_weights.items():
            # Gather values for this metric across all questions
            weighted_vals: List[float] = []
            weights_q: List[float] = []
            for qname, ac in self.comparison.items():
                v = ac[metric_name]
                if v is None:
                    continue
                # Booleans -> numeric
                if isinstance(v, bool):
                    v = 1.0 if v else 0.0
                else:
                    try:
                        v = float(v)
                    except (TypeError, ValueError):
                        continue

                wq = question_weights.get(qname, 1.0)
                weighted_vals.append(v * wq)
                weights_q.append(wq)

            metric_avg = (
                sum(weighted_vals) / sum(weights_q)
                if weights_q and sum(weights_q) != 0
                else 0.0
            )
            total += weight * metric_avg

        # Cache and return
        self._cached_scores[cache_key] = total
        return total

    @staticmethod
    def metric_heatmap(
        results: Sequence,
        metric_name: str,
        comparison_factory: ComparisonFactory | None = None,
        agg_func: Callable[[List[float]], float] | None = None,
        title: str | None = None,
        ax: Optional[Any] = None,
    ):
        return render_metric_heatmap(
            results,
            metric_name=metric_name,
            comparison_factory=comparison_factory,
            agg_func=agg_func,
            title=title,
            ax=ax,
        )

    @classmethod
    def example(
        cls, comparison_factory: ComparisonFactory | None = None
    ) -> "ResultPairComparison":
        """Return a *ResultPairComparison* instance based on `edsl.Results.example()`.

        The helper uses two example *Result* entries (index 0 and 1) and a
        default metric set (including cosine similarity).

        Examples
        --------
        >>> from edsl.comparisons import (
        ...     ResultPairComparison,
        ...     example_metric_weighting_dict,
        ...     example_question_weighting_dict,
        ... )
        >>> rc = ResultPairComparison.example()
        >>> mw = example_metric_weighting_dict(rc.comparison_factory)
        >>> qw = example_question_weighting_dict(rc)
        >>> isinstance(rc.weighted_score(mw, qw), float)
        True
        """

        # Use provided factory or default to full ComparisonFactory with COSINE metrics
        if comparison_factory is None:
            comparison_factory = ComparisonFactory.with_defaults()

        # Rely on edsl built-in example results ----------------------------
        try:
            from edsl import Results as _EDSLResults  # local import to avoid hard dep
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "edsl is required for ResultPairComparison.example(); install edsl to use this helper."
            ) from exc

        example_results: "Results" = _EDSLResults.example()

        if len(example_results) < 2:
            raise RuntimeError("Results.example() did not return at least two entries.")

        return cls(
            example_results[0],
            example_results[1],
            comparison_factory=comparison_factory,
        )


if __name__ == "__main__":  # pragma: no cover
    import doctest

    doctest.testmod(verbose=True)

    rc = ResultPairComparison.example()
    import rich

    c = rich.console.Console()
    c.print(rc.to_table())

    # Focused weighting: cosine similarity metric + 'how_feeling' question
    target_metric = "cosine_similarity (all-MiniLM-L6-v2)"
    target_question = "how_feeling"

    mw_focus = single_metric_weighting_dict(rc.comparison_factory, target_metric)
    qw_focus = single_question_weighting_dict(rc, target_question)

    print("\nFocused Metric Weights:", mw_focus)
    print("Focused Question Weights:", qw_focus)

    score_focus = rc.weighted_score(mw_focus, qw_focus)
    c.print(f"\n[bold]Focused Weighted Score:[/bold] {score_focus:.3f}")
