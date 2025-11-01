"""Batch comparison of Results objects by matching agent names.

This module provides the BatchCompare class for comparing two Results objects
by matching their individual Result objects based on agent.name values, then
computing a ResultPairComparison for each matched pair.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Callable
from collections import defaultdict

from .result_pair_comparison import ResultPairComparison
from .factory import ComparisonFactory

if TYPE_CHECKING:
    from edsl import Results
    from edsl.results import Result
    from rich.table import Table
    from rich.console import Console


class BatchCompare:
    """Compare two Results objects by matching Result pairs on agent.name.

    This class takes two Results objects, matches individual Result objects
    where their agent.name values are equal, and computes a ResultPairComparison
    for each matched pair.

    Attributes:
        results_a: The first Results object to compare
        results_b: The second Results object to compare
        comparison_factory: Optional factory for comparison metrics
        comparisons: Dictionary mapping agent names to ResultPairComparison objects
        unmatched_a: List of Result objects from results_a without matches
        unmatched_b: List of Result objects from results_b without matches

    Example:
        >>> from edsl import Results
        >>> from edsl.comparisons import BatchCompare
        >>> # Create two Results objects with named agents
        >>> results_a = Results.example()
        >>> results_b = Results.example()
        >>> # Compare them
        >>> batch = BatchCompare(results_a, results_b)
        >>> # Access comparisons by agent name
        >>> len(batch.comparisons) > 0
        True
    """

    def __init__(
        self,
        results_a: "Results",
        results_b: "Results",
        comparison_factory: Optional[ComparisonFactory] = None,
    ):
        """Initialize a BatchCompare instance.

        Args:
            results_a: The first Results object to compare
            results_b: The second Results object to compare
            comparison_factory: Optional ComparisonFactory for custom metrics.
                If None, uses default factory.
        """
        self.results_a = results_a
        self.results_b = results_b
        self.comparison_factory = (
            comparison_factory or ComparisonFactory.with_defaults()
        )

        # Storage for comparisons and unmatched results
        self.comparisons: Dict[str, ResultPairComparison] = {}
        self.unmatched_a: List["Result"] = []
        self.unmatched_b: List["Result"] = []

        # Perform the matching and comparison
        self._match_and_compare()

    def _match_and_compare(self) -> None:
        """Match Result objects by agent.name and create comparisons.

        This internal method:
        1. Groups Result objects from both Results by agent.name
        2. For matching names, creates ResultPairComparison objects
        3. Tracks unmatched Result objects
        """
        # Group results by agent.name
        results_a_by_name: Dict[str, List["Result"]] = defaultdict(list)
        results_b_by_name: Dict[str, List["Result"]] = defaultdict(list)

        # Index results from A
        for result in self.results_a:
            agent_name = result.agent.name
            results_a_by_name[agent_name].append(result)

        # Index results from B
        for result in self.results_b:
            agent_name = result.agent.name
            results_b_by_name[agent_name].append(result)

        # Find all agent names
        names_a = set(results_a_by_name.keys())
        names_b = set(results_b_by_name.keys())

        # Match and compare
        matched_names = names_a & names_b

        for name in matched_names:
            results_list_a = results_a_by_name[name]
            results_list_b = results_b_by_name[name]

            # Create comparisons for all pairs with this name
            # If there are multiple results per agent name, we pair them in order
            for i in range(max(len(results_list_a), len(results_list_b))):
                result_a = results_list_a[i] if i < len(results_list_a) else None
                result_b = results_list_b[i] if i < len(results_list_b) else None

                # Only create comparison if both exist
                if result_a is not None and result_b is not None:
                    # Create a unique key for this comparison
                    key = (
                        f"{name}_{i}"
                        if len(results_list_a) > 1 or len(results_list_b) > 1
                        else str(name)
                    )

                    comparison = ResultPairComparison(
                        result_A=result_a,
                        result_B=result_b,
                        comparison_factory=self.comparison_factory,
                    )
                    self.comparisons[key] = comparison
                else:
                    # Track unmatched
                    if result_a is not None:
                        self.unmatched_a.append(result_a)
                    if result_b is not None:
                        self.unmatched_b.append(result_b)

        # Track completely unmatched names
        unmatched_names_a = names_a - matched_names
        unmatched_names_b = names_b - matched_names

        for name in unmatched_names_a:
            self.unmatched_a.extend(results_a_by_name[name])

        for name in unmatched_names_b:
            self.unmatched_b.extend(results_b_by_name[name])

    def get_comparison(self, agent_name: str) -> Optional[ResultPairComparison]:
        """Get the ResultPairComparison for a specific agent name.

        Args:
            agent_name: The agent name to look up

        Returns:
            ResultPairComparison if found, None otherwise

        Example:
            >>> from edsl import Results, Agent
            >>> from edsl.comparisons import BatchCompare
            >>> # Create results with named agents
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> # Get specific comparison (if agents were named)
            >>> # comparison = batch.get_comparison("alice")
        """
        return self.comparisons.get(agent_name)

    def summary(self) -> Dict[str, Any]:
        """Get a summary of the batch comparison.

        Returns:
            Dictionary with counts of matched and unmatched results

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> summary = batch.summary()
            >>> 'total_comparisons' in summary
            True
            >>> 'unmatched_in_a' in summary
            True
        """
        return {
            "total_comparisons": len(self.comparisons),
            "unmatched_in_a": len(self.unmatched_a),
            "unmatched_in_b": len(self.unmatched_b),
            "total_in_a": len(self.results_a),
            "total_in_b": len(self.results_b),
            "matched_agent_names": list(self.comparisons.keys()),
        }

    def print_summary(self) -> None:
        """Print a formatted summary of the batch comparison.

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> batch.print_summary()
            Batch Comparison Summary
            ========================
            Total in Results A: ...
            Total in Results B: ...
            <BLANKLINE>
            Matched comparisons: ...
            Unmatched in A: ...
            Unmatched in B: ...
        """
        summary = self.summary()
        print("Batch Comparison Summary")
        print("=" * 24)
        print(f"Total in Results A: {summary['total_in_a']}")
        print(f"Total in Results B: {summary['total_in_b']}")
        print()
        print(f"Matched comparisons: {summary['total_comparisons']}")
        print(f"Unmatched in A: {summary['unmatched_in_a']}")
        print(f"Unmatched in B: {summary['unmatched_in_b']}")

        if summary["matched_agent_names"]:
            print()
            print("Matched agent names:")
            for name in summary["matched_agent_names"]:
                print(f"  - {name}")

    def __len__(self) -> int:
        """Return the number of comparisons."""
        return len(self.comparisons)

    def __getitem__(self, agent_name: str) -> ResultPairComparison:
        """Access a comparison by agent name using bracket notation.

        Args:
            agent_name: The agent name to look up

        Returns:
            The ResultPairComparison for that agent

        Raises:
            KeyError: If the agent name is not found
        """
        return self.comparisons[agent_name]

    def __iter__(self):
        """Iterate over (agent_name, comparison) pairs."""
        return iter(self.comparisons.items())

    def __repr__(self) -> str:
        """Return a string representation of the BatchCompare object."""
        return (
            f"BatchCompare("
            f"comparisons={len(self.comparisons)}, "
            f"unmatched_a={len(self.unmatched_a)}, "
            f"unmatched_b={len(self.unmatched_b)})"
        )

    def aggregate_metrics(
        self, agg_func: Optional[Callable[[List[float]], float]] = None
    ) -> Dict[str, float]:
        """Compute aggregated metrics across all comparisons.

        For each metric, aggregates the values across all agent pairs and all questions.

        Args:
            agg_func: Function to aggregate metric values. If None, uses mean.
                Common options: mean, median, min, max, etc.

        Returns:
            Dictionary mapping metric names to aggregated values

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> metrics = batch.aggregate_metrics()
            >>> 'exact_match' in metrics
            True
        """
        if agg_func is None:
            # Default to mean
            def agg_func(values):
                return sum(values) / len(values) if values else 0.0

        metric_names = [str(fn) for fn in self.comparison_factory.comparison_fns]
        aggregated = {}

        for metric_name in metric_names:
            all_values = []

            for agent_name, comparison in self.comparisons.items():
                comp_result = comparison.compare()

                for question_name, answer_comp in comp_result.items():
                    value = answer_comp[metric_name]

                    # Convert to numeric
                    if value is None:
                        continue
                    elif isinstance(value, bool):
                        value = 1.0 if value else 0.0
                    else:
                        try:
                            value = float(value)
                        except (TypeError, ValueError):
                            continue

                    all_values.append(value)

            if all_values:
                aggregated[metric_name] = agg_func(all_values)
            else:
                aggregated[metric_name] = None

        return aggregated

    def to_table(
        self, title: Optional[str] = None, show_questions: bool = False
    ) -> "Table":
        """Create a Rich table showing metrics for each agent pair.

        Creates a table with one row per agent pair, showing aggregated
        comparison metrics across all questions for that pair.

        Args:
            title: Optional title for the table
            show_questions: If True, creates a detailed table with one row
                per (agent, question) pair. If False (default), shows aggregated
                metrics per agent.

        Returns:
            Rich Table object ready for display

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> table = batch.to_table()
            >>> table is not None
            True
        """
        from rich.table import Table

        if title is None:
            title = f"Batch Comparison ({len(self.comparisons)} pairs)"

        metric_names = [str(fn) for fn in self.comparison_factory.comparison_fns]

        if show_questions:
            # Detailed view: one row per (agent, question)
            table = Table(title=title, show_header=True, header_style="bold magenta")
            table.add_column("Agent", style="cyan", no_wrap=True)
            table.add_column("Question", style="yellow")

            for metric_name in metric_names:
                pretty_name = metric_name.replace("_", " ").title()
                table.add_column(pretty_name, justify="right")

            for agent_name, comparison in sorted(self.comparisons.items()):
                comp_result = comparison.compare()

                for question_name, answer_comp in comp_result.items():
                    row = [str(agent_name), str(question_name)]

                    for metric_name in metric_names:
                        value = answer_comp[metric_name]

                        if value is None:
                            formatted = "N/A"
                        elif isinstance(value, bool):
                            formatted = "✓" if value else "✗"
                        elif isinstance(value, float):
                            formatted = f"{value:.3f}"
                        else:
                            formatted = str(value)

                        row.append(formatted)

                    table.add_row(*row)
        else:
            # Summary view: one row per agent with aggregated metrics
            table = Table(title=title, show_header=True, header_style="bold magenta")
            table.add_column("Agent", style="cyan", no_wrap=True)
            table.add_column("Questions", justify="right", style="dim")

            for metric_name in metric_names:
                pretty_name = metric_name.replace("_", " ").title()
                table.add_column(pretty_name, justify="right")

            for agent_name, comparison in sorted(self.comparisons.items()):
                comp_result = comparison.compare()
                num_questions = len(comp_result)

                row = [str(agent_name), str(num_questions)]

                # Aggregate metrics for this agent across all questions
                for metric_name in metric_names:
                    values = []

                    for question_name, answer_comp in comp_result.items():
                        value = answer_comp[metric_name]

                        if value is None:
                            continue
                        elif isinstance(value, bool):
                            value = 1.0 if value else 0.0
                        else:
                            try:
                                value = float(value)
                            except (TypeError, ValueError):
                                continue

                        values.append(value)

                    if values:
                        avg_value = sum(values) / len(values)
                        formatted = f"{avg_value:.3f}"
                    else:
                        formatted = "N/A"

                    row.append(formatted)

                table.add_row(*row)

        return table

    def print_table(
        self, console: Optional["Console"] = None, show_questions: bool = False
    ) -> None:
        """Print a Rich table showing metrics for each agent pair.

        Args:
            console: Optional Rich Console instance. If None, creates a new one.
            show_questions: If True, shows detailed table with one row per
                (agent, question) pair. If False (default), shows aggregated
                metrics per agent.

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> batch.print_table()  # doctest: +SKIP
        """
        from rich.console import Console

        if console is None:
            console = Console()

        console.print(self.to_table(show_questions=show_questions))

    def to_scenario_list(self) -> "Any":
        """Convert the batch comparison to a ScenarioList.

        Creates a ScenarioList where each row represents a (agent, question)
        comparison with all metrics and a codebook.

        Returns:
            ScenarioList with comparison data and codebook

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> sl = batch.to_scenario_list()
            >>> len(sl) > 0
            True
        """
        from edsl.scenarios import Scenario, ScenarioList

        metric_names = [str(fn) for fn in self.comparison_factory.comparison_fns]

        scenarios = []
        codebook = {
            "agent_name": "Agent Name",
            "question": "Question Name",
            "question_text": "Question Text",
            "answer_a": "Answer A",
            "answer_b": "Answer B",
            "question_type": "Question Type",
        }

        # Add metric names to codebook
        for metric_name in metric_names:
            pretty_name = metric_name.replace("_", " ").title()
            codebook[metric_name] = pretty_name

        # Build rows
        for agent_name, comparison in self.comparisons.items():
            comp_result = comparison.compare()

            for question_name, answer_comp in comp_result.items():
                row = {
                    "agent_name": str(agent_name),
                    "question": str(question_name),
                    "question_text": answer_comp["question_text"],
                    "answer_a": answer_comp.answer_a,
                    "answer_b": answer_comp.answer_b,
                    "question_type": answer_comp["question_type"],
                }

                # Add metrics
                for metric_name in metric_names:
                    value = answer_comp[metric_name]
                    if isinstance(value, (int, float)):
                        row[metric_name] = value
                    else:
                        row[metric_name] = str(value) if value is not None else None

                scenarios.append(Scenario(row))

        return ScenarioList(scenarios, codebook=codebook)

    def to_dataset(self) -> "Any":
        """Convert the batch comparison to a Dataset.

        Convenience method that converts to ScenarioList then to Dataset.

        Returns:
            Dataset with comparison data

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> ds = batch.to_dataset()
            >>> len(ds) > 0
            True
        """
        return self.to_scenario_list().to_dataset()

    def pareto_tally(
        self,
        expected_answers: Optional[Dict[str, Any]] = None,
        scorer: Optional[Callable] = None,
        threshold: float = 0.01,
    ) -> Dict[str, Dict[str, int]]:
        """Compute Pareto tally showing wins/ties/losses for each agent.

        For each agent, tallies how many questions where:
        - Result A is better than Result B (+1 / A wins)
        - Results are tied (0 / ties)
        - Result B is better than Result A (-1 / B wins)

        Three modes of operation:

        1. With expected_answers: Compares each result to expected answers using
           exact_match metric. Result closer to expected wins.

        2. With scorer: Uses custom scoring function scorer(answer) -> float.
           Higher score wins.

        3. Default: Uses exact_match metric. If answers match, it's a tie.
           If they differ, both are counted as needing review (shown separately).

        Args:
            expected_answers: Optional dict mapping question names to expected answers.
                If provided, determines winner by comparing to these answers.
            scorer: Optional scoring function that takes an answer and returns a numeric
                score. Higher scores are better. Function signature: scorer(answer) -> float
            threshold: Threshold for determining ties when using scorer. If score
                difference is less than threshold, it's a tie. Default: 0.01

        Returns:
            Dictionary mapping agent names to tally dicts with keys:
            - 'A_wins': Count where A > B
            - 'ties': Count where A == B
            - 'B_wins': Count where B > A
            - 'different': Count where A != B but can't determine winner (default mode only)
            - 'total': Total questions compared

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> tallies = batch.pareto_tally()
            >>> all(key in tallies for key in batch.comparisons.keys())
            True
        """
        tallies = {}

        for agent_name, comparison in self.comparisons.items():
            comp_result = comparison.compare()

            a_wins = 0
            b_wins = 0
            ties = 0
            different = 0  # For cases where we can't determine winner

            for question_name, answer_comp in comp_result.items():
                answer_a = answer_comp.answer_a
                answer_b = answer_comp.answer_b

                if expected_answers is not None:
                    # Mode 1: Compare to expected answers
                    if question_name in expected_answers:
                        expected = expected_answers[question_name]

                        a_correct = answer_a == expected
                        b_correct = answer_b == expected

                        if a_correct and b_correct:
                            ties += 1
                        elif a_correct:
                            a_wins += 1
                        elif b_correct:
                            b_wins += 1
                        else:
                            # Neither correct - tie
                            ties += 1
                    else:
                        # No expected answer for this question
                        ties += 1

                elif scorer is not None:
                    # Mode 2: Use custom scorer
                    try:
                        score_a = float(scorer(answer_a))
                        score_b = float(scorer(answer_b))

                        diff = score_a - score_b

                        if abs(diff) < threshold:
                            ties += 1
                        elif diff > 0:
                            a_wins += 1
                        else:
                            b_wins += 1
                    except Exception:
                        # Scoring failed, count as tie
                        ties += 1

                else:
                    # Mode 3: Default - just check if they're the same
                    exact_match = answer_comp["exact_match"]

                    if exact_match:
                        ties += 1
                    else:
                        # They're different but we can't say which is better
                        different += 1

            tallies[agent_name] = {
                "A_wins": a_wins,
                "ties": ties,
                "B_wins": b_wins,
                "different": different,
                "total": a_wins + ties + b_wins + different,
            }

        return tallies

    def print_pareto_tally(
        self,
        expected_answers: Optional[Dict[str, Any]] = None,
        scorer: Optional[Callable] = None,
        threshold: float = 0.01,
        console: Optional["Console"] = None,
    ) -> None:
        """Print a table showing Pareto tally (wins/ties/losses) for each agent.

        Creates a table where:
        - Rows are agents
        - Columns show counts for: A wins (+1), Ties (0), B wins (-1), and Different (?)

        Args:
            expected_answers: Optional dict of expected answers to compare against.
            scorer: Optional scoring function to evaluate answer quality.
            threshold: Threshold for determining ties when using scorer.
            console: Optional Rich Console instance. If None, creates a new one.

        Example:
            >>> from edsl import Results
            >>> from edsl.comparisons import BatchCompare
            >>> results_a = Results.example()
            >>> results_b = Results.example()
            >>> batch = BatchCompare(results_a, results_b)
            >>> batch.print_pareto_tally()  # doctest: +SKIP
        """
        from rich.console import Console
        from rich.table import Table

        if console is None:
            console = Console()

        tallies = self.pareto_tally(expected_answers, scorer, threshold)

        table = Table(
            title="Pareto Tally: Result Comparisons by Agent",
            show_header=True,
            header_style="bold magenta",
        )

        table.add_column("Agent", style="cyan", no_wrap=True)
        table.add_column("A Wins (+1)", justify="center", style="green")
        table.add_column("Ties (0)", justify="center", style="yellow")
        table.add_column("B Wins (-1)", justify="center", style="red")

        # Only show "Different" column if we're in default mode (no scorer/expected)
        show_different = expected_answers is None and scorer is None
        if show_different:
            table.add_column("Different (?)", justify="center", style="blue")

        table.add_column("Total", justify="center", style="dim")

        for agent_name in sorted(tallies.keys()):
            tally = tallies[agent_name]
            row = [
                str(agent_name),
                str(tally["A_wins"]),
                str(tally["ties"]),
                str(tally["B_wins"]),
            ]

            if show_different:
                row.append(str(tally["different"]))

            row.append(str(tally["total"]))

            table.add_row(*row)

        console.print(table)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
