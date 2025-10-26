from __future__ import annotations

"""Factory that bundles together multiple comparison metrics."""

from typing import Sequence, Dict, List, Any
from .metrics import (
    ComparisonFunction,
    ExactMatch,
    CosineSimilarity,
    SquaredDistance,
    Overlap,
    JaccardSimilarity,
    # LLMSimilarity,
)

__all__ = ["ComparisonFactory", "ComparisonOutput"]


class ComparisonFactory:
    """Factory for creating and executing multiple comparison metrics on answer pairs.

    This class implements the factory pattern to combine multiple comparison functions
    and execute them in batch on answer lists. It supports method chaining for
    fluent configuration and provides both low-level and high-level comparison methods.

    Examples:
        Basic factory usage:

        >>> factory = ComparisonFactory()
        >>> factory.add_comparison(ExactMatch())  # doctest: +ELLIPSIS
        <...ComparisonFactory object at 0x...>
        >>> factory.add_comparison(Overlap())  # doctest: +ELLIPSIS
        <...ComparisonFactory object at 0x...>

        Method chaining:

        >>> factory = (ComparisonFactory()
        ...           .add_comparison(ExactMatch())
        ...           .add_comparison(Overlap()))

        Using default comparisons:

        >>> factory = ComparisonFactory.with_defaults()
        >>> len(factory.comparison_fns) >= 3  # Has several default comparisons
        True

        Comparing answer lists:

        >>> factory = ComparisonFactory().add_comparison(ExactMatch())
        >>> answers_A = ['yes', 'no', 'maybe']
        >>> answers_B = ['yes', 'no', 'perhaps']
        >>> output = factory.compare_answers(answers_A, answers_B)
        >>> output.exact_match
        [True, True, False]

        Error handling for empty factory:

        >>> empty_factory = ComparisonFactory()
        >>> empty_factory.compare_answers(['a'], ['b'])
        Traceback (most recent call last):
            ...
        ValueError: No comparison functions registered. Use add_comparison() or add_comparisons() first.
    """

    def __init__(self, comparison_fns: Sequence[ComparisonFunction] | None = None):
        """Initialize factory with optional comparison functions.

        Args:
            comparison_fns: Optional sequence of ComparisonFunction instances.
                          If None, creates an empty factory that requires
                          manual addition of functions before use.
        """
        if comparison_fns is None:
            comparison_fns = []
        self.comparison_fns = list(comparison_fns)

    def add_comparison(self, comparison_fn: ComparisonFunction) -> "ComparisonFactory":
        """Add a single comparison function via dependency injection.

        Args:
            comparison_fn: A ComparisonFunction instance to add

        Returns:
            Self for method chaining

        Raises:
            TypeError: If comparison_fn is not a ComparisonFunction instance

        Examples:
            >>> factory = ComparisonFactory()
            >>> factory.add_comparison(ExactMatch())  # doctest: +ELLIPSIS
            <...ComparisonFactory object at 0x...>
        """
        if not isinstance(comparison_fn, ComparisonFunction):
            raise TypeError(
                f"Expected ComparisonFunction instance, got {type(comparison_fn).__name__}"
            )
        self.comparison_fns.append(comparison_fn)
        return self

    def add_comparisons(
        self, comparison_fns: Sequence[ComparisonFunction]
    ) -> "ComparisonFactory":
        """Add multiple comparison functions via dependency injection.

        Args:
            comparison_fns: Sequence of ComparisonFunction instances

        Returns:
            Self for method chaining

        Raises:
            TypeError: If any item is not a ComparisonFunction instance

        Examples:
            >>> factory = ComparisonFactory()
            >>> factory.add_comparisons([ExactMatch(), Overlap()])  # doctest: +ELLIPSIS
            <...ComparisonFactory object at 0x...>
        """
        for i, comparison_fn in enumerate(comparison_fns):
            if not isinstance(comparison_fn, ComparisonFunction):
                raise TypeError(
                    f"Expected ComparisonFunction instance at index {i}, got {type(comparison_fn).__name__}"
                )
        self.comparison_fns.extend(comparison_fns)
        return self

    @classmethod
    def with_defaults(cls) -> "ComparisonFactory":
        """Create a factory with a sensible set of default comparison functions.

        The default set includes:
        - ExactMatch: For categorical/exact comparisons
        - CosineSimilarity (two models): For semantic similarity (if available)
        - Overlap: For collection-based comparisons (recall-focused)
        - JaccardSimilarity: For collection-based comparisons (balanced)
        - SquaredDistance: For numerical comparisons

        Returns:
            ComparisonFactory configured with default comparison functions

        Examples:
            >>> factory = ComparisonFactory.with_defaults()
            >>> len(factory.comparison_fns) >= 2  # At least ExactMatch and Overlap
            True
            >>> any(isinstance(fn, ExactMatch) for fn in factory.comparison_fns)
            True
        """
        comparisons = [ExactMatch()]

        # Add CosineSimilarity functions only if sentence-transformers is available
        from .metrics import SENTENCE_TRANSFORMERS_AVAILABLE

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            comparisons.extend(
                [
                    CosineSimilarity("all-MiniLM-L6-v2"),
                    CosineSimilarity("all-mpnet-base-v2"),
                ]
            )

        comparisons.extend(
            [
                SquaredDistance(),
                Overlap(),
                JaccardSimilarity(),
            ]
        )

        return cls().add_comparisons(comparisons)

    def compare_answers(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> "ComparisonOutput":
        """Compare two lists of answers using all registered comparison functions.

        This is the core method that executes all registered comparison functions
        on the provided answer lists and returns the aggregated results.

        Args:
            answers_A: First list of answers to compare
            answers_B: Second list of answers to compare
            questions: Optional list of question objects for context

        Returns:
            ComparisonOutput containing results from all comparison functions

        Raises:
            ValueError: If no comparison functions have been registered

        Examples:
            >>> factory = ComparisonFactory().add_comparison(ExactMatch())
            >>> answers_A = ['yes', 'no']
            >>> answers_B = ['yes', 'maybe']
            >>> output = factory.compare_answers(answers_A, answers_B)
            >>> output.exact_match
            [True, False]
        """
        if not self.comparison_fns:
            raise ValueError(
                "No comparison functions registered. Use add_comparison() or add_comparisons() first."
            )

        questions = questions or [None] * len(answers_A)

        metrics: Dict[str, List[Any]] = {}
        for fn in self.comparison_fns:
            metrics[str(fn)] = fn.execute(answers_A, answers_B, questions)

        return ComparisonOutput(**metrics)

    def compare_results(
        self,
        result_A,
        result_B,
    ) -> "ComparisonResults":
        """Compare answers from two EDSL Results objects with rich metadata handling.

        This high-level method extracts answers and question metadata from EDSL Results
        objects, compares them using all registered comparison functions, and returns
        a rich ComparisonResults object with rendering and analysis capabilities.

        Args:
            result_A: First EDSL Results object
            result_B: Second EDSL Results object

        Returns:
            ComparisonResults object containing per-question comparisons with metadata

        Raises:
            ValueError: If no comparison functions have been registered
            KeyError: If Results objects don't have expected structure

        Examples:
            # Note: This example requires actual EDSL Results objects
            # >>> factory = ComparisonFactory.with_defaults()
            # >>> comparison = factory.compare_results(result_A, result_B)
            # >>> comparison.question_types()  # Access question metadata
            # {'q1': 'multiple_choice', 'q2': 'free_text'}
            # >>> table = comparison.render_table()  # Rich table output

        Note:
            This method expects Results objects with 'sub_dicts' containing 'answer'
            dictionaries and 'question_to_attributes' metadata. It automatically
            handles question metadata extraction and creates AnswerComparison objects
            with full context.
        """
        from .answer_comparison import AnswerComparison

        if not self.comparison_fns:
            raise ValueError(
                "No comparison functions registered. Use add_comparison() or add_comparisons() first."
            )

        answers_A_dict = result_A.sub_dicts["answer"]  # type: ignore[attr-defined]
        answers_B_dict = result_B.sub_dicts["answer"]  # type: ignore[attr-defined]

        common_qs = sorted(set(answers_A_dict.keys()) & set(answers_B_dict.keys()))

        answers_A_list = [answers_A_dict[q] for q in common_qs]
        answers_B_list = [answers_B_dict[q] for q in common_qs]

        # Attempt to pull question objects if available; otherwise placeholder None
        qa = result_A["question_to_attributes"]
        questions_list = [qa.get(q) for q in common_qs]

        comp_output: ComparisonOutput = self.compare_answers(
            answers_A_list, answers_B_list, questions_list
        )

        comparison_by_q: Dict[str, AnswerComparison] = {}
        for idx, qname in enumerate(common_qs):
            params: Dict[str, Any] = {
                "answer_a": answers_A_list[idx],
                "answer_b": answers_B_list[idx],
                "question_type": qa[qname].get("question_type"),
                "question_text": qa[qname].get("question_text"),
                "question_options": qa[qname].get("question_options"),
            }

            # Add metric values dynamically if the AnswerComparison class has the attribute
            for metric_name, metric_values in comp_output.items():
                params[metric_name] = metric_values[idx]

            comparison_by_q[qname] = AnswerComparison(**params)

        # Import ComparisonResults here to avoid circular imports
        from .comparison_results import ComparisonResults

        return ComparisonResults(comparison_by_q, self.comparison_fns)


class ComparisonOutput:
    """Container for comparison metrics with dict-like and attribute access.

    This class stores the raw output from comparison functions, providing both
    dictionary-style access and attribute-style access to metric results.
    Each metric maps to a list of scores parallel to the input answer lists.

    Examples:
        Creating and accessing comparison output:

        >>> output = ComparisonOutput(
        ...     exact_match=[True, False, True],
        ...     similarity=[0.9, 0.3, 0.8]
        ... )
        >>>
        >>> # Dictionary-style access via keys/items
        >>> list(output.keys())
        ['exact_match', 'similarity']

        Attribute-style access:

        >>> output.exact_match
        [True, False, True]
        >>> output.similarity
        [0.9, 0.3, 0.8]

        Iteration over metrics:

        >>> for metric_name, scores in output.items():
        ...     print(f"{metric_name}: {len(scores)} scores")
        exact_match: 3 scores
        similarity: 3 scores

        String representation:

        >>> repr(output)
        'ComparisonOutput(metrics=[exact_match, similarity])'

        Accessing non-existent metrics raises AttributeError:

        >>> output.nonexistent
        Traceback (most recent call last):
            ...
        AttributeError: nonexistent
    """

    def __init__(self, **metrics: Dict[str, List[Any]]):
        """Initialize with metric name -> scores mapping.

        Args:
            **metrics: Keyword arguments where keys are metric names and
                      values are lists of scores parallel to input answers.
        """
        self._metrics = metrics

    def __getattr__(self, item):
        """Provide attribute-style access to metrics.

        Args:
            item: Name of the metric to retrieve

        Returns:
            List of scores for the requested metric

        Raises:
            AttributeError: If the metric name doesn't exist
        """
        try:
            return self._metrics[item]
        except KeyError as e:
            raise AttributeError(item) from e

    def keys(self):
        """Return metric names.

        Returns:
            dict_keys view of metric names
        """
        return self._metrics.keys()

    def items(self):
        """Return (metric_name, scores) pairs.

        Returns:
            dict_items view of (name, scores) tuples
        """
        return self._metrics.items()

    def __repr__(self):
        """Return string representation showing available metrics."""
        keys = ", ".join(self._metrics.keys())
        return f"ComparisonOutput(metrics=[{keys}])"
