from __future__ import annotations

"""Compare two candidate results against a shared gold standard."""

from typing import Any, TYPE_CHECKING
from collections import defaultdict

if TYPE_CHECKING:
    from edsl.scenarios import ScenarioList
    from .result_pair_comparison import ResultPairComparison


class CompareCandidates:
    """Compare two candidate results against a shared gold standard.

    Takes two ResultPairComparison objects where result_B (the gold standard)
    should be identical in both. Produces a ScenarioList showing which
    candidate performs better on each metric for each question.
    """

    def __init__(
        self,
        results_comparison_a: "ResultPairComparison",
        results_comparison_b: "ResultPairComparison",
    ):
        """Initialize with two ResultPairComparison objects.

        Args:
            results_comparison_a: First comparison (candidate_1 vs gold standard)
            results_comparison_b: Second comparison (candidate_2 vs gold standard)

        Note:
            The result_B in both comparisons should be the same (gold standard).
        """
        self.results_comparison_a = results_comparison_a
        self.results_comparison_b = results_comparison_b

        self._comparison = self._compare()

    def __repr__(self) -> str:
        return CompareCandidatesRich(self._comparison).to_string()

    @classmethod
    def example(cls) -> "CompareCandidates":
        """Create an example CompareCandidates object.

        Returns:
            CompareCandidates object
        """
        from .result_pair_comparison import ResultPairComparison

        return cls(
            ResultPairComparison.example(first_index=0, second_index=3),
            ResultPairComparison.example(first_index=1, second_index=3),
        )

    def compare(self) -> "ScenarioList":
        """Compare the two candidates and return a ScenarioList with performance data.

        Returns:
            ScenarioList with columns:
            - question_name: Name of the question
            - question_text: Text of the question
            - question_type: Type of the question
            - question_options: Available options for the question
            - candidate_answer_1: Answer from first candidate
            - candidate_answer_2: Answer from second candidate
            - actual_answer: The gold standard answer
            - metric_name: Name of the metric being compared
            - candidate_metric_value_1: Metric value for first candidate
            - candidate_metric_value_2: Metric value for second candidate
            - winner: Which candidate performed better ('candidate_1', 'candidate_2', or 'tie')
        """
        if self._comparison is None:
            self._comparison = self._compare()
        return self._comparison

    def _compare(self) -> "ScenarioList":
        """Compare the two candidates and return a ScenarioList with performance data.

        Returns:
            ScenarioList with columns:
            - question_name: Name of the question
            - metric_name: Name of the metric being compared
            - candidate_answer_1: Answer from first candidate
            - candidate_answer_2: Answer from second candidate
            - candidate_metric_value_1: Metric value for first candidate
            - candidate_metric_value_2: Metric value for second candidate
            - actual_answer: The gold standard answer
            - winner: Which candidate performed better ('candidate_1', 'candidate_2', or 'tie')

        Examples:
            >>> from edsl.comparisons import ResultPairComparison, CompareCandidates
            >>> rc1 = ResultPairComparison.example()
            >>> rc2 = ResultPairComparison.example()
            >>> cc = CompareCandidates(rc1, rc2)
            >>> sl = cc.compare()
            >>> len(sl) > 0
            True
        """
        from edsl.scenarios import Scenario, ScenarioList

        # Get comparisons from both
        comp_a = self.results_comparison_a.comparison
        comp_b = self.results_comparison_b.comparison

        # Get metric names
        metric_names = [
            str(fn)
            for fn in self.results_comparison_a.comparison_factory.comparison_fns
        ]

        # Build scenarios
        scenarios = []

        # Get the gold standard answer (result_B, which should be the same in both)
        for question_name in comp_a.keys():
            if question_name not in comp_b:
                continue

            metrics_a = comp_a[question_name]
            metrics_b = comp_b[question_name]

            # Get the actual answer (from result_B, the gold standard)
            actual_answer = metrics_a.answer_b  # result_B is the gold standard

            # Get candidate answers
            candidate_answer_1 = metrics_a.answer_a  # result_A from first comparison
            candidate_answer_2 = metrics_b.answer_a  # result_A from second comparison

            # Get question metadata
            question_text = getattr(metrics_a, "question_text", "")
            question_type = getattr(metrics_a, "question_type", "")
            question_options = getattr(metrics_a, "question_options", "")

            # For each metric, create a row
            for metric_name in metric_names:
                value_1 = metrics_a[metric_name]
                value_2 = metrics_b[metric_name]

                # Determine winner (higher is better for similarity metrics)
                winner = self._determine_winner(value_1, value_2)

                row = {
                    "question_name": str(question_name),
                    "question_text": question_text,
                    "question_type": question_type,
                    "question_options": question_options,
                    "candidate_answer_1": candidate_answer_1,
                    "candidate_answer_2": candidate_answer_2,
                    "actual_answer": actual_answer,
                    "winner": winner,
                    "metric_name": metric_name,
                    "candidate_metric_value_1": value_1,
                    "candidate_metric_value_2": value_2,
                }

                scenarios.append(Scenario(row))

        return ScenarioList(scenarios)

    def _determine_winner(
        self, value_1: Any, value_2: Any, tie_threshold: float = 0.001
    ) -> str:
        """Determine which candidate has the better metric value.

        Args:
            value_1: Metric value for candidate 1
            value_2: Metric value for candidate 2
            tie_threshold: Values within this threshold are considered tied

        Returns:
            'candidate_1', 'candidate_2', or 'tie'
        """
        # Handle None values
        if value_1 is None and value_2 is None:
            return "tie"
        if value_1 is None:
            return "candidate_2"
        if value_2 is None:
            return "candidate_1"

        # Convert booleans to numeric
        if isinstance(value_1, bool):
            value_1 = 1.0 if value_1 else 0.0
        if isinstance(value_2, bool):
            value_2 = 1.0 if value_2 else 0.0

        # Try to convert to float for comparison
        try:
            v1 = float(value_1)
            v2 = float(value_2)

            # Check if within tie threshold
            if abs(v1 - v2) <= tie_threshold:
                return "tie"

            # Higher is better for similarity metrics
            return "candidate_1" if v1 > v2 else "candidate_2"
        except (TypeError, ValueError):
            # If we can't convert to numeric, check for equality
            return "tie" if value_1 == value_2 else "candidate_1"


