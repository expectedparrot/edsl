"""Compare answer distributions between two QuestionAnalysis objects.

Provides statistical distance metrics: KL divergence, Jensen-Shannon,
Hellinger, total variation, chi-squared, Bhattacharyya, and custom metrics.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Callable, Dict, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from ...reports.report import QuestionAnalysis


class AnswersCompare:
    """Compare answer distributions between two QuestionAnalysis objects."""

    def __init__(self, qa1: "QuestionAnalysis", qa2: "QuestionAnalysis"):
        from ...reports.report import QuestionAnalysis as QA

        if not isinstance(qa1, QA):
            raise TypeError(f"qa1 must be QuestionAnalysis, got {type(qa1)}")
        if not isinstance(qa2, QA):
            raise TypeError(f"qa2 must be QuestionAnalysis, got {type(qa2)}")
        if qa1._question_names != qa2._question_names:
            raise ValueError(
                f"Question names must match: {qa1._question_names} vs {qa2._question_names}"
            )
        if len(qa1._question_names) != 1:
            raise ValueError("Only single-question analysis supported")

        self.qa1 = qa1
        self.qa2 = qa2
        self.question_name = qa1._question_names[0]
        self._dist1 = None
        self._dist2 = None

    def _get_distributions(
        self, smoothing: float = 1e-10
    ) -> tuple[Dict[Any, float], Dict[Any, float]]:
        if self._dist1 is not None and self._dist2 is not None:
            return self._dist1, self._dist2

        answers1 = [a for a in self.qa1._report.results.get_answers(self.question_name) if a is not None]
        answers2 = [a for a in self.qa2._report.results.get_answers(self.question_name) if a is not None]

        if not answers1:
            raise ValueError("No valid answers in first QuestionAnalysis")
        if not answers2:
            raise ValueError("No valid answers in second QuestionAnalysis")

        question = self.qa1._report.results.survey.get(self.question_name)
        if hasattr(question, "question_options") and question.question_options:
            all_values = list(question.question_options)
        else:
            all_values = list(set(answers1) | set(answers2))

        counts1, counts2 = Counter(answers1), Counter(answers2)
        n1, n2 = len(answers1), len(answers2)
        n_vals = len(all_values)

        dist1 = {v: (counts1.get(v, 0) + smoothing) / (n1 + smoothing * n_vals) for v in all_values}
        dist2 = {v: (counts2.get(v, 0) + smoothing) / (n2 + smoothing * n_vals) for v in all_values}

        # Re-normalise
        s1, s2 = sum(dist1.values()), sum(dist2.values())
        self._dist1 = {k: v / s1 for k, v in dist1.items()}
        self._dist2 = {k: v / s2 for k, v in dist2.items()}
        return self._dist1, self._dist2

    def kl_divergence(self, reverse: bool = False) -> float:
        """KL divergence D_KL(P||Q). Set reverse=True for D_KL(Q||P)."""
        d1, d2 = self._get_distributions()
        if reverse:
            d1, d2 = d2, d1
        return float(sum(d1[k] * np.log(d1[k] / d2[k]) for k in d1 if d1[k] > 0))

    def jensen_shannon_divergence(self) -> float:
        """Symmetric Jensen-Shannon divergence, bounded [0, ln(2)]."""
        d1, d2 = self._get_distributions()
        m = {k: (d1[k] + d2[k]) / 2 for k in d1}
        kl1 = sum(d1[k] * np.log(d1[k] / m[k]) for k in d1 if d1[k] > 0)
        kl2 = sum(d2[k] * np.log(d2[k] / m[k]) for k in d2 if d2[k] > 0)
        return float((kl1 + kl2) / 2)

    def hellinger_distance(self) -> float:
        """Hellinger distance, bounded [0, 1]."""
        d1, d2 = self._get_distributions()
        return float(np.sqrt(1 - sum(np.sqrt(d1[k] * d2[k]) for k in d1)))

    def total_variation_distance(self) -> float:
        """Total variation distance (half L1), bounded [0, 1]."""
        d1, d2 = self._get_distributions()
        return float(0.5 * sum(abs(d1[k] - d2[k]) for k in d1))

    def chi_squared(self) -> float:
        """Chi-squared statistic."""
        d1, d2 = self._get_distributions()
        return float(sum((d1[k] - d2[k]) ** 2 / d2[k] for k in d1 if d2[k] > 0))

    def bhattacharyya_distance(self) -> float:
        """Bhattacharyya distance."""
        d1, d2 = self._get_distributions()
        bc = sum(np.sqrt(d1[k] * d2[k]) for k in d1)
        return float(-np.log(bc))

    def custom_metric(self, metric_fn: Callable[[Dict, Dict], float]) -> float:
        """Apply a custom distance function to the two distributions."""
        d1, d2 = self._get_distributions()
        return metric_fn(d1, d2)

    def all_metrics(self) -> Dict[str, float]:
        """Compute all built-in distance metrics."""
        return {
            "kl_divergence": self.kl_divergence(),
            "kl_divergence_reverse": self.kl_divergence(reverse=True),
            "jensen_shannon_divergence": self.jensen_shannon_divergence(),
            "hellinger_distance": self.hellinger_distance(),
            "total_variation_distance": self.total_variation_distance(),
            "chi_squared": self.chi_squared(),
            "bhattacharyya_distance": self.bhattacharyya_distance(),
        }

    def __repr__(self) -> str:
        return f"AnswersCompare(question='{self.question_name}')"

    @classmethod
    def example(cls) -> "AnswersCompare":
        """Return an example (requires a Results object with a report/analyze method).

        This is a placeholder — wire it up once QuestionAnalysis.example() exists.
        """
        raise NotImplementedError(
            "AnswersCompare.example() requires QuestionAnalysis objects. "
            "Use results.analyze('question_name') to create them."
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod()
