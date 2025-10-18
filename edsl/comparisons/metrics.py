from __future__ import annotations

"""Individual comparison metrics for EDSL answers."""

from abc import ABC, abstractmethod
from typing import List, Optional, Any
import numpy as np


# Elegant defensive import utility
def optional_import(
    module_name, package_name=None, install_name=None, description=None
):
    """Elegantly handle optional imports with helpful error messages."""
    if package_name is None:
        package_name = module_name
    if install_name is None:
        install_name = package_name
    if description is None:
        description = f"the {package_name} package"

    try:
        return __import__(module_name, fromlist=[""])
    except ImportError:

        class MissingModule:
            def __init__(self, name, install_name, description):
                self.name = name
                self.install_name = install_name
                self.description = description

            def __getattr__(self, item):
                raise ImportError(
                    f"{self.description} is required but not installed. "
                    f"Install with: pip install {self.install_name}"
                )

            def __call__(self, *args, **kwargs):
                raise ImportError(
                    f"{self.description} is required but not installed. "
                    f"Install with: pip install {self.install_name}"
                )

            def __bool__(self):
                return False

        return MissingModule(package_name, install_name, description)


# Clean, concise optional imports
sentence_transformers = optional_import(
    "sentence_transformers",
    install_name="sentence-transformers",
    description="sentence-transformers (required for semantic similarity)",
)

# Extract what we need with fallbacks
SentenceTransformer = getattr(sentence_transformers, "SentenceTransformer", None)

# Simple availability checks
SENTENCE_TRANSFORMERS_AVAILABLE = bool(sentence_transformers)

__all__ = [
    "ComparisonFunction",
    "Overlap",
    "SquaredDistance",
    "ExactMatch",
    "CosineSimilarity",
    "LLMSimilarity",
]


class ComparisonFunction(ABC):
    """Abstract base class for vectorized comparison metrics between answer lists.

    This class defines the interface for all comparison functions in the framework.
    Subclasses must implement the execute method and define a short_name class attribute.

    The design supports vectorized operations where entire lists of answers are compared
    at once, rather than pairwise comparisons, for better performance.

    Attributes:
        short_name (str): A unique identifier for this comparison function.
                         Must be defined by subclasses.

    Examples:
        Creating a custom comparison function:

        >>> class CustomComparison(ComparisonFunction):
        ...     short_name = "custom"
        ...
        ...     def execute(self, answers_A, answers_B, questions=None):
        ...         return [len(a) - len(b) for a, b in zip(answers_A, answers_B)]
        >>>
        >>> comparator = CustomComparison()
        >>> str(comparator)
        'custom'
        >>> comparator.execute(["hello", "world"], ["hi", "earth"])
        [2, -1]

        Subclasses without short_name raise TypeError:

        >>> class BadComparison(ComparisonFunction):
        ...     def execute(self, answers_A, answers_B, questions=None):
        ...         return []
        Traceback (most recent call last):
            ...
        TypeError: BadComparison must define a non-None 'short_name' class attribute
    """

    short_name: str  # subclasses must override with non-None value

    def __init_subclass__(cls, **kwargs):
        """Enforce that subclasses have a non-None short_name.

        Raises:
            TypeError: If subclass doesn't define short_name or it's None
        """
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "short_name") or cls.short_name is None:
            raise TypeError(
                f"{cls.__name__} must define a non-None 'short_name' class attribute"
            )

    @abstractmethod
    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Any]:
        """Execute the comparison function on two lists of answers.

        Args:
            answers_A: First list of answers to compare
            answers_B: Second list of answers to compare
            questions: Optional list of question objects for context

        Returns:
            List of comparison scores/results, parallel to the input answer lists.
            The specific type depends on the comparison function implementation.

        Note:
            All three lists must have the same length when provided.
        """
        ...

    def __str__(self) -> str:
        """Return human-readable identifier for this comparison function.

        Returns:
            The short_name of this comparison function.
            Subclasses can override for more detailed representation.
        """
        return self.short_name


# ---------------------------------------------------------------------------
# Simple metrics
# ---------------------------------------------------------------------------


