"""Compare answer distributions between two QuestionAnalysis objects.

This module provides the AnswersCompare class for computing various distance
metrics between answer distributions from different survey populations.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Any, Callable
from collections import Counter
import numpy as np

if TYPE_CHECKING:
    from ..reports.report import QuestionAnalysis


class AnswersCompare:
    """Compare answer distributions between two QuestionAnalysis objects.

    This class takes two QuestionAnalysis instances and provides methods to compute
    various statistical distance metrics between their answer distributions. This is
    useful for comparing survey responses across different populations, time periods,
    or experimental conditions.

    Attributes:
        qa1: First QuestionAnalysis object
        qa2: Second QuestionAnalysis object
        question_name: Name of the question being compared

    Examples:
        Compare two survey populations:

        >>> from edsl import Results
        >>> from edsl.comparisons import AnswersCompare
        >>> results1 = Results.from_survey_population1()
        >>> results2 = Results.from_survey_population2()
        >>> qa1 = results1.analyze('satisfaction')
        >>> qa2 = results2.analyze('satisfaction')
        >>> compare = AnswersCompare(qa1, qa2)
        >>> compare.kl_divergence()
        0.234
        >>> compare.jensen_shannon_divergence()
        0.145
        >>> compare.hellinger_distance()
        0.289

        Get all metrics at once:

        >>> metrics = compare.all_metrics()
        >>> print(metrics)
        {
            'kl_divergence': 0.234,
            'kl_divergence_reverse': 0.198,
            'jensen_shannon_divergence': 0.145,
            'hellinger_distance': 0.289,
            'total_variation_distance': 0.156,
            'chi_squared': 12.45
        }

        Compare with custom metric:

        >>> def custom_distance(p, q):
        ...     return sum(abs(p[k] - q[k]) for k in p.keys())
        >>> compare.custom_metric(custom_distance)
        0.312
    """

    def __init__(self, qa1: "QuestionAnalysis", qa2: "QuestionAnalysis"):
        """Initialize with two QuestionAnalysis objects.

        Args:
            qa1: First QuestionAnalysis object
            qa2: Second QuestionAnalysis object

        Raises:
            TypeError: If inputs are not QuestionAnalysis objects
            ValueError: If question names don't match or multiple questions are analyzed
        """
        from ..reports.report import QuestionAnalysis

        if not isinstance(qa1, QuestionAnalysis):
            raise TypeError(f"qa1 must be QuestionAnalysis, got {type(qa1)}")
        if not isinstance(qa2, QuestionAnalysis):
            raise TypeError(f"qa2 must be QuestionAnalysis, got {type(qa2)}")

        if qa1._question_names != qa2._question_names:
            raise ValueError(
                f"Question names must match. Got {qa1._question_names} and {qa2._question_names}"
            )

        if len(qa1._question_names) != 1:
            raise ValueError("Only single-question analysis supported for comparison")

        self.qa1 = qa1
        self.qa2 = qa2
        self.question_name = qa1._question_names[0]

        # Cache distributions
        self._dist1 = None
        self._dist2 = None

    def _get_distributions(self, smoothing: float = 1e-10) -> tuple[Dict[Any, float], Dict[Any, float]]:
        """Get probability distributions for both question analyses.

        Args:
            smoothing: Small value to add to zero probabilities

        Returns:
            Tuple of (dist1, dist2) where each is a dict mapping values to probabilities
        """
        if self._dist1 is not None and self._dist2 is not None:
            return self._dist1, self._dist2

        # Get answers from both analyses
        answers1 = self.qa1._report.results.get_answers(self.question_name)
        answers2 = self.qa2._report.results.get_answers(self.question_name)

        valid_answers1 = [a for a in answers1 if a is not None]
        valid_answers2 = [a for a in answers2 if a is not None]

        if not valid_answers1:
            raise ValueError("No valid answers in first QuestionAnalysis")
        if not valid_answers2:
            raise ValueError("No valid answers in second QuestionAnalysis")

        # Get question to determine all possible values
        question = self.qa1._report.results.survey.get(self.question_name)

        # Get all possible values
        if hasattr(question, 'question_options') and question.question_options:
            all_values = list(question.question_options)
        else:
            # Use union of observed values
            all_values = list(set(valid_answers1) | set(valid_answers2))

        # Count frequencies
        counts1 = Counter(valid_answers1)
        counts2 = Counter(valid_answers2)
        total1 = len(valid_answers1)
        total2 = len(valid_answers2)

        # Compute probability distributions with smoothing
        dist1 = {}
        dist2 = {}
        for value in all_values:
            count1 = counts1.get(value, 0)
            count2 = counts2.get(value, 0)
            dist1[value] = (count1 + smoothing) / (total1 + smoothing * len(all_values))
            dist2[value] = (count2 + smoothing) / (total2 + smoothing * len(all_values))

        # Renormalize to ensure they sum to 1
        sum1 = sum(dist1.values())
        sum2 = sum(dist2.values())
        dist1 = {k: v/sum1 for k, v in dist1.items()}
        dist2 = {k: v/sum2 for k, v in dist2.items()}

        # Cache for reuse
        self._dist1 = dist1
        self._dist2 = dist2

        return dist1, dist2

    def kl_divergence(self, reverse: bool = False) -> float:
        """Compute Kullback-Leibler divergence.

        KL divergence measures how one distribution differs from another.
        It is asymmetric: D_KL(P||Q) ≠ D_KL(Q||P).

        Args:
            reverse: If True, compute D_KL(Q||P) instead of D_KL(P||Q)

        Returns:
            KL divergence value (0 = identical, higher = more different)

        Examples:
            >>> compare = AnswersCompare(qa1, qa2)
            >>> compare.kl_divergence()  # D_KL(qa1||qa2)
            0.234
            >>> compare.kl_divergence(reverse=True)  # D_KL(qa2||qa1)
            0.198
        """
        dist1, dist2 = self._get_distributions()

        if reverse:
            dist1, dist2 = dist2, dist1

        kl_div = 0.0
        for key in dist1.keys():
            p_val = dist1[key]
            q_val = dist2[key]
            if p_val > 0:
                kl_div += p_val * np.log(p_val / q_val)

        return float(kl_div)

    def jensen_shannon_divergence(self) -> float:
        """Compute Jensen-Shannon divergence.

        JS divergence is a symmetrized and smoothed version of KL divergence.
        It is bounded between 0 and log(2) ≈ 0.693.

        Returns:
            JS divergence value (0 = identical, 0.693 = maximally different)

        Examples:
            >>> compare = AnswersCompare(qa1, qa2)
            >>> compare.jensen_shannon_divergence()
            0.145
        """
        dist1, dist2 = self._get_distributions()

        # Compute average distribution
        m_dist = {k: (dist1[k] + dist2[k]) / 2 for k in dist1.keys()}

        # JS divergence is average of two KL divergences
        kl1 = sum(dist1[k] * np.log(dist1[k] / m_dist[k])
                  for k in dist1.keys() if dist1[k] > 0)
        kl2 = sum(dist2[k] * np.log(dist2[k] / m_dist[k])
                  for k in dist2.keys() if dist2[k] > 0)

        return float((kl1 + kl2) / 2)

    def hellinger_distance(self) -> float:
        """Compute Hellinger distance.

        Hellinger distance is a metric that satisfies the triangle inequality.
        It is bounded between 0 and 1.

        Returns:
            Hellinger distance (0 = identical, 1 = maximally different)

        Examples:
            >>> compare = AnswersCompare(qa1, qa2)
            >>> compare.hellinger_distance()
            0.289
        """
        dist1, dist2 = self._get_distributions()

        sum_sqrt_products = sum(np.sqrt(dist1[k] * dist2[k]) for k in dist1.keys())
        return float(np.sqrt(1 - sum_sqrt_products))

    def total_variation_distance(self) -> float:
        """Compute total variation distance.

        Total variation distance is half the L1 distance between distributions.
        It is bounded between 0 and 1.

        Returns:
            Total variation distance (0 = identical, 1 = maximally different)

        Examples:
            >>> compare = AnswersCompare(qa1, qa2)
            >>> compare.total_variation_distance()
            0.156
        """
        dist1, dist2 = self._get_distributions()

        return float(0.5 * sum(abs(dist1[k] - dist2[k]) for k in dist1.keys()))

    def chi_squared(self) -> float:
        """Compute chi-squared statistic.

        Chi-squared measures the difference between observed and expected frequencies.
        Higher values indicate greater difference.

        Returns:
            Chi-squared statistic (0 = identical, unbounded)

        Examples:
            >>> compare = AnswersCompare(qa1, qa2)
            >>> compare.chi_squared()
            12.45
        """
        dist1, dist2 = self._get_distributions()

        chi2 = 0.0
        for key in dist1.keys():
            if dist2[key] > 0:
                chi2 += (dist1[key] - dist2[key]) ** 2 / dist2[key]

        return float(chi2)

    def bhattacharyya_distance(self) -> float:
        """Compute Bhattacharyya distance.

        Bhattacharyya distance is related to Hellinger distance and measures
        similarity between distributions.

        Returns:
            Bhattacharyya distance (0 = identical, unbounded)

        Examples:
            >>> compare = AnswersCompare(qa1, qa2)
            >>> compare.bhattacharyya_distance()
            0.156
        """
        dist1, dist2 = self._get_distributions()

        bc = sum(np.sqrt(dist1[k] * dist2[k]) for k in dist1.keys())
        return float(-np.log(bc))

    def custom_metric(self, metric_fn: Callable[[Dict, Dict], float]) -> float:
        """Compute a custom distance metric.

        Args:
            metric_fn: Function that takes two distribution dicts and returns a distance

        Returns:
            Result of the custom metric function

        Examples:
            Custom L1 distance:

            >>> def l1_distance(p, q):
            ...     return sum(abs(p[k] - q[k]) for k in p.keys())
            >>> compare.custom_metric(l1_distance)
            0.312

            Custom max difference:

            >>> def max_diff(p, q):
            ...     return max(abs(p[k] - q[k]) for k in p.keys())
            >>> compare.custom_metric(max_diff)
            0.125
        """
        dist1, dist2 = self._get_distributions()
        return metric_fn(dist1, dist2)

    def all_metrics(self) -> Dict[str, float]:
        """Compute all available distance metrics.

        Returns:
            Dictionary mapping metric names to their values

        Examples:
            >>> compare = AnswersCompare(qa1, qa2)
            >>> metrics = compare.all_metrics()
            >>> for name, value in metrics.items():
            ...     print(f"{name}: {value:.4f}")
            kl_divergence: 0.234
            kl_divergence_reverse: 0.198
            jensen_shannon_divergence: 0.145
            hellinger_distance: 0.289
            total_variation_distance: 0.156
            chi_squared: 12.45
            bhattacharyya_distance: 0.156
        """
        return {
            'kl_divergence': self.kl_divergence(),
            'kl_divergence_reverse': self.kl_divergence(reverse=True),
            'jensen_shannon_divergence': self.jensen_shannon_divergence(),
            'hellinger_distance': self.hellinger_distance(),
            'total_variation_distance': self.total_variation_distance(),
            'chi_squared': self.chi_squared(),
            'bhattacharyya_distance': self.bhattacharyya_distance(),
        }

    def _repr_html_(self) -> str:
        from ..scenarios import Scenario
        return Scenario({str(k): str(v) for k, v in self.all_metrics().items()})._repr_html_()

    # def summary(self) -> str:
    #     """Generate a formatted summary of all distance metrics.

    #     Returns:
    #         Formatted string with all metrics

    #     Examples:
    #         >>> compare = AnswersCompare(qa1, qa2)
    #         >>> print(compare.summary())
    #     """
    #     from rich.console import Console
    #     from rich.table import Table
    #     from rich import box
    #     import io

    #     console = Console(file=io.StringIO(), force_terminal=True, width=80)

    #     # Header
    #     console.print(f"\n[bold cyan]Distribution Comparison: {self.question_name}[/bold cyan]\n")

    #     # Metrics table
    #     metrics = self.all_metrics()
    #     table = Table(title="Distance Metrics", box=box.SIMPLE, border_style="cyan")
    #     table.add_column("Metric", style="cyan", width=30)
    #     table.add_column("Value", style="yellow", width=15)
    #     table.add_column("Interpretation", style="white", width=30)

    #     # Add metrics with interpretations
    #     interpretations = {
    #         'kl_divergence': 'Asymmetric (qa1→qa2)',
    #         'kl_divergence_reverse': 'Asymmetric (qa2→qa1)',
    #         'jensen_shannon_divergence': 'Symmetric [0, 0.69]',
    #         'hellinger_distance': 'Metric [0, 1]',
    #         'total_variation_distance': 'L1 distance [0, 1]',
    #         'chi_squared': 'Unbounded',
    #         'bhattacharyya_distance': 'Unbounded',
    #     }

    #     for name, value in metrics.items():
    #         interpretation = interpretations.get(name, '')
    #         table.add_row(name.replace('_', ' ').title(), f"{value:.4f}", interpretation)

    #     console.print(table)

    #     # Overall assessment
    #     js_div = metrics['jensen_shannon_divergence']
    #     if js_div < 0.05:
    #         assessment = "[green]Very similar distributions[/green]"
    #     elif js_div < 0.15:
    #         assessment = "[yellow]Somewhat different distributions[/yellow]"
    #     elif js_div < 0.30:
    #         assessment = "[orange1]Quite different distributions[/orange1]"
    #     else:
    #         assessment = "[red]Very different distributions[/red]"

    #     console.print(f"\nOverall: {assessment}\n")

    #     return console.file.getvalue()

    # def __repr__(self):
    #     """Return rich-formatted string representation with key metrics."""
    #     try:
    #         from rich.console import Console
    #         from rich.table import Table
    #         from rich import box
    #         import io

    #         console = Console(file=io.StringIO(), force_terminal=True, width=90)

    #         # Header
    #         console.print(f"\n[bold cyan]Distribution Comparison[/bold cyan]")
    #         console.print(f"[dim]Question: {self.question_name}[/dim]")

    #         # Get key metrics
    #         try:
    #             js_div = self.jensen_shannon_divergence()
    #             hellinger = self.hellinger_distance()
    #             tv_dist = self.total_variation_distance()

    #             # Compact metrics table
    #             table = Table(show_header=False, box=box.SIMPLE, border_style="cyan",
    #                          padding=(0, 1), collapse_padding=True)
    #             table.add_column("Metric", style="cyan", width=28)
    #             table.add_column("Value", style="yellow", width=12)

    #             table.add_row("Jensen-Shannon", f"{js_div:.4f}")
    #             table.add_row("Hellinger", f"{hellinger:.4f}")
    #             table.add_row("Total Variation", f"{tv_dist:.4f}")

    #             console.print(table)

    #             # Overall assessment
    #             if js_div < 0.05:
    #                 assessment = "[green]Very similar[/green]"
    #             elif js_div < 0.15:
    #                 assessment = "[yellow]Somewhat different[/yellow]"
    #             elif js_div < 0.30:
    #                 assessment = "[orange1]Quite different[/orange1]"
    #             else:
    #                 assessment = "[red]Very different[/red]"

    #             console.print(f"Assessment: {assessment}")

    #             # Tip
    #             console.print("\n[dim]Tip: Use .summary() for all metrics or .all_metrics() for dict[/dim]\n")

    #         except Exception as e:
    #             console.print(f"\n[dim]Metrics not yet computed: {e}[/dim]\n")

    #         return console.file.getvalue()

    #     except Exception:
    #         # Fallback to simple repr if rich formatting fails
    #         return f"AnswersCompare(question='{self.question_name}')"


if __name__ == "__main__":
    import doctest
    doctest.testmod()
