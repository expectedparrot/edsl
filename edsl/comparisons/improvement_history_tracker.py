from __future__ import annotations

"""Helper class for tracking persona improvement history across iterations."""

from typing import List, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .iteration_evaluator import EvaluationResult


class ImprovementHistoryTracker:
    """Tracks the history of persona improvements across iterations.

    Records results from each iteration evaluation and provides methods
    to summarize and report on the improvement journey.

    The tracker provides a Rich-formatted visual summary that can be displayed
    by simply printing the tracker object or calling .print_rich().

    Example:
        >>> tracker = ImprovementHistoryTracker()
        >>> # ... record iterations ...
        >>> print(tracker)  # Displays Rich-formatted summary
        >>> # or
        >>> tracker.print_rich()  # Prints directly to console with full color
    """

    def __init__(self):
        """Initialize an empty improvement history tracker."""
        self.history: List[Dict[str, Any]] = []
        self.first_comparison = None
        self.best_comparison = None
        self.agent_name = None

    def __repr__(self) -> str:
        """Return Rich-formatted representation of the improvement history."""
        return self._rich_repr()

    def __str__(self) -> str:
        """Return Rich-formatted representation of the improvement history."""
        return self._rich_repr()

    def _rich_repr(self) -> str:
        """Generate Rich-formatted summary of improvement history."""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text
        from io import StringIO

        if not self.history:
            return "[yellow]No iterations recorded yet.[/yellow]"

        # Create a string buffer to capture Rich output
        string_buffer = StringIO()
        console = Console(file=string_buffer, force_terminal=True, width=100)

        # Calculate summary statistics
        total_attempts = self.get_total_attempts()
        total_improvements = self.get_total_improvements()
        improvement_rate = self.get_improvement_rate()

        # Create summary panel
        summary_text = Text()
        summary_text.append("Total Iterations: ", style="bold cyan")
        summary_text.append(f"{total_attempts}\n", style="white")
        summary_text.append("Successful Improvements: ", style="bold green")
        summary_text.append(f"{total_improvements}\n", style="white")
        summary_text.append("Failed Attempts: ", style="bold red")
        summary_text.append(f"{total_attempts - total_improvements}\n", style="white")
        summary_text.append("Improvement Rate: ", style="bold yellow")
        summary_text.append(f"{improvement_rate:.1%}", style="white")

        # Create detailed table
        table = Table(
            title="Iteration Details",
            show_header=True,
            header_style="bold magenta",
            title_style="bold blue",
        )

        table.add_column("Iter", justify="center", style="cyan", width=6)
        table.add_column("Status", justify="center", width=12)
        table.add_column("Wins (New)", justify="right", style="green", width=11)
        table.add_column("Wins (Old)", justify="right", style="yellow", width=11)
        table.add_column("Ties", justify="right", style="blue", width=6)
        table.add_column("Score (New)", justify="right", width=12)
        table.add_column("Score (Old)", justify="right", width=12)
        table.add_column("Delta", justify="right", width=10)

        for record in self.history:
            is_improved = record["result"] == "improved"
            status_text = "✓ IMPROVED" if is_improved else "✗ NO CHANGE"
            status_style = "bold green" if is_improved else "bold red"

            delta_value = record["weighted_score_delta"]
            delta_style = (
                "green" if delta_value > 0 else "red" if delta_value < 0 else "white"
            )

            table.add_row(
                str(record["iteration"]),
                f"[{status_style}]{status_text}[/{status_style}]",
                str(record["wins_new"]),
                str(record["wins_old"]),
                str(record["ties"]),
                f"{record['weighted_score_new']:.4f}",
                f"{record['weighted_score_old']:.4f}",
                f"[{delta_style}]{delta_value:+.4f}[/{delta_style}]",
            )

        # Print summary panel
        console.print(
            Panel(
                summary_text,
                title="[bold white]Improvement Summary[/bold white]",
                border_style="blue",
                padding=(1, 2),
            )
        )

        console.print()
        console.print(table)

        return string_buffer.getvalue()

    def print_rich(self) -> None:
        """Print Rich-formatted summary directly to console.

        This method prints directly to the console with full Rich formatting,
        as opposed to __repr__/__str__ which return captured string output.
        """
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text

        if not self.history:
            console = Console()
            console.print("[yellow]No iterations recorded yet.[/yellow]")
            return

        console = Console()

        # Calculate summary statistics
        total_attempts = self.get_total_attempts()
        total_improvements = self.get_total_improvements()
        improvement_rate = self.get_improvement_rate()

        # Create summary panel
        summary_text = Text()
        summary_text.append("Total Iterations: ", style="bold cyan")
        summary_text.append(f"{total_attempts}\n", style="white")
        summary_text.append("Successful Improvements: ", style="bold green")
        summary_text.append(f"{total_improvements}\n", style="white")
        summary_text.append("Failed Attempts: ", style="bold red")
        summary_text.append(f"{total_attempts - total_improvements}\n", style="white")
        summary_text.append("Improvement Rate: ", style="bold yellow")
        summary_text.append(f"{improvement_rate:.1%}", style="white")

        # Create detailed table
        table = Table(
            title="Iteration Details",
            show_header=True,
            header_style="bold magenta",
            title_style="bold blue",
        )

        table.add_column("Iter", justify="center", style="cyan", width=6)
        table.add_column("Status", justify="center", width=12)
        table.add_column("Wins (New)", justify="right", style="green", width=11)
        table.add_column("Wins (Old)", justify="right", style="yellow", width=11)
        table.add_column("Ties", justify="right", style="blue", width=6)
        table.add_column("Score (New)", justify="right", width=12)
        table.add_column("Score (Old)", justify="right", width=12)
        table.add_column("Delta", justify="right", width=10)

        for record in self.history:
            is_improved = record["result"] == "improved"
            status_text = "✓ IMPROVED" if is_improved else "✗ NO CHANGE"
            status_style = "bold green" if is_improved else "bold red"

            delta_value = record["weighted_score_delta"]
            delta_style = (
                "green" if delta_value > 0 else "red" if delta_value < 0 else "white"
            )

            table.add_row(
                str(record["iteration"]),
                f"[{status_style}]{status_text}[/{status_style}]",
                str(record["wins_new"]),
                str(record["wins_old"]),
                str(record["ties"]),
                f"{record['weighted_score_new']:.4f}",
                f"{record['weighted_score_old']:.4f}",
                f"[{delta_style}]{delta_value:+.4f}[/{delta_style}]",
            )

        # Print summary panel and table
        console.print()
        console.print(
            Panel(
                summary_text,
                title="[bold white]Improvement Summary[/bold white]",
                border_style="blue",
                padding=(1, 2),
            )
        )
        console.print()
        console.print(table)
        console.print()

    def record_iteration(self, result: "EvaluationResult", iteration: int) -> None:
        """Record the results of an iteration evaluation.

        Args:
            result: The EvaluationResult from the iteration
            iteration: The iteration number
        """
        record = {
            "iteration": iteration,
            "result": "improved" if result.is_improvement else "no_improvement",
            "wins_new": result.wins_candidate,
            "wins_old": result.wins_best,
            "ties": result.ties,
            "weighted_score_new": result.weighted_score_candidate,
            "weighted_score_old": result.weighted_score_best,
            "weighted_score_delta": result.weighted_score_delta,
        }
        self.history.append(record)

    def print_summary(self) -> None:
        """Print a formatted summary of the entire improvement history."""
        if not self.history:
            print("No iterations recorded.")
            return

        print(f"\n{'='*80}")
        print("IMPROVEMENT SUMMARY")
        print(f"{'='*80}\n")

        for record in self.history:
            status = "✓ IMPROVED" if record["result"] == "improved" else "✗ NO CHANGE"
            print(f"Iteration {record['iteration']}: {status}")
            print(
                f"  Wins - New: {record['wins_new']}, Old: {record['wins_old']}, Ties: {record['ties']}"
            )
            print(
                f"  Weighted Score - New: {record['weighted_score_new']:.4f}, Old: {record['weighted_score_old']:.4f}, Delta: {record['weighted_score_delta']:+.4f}"
            )

    def get_total_improvements(self) -> int:
        """Get the total number of successful improvements.

        Returns:
            Count of iterations that resulted in improvements
        """
        return sum(1 for r in self.history if r["result"] == "improved")

    def get_total_attempts(self) -> int:
        """Get the total number of iteration attempts.

        Returns:
            Total count of recorded iterations
        """
        return len(self.history)

    def get_improvement_rate(self) -> float:
        """Get the rate of successful improvements.

        Returns:
            Proportion of iterations that resulted in improvements (0.0 to 1.0)
        """
        total = self.get_total_attempts()
        if total == 0:
            return 0.0
        return self.get_total_improvements() / total

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the complete history as a list of dictionaries.

        Returns:
            List of iteration records
        """
        return self.history.copy()

    def get_latest_record(self) -> Dict[str, Any]:
        """Get the most recent iteration record.

        Returns:
            The latest iteration record

        Raises:
            IndexError: If no iterations have been recorded
        """
        if not self.history:
            raise IndexError("No iterations recorded")
        return self.history[-1].copy()

    def set_comparisons(
        self, first_comparison, best_comparison, agent_name: str = None
    ):
        """Set the first and best comparisons for absolute performance tracking.

        Args:
            first_comparison: ResultPairComparison from the initial iteration
            best_comparison: ResultPairComparison from the best iteration
            agent_name: Optional agent name for display purposes
        """
        self.first_comparison = first_comparison
        self.best_comparison = best_comparison
        self.agent_name = agent_name

    def print_absolute_performance(self):
        """Print a table showing absolute performance improvement by question.

        Compares the first iteration to the best iteration, showing per-question
        and per-metric improvements.

        Requires set_comparisons() to be called first.
        """
        if self.first_comparison is None or self.best_comparison is None:
            print(
                "[yellow]No comparison data available. Call set_comparisons() first.[/yellow]"
            )
            return

        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        console = Console()

        # Extract per-question metrics from both comparisons
        first_metrics = {}
        best_metrics = {}

        for question_name in self.first_comparison.comparison.keys():
            first_answer_comp = self.first_comparison.comparison[question_name]
            best_answer_comp = self.best_comparison.comparison[question_name]

            first_dict = first_answer_comp.to_dict()
            best_dict = best_answer_comp.to_dict()

            first_metrics[question_name] = first_dict
            best_metrics[question_name] = best_dict

        # Create table
        table = Table(
            title="Absolute Performance Improvement: First vs Best Iteration",
            show_header=True,
            header_style="bold magenta",
            title_style="bold blue",
        )

        table.add_column("Question", style="cyan", width=30, no_wrap=False)
        table.add_column("Metric", style="yellow", width=20)
        table.add_column("First", justify="right", width=10)
        table.add_column("Best", justify="right", width=10)
        table.add_column("Delta", justify="right", width=10)
        table.add_column("Change", justify="center", width=8)

        # Collect all unique metric names
        all_metrics = set()
        for metrics_dict in first_metrics.values():
            all_metrics.update(
                k for k, v in metrics_dict.items() if isinstance(v, (int, float))
            )

        # Populate table
        for question_name in sorted(first_metrics.keys()):
            first_q = first_metrics[question_name]
            best_q = best_metrics[question_name]

            # Track if this is the first metric for this question (for row styling)
            first_metric_in_question = True

            for metric_name in sorted(all_metrics):
                if metric_name in first_q and metric_name in best_q:
                    first_val = first_q[metric_name]
                    best_val = best_q[metric_name]

                    if isinstance(first_val, (int, float)) and isinstance(
                        best_val, (int, float)
                    ):
                        delta = best_val - first_val

                        # Determine if this is an improvement
                        # Higher is generally better for similarity metrics
                        if delta > 0.001:
                            change_symbol = "↑"
                            change_style = "green"
                        elif delta < -0.001:
                            change_symbol = "↓"
                            change_style = "red"
                        else:
                            change_symbol = "="
                            change_style = "white"

                        # Format delta with color
                        delta_str = f"[{change_style}]{delta:+.3f}[/{change_style}]"
                        change_str = f"[{change_style}]{change_symbol}[/{change_style}]"

                        # Display question name only on first metric
                        q_display = question_name if first_metric_in_question else ""
                        first_metric_in_question = False

                        table.add_row(
                            q_display,
                            metric_name,
                            f"{first_val:.3f}",
                            f"{best_val:.3f}",
                            delta_str,
                            change_str,
                        )

        # Calculate overall statistics
        all_deltas = []
        for question_name in first_metrics.keys():
            first_q = first_metrics[question_name]
            best_q = best_metrics[question_name]
            for metric_name in all_metrics:
                if metric_name in first_q and metric_name in best_q:
                    first_val = first_q[metric_name]
                    best_val = best_q[metric_name]
                    if isinstance(first_val, (int, float)) and isinstance(
                        best_val, (int, float)
                    ):
                        all_deltas.append(best_val - first_val)

        if all_deltas:
            avg_delta = sum(all_deltas) / len(all_deltas)
            positive_deltas = sum(1 for d in all_deltas if d > 0.001)
            negative_deltas = sum(1 for d in all_deltas if d < -0.001)

            summary_text = (
                f"[cyan]Average Delta:[/cyan] {avg_delta:+.4f}  |  "
                f"[green]Improvements:[/green] {positive_deltas}  |  "
                f"[red]Declines:[/red] {negative_deltas}  |  "
                f"[white]Unchanged:[/white] {len(all_deltas) - positive_deltas - negative_deltas}"
            )
        else:
            summary_text = "[yellow]No numeric metrics to compare[/yellow]"

        console.print()
        console.print(
            Panel(
                summary_text,
                title="[bold white]Overall Summary[/bold white]",
                border_style="blue",
            )
        )
        console.print()
        console.print(table)
        console.print()