class Overlap(ComparisonFunction):
    """Computes normalized overlap between two lists of iterable answers.

    This comparison function treats answers as collections and computes the overlap
    as the size of the intersection divided by the minimum collection size.
    String and bytes objects are not treated as iterables to avoid character-level
    comparison.

    The overlap score ranges from 0.0 (no overlap) to 1.0 (complete overlap of
    the smaller set). Returns None for non-iterable answers.

    Examples:
        Basic list overlap:

        >>> overlap = Overlap()
        >>> answers_A = [['a', 'b', 'c'], ['x', 'y']]
        >>> answers_B = [['b', 'c', 'd'], ['y', 'z']]
        >>> overlap.execute(answers_A, answers_B)
        [0.6666666666666666, 0.5]

        String answers return None (not treated as iterables):

        >>> overlap.execute(['hello'], ['world'])
        [None]

        Empty collections return 0.0:

        >>> overlap.execute([[]], [['a']])
        [0.0]

        Complete overlap:

        >>> overlap.execute([['a', 'b']], [['a', 'b']])
        [1.0]

        No overlap:

        >>> overlap.execute([['a', 'b']], [['c', 'd']])
        [0.0]
    """

    short_name = "overlap"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        """Compute normalized overlap between two answer lists.

        Args:
            answers_A: First list of answers (should be iterables)
            answers_B: Second list of answers (should be iterables)
            questions: Unused in this implementation

        Returns:
            List of overlap scores where each score is:
            - Float between 0.0-1.0: |intersection| / min(len(a), len(b))
            - 0.0: When one collection is empty
            - None: When either answer is not an iterable (or is string/bytes)

        Note:
            Strings and bytes are explicitly not treated as iterables to avoid
            character-level comparison which is usually not desired.
        """

        from collections.abc import Iterable

        def is_sequence(obj: Any) -> bool:
            return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes))

        overlap_frac: List[Optional[float]] = []
        for a, b in zip(answers_A, answers_B):
            if not (is_sequence(a) and is_sequence(b)):
                overlap_frac.append(None)
                continue

            set_a, set_b = set(a), set(b)

            if len(set_a) == 0 or len(set_b) == 0:
                overlap_frac.append(0.0)
                continue

            intersection_size = len(set_a & set_b)
            overlap_frac.append(intersection_size / min(len(set_a), len(set_b)))

        return overlap_frac


class JaccardSimilarity(ComparisonFunction):
    """Computes Jaccard similarity between two lists of iterable answers.

    Jaccard similarity is defined as the size of the intersection divided by
    the size of the union of two sets. This provides a measure of how similar
    two sets are, ranging from 0.0 (completely different) to 1.0 (identical).

    Unlike the Overlap metric which divides by the minimum set size, Jaccard
    divides by the union size, providing a more balanced measure of similarity
    that accounts for both overlapping and non-overlapping elements.

    The score ranges from 0.0 (no overlap) to 1.0 (identical sets).
    Returns None for non-iterable answers.

    Examples:
        Basic list Jaccard similarity:

        >>> jaccard = JaccardSimilarity()
        >>> answers_A = [['a', 'b', 'c'], ['x', 'y']]
        >>> answers_B = [['b', 'c', 'd'], ['y', 'z']]
        >>> jaccard.execute(answers_A, answers_B)
        [0.5, 0.3333333333333333]

        String answers return None (not treated as iterables):

        >>> jaccard.execute(['hello'], ['world'])
        [None]

        Empty collections return 0.0:

        >>> jaccard.execute([[]], [['a']])
        [0.0]

        Identical sets:

        >>> jaccard.execute([['a', 'b']], [['a', 'b']])
        [1.0]

        No overlap:

        >>> jaccard.execute([['a', 'b']], [['c', 'd']])
        [0.0]

        Multi-select question example (subset vs superset):

        >>> correct = [['Learning']]
        >>> answer = [['Task Iteration', 'Learning', 'Validation', 'Feedback']]
        >>> jaccard.execute(correct, answer)
        [0.25]
    """

    short_name = "jaccard_similarity"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        """Compute Jaccard similarity between two answer lists.

        Args:
            answers_A: First list of answers (should be iterables)
            answers_B: Second list of answers (should be iterables)
            questions: Unused in this implementation

        Returns:
            List of Jaccard similarity scores where each score is:
            - Float between 0.0-1.0: |intersection| / |union|
            - 0.0: When one or both collections are empty
            - None: When either answer is not an iterable (or is string/bytes)

        Note:
            Strings and bytes are explicitly not treated as iterables to avoid
            character-level comparison which is usually not desired.
        """

        from collections.abc import Iterable

        def is_sequence(obj: Any) -> bool:
            return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes))

        jaccard_scores: List[Optional[float]] = []
        for a, b in zip(answers_A, answers_B):
            if not (is_sequence(a) and is_sequence(b)):
                jaccard_scores.append(None)
                continue

            set_a, set_b = set(a), set(b)

            # Handle empty sets
            if len(set_a) == 0 and len(set_b) == 0:
                jaccard_scores.append(1.0)  # Two empty sets are identical
                continue

            if len(set_a) == 0 or len(set_b) == 0:
                jaccard_scores.append(0.0)
                continue

            intersection_size = len(set_a & set_b)
            union_size = len(set_a | set_b)
            jaccard_scores.append(intersection_size / union_size)

        return jaccard_scores