class CompareCandidatesRich:
    """Create rich table representations of candidate comparisons.

    Takes the output from CompareCandidates.compare() and formats it as
    stacked rich tables, one per question, with metrics as rows.
    """

    def __init__(self, scenario_list: "ScenarioList"):
        """Initialize with a ScenarioList from CompareCandidates.compare().

        Args:
            scenario_list: Output from CompareCandidates.compare()
        """
        self.scenario_list = scenario_list

    @classmethod
    def example(cls) -> "CompareCandidatesRich":
        """Create an example CompareCandidatesRich object.

        Returns:
            CompareCandidatesRich object
        """
        from .compare_candidates import CompareCandidates

        return cls(CompareCandidates.example().compare())

    def to_string(self) -> str:
        """Return the comparison as a string with rich formatting.

        Returns:
            Formatted string representation of the comparison
        """
        from io import StringIO
        from rich.console import Console

        string_io = StringIO()
        console = Console(file=string_io, force_terminal=True, width=120)
        self._render_to_console(console)
        return string_io.getvalue()

    def display(self) -> None:
        """Display the comparison as rich tables grouped by question."""
        from rich.console import Console

        console = Console()
        self._render_to_console(console)

    def _render_to_console(self, console) -> None:
        """Render the comparison to the given console.

        Args:
            console: Rich Console object to render to
        """
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text

        # Group scenarios by question_name
        questions = defaultdict(list)
        for scenario in self.scenario_list:
            questions[scenario["question_name"]].append(scenario)

        # Track Pareto winners for summary
        pareto_summary = {}

        # Create a table for each question
        for question_name, scenarios in questions.items():
            # Get the answers (same across all metrics for this question)
            first_scenario = scenarios[0]
            candidate_answer_1 = str(first_scenario["candidate_answer_1"])
            candidate_answer_2 = str(first_scenario["candidate_answer_2"])
            actual_answer = str(first_scenario["actual_answer"])

            # Get question metadata
            question_text = str(first_scenario.get("question_text", ""))
            question_type = str(first_scenario.get("question_type", ""))
            question_options = str(first_scenario.get("question_options", ""))

            # Create metadata table
            metadata_table = Table(
                show_header=False,
                box=None,
                padding=(0, 1),
            )
            metadata_table.add_column("Field", style="dim italic")
            metadata_table.add_column("Value", no_wrap=False)

            if question_text:
                metadata_table.add_row("Question Text:", question_text)
            if question_type:
                metadata_table.add_row("Question Type:", question_type)
            if question_options:
                metadata_table.add_row("Options:", question_options)

            # Create answers table
            answers_table = Table(
                show_header=True,
                header_style="bold magenta",
                box=None,
                padding=(0, 2),
            )
            answers_table.add_column("Candidate 1 Answer", no_wrap=False)
            answers_table.add_column("Candidate 2 Answer", no_wrap=False)
            answers_table.add_column("Gold Standard", style="green", no_wrap=False)
            answers_table.add_row(
                candidate_answer_1,
                candidate_answer_2,
                Text(actual_answer, style="green"),
            )

            # Create metrics table
            metrics_table = Table(
                show_header=True,
                header_style="bold magenta",
            )
            metrics_table.add_column("Metric", style="cyan", no_wrap=True)
            metrics_table.add_column("Candidate 1 Value", justify="right")
            metrics_table.add_column("Candidate 2 Value", justify="right")
            metrics_table.add_column("Winner", justify="center")

            # Determine Pareto winner for this question
            winners = [scenario["winner"] for scenario in scenarios]
            candidate_1_wins = winners.count("candidate_1")
            candidate_2_wins = winners.count("candidate_2")
            ties = winners.count("tie")

            if ties == len(winners):
                pareto_winner = "Tie"
            elif candidate_1_wins > 0 and candidate_2_wins == 0:
                pareto_winner = "Candidate 1"
            elif candidate_2_wins > 0 and candidate_1_wins == 0:
                pareto_winner = "Candidate 2"
            else:
                pareto_winner = "Mixed"

            pareto_summary[question_name] = pareto_winner

            # Add rows for each metric
            for scenario in scenarios:
                metric_name = scenario["metric_name"]
                value_1 = scenario["candidate_metric_value_1"]
                value_2 = scenario["candidate_metric_value_2"]
                winner = scenario["winner"]

                # Format metric values with winner highlighting
                if winner == "candidate_1":
                    value_1_text = Text(
                        f"{value_1:.4f}"
                        if isinstance(value_1, float)
                        else str(value_1),
                        style="blue",
                    )
                    value_2_text = Text(
                        f"{value_2:.4f}" if isinstance(value_2, float) else str(value_2)
                    )
                elif winner == "candidate_2":
                    value_1_text = Text(
                        f"{value_1:.4f}" if isinstance(value_1, float) else str(value_1)
                    )
                    value_2_text = Text(
                        f"{value_2:.4f}"
                        if isinstance(value_2, float)
                        else str(value_2),
                        style="blue",
                    )
                else:  # tie
                    value_1_text = Text(
                        f"{value_1:.4f}" if isinstance(value_1, float) else str(value_1)
                    )
                    value_2_text = Text(
                        f"{value_2:.4f}" if isinstance(value_2, float) else str(value_2)
                    )

                metrics_table.add_row(
                    metric_name,
                    value_1_text,
                    value_2_text,
                    winner.replace("_", " ").title(),
                )

            # Combine tables vertically
            from rich.console import Group

            combined = Group(
                Text(f"Question: {question_name}", style="bold cyan", justify="center"),
                Text(""),  # Spacing
                metadata_table,
                Text(""),  # Spacing
                answers_table,
                Text(""),  # Spacing
                metrics_table,
            )

            # Display in a panel
            panel = Panel(combined, expand=False, border_style="bright_blue")
            console.print(panel)
            console.print()  # Add spacing between questions

        # Display summary table
        self._render_summary_table(console, pareto_summary)

    def _render_summary_table(self, console, pareto_summary: dict) -> None:
        """Render a summary table showing Pareto winners for each question.

        Args:
            console: Rich Console object to render to
            pareto_summary: Dictionary mapping question names to Pareto winner status
        """
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text

        # Create summary table
        summary_table = Table(
            title="Summary: Pareto Winners by Question",
            show_header=True,
            header_style="bold magenta",
        )
        summary_table.add_column("Question", style="cyan", no_wrap=False)
        summary_table.add_column("Pareto Winner", justify="center")

        # Add rows for each question
        for question_name, pareto_winner in pareto_summary.items():
            # Style the winner text
            if pareto_winner == "Candidate 1":
                winner_text = Text(pareto_winner, style="blue bold")
            elif pareto_winner == "Candidate 2":
                winner_text = Text(pareto_winner, style="blue bold")
            elif pareto_winner == "Tie":
                winner_text = Text(pareto_winner, style="dim")
            else:  # Mixed
                winner_text = Text(pareto_winner, style="yellow")

            summary_table.add_row(question_name, winner_text)

        # Display in a panel
        panel = Panel(summary_table, expand=False, border_style="green")
        console.print(panel)


if __name__ == "__main__":
    import doctest

    doctest.testmod(verbose=True)
