from __future__ import annotations

"""High-level wrapper around two `edsl.Results` objects."""

from typing import Sequence, Optional, Dict, Any, List, Callable
from rich.console import Console
from rich.table import Table
from typing import TYPE_CHECKING

from .factory import ComparisonFactory
from .answer_comparison import AnswerComparison
from .visualization import render_comparison_table, render_metric_heatmap
from .result_differences import ResultDifferences

# Public API -----------------------------------------------------------

__all__ = [
    "ResultPairComparison",
    "ResultDifferences",
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
        ScenarioList,
    )  # pragma: no cover – only for type hints

from ..base import Base


class ResultPairComparison(Base):
    """Pair-wise result comparison and visualisation."""

    def __repr__(self) -> str:
        import ast

        def get_name(name_field):
            try:
                extracted_name = ast.literal_eval(name_field)["name"][:4]
                return extracted_name
            except Exception:
                return name_field[:4]

        agent_1 = get_name(self.result_A.agent.name)
        agent_2 = get_name(self.result_B.agent.name)

        questions = list(self.result_A.answer.keys())
        if len(questions) > 10:
            questions = ",".join(questions[:3]) + "..." + ",".join(questions[-3:])
        else:
            questions = ", ".join(questions)

        return (
            f"ResultPairComparison: '{agent_1}' vs '{agent_2}' on Survey: '{questions}'"
        )

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

    def _repr_html_(self) -> str:
        return self.to_scenario_list()._repr_html_()

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

    def should_include_question(
        self,
        question_name: str,
        exclude_exact_match: bool = True,
        exclude_answer_values: Optional[Sequence[str]] = None,
    ) -> bool:
        """Determine if a question should be included based on filter criteria.

        Args:
            question_name: Name of the question to check
            exclude_exact_match: If True, exclude questions where exact_match is True
            exclude_answer_values: If provided, exclude questions where answer_b
                                  matches any of these values (case-insensitive)

        Returns:
            True if the question should be included, False otherwise

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> # Get a question name
            >>> qname = list(rc.comparison.keys())[0]
            >>> isinstance(rc.should_include_question(qname), bool)
            True
        """
        if question_name not in self.comparison:
            return False

        comparison_data = self.comparison[question_name]

        # Check exact match filter
        if exclude_exact_match:
            exact_match = comparison_data["exact_match"]
            if exact_match is True:
                return False

        # Check answer value filter
        if exclude_answer_values:
            answer_b = comparison_data.answer_b
            # Convert to string for comparison
            answer_b_str = str(answer_b).strip().lower() if answer_b is not None else ""

            # Normalize the exclude values to lowercase
            exclude_values_lower = [
                str(v).strip().lower() for v in exclude_answer_values
            ]

            if answer_b_str in exclude_values_lower:
                return False

        return True

    def differences(
        self,
        question_names: Optional[Sequence[str]] = None,
        template: Optional[str] = None,
        exclude_exact_match: bool = True,
        exclude_answer_values: Optional[Sequence[str]] = None,
        filter_func: Optional[Callable[[str, AnswerComparison], bool]] = None,
    ) -> "ResultDifferences":
        """Create a ResultDifferences object containing formatted differences.

        Returns a ResultDifferences container with formatted comparison data for
        questions. By default, excludes questions with exact matches and common
        placeholder answers. The ResultDifferences object can be displayed
        interactively using its show() method or converted to string.

        Args:
            question_names: Optional sequence of question names to include.
                          If None, includes all questions (subject to filters).
            template: Optional Jinja2 template string. If None, uses default template.
            exclude_exact_match: If True, exclude questions where exact_match is True.
                               Default: True
            exclude_answer_values: Sequence of answer values to exclude. Questions where
                                 answer_b matches any of these values (case-insensitive)
                                 will be excluded. Default: ["n/a", "none", "missing"]
            filter_func: Optional custom filter function that takes (question_name,
                        AnswerComparison) and returns True to include. Applied after
                        built-in filters.

        Returns:
            ResultDifferences object containing the formatted differences

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> rd = rc.differences()
            >>> len(rd) > 0
            True
            >>> "<question_text>" in str(rd)
            True

            Show specific questions:
            >>> rd = rc.differences(question_names=["how_feeling"])
            >>> len(rd) >= 0
            True

            Disable default filters:
            >>> rd = rc.differences(exclude_exact_match=False, exclude_answer_values=None)
            >>> isinstance(rd, object)
            True

            Custom filter function:
            >>> def my_filter(qname, comp):
            ...     return len(str(comp.answer_a)) > 5
            >>> rd = rc.differences(filter_func=my_filter)
            >>> len(rd) >= 0
            True
        """
        from .result_differences import ResultDifferences

        return ResultDifferences.from_comparison(
            result_comparison=self,
            question_names=question_names,
            template=template,
            exclude_exact_match=exclude_exact_match,
            exclude_answer_values=exclude_answer_values,
            filter_func=filter_func,
        )

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

        The score is normalized to be a float between [0, 1] by normalizing the
        metric weights to sum to 1. Question weights are used to compute weighted
        averages within each metric.

        Parameters
        ----------
        metric_weights
            Mapping *metric_name* -> *weight* used for aggregation.
            The argument is required; omitting it raises a ``ValueError``.
            Weights are automatically normalized to sum to 1.
        question_weights
            Mapping *question_name* -> *weight* used for aggregation.
            The argument is optional; if omitted, all questions are weighted equally (weight of 1).

        Returns
        -------
        float
            Normalized score between 0 and 1.
        """

        if metric_weights is None:
            raise ValueError("metric_weights must be provided for weighted_score().")

        # Default question weights equal for all questions if not provided
        if question_weights is None:
            question_weights = {q: 1.0 for q in self.comparison.keys()}
        else:
            self._validate_question_weights(question_weights, self.comparison.keys())

        # Validate provided weights
        self._validate_metric_weights(metric_weights)

        # Normalize metric weights to sum to 1 for [0, 1] score range
        total_metric_weight = sum(metric_weights.values())
        if total_metric_weight == 0:
            return 0.0

        normalized_metric_weights = {
            name: weight / total_metric_weight
            for name, weight in metric_weights.items()
        }

        cache_key = (
            frozenset(normalized_metric_weights.items()),
            frozenset(question_weights.items()),
        )
        if cache_key in self._cached_scores:
            return self._cached_scores[cache_key]

        total = 0.0
        for metric_name, weight in normalized_metric_weights.items():
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

    def visualize_weighted_score(
        self,
        metric_weights: Optional[Dict[str, float]] = None,
        question_weights: Optional[Dict[str, float]] = None,
    ) -> "WeightedScoreVisualization":
        """Create a detailed visualization of the weighted score calculation.

        Returns a WeightedScoreVisualization object that shows a breakdown table
        with each metric, question, their weights, and contribution to the final score.

        If no weights are provided, uses default equal weighting for all metrics
        and questions, making this method work out-of-the-box.

        Parameters
        ----------
        metric_weights
            Mapping *metric_name* -> *weight* used for aggregation.
            If None, uses equal weights for all metrics (default).
            Weights are automatically normalized to sum to 1.
        question_weights
            Mapping *question_name* -> *weight* used for aggregation.
            If None, all questions are weighted equally (weight of 1.0).

        Returns
        -------
        WeightedScoreVisualization
            Visualization object with _repr_html_ for displaying the breakdown table

        Examples
        --------
        Default weights (no parameters):

        >>> from edsl.comparisons import ResultPairComparison
        >>> rc = ResultPairComparison.example()
        >>> viz = rc.visualize_weighted_score()
        >>> isinstance(viz.final_score, float)
        True
        >>> len(viz.breakdown) > 0
        True

        Custom weights:

        >>> from edsl.comparisons import example_metric_weighting_dict, example_question_weighting_dict
        >>> mw = example_metric_weighting_dict(rc.comparison_factory)
        >>> qw = example_question_weighting_dict(rc)
        >>> viz = rc.visualize_weighted_score(mw, qw)
        >>> isinstance(viz.final_score, float)
        True
        """
        from .weighted_score_visualization import WeightedScoreVisualization

        # Use default equal weights if none provided
        if metric_weights is None:
            metric_weights = example_metric_weighting_dict(
                self.comparison_factory, weight=1.0
            )

        # Default question weights equal for all questions if not provided
        if question_weights is None:
            question_weights = {q: 1.0 for q in self.comparison.keys()}
        else:
            self._validate_question_weights(question_weights, self.comparison.keys())

        # Validate provided weights
        self._validate_metric_weights(metric_weights)

        # Normalize metric weights to sum to 1 for [0, 1] score range
        total_metric_weight = sum(metric_weights.values())
        if total_metric_weight == 0:
            # Return empty visualization
            return WeightedScoreVisualization(
                result_comparison=self,
                metric_weights={},
                question_weights=question_weights,
                final_score=0.0,
                breakdown=[],
            )

        normalized_metric_weights = {
            name: weight / total_metric_weight
            for name, weight in metric_weights.items()
        }

        # Build detailed breakdown
        breakdown = []
        total = 0.0

        for metric_name, weight in normalized_metric_weights.items():
            # Gather values for this metric across all questions
            questions_data = []
            weighted_vals: List[float] = []
            weights_q: List[float] = []

            for qname, ac in self.comparison.items():
                v = ac[metric_name]
                wq = question_weights.get(qname, 1.0)

                # Convert value to float if possible
                numeric_v = None
                if v is not None:
                    if isinstance(v, bool):
                        numeric_v = 1.0 if v else 0.0
                    else:
                        try:
                            numeric_v = float(v)
                        except (TypeError, ValueError):
                            pass

                # Store question data
                weighted_score = (numeric_v * wq) if numeric_v is not None else None
                questions_data.append(
                    {
                        "question": qname,
                        "score": numeric_v,
                        "question_weight": wq,
                        "weighted_score": weighted_score,
                    }
                )

                # Accumulate for average
                if numeric_v is not None:
                    weighted_vals.append(numeric_v * wq)
                    weights_q.append(wq)

            metric_avg = (
                sum(weighted_vals) / sum(weights_q)
                if weights_q and sum(weights_q) != 0
                else 0.0
            )

            breakdown.append(
                {
                    "metric_name": metric_name,
                    "metric_weight": weight,
                    "metric_avg": metric_avg,
                    "questions": questions_data,
                }
            )

            total += weight * metric_avg

        return WeightedScoreVisualization(
            result_comparison=self,
            metric_weights=normalized_metric_weights,
            question_weights=question_weights,
            final_score=total,
            breakdown=breakdown,
        )

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

    def _serialize_value(self, value: Any) -> Any:
        """Recursively serialize a value, handling BaseDiff objects and other complex types.

        Args:
            value: The value to serialize

        Returns:
            Serialized value that is JSON-compatible
        """
        # Handle None
        if value is None:
            return None

        # Handle BaseDiff objects
        if (
            hasattr(value, "to_dict")
            and hasattr(value, "__class__")
            and "BaseDiff" in value.__class__.__name__
        ):
            diff_dict = value.to_dict()
            # Recursively serialize the diff_dict
            return self._serialize_value(diff_dict)

        # Handle dictionaries
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}

        # Handle lists
        if isinstance(value, list):
            return [self._serialize_value(item) for item in value]

        # Handle tuples (convert to list and recursively serialize)
        if isinstance(value, tuple):
            return [self._serialize_value(item) for item in value]

        # Handle generators and other non-serializable iterables - convert to string representation
        if hasattr(value, "__iter__") and not isinstance(
            value, (str, bytes, dict, list)
        ):
            try:
                # Try to convert to list
                return [self._serialize_value(item) for item in value]
            except:
                # If that fails, just return string representation
                return str(value)

        # Handle other objects with to_dict
        if hasattr(value, "to_dict"):
            return value.to_dict()

        # Return simple types as-is
        return value

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize to dictionary.

        Args:
            add_edsl_version: Whether to include EDSL version

        Returns:
            Dictionary representation

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> d = rc.to_dict()
            >>> 'result_A' in d
            True
            >>> 'result_B' in d
            True
        """
        # Serialize the comparison dict (which contains AnswerComparison objects)
        comparison_serialized = {
            qname: ac.to_dict() for qname, ac in self.comparison.items()
        }

        # Serialize the diffs dict (which may contain diff objects)
        diffs_serialized = {}
        for key, diff_obj in self._diffs.items():
            diffs_serialized[key] = self._serialize_value(diff_obj)

        result = {
            "result_A": self.result_A.to_dict(),
            "result_B": self.result_B.to_dict(),
            "comparison": comparison_serialized,
            "diff_keys": list(self.diff_keys),
            "diffs": diffs_serialized,
            "edsl_class_name": self.__class__.__name__,
        }

        # Serialize comparison_factory if it has to_dict, otherwise store class info
        if hasattr(self.comparison_factory, "to_dict"):
            result["comparison_factory"] = self.comparison_factory.to_dict()
        else:
            # Store minimal info to reconstruct with defaults
            result["comparison_factory"] = {
                "type": "default",
                "metric_names": [
                    str(fn) for fn in self.comparison_factory.comparison_fns
                ],
            }

        if add_edsl_version:
            try:
                from edsl import __version__

                result["edsl_version"] = __version__
            except ImportError:
                pass

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResultPairComparison":
        """Deserialize from dictionary.

        Args:
            data: Dictionary containing ResultPairComparison data

        Returns:
            ResultPairComparison instance

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> d = rc.to_dict()
            >>> rc2 = ResultPairComparison.from_dict(d)
            >>> isinstance(rc2, ResultPairComparison)
            True
        """
        # Import Result to deserialize
        try:
            from edsl import Result
        except ImportError as exc:
            raise ImportError(
                "edsl is required for ResultPairComparison.from_dict(); install edsl to use this method."
            ) from exc

        # Remove edsl_version if present
        data_copy = {k: v for k, v in data.items() if k != "edsl_version"}

        # Deserialize results
        result_A = Result.from_dict(data_copy["result_A"])
        result_B = Result.from_dict(data_copy["result_B"])

        # Reconstruct comparison_factory
        factory_data = data_copy.get("comparison_factory")
        if factory_data and factory_data.get("type") == "default":
            comparison_factory = ComparisonFactory.with_defaults()
        elif factory_data and hasattr(ComparisonFactory, "from_dict"):
            comparison_factory = ComparisonFactory.from_dict(factory_data)
        else:
            comparison_factory = ComparisonFactory.with_defaults()

        # Create instance with the deserialized data
        diff_keys = tuple(data_copy.get("diff_keys", ("scenario", "agent", "model")))
        instance = cls(
            result_A,
            result_B,
            comparison_factory=comparison_factory,
            diff_keys=diff_keys,
        )

        return instance

    def code(self) -> str:
        """Return Python code to recreate this ResultPairComparison.

        Returns:
            Python code string

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> code_str = rc.code()
            >>> 'ResultPairComparison' in code_str
            True
        """
        return (
            f"from edsl.comparisons import ResultPairComparison, ComparisonFactory\n"
            f"# Note: Requires result_A and result_B Result objects\n"
            f"# comparison_factory = ComparisonFactory.with_defaults()\n"
            f"# rc = ResultPairComparison(result_A, result_B, comparison_factory=comparison_factory, "
            f"diff_keys={self.diff_keys})"
        )

    def __hash__(self) -> int:
        """Return hash of the ResultPairComparison.

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> isinstance(hash(rc), int)
            True
        """
        from ..utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

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

    def example_difference(
        self,
        question_name: Optional[str] = None,
        exclude_exact_match: bool = True,
        exclude_answer_values: Optional[Sequence[str]] = None,
        print_output: bool = True,
    ) -> "ResultDifferences":
        """Display a formatted difference for a randomly selected question.

        Randomly samples one question from the available comparisons (subject to filters)
        and returns a ResultDifferences object. Useful for quickly inspecting
        example comparisons.

        Args:
            question_name: If provided, shows this specific question. If None, randomly
                          samples from available questions (subject to filters).
            exclude_exact_match: If True, only sample from questions without exact matches.
                               Default: True
            exclude_answer_values: Answer values to exclude from sampling.
                                 Default: ["n/a", "none", "missing"]
            print_output: If True, prints the output using rich Console. Default: True

        Returns:
            ResultDifferences object containing the selected question

        Raises:
            ValueError: If no questions are available after applying filters

        Examples:
            >>> from edsl.comparisons import ResultPairComparison
            >>> rc = ResultPairComparison.example()
            >>> rd = rc.example_difference(print_output=False)
            >>> "<question_text>" in str(rd)
            True

            Show specific question:
            >>> rd = rc.example_difference(question_name="how_feeling", print_output=False)
            >>> "<question_text>" in str(rd)
            True

            Include questions with exact matches:
            >>> rd = rc.example_difference(exclude_exact_match=False, print_output=False)
            >>> "<question_text>" in str(rd)
            True
        """
        import random

        if question_name is None:
            # Get all questions that pass the filters
            if exclude_answer_values is None:
                exclude_answer_values = ["n/a", "none", "missing"]

            available_questions = [
                qname
                for qname in self.comparison.keys()
                if self.should_include_question(
                    qname,
                    exclude_exact_match=exclude_exact_match,
                    exclude_answer_values=exclude_answer_values,
                )
            ]

            if not available_questions:
                raise ValueError(
                    "No questions available after applying filters. "
                    "Try setting exclude_exact_match=False or exclude_answer_values=None"
                )

            # Randomly sample one question
            question_name = random.choice(available_questions)

        # Get the formatted difference for this question
        result_diffs = self.differences(
            question_names=[question_name],
            exclude_exact_match=False,  # Don't filter since we already selected
            exclude_answer_values=None,
        )

        if print_output:
            console = Console()
            console.print(f"[bold]Random question sample:[/bold] {question_name}\n")
            console.print(str(result_diffs))

        return result_diffs


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