class SquaredDistance(ComparisonFunction):
    """*Negative* squared distance

    Returns ``-((a - b) ** 2)`` for numerical questions so that **higher values
    indicate better similarity**, aligning with other metrics such as cosine
    similarity or exact match. Non-numerical questions yield ``None``.
    """

    short_name = "negative_squared_distance"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        if questions is None:
            questions = [None] * len(answers_A)

        scores: List[Optional[float]] = []
        for a, b, q in zip(answers_A, answers_B, questions):
            if not (isinstance(q, dict) and q.get("question_type") == "numerical"):
                scores.append(None)
                continue
            try:
                diff_sq = (float(a) - float(b)) ** 2
                scores.append(-diff_sq)  # negative to make larger better
            except (ValueError, TypeError):
                scores.append(None)
        return scores


class ExactMatch(ComparisonFunction):
    """Performs exact equality comparison between corresponding answer pairs.

    This is the simplest comparison function that returns True when answers
    are exactly equal using Python's == operator, and False otherwise.
    Useful for categorical questions or when precise matching is required.

    Examples:
        Basic exact matching:

        >>> exact = ExactMatch()
        >>> answers_A = ['yes', 'no', 'maybe']
        >>> answers_B = ['yes', 'no', 'perhaps']
        >>> exact.execute(answers_A, answers_B)
        [True, True, False]

        Works with any comparable types:

        >>> exact.execute([1, 2.5, None], [1, 2.5, None])
        [True, True, True]

        Case-sensitive string comparison:

        >>> exact.execute(['Hello'], ['hello'])
        [False]

        Empty lists:

        >>> exact.execute([], [])
        []
    """

    short_name = "exact_match"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[bool]:
        """Compare answers for exact equality.

        Args:
            answers_A: First list of answers
            answers_B: Second list of answers
            questions: Unused in this implementation

        Returns:
            List of boolean values where True indicates exact equality
            and False indicates difference.

        Note:
            Uses Python's == operator, so comparison behavior depends
            on the types being compared.
        """
        return [a == b for a, b in zip(answers_A, answers_B)]


# ---------------------------------------------------------------------------
# Embedding-based metric(s)
# ---------------------------------------------------------------------------


