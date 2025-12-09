"""PerformanceDelta class for comparing performance across two ResultPairComparison outputs.

This module provides functionality to analyze whether one agent's performance improved,
stayed the same, or worsened compared to another across multiple metrics.
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from ..base import Base
from ..utilities import dict_hash, remove_edsl_version

if TYPE_CHECKING:
    from .result_pair_comparison import ResultPairComparison


class PerformanceDelta(Base):
    """Compares performance metrics between two ResultPairComparison objects.

    For each metric in the comparison, PerformanceDelta determines whether performance
    improved (+1), stayed the same (0), or worsened (-1). This is useful for tracking
    agent improvements over iterations and identifying Pareto improvements.

    A Pareto improvement occurs when at least one metric improves and no metric worsens.

    Examples:
        >>> from edsl.comparisons import ResultPairComparison, PerformanceDelta
        >>> # rc_before = ResultPairComparison(result_a_v1, result_b)
        >>> # rc_after = ResultPairComparison(result_a_v2, result_b)
        >>> # perf_delta = PerformanceDelta(rc_before, rc_after)
        >>> # perf_delta.is_pareto()  # True if no metrics worsened
    """

    def __init__(
        self,
        baseline_comparison: "ResultPairComparison",
        updated_comparison: "ResultPairComparison",
        higher_is_better: Optional[Dict[str, bool]] = None,
    ):
        """Initialize a PerformanceDelta from two ResultPairComparison objects.

        Args:
            baseline_comparison: ResultPairComparison from the baseline agent
            updated_comparison: ResultPairComparison from the updated agent
            higher_is_better: Optional dict mapping metric names to whether higher
                            values are better. If None, assumes higher is always better
                            except for metrics with 'distance' or 'error' in the name.

        Raises:
            ValueError: If comparisons don't have matching questions or metrics
        """
        # Convert ResultPairComparison objects to ScenarioLists
        self.baseline_sl = baseline_comparison.to_scenario_list()
        self.updated_sl = updated_comparison.to_scenario_list()

        # Store the original comparison objects for reference
        self.baseline_comparison = baseline_comparison
        self.updated_comparison = updated_comparison

        # Validate that scenario lists are compatible
        self._validate_scenario_lists()

        # Determine which metrics have higher-is-better semantics
        self.higher_is_better = higher_is_better or self._infer_metric_direction()

        # Calculate deltas for each question and metric
        self.deltas: Dict[str, Dict[str, int]] = self._calculate_deltas()

    def _validate_scenario_lists(self) -> None:
        """Validate that the two scenario lists are compatible for comparison."""
        if len(self.baseline_sl) != len(self.updated_sl):
            raise ValueError(
                f"Scenario lists must have same length. "
                f"Baseline: {len(self.baseline_sl)}, Updated: {len(self.updated_sl)}"
            )

        # Check that questions match
        baseline_questions = [s["question"] for s in self.baseline_sl]
        updated_questions = [s["question"] for s in self.updated_sl]

        if baseline_questions != updated_questions:
            raise ValueError(
                "Scenario lists must have matching questions in the same order."
            )

    def _infer_metric_direction(self) -> Dict[str, bool]:
        """Infer whether higher is better for each metric.

        By default:
        - Metrics with 'distance', 'error', 'loss' in name: lower is better
        - All others: higher is better
        """
        higher_is_better = {}

        # Get metric names from codebook
        if hasattr(self.baseline_sl, "codebook") and self.baseline_sl.codebook:
            metric_names = [
                key
                for key in self.baseline_sl.codebook.keys()
                if key
                not in (
                    "question",
                    "question_text",
                    "answer_a",
                    "answer_b",
                    "question_type",
                )
            ]
        else:
            # Infer from first scenario
            if len(self.baseline_sl) > 0:
                first_scenario = self.baseline_sl[0]
                metric_names = [
                    key
                    for key in first_scenario.keys()
                    if key
                    not in (
                        "question",
                        "question_text",
                        "answer_a",
                        "answer_b",
                        "question_type",
                    )
                ]
            else:
                metric_names = []

        for metric_name in metric_names:
            # Lower is better for distance, error, loss metrics
            lower_is_better_keywords = ["distance", "error", "loss", "diff"]
            metric_lower = metric_name.lower()

            if any(keyword in metric_lower for keyword in lower_is_better_keywords):
                higher_is_better[metric_name] = False
            else:
                higher_is_better[metric_name] = True

        return higher_is_better

    def _calculate_deltas(self) -> Dict[str, Dict[str, int]]:
        """Calculate performance deltas for each question and metric.

        Returns:
            Dictionary mapping question names to dictionaries of metric deltas.
            Each delta is:
            - 1: improvement
            - 0: no change
            - -1: worsening
        """
        deltas = {}

        for baseline_scenario, updated_scenario in zip(
            self.baseline_sl, self.updated_sl
        ):
            question_name = baseline_scenario["question"]
            deltas[question_name] = {}

            # Compare each metric
            for key in baseline_scenario.keys():
                # Skip non-metric fields
                if key in (
                    "question",
                    "question_text",
                    "answer_a",
                    "answer_b",
                    "question_type",
                ):
                    continue

                baseline_value = baseline_scenario[key]
                updated_value = updated_scenario[key]

                # Skip if either value is None or non-numeric
                if baseline_value is None or updated_value is None:
                    deltas[question_name][key] = 0
                    continue

                try:
                    baseline_float = float(baseline_value)
                    updated_float = float(updated_value)
                except (TypeError, ValueError):
                    # For non-numeric values, treat as no change
                    deltas[question_name][key] = 0
                    continue

                # Determine if higher is better for this metric
                higher_better = self.higher_is_better.get(key, True)

                # Calculate delta
                if abs(updated_float - baseline_float) < 1e-9:  # Essentially equal
                    deltas[question_name][key] = 0
                elif updated_float > baseline_float:
                    deltas[question_name][key] = 1 if higher_better else -1
                else:  # updated_float < baseline_float
                    deltas[question_name][key] = -1 if higher_better else 1

        return deltas

    def is_pareto(self) -> bool:
        """Check if this represents a Pareto improvement.

        A Pareto improvement occurs when no metric worsened (no -1 values).

        Returns:
            True if no metrics worsened, False otherwise

        Examples:
            >>> # All metrics improved or stayed same
            >>> # perf_delta.deltas = {'q1': {'metric1': 1, 'metric2': 0}}
            >>> # perf_delta.is_pareto()
            True

            >>> # One metric worsened
            >>> # perf_delta.deltas = {'q1': {'metric1': 1, 'metric2': -1}}
            >>> # perf_delta.is_pareto()
            False
        """
        for question_deltas in self.deltas.values():
            for delta_value in question_deltas.values():
                if delta_value < 0:
                    return False
        return True

    def is_strict_pareto(self) -> bool:
        """Check if this represents a strict Pareto improvement.

        A strict Pareto improvement requires:
        - At least one metric improved (at least one +1)
        - No metric worsened (no -1 values)

        Returns:
            True if at least one metric improved and none worsened

        Examples:
            >>> # At least one improvement, no worsening
            >>> # perf_delta.deltas = {'q1': {'metric1': 1, 'metric2': 0}}
            >>> # perf_delta.is_strict_pareto()
            True

            >>> # No improvements (all zeros)
            >>> # perf_delta.deltas = {'q1': {'metric1': 0, 'metric2': 0}}
            >>> # perf_delta.is_strict_pareto()
            False
        """
        has_improvement = False
        has_worsening = False

        for question_deltas in self.deltas.values():
            for delta_value in question_deltas.values():
                if delta_value > 0:
                    has_improvement = True
                elif delta_value < 0:
                    has_worsening = True

        return has_improvement and not has_worsening

    def improvement_count(self) -> int:
        """Count the number of metrics that improved.

        Returns:
            Number of metric values that are +1
        """
        count = 0
        for question_deltas in self.deltas.values():
            count += sum(1 for v in question_deltas.values() if v > 0)
        return count

    def worsening_count(self) -> int:
        """Count the number of metrics that worsened.

        Returns:
            Number of metric values that are -1
        """
        count = 0
        for question_deltas in self.deltas.values():
            count += sum(1 for v in question_deltas.values() if v < 0)
        return count

    def unchanged_count(self) -> int:
        """Count the number of metrics that stayed the same.

        Returns:
            Number of metric values that are 0
        """
        count = 0
        for question_deltas in self.deltas.values():
            count += sum(1 for v in question_deltas.values() if v == 0)
        return count

    def total_metrics(self) -> int:
        """Count the total number of metrics being compared.

        Returns:
            Total number of metric comparisons across all questions
        """
        total = 0
        for question_deltas in self.deltas.values():
            total += len(question_deltas)
        return total

    def summary(self) -> Dict[str, Any]:
        """Get a summary of the performance delta.

        Returns:
            Dictionary with summary statistics

        Examples:
            >>> # summary = perf_delta.summary()
            >>> # {
            >>> #     'is_pareto': True,
            >>> #     'is_strict_pareto': True,
            >>> #     'improvements': 5,
            >>> #     'unchanged': 2,
            >>> #     'worsenings': 0,
            >>> #     'total_metrics': 7,
            >>> #     'improvement_rate': 0.714
            >>> # }
        """
        total = self.total_metrics()
        improvements = self.improvement_count()

        return {
            "is_pareto": self.is_pareto(),
            "is_strict_pareto": self.is_strict_pareto(),
            "improvements": improvements,
            "unchanged": self.unchanged_count(),
            "worsenings": self.worsening_count(),
            "total_metrics": total,
            "improvement_rate": improvements / total if total > 0 else 0.0,
        }

    def get_improved_metrics(self) -> List[tuple[str, str]]:
        """Get list of (question, metric) pairs that improved.

        Returns:
            List of tuples (question_name, metric_name) for improved metrics
        """
        improved = []
        for question_name, question_deltas in self.deltas.items():
            for metric_name, delta_value in question_deltas.items():
                if delta_value > 0:
                    improved.append((question_name, metric_name))
        return improved

    def get_worsened_metrics(self) -> List[tuple[str, str]]:
        """Get list of (question, metric) pairs that worsened.

        Returns:
            List of tuples (question_name, metric_name) for worsened metrics
        """
        worsened = []
        for question_name, question_deltas in self.deltas.items():
            for metric_name, delta_value in question_deltas.items():
                if delta_value < 0:
                    worsened.append((question_name, metric_name))
        return worsened

    def __repr__(self) -> str:
        """Return string representation of PerformanceDelta."""
        summary = self.summary()
        return (
            f"PerformanceDelta("
            f"improvements={summary['improvements']}, "
            f"unchanged={summary['unchanged']}, "
            f"worsenings={summary['worsenings']}, "
            f"is_pareto={summary['is_pareto']})"
        )

    def __str__(self) -> str:
        """Return human-readable string representation."""
        summary = self.summary()
        lines = [
            "Performance Delta Summary:",
            f"  Total metrics: {summary['total_metrics']}",
            f"  Improvements: {summary['improvements']} ({summary['improvement_rate']:.1%})",
            f"  Unchanged: {summary['unchanged']}",
            f"  Worsenings: {summary['worsenings']}",
            f"  Pareto improvement: {summary['is_pareto']}",
            f"  Strict Pareto: {summary['is_strict_pareto']}",
        ]
        return "\n".join(lines)

    def plot_matrix(
        self,
        figsize: Optional[tuple[int, int]] = None,
        title: Optional[str] = "Performance Delta Matrix",
        show_values: bool = True,
        ax: Optional[Any] = None,
    ) -> Any:
        """Plot performance delta as a matrix with color-coded cells.

        Creates a heatmap-style visualization where:
        - Green cells (+1): metric improved
        - White cells (0): metric unchanged
        - Red cells (-1): metric worsened

        Args:
            figsize: Figure size as (width, height). If None, auto-sized based on data.
            title: Plot title. Set to None to hide title.
            show_values: If True, display delta values (+1, 0, -1) in cells
            ax: Matplotlib axes to plot on. If None, creates new figure.

        Returns:
            Matplotlib axes object

        Raises:
            ImportError: If matplotlib is not installed

        Examples:
            Basic usage in script:

            >>> from edsl.comparisons import PerformanceDelta
            >>> import matplotlib.pyplot as plt
            >>> # perf_delta = PerformanceDelta(rc_before, rc_after)
            >>> # perf_delta.plot_matrix()
            >>> # plt.show()

            In Jupyter notebook (suppress axes output):

            >>> # perf_delta.plot_matrix();  # Note the semicolon

            Or save without display:

            >>> # ax = perf_delta.plot_matrix()
            >>> # plt.savefig('delta.png')
            >>> # plt.close()
        """
        try:
            import matplotlib.pyplot as plt
            import matplotlib.patches as mpatches
            from matplotlib.colors import ListedColormap
            import numpy as np
        except ImportError:
            raise ImportError(
                "matplotlib is required for plotting. "
                "Install it with: pip install matplotlib"
            )

        # Prepare data for plotting
        questions = sorted(self.deltas.keys())
        if not questions:
            raise ValueError("No data to plot")

        # Get all unique metrics across all questions
        all_metrics = set()
        for question_deltas in self.deltas.values():
            all_metrics.update(question_deltas.keys())
        metrics = sorted(all_metrics)

        # Create matrix: rows=questions, cols=metrics
        matrix = np.zeros((len(questions), len(metrics)))
        for i, question in enumerate(questions):
            for j, metric in enumerate(metrics):
                matrix[i, j] = self.deltas[question].get(metric, 0)

        # Create figure if ax not provided
        if ax is None:
            if figsize is None:
                # Auto-size based on data
                width = max(8, len(metrics) * 1.5)
                height = max(6, len(questions) * 0.8)
                figsize = (width, height)
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure

        # Create custom colormap: red (-1), white (0), green (+1)
        colors = ["#ef4444", "#ffffff", "#22c55e"]  # red, white, green
        cmap = ListedColormap(colors)

        # Plot heatmap
        im = ax.imshow(matrix, cmap=cmap, aspect="auto", vmin=-1, vmax=1)

        # Set ticks and labels
        ax.set_xticks(np.arange(len(metrics)))
        ax.set_yticks(np.arange(len(questions)))
        ax.set_xticklabels(metrics, rotation=45, ha="right")
        ax.set_yticklabels(questions)

        # Add gridlines
        ax.set_xticks(np.arange(len(metrics)) - 0.5, minor=True)
        ax.set_yticks(np.arange(len(questions)) - 0.5, minor=True)
        ax.grid(which="minor", color="gray", linestyle="-", linewidth=0.5)

        # Add values in cells if requested
        if show_values:
            for i in range(len(questions)):
                for j in range(len(metrics)):
                    value = int(matrix[i, j])
                    # Choose text color based on cell color
                    text_color = "black" if value == 0 else "white"
                    symbol = "+1" if value == 1 else ("-1" if value == -1 else "0")
                    ax.text(
                        j,
                        i,
                        symbol,
                        ha="center",
                        va="center",
                        color=text_color,
                        fontweight="bold",
                        fontsize=10,
                    )

        # Add title
        if title:
            summary = self.summary()
            full_title = f"{title}\n"
            full_title += f"Improvements: {summary['improvements']} | "
            full_title += f"Unchanged: {summary['unchanged']} | "
            full_title += f"Worsenings: {summary['worsenings']}"
            if summary["is_pareto"]:
                full_title += " ✓ Pareto"
            ax.set_title(full_title, fontsize=12, pad=20)

        # Add legend
        legend_elements = [
            mpatches.Patch(
                facecolor="#22c55e", edgecolor="gray", label="Improved (+1)"
            ),
            mpatches.Patch(
                facecolor="#ffffff", edgecolor="gray", label="Unchanged (0)"
            ),
            mpatches.Patch(
                facecolor="#ef4444", edgecolor="gray", label="Worsened (-1)"
            ),
        ]
        ax.legend(handles=legend_elements, loc="upper left", bbox_to_anchor=(1.05, 1))

        # Adjust layout to prevent label cutoff
        plt.tight_layout()

        return ax

    def to_dict(self, add_edsl_version: bool = True) -> Dict[str, Any]:
        """Serialize to dictionary.

        Args:
            add_edsl_version: Whether to include EDSL version

        Returns:
            Dictionary representation
        """
        result = {
            "deltas": self.deltas,
            "higher_is_better": self.higher_is_better,
            "summary": self.summary(),
            "edsl_class_name": self.__class__.__name__,
        }

        if add_edsl_version:
            from edsl import __version__

            result["edsl_version"] = __version__

        return result

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: Dict[str, Any]) -> "PerformanceDelta":
        """Deserialize from dictionary.

        Note: This creates a PerformanceDelta without the original scenario lists.
        The deltas and higher_is_better mappings are preserved.

        Args:
            data: Dictionary containing PerformanceDelta data

        Returns:
            PerformanceDelta instance
        """
        # Create a minimal instance
        instance = cls.__new__(cls)
        instance.deltas = data["deltas"]
        instance.higher_is_better = data["higher_is_better"]
        instance.baseline_sl = None
        instance.updated_sl = None
        return instance

    def code(self) -> str:
        """Return Python code to recreate this PerformanceDelta.

        Returns:
            Python code string
        """
        return (
            f"from edsl.comparisons import PerformanceDelta\n"
            f"# Note: Requires original ResultPairComparison objects to recreate\n"
            f"# perf_delta = PerformanceDelta(baseline_comparison, updated_comparison, "
            f"higher_is_better={self.higher_is_better})"
        )

    def __hash__(self) -> int:
        """Return hash of the PerformanceDelta."""
        return dict_hash(self.to_dict(add_edsl_version=False))

    @classmethod
    def example(cls, randomize: bool = False) -> "PerformanceDelta":
        """Return an example PerformanceDelta instance.

        Args:
            randomize: If True, adds random variation

        Returns:
            Example PerformanceDelta instance
        """
        from ..scenarios import Scenario, ScenarioList

        # Create example baseline scenario list
        baseline_sl = ScenarioList(
            [
                Scenario(
                    {
                        "question": "q1",
                        "exact_match": 0.5,
                        "cosine_similarity": 0.7,
                        "answer_a": "baseline answer",
                        "answer_b": "target answer",
                    }
                ),
                Scenario(
                    {
                        "question": "q2",
                        "exact_match": 0.3,
                        "cosine_similarity": 0.6,
                        "answer_a": "another baseline",
                        "answer_b": "another target",
                    }
                ),
            ]
        )

        # Create example updated scenario list (with improvements)
        updated_sl = ScenarioList(
            [
                Scenario(
                    {
                        "question": "q1",
                        "exact_match": 0.8,  # Improved
                        "cosine_similarity": 0.85,  # Improved
                        "answer_a": "updated answer",
                        "answer_b": "target answer",
                    }
                ),
                Scenario(
                    {
                        "question": "q2",
                        "exact_match": 0.3,  # Unchanged
                        "cosine_similarity": 0.75,  # Improved
                        "answer_a": "updated baseline",
                        "answer_b": "another target",
                    }
                ),
            ]
        )

        # Create mock ResultPairComparison objects
        class MockResultPairComparison:
            def __init__(self, scenario_list):
                self._scenario_list = scenario_list

            def to_scenario_list(self):
                return self._scenario_list

        baseline_comparison = MockResultPairComparison(baseline_sl)
        updated_comparison = MockResultPairComparison(updated_sl)

        return cls(baseline_comparison, updated_comparison)

    def _eval_repr_(self) -> str:
        """Return an eval-able string representation of the PerformanceDelta.

        Returns:
            str: A string that can be evaluated to recreate the PerformanceDelta
        """
        summary = self.summary()
        return (
            f"PerformanceDelta("
            f"improvements={summary['improvements']}, "
            f"worsenings={summary['worsenings']})"
        )

    def _summary_repr(self) -> str:
        """Generate a summary representation of the PerformanceDelta with Rich formatting.

        Returns:
            str: A formatted summary representation of the PerformanceDelta
        """
        from rich.console import Console
        from rich.text import Text
        import io
        from edsl.config import RICH_STYLES

        summary = self.summary()

        output = Text()
        output.append("PerformanceDelta(", style=RICH_STYLES["primary"])
        output.append(
            f"improvements={summary['improvements']}", style=RICH_STYLES["key"]
        )
        output.append(", ", style=RICH_STYLES["default"])
        output.append(f"unchanged={summary['unchanged']}", style=RICH_STYLES["default"])
        output.append(", ", style=RICH_STYLES["default"])
        output.append(f"worsenings={summary['worsenings']}", style="red")
        output.append(", ", style=RICH_STYLES["default"])

        if summary["is_pareto"]:
            output.append("✓ Pareto", style=RICH_STYLES["secondary"])
        else:
            output.append("✗ Not Pareto", style=RICH_STYLES["dim"])

        output.append(")", style=RICH_STYLES["primary"])

        console = Console(file=io.StringIO(), force_terminal=True, width=120)
        console.print(output, end="")
        return console.file.getvalue()


__all__ = ["PerformanceDelta"]