class CosineSimilarity(ComparisonFunction):
    """Computes semantic similarity using sentence transformer embeddings and cosine similarity.

    This comparison function uses pre-trained sentence transformer models to convert
    text answers into high-dimensional embeddings, then computes cosine similarity
    between corresponding answer pairs. Values are normalized to range from 0 to 1,
    where 0 indicates opposite meaning, 0.5 indicates no similarity, and 1 indicates
    identical meaning.

    The model is loaded once during initialization and reused for all comparisons,
    making it efficient for batch processing.

    Args:
        model_name: Name of the sentence transformer model to use.
                   Defaults to "all-MiniLM-L6-v2" (384-dim, fast, good quality).

    Examples:
        Basic semantic similarity:

        >>> # Note: Actual values may vary slightly due to model differences
        >>> cosine = CosineSimilarity("all-MiniLM-L6-v2")
        >>> answers_A = ["The cat is happy", "I like pizza"]
        >>> answers_B = ["A happy feline", "Pizza is delicious"]
        >>> similarities = cosine.execute(answers_A, answers_B)
        >>> len(similarities) == 2
        True
        >>> all(0.0 <= sim <= 1.0 for sim in similarities)
        True

        String representation includes model name:

        >>> str(cosine)
        'cosine_similarity (all-MiniLM-L6-v2)'

        Different models can be used:

        >>> cosine_large = CosineSimilarity("all-mpnet-base-v2")
        >>> str(cosine_large)
        'cosine_similarity (all-mpnet-base-v2)'
    """

    short_name = "cosine_similarity"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize with specified sentence transformer model.

        Args:
            model_name: HuggingFace model name or path. Popular choices:
                       - "all-MiniLM-L6-v2": Fast, 384-dim, good quality
                       - "all-mpnet-base-v2": Slower, 768-dim, best quality
                       - "all-distilroberta-v1": Balanced speed/quality
        """
        self.model_name = model_name
        self.model = SentenceTransformer(
            model_name
        )  # Will raise ImportError with helpful message if missing

    def __str__(self) -> str:
        """Return string representation including model name."""
        return f"{self.short_name} ({self.model_name})"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[float]:
        """Compute normalized cosine similarity between corresponding answer pairs.

        Args:
            answers_A: First list of text answers
            answers_B: Second list of text answers
            questions: Unused in this implementation

        Returns:
            List of normalized cosine similarity scores between 0 and 1, where:
            - 1.0: Identical semantic meaning
            - 0.5: No semantic relationship (orthogonal)
            - 0.0: Opposite semantic meaning (rare in practice)

        Note:
            Raw cosine similarity ranges from [-1, 1] and is normalized to [0, 1]
            using the transformation: (similarity + 1) / 2.
            All answers are encoded in a single batch for efficiency,
            then similarity is computed pairwise.
        """

        # Convert all answers to strings (handles lists from checkbox questions, etc.)
        def to_string(answer):
            if isinstance(answer, list):
                return ", ".join(str(item) for item in answer)
            return str(answer)

        answers_A_str = [to_string(a) for a in answers_A]
        answers_B_str = [to_string(b) for b in answers_B]

        all_sentences = answers_A_str + answers_B_str
        embeddings = self.model.encode(all_sentences)
        n = len(answers_A)
        sims: List[float] = []
        for i in range(n):
            ea, eb = embeddings[i], embeddings[i + n]
            # Compute raw cosine similarity [-1, 1]
            raw_similarity = float(
                np.dot(ea, eb) / (np.linalg.norm(ea) * np.linalg.norm(eb))
            )
            # Normalize to [0, 1] range
            normalized_similarity = (raw_similarity + 1.0) / 2.0
            sims.append(normalized_similarity)
        return sims


class LLMSimilarity(ComparisonFunction):
    """Similarity judged by an LLM via EDSL linear scale question."""

    short_name = "llm_similarity"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        try:
            from edsl import QuestionLinearScale, ScenarioList
        except ImportError:
            return [None] * len(answers_A)

        q = QuestionLinearScale(
            question_name="similarity",
            question_text=(
                "A question was asked. One of the answers was: {{ scenario.answer_A }}. "
                "The other answer was: {{ scenario.answer_B }}.\nHow similar are the answers?"
            ),
            question_options=[1, 2, 3, 4, 5],
            option_labels={
                1: "Not at all similar",
                2: "Somewhat similar",
                3: "Moderately similar",
                4: "Very similar",
                5: "Completely similar",
            },
        )
        sl = ScenarioList.from_list("answer_A", answers_A).add_list(
            "answer_B", answers_B
        )
        try:
            return [float(x) for x in q.by(sl).run().select("similarity").to_list()]
        except Exception:
            return [None] * len(answers_A)
