"""EDSL Answer Comparison Framework.

A comprehensive framework for comparing answers from EDSL survey results using multiple
similarity metrics including exact matching, cosine similarity, overlap analysis, and 
LLM-based similarity scoring.

This module provides:
- Abstract comparison function interface with concrete implementations
- Factory pattern for combining multiple comparison metrics
- Rich table rendering and data export capabilities
- Caching utilities for expensive EDSL job results
- Comprehensive question metadata handling

Example Usage:
    >>> from edsl import Results
    >>> # Assume you have two Results objects: result_A and result_B
    >>> factory = ComparisonFactory.with_defaults()
    >>> comparison = factory.compare_results(result_A, result_B)
    >>> print(comparison.render_table())
    >>> 
    >>> # Access question attributes
    >>> types = comparison.question_types()
    >>> texts = comparison.question_texts()
    >>> 
    >>> # Convert to scenario list for further analysis
    >>> scenarios = comparison.to_scenario_list()

Classes:
    ComparisonFunction: Abstract base for comparison metrics
    ComparisonFactory: Factory for creating comparison workflows
    ComparisonResults: Container for comparison results with rich output
    AnswerComparison: Individual question comparison holder
    ComparisonOutput: Raw metric outputs container

Functions:
    local_results_cache: Context manager for caching EDSL job results
    main: Demo function showing framework capabilities
"""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pip",
#   "sentence-transformers",
#   "edsl @ file:///Users/johnhorton/tools/ep/edsl",
#   "numpy",
#   "rich",
# ]
# ///
from contextlib import contextmanager
from pathlib import Path
import tempfile
from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Sequence

import numpy as np

# Elegant defensive import utility
def optional_import(module_name, package_name=None, install_name=None, description=None):
    """Elegantly handle optional imports with helpful error messages."""
    if package_name is None:
        package_name = module_name
    if install_name is None:
        install_name = package_name
    if description is None:
        description = f"the {package_name} package"
    
    try:
        return __import__(module_name, fromlist=[''])
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
    'sentence_transformers', 
    install_name='sentence-transformers',
    description='sentence-transformers (required for semantic similarity)'
)

rich = optional_import(
    'rich',
    description='rich (required for beautiful terminal output)'
)

# Extract what we need with fallbacks
SentenceTransformer = getattr(sentence_transformers, 'SentenceTransformer', None)
Console = getattr(rich, 'Console', None) 
Progress = getattr(rich, 'Progress', None)
SpinnerColumn = getattr(rich, 'SpinnerColumn', None)
TextColumn = getattr(rich, 'TextColumn', None)

# Simple availability checks
SENTENCE_TRANSFORMERS_AVAILABLE = bool(sentence_transformers)
RICH_AVAILABLE = bool(rich)


# ----------------------------
# Local caching context manager
# ----------------------------

@contextmanager
def local_results_cache(job, cache_dir: str | None = None, verbose: bool = True):
    """Context manager that caches EDSL job.run() results to disk for performance.

    This context manager automatically handles caching of expensive EDSL job results.
    On first run, it executes the job and saves results to disk. On subsequent runs
    with the same job hash, it loads results from cache instead of re-executing.

    Args:
        job: EDSL job object with a .run() method
        cache_dir: Optional directory for cache files. If None, uses system temp directory
        verbose: Whether to print cache status messages

    Yields:
        Results: The EDSL Results object, either from cache or fresh execution

    Raises:
        Exception: Any exception from job.run() or file I/O operations

    Examples:
        Basic usage with automatic caching:
        
        >>> from edsl import QuestionFreeText, ScenarioList
        >>> job = QuestionFreeText(
        ...     question_name="test",
        ...     question_text="What is 2+2?"
        ... ).by(ScenarioList.from_list("dummy", [1]))
        >>> 
        >>> # First run executes job and caches result
        >>> with local_results_cache(job, verbose=False) as results:
        ...     len(results) > 0
        True
        
        Custom cache directory:
        
        >>> import tempfile
        >>> with tempfile.TemporaryDirectory() as tmpdir:
        ...     with local_results_cache(job, cache_dir=tmpdir, verbose=False) as results:
        ...         len(results) > 0
        True

    Note:
        - Cache files are named using hash(job) for uniqueness
        - Corrupted cache files are automatically detected and regenerated
        - The context manager properly handles exceptions including debugger quits
    """


    # Determine cache directory and file locations (single cache per script)
    root = Path(cache_dir) if cache_dir else Path(tempfile.gettempdir()) / "edsl_job_cache"
    root.mkdir(parents=True, exist_ok=True)

    current_hash = str(hash(job))

    results_path = root / f"{current_hash}.json.gz"

    if verbose:
        print(f"[cache] directory: {root}")
        print(f"[cache] job hash: {current_hash}")
        print(f"[cache] results file: {results_path}")

    # Attempt to load cache using hash-named file
    if results_path.exists():
        try:
            results_obj = Results.load(str(results_path))
            if verbose:
                print("[cache] hit – loaded results from disk")
            try:
                yield results_obj
            except Exception:
                # Re-raise any exception that occurs in the yield block
                # This prevents the "generator didn't stop after throw()" error
                raise
            return
        except Exception:
            if verbose:
                print("[cache] load failed – cache corrupt, rerunning job")

    # Cache miss → run and save
    if verbose:
        print("[cache] miss – running job")
    results_obj = job.run()
    try:
        results_obj.save(str(results_path))
        if verbose:
            print("[cache] saved results to", results_path)
    except Exception as e:
        if verbose:
            print("[cache] failed to save cache:", e)
    
    try:
        yield results_obj
    except Exception:
        # Re-raise any exception that occurs in the yield block
        # This prevents the "generator didn't stop after throw()" error
        raise


# ----------------------------
# Comparison framework (functions -> ABC classes)
# ----------------------------


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
        if not hasattr(cls, 'short_name') or cls.short_name is None:
            raise TypeError(f"{cls.__name__} must define a non-None 'short_name' class attribute")

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


class CosineSimilarity(ComparisonFunction):
    """Computes semantic similarity using sentence transformer embeddings and cosine similarity.

    This comparison function uses pre-trained sentence transformer models to convert
    text answers into high-dimensional embeddings, then computes cosine similarity
    between corresponding answer pairs. Values range from -1 (opposite) to 1 (identical),
    with 0 indicating orthogonal (no similarity).

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
        >>> all(0.0 <= sim <= 1.0 for sim in similarities)  # Should be positive
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
        self.model = SentenceTransformer(model_name)  # Will raise ImportError with helpful message if missing

    def __str__(self) -> str:
        """Return string representation including model name."""
        return f"{self.short_name} ({self.model_name})"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[float]:
        """Compute cosine similarity between corresponding answer pairs.

        Args:
            answers_A: First list of text answers
            answers_B: Second list of text answers
            questions: Unused in this implementation

        Returns:
            List of cosine similarity scores between -1 and 1, where:
            - 1.0: Identical semantic meaning
            - 0.0: No semantic relationship  
            - -1.0: Opposite semantic meaning (rare in practice)

        Note:
            All answers are encoded in a single batch for efficiency,
            then similarity is computed pairwise.
        """
        all_sentences = answers_A + answers_B
        embeddings = self.model.encode(all_sentences)
        n = len(answers_A)
        sims: List[float] = []
        for i in range(n):
            ea, eb = embeddings[i], embeddings[i + n]
            sims.append(float(np.dot(ea, eb) / (np.linalg.norm(ea) * np.linalg.norm(eb))))
        return sims


class LLMSimilarity(ComparisonFunction):
    """Uses a large language model to assess semantic similarity between answer pairs.

    This comparison function leverages EDSL's QuestionLinearScale to ask an LLM
    to rate the similarity between answer pairs on a 1-5 scale. This can capture
    nuanced semantic relationships that embedding-based methods might miss.

    The LLM evaluation is more expensive than other methods but can provide
    more contextually aware similarity assessments, especially for complex
    or domain-specific content.

    Returns:
        Similarity scores from 1.0 (not similar) to 5.0 (completely similar),
        or None if the LLM evaluation fails.

    Examples:
        Basic LLM similarity (requires EDSL and API access):

        >>> llm_sim = LLMSimilarity()
        >>> str(llm_sim)
        'llm_similarity'

        Note: Actual execution requires EDSL setup and API credentials:
        # >>> answers_A = ["The weather is nice", "I enjoy reading"]  
        # >>> answers_B = ["It's a beautiful day", "Books are interesting"]
        # >>> scores = llm_sim.execute(answers_A, answers_B)
        # >>> all(1.0 <= score <= 5.0 for score in scores if score is not None)
        # True

        Graceful handling of import/execution errors:

        >>> # If EDSL is not available or execution fails, returns None values
        >>> # This is tested internally in the execute method
    """
    short_name = "llm_similarity"

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Optional[float]]:
        """Execute LLM-based similarity assessment.

        Args:
            answers_A: First list of text answers
            answers_B: Second list of text answers  
            questions: Unused in this implementation

        Returns:
            List of similarity scores where each score is:
            - Float 1.0-5.0: LLM similarity rating
            - None: If EDSL import fails or LLM execution fails

        Note:
            This method requires EDSL to be properly installed and configured
            with API credentials. Failures are handled gracefully by returning None.
        """
        # Using EDSL linear scale for LLM-based similarity assessment
        try:
            from edsl import QuestionLinearScale, ScenarioList
        except ImportError:
            return [None] * len(answers_A)

        q = QuestionLinearScale(
            question_name="similarity",
            question_text="""A question was asked. One of the answers was: {{ scenario.answer_A }}. The other answer was: {{ scenario.answer_B }}.\nHow similar are the answers?""",
            question_options=[1, 2, 3, 4, 5],
            option_labels={
                1: "Not at all similar",
                2: "Somewhat similar", 
                3: "Moderately similar",
                4: "Very similar",
                5: "Completely similar",
            },
        )
        sl = ScenarioList.from_list("answer_A", answers_A).add_list("answer_B", answers_B)
        try:
            return [float(x) for x in q.by(sl).run().select("similarity").to_list()]
        except Exception:
            return [None] * len(answers_A)


# ----------------------------
# Comparison Factory + Output
# ----------------------------


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
        >>> # Dictionary-style access
        >>> list(output.keys())
        ['exact_match', 'similarity']
        >>> output['exact_match']  # Not implemented, use attribute access
        Traceback (most recent call last):
            ...
        TypeError: 'ComparisonOutput' object is not subscriptable

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

    def __init__(self):
        """Initialize empty factory. Add comparison functions before use."""
        self.comparison_fns: List[ComparisonFunction] = []

    def add_comparison(self, comparison_fn: ComparisonFunction) -> 'ComparisonFactory':
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
            raise TypeError(f"Expected ComparisonFunction instance, got {type(comparison_fn).__name__}")
        self.comparison_fns.append(comparison_fn)
        return self

    def add_comparisons(self, comparison_fns: Sequence[ComparisonFunction]) -> 'ComparisonFactory':
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
                raise TypeError(f"Expected ComparisonFunction instance at index {i}, got {type(comparison_fn).__name__}")
        self.comparison_fns.extend(comparison_fns)
        return self

    @classmethod
    def with_defaults(cls) -> 'ComparisonFactory':
        """Create a factory with a sensible set of default comparison functions.
        
        The default set includes:
        - ExactMatch: For categorical/exact comparisons
        - CosineSimilarity (two models): For semantic similarity (if available)
        - Overlap: For collection-based comparisons
        
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
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            comparisons.extend([
                CosineSimilarity("all-MiniLM-L6-v2"),
                CosineSimilarity("all-mpnet-base-v2"),
            ])
        
        # LLMSimilarity(),  # Commented out due to API requirements
        comparisons.append(Overlap())
        
        return cls().add_comparisons(comparisons)

    def compare_answers(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> ComparisonOutput:
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
            raise ValueError("No comparison functions registered. Use add_comparison() or add_comparisons() first.")
        
        questions = questions or [None] * len(answers_A)

        metrics: Dict[str, List[Any]] = {}
        for fn in self.comparison_fns:
            metrics[str(fn)] = fn.execute(answers_A, answers_B, questions)

        return ComparisonOutput(**metrics)

    def compare_results(
        self,
        result_A,
        result_B,
    ) -> 'ComparisonResults':
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
        if not self.comparison_fns:
            raise ValueError("No comparison functions registered. Use add_comparison() or add_comparisons() first.")

        answers_A_dict = result_A.sub_dicts['answer']  # type: ignore[attr-defined]
        answers_B_dict = result_B.sub_dicts['answer']  # type: ignore[attr-defined]

        common_qs = sorted(set(answers_A_dict.keys()) & set(answers_B_dict.keys()))

        answers_A_list = [answers_A_dict[q] for q in common_qs]
        answers_B_list = [answers_B_dict[q] for q in common_qs]

        # Attempt to pull question objects if available; otherwise placeholder None
        qa = result_A['question_to_attributes']
        questions_list = [qa.get(q) for q in common_qs]

        comp_output: ComparisonOutput = self.compare_answers(answers_A_list, answers_B_list, questions_list)

        comparison_by_q: Dict[str, AnswerComparison] = {}
        for idx, qname in enumerate(common_qs):
            # Grab question type if available
            #qt = None
            #if isinstance(questions_list[idx], dict):
            #    qt = questions_list[idx].get("question_type")
            

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

        return ComparisonResults(comparison_by_q, self.comparison_fns)


# ----------------------------
# Flexible per-question comparison holder
# ----------------------------


class AnswerComparison:
    """Container for a single question's answer pair and all comparison metrics.

    This class stores two answers and all computed comparison metrics for a single
    question, providing flexible access to both the raw answers and computed scores.
    It's designed to be metric-agnostic, accepting arbitrary comparison results
    as keyword arguments.

    The class also provides utility methods for display formatting and data export.

    Attributes:
        answer_a: The first answer being compared
        answer_b: The second answer being compared
        _truncate_len: Class-level setting for display truncation (60 characters)

    Examples:
        Basic usage with metrics:

        >>> comparison = AnswerComparison(
        ...     answer_a="yes",
        ...     answer_b="no", 
        ...     exact_match=False,
        ...     similarity=0.2,
        ...     question_type="yes_no"
        ... )
        >>> comparison.answer_a
        'yes'
        >>> comparison.exact_match
        False
        >>> comparison.similarity
        0.2

        Attribute access for question metadata:

        >>> comparison.question_type
        'yes_no'

        Dictionary conversion:

        >>> data = comparison.to_dict()
        >>> data['answer_a']
        'yes'
        >>> data['exact_match']
        False

        Display truncation:

        >>> long_answer = "This is a very long answer that will be truncated for display purposes"
        >>> AnswerComparison._truncate(long_answer, 20)
        'This is...purposes'

        String representation:

        >>> str(comparison)  # doctest: +ELLIPSIS
        "AnswerComparison(answer_a='yes', answer_b='no', exact_match=False, similarity=0.200, question_type=yes_no)"
    """

    _truncate_len: int = 60  # characters for display

    def __init__(self, answer_a: Any, answer_b: Any, **metrics: Any):
        """Initialize with answer pair and arbitrary metrics.
        
        Args:
            answer_a: First answer in the comparison
            answer_b: Second answer in the comparison
            **metrics: Arbitrary keyword arguments for comparison metrics
                      and question metadata (e.g., exact_match=True, 
                      question_type='multiple_choice')
        """
        self.answer_a = answer_a
        self.answer_b = answer_b
        # Store metrics in a private dict to avoid namespace clashes
        self._metrics: Dict[str, Any] = metrics

    # ---------------- Utility helpers -----------------

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Return a shortened, render-safe string for table cells.
        
        Converts non-string iterables to comma-separated strings and truncates
        long text by taking characters from both ends with "..." in the middle.
        
        Args:
            text: Text to truncate (will be converted to string if not already)
            max_len: Maximum length of returned string
            
        Returns:
            Truncated string, or original if shorter than max_len
            
        Examples:
            >>> AnswerComparison._truncate("hello world", 8)
            'he...rld'
            >>> AnswerComparison._truncate("short", 10)
            'short'
            >>> AnswerComparison._truncate(['a', 'b', 'c'], 10)
            'a, b, c'
        """
        # Convert non-string iterables (lists/tuples etc.) to a comma-separated string
        if not isinstance(text, str):
            from collections.abc import Iterable
            if isinstance(text, Iterable):
                text = ", ".join(map(str, text))
            else:
                text = str(text)

        if len(text) <= max_len:
            return text

        half = (max_len - 3) // 2
        return text[:half] + "..." + text[-half:]

    # ---------------- Dunder methods ------------------

    def __getattr__(self, item: str):
        """Provide attribute-style access to metric values.
        
        Args:
            item: Name of the metric or attribute to access
            
        Returns:
            The value associated with the metric name
            
        Raises:
            AttributeError: If the metric name doesn't exist
            
        Examples:
            >>> comp = AnswerComparison("a", "b", score=0.5)
            >>> comp.score
            0.5
        """
        if item in self._metrics:
            return self._metrics[item]
        raise AttributeError(item)

    def __getitem__(self, item: str):
        """Provide dictionary-style access to metric values.
        
        Args:
            item: Name of the metric to access
            
        Returns:
            The value associated with the metric name, or None if not found
        """
        return self._metrics.get(item)

    def to_dict(self) -> Dict[str, Any]:
        """Return all comparison data as a dictionary.
        
        Returns:
            Dictionary containing answer_a, answer_b, and all metrics
            
        Examples:
            >>> comp = AnswerComparison("yes", "no", exact_match=False)
            >>> data = comp.to_dict()
            >>> sorted(data.keys())
            ['answer_a', 'answer_b', 'exact_match']
        """
        result = {
            'answer_a': self.answer_a,
            'answer_b': self.answer_b,
        }
        result.update(self._metrics)
        return result

    def __repr__(self) -> str:
        """Return string representation with truncated answers and formatted metrics.
        
        Returns:
            String showing AnswerComparison with truncated answers and all metrics
            
        Examples:
            >>> comp = AnswerComparison("yes", "no", exact_match=False, score=0.123456)
            >>> repr(comp)
            "AnswerComparison(answer_a='yes', answer_b='no', exact_match=False, score=0.123)"
        """
        a = self._truncate(self.answer_a, self._truncate_len)
        b = self._truncate(self.answer_b, self._truncate_len)

        # Build metric part of the representation dynamically, truncating long floats
        metric_parts = []
        for k, v in self._metrics.items():
            if isinstance(v, float):
                metric_parts.append(f"{k}={v:.3f}")
            else:
                metric_parts.append(f"{k}={v}")

        metrics_str = ", ".join(metric_parts)
        return f"AnswerComparison(answer_a='{a}', answer_b='{b}', {metrics_str})"


class ComparisonResults:
    """Rich container for comparison results with analysis and rendering capabilities.

    This class wraps a collection of AnswerComparison objects (one per question)
    and provides high-level methods for analysis, data extraction, and visualization.
    It maintains references to the comparison functions used and offers convenient
    access to question metadata and comparison metrics.

    Attributes:
        comparisons: Dictionary mapping question names to AnswerComparison objects
        comparison_fns: List of ComparisonFunction objects used to generate results

    Examples:
        Basic usage (requires actual AnswerComparison objects):

        >>> # Create mock comparisons for testing
        >>> from collections import OrderedDict
        >>> comparisons = OrderedDict([
        ...     ('q1', AnswerComparison('yes', 'no', exact_match=False, question_type='yes_no')),
        ...     ('q2', AnswerComparison('maybe', 'perhaps', exact_match=False, question_type='free_text'))
        ... ])
        >>> factory = ComparisonFactory().add_comparison(ExactMatch())
        >>> results = ComparisonResults(comparisons, factory.comparison_fns)

        Dictionary-like access:

        >>> results['q1'].answer_a
        'yes'
        >>> results['q1'].exact_match
        False

        Iteration:

        >>> list(results.keys())
        ['q1', 'q2']
        >>> len(list(results.items()))
        2

        Question metadata access:

        >>> types = results.question_types()
        >>> types['q1']
        'yes_no'
        >>> types['q2']
        'free_text'

        Grouping by question type:

        >>> by_type = results.questions_by_type
        >>> by_type['yes_no']
        ['q1']
        >>> by_type['free_text']
        ['q2']
    """
    
    def __init__(self, comparisons: Dict[str, AnswerComparison], comparison_fns: List[ComparisonFunction]):
        """Initialize with comparison results and function metadata.
        
        Args:
            comparisons: Dictionary mapping question names to AnswerComparison objects
            comparison_fns: List of ComparisonFunction objects used to generate the results
        """
        self.comparisons = comparisons
        self.comparison_fns = comparison_fns
    
    def __getitem__(self, key: str) -> AnswerComparison:
        """Get AnswerComparison by question name.
        
        Args:
            key: Question name
            
        Returns:
            AnswerComparison object for the specified question
        """
        return self.comparisons[key]
    
    def __iter__(self):
        """Iterate over question names."""
        return iter(self.comparisons)
    
    def items(self):
        """Return (question_name, AnswerComparison) pairs."""
        return self.comparisons.items()
    
    def keys(self):
        """Return question names."""
        return self.comparisons.keys()
    
    def values(self):
        """Return AnswerComparison objects."""
        return self.comparisons.values()
    
    def question_types(self) -> Dict[str, Optional[str]]:
        """Get question types for all questions.
        
        Returns:
            Dict mapping question names to their question types
        """
        return {qname: comparison.question_type for qname, comparison in self.comparisons.items()}
    
    def question_texts(self) -> Dict[str, Optional[str]]:
        """Get question texts for all questions.
        
        Returns:
            Dict mapping question names to their question texts
        """
        return {qname: comparison.question_text for qname, comparison in self.comparisons.items()}
    
    def question_options(self) -> Dict[str, Optional[List]]:
        """Get question options for all questions.
        
        Returns:
            Dict mapping question names to their question options (if any)
        """
        return {qname: comparison.question_options for qname, comparison in self.comparisons.items()}
    
    def get_question_attribute(self, attribute: str) -> Dict[str, Any]:
        """Get a specific question attribute for all questions.
        
        Args:
            attribute: The attribute name to retrieve (e.g., 'question_type', 'question_text', 'question_options')
            
        Returns:
            Dict mapping question names to the requested attribute values
        """
        return {qname: getattr(comparison, attribute, None) for qname, comparison in self.comparisons.items()}
    
    @property
    def all_question_types(self) -> List[str]:
        """Get a list of all unique question types in the results."""
        types = set()
        for comparison in self.comparisons.values():
            if hasattr(comparison, 'question_type') and comparison.question_type:
                types.add(comparison.question_type)
        return sorted(list(types))
    
    @property 
    def questions_by_type(self) -> Dict[str, List[str]]:
        """Group question names by their question type."""
        by_type = {}
        for qname, comparison in self.comparisons.items():
            qtype = getattr(comparison, 'question_type', 'unknown')
            if qtype not in by_type:
                by_type[qtype] = []
            by_type[qtype].append(qname)
        return by_type

    def to_scenario_list(self) -> 'ScenarioList':
        """Convert the comparison results to a ScenarioList."""
        from edsl import ScenarioList, Scenario
        scenarios = []
        for q, answer_comparison in self.comparisons.items():
            combined_dict = {'question_name': q}
            combined_dict.update(answer_comparison.to_dict())
            scenarios.append(Scenario(combined_dict))
        return ScenarioList(scenarios)
    
    def render_table(self) -> 'Table':
        """Create a rich Table for the comparison results."""
        from rich.table import Table  # Will raise ImportError with helpful message if missing
        
        table = Table(title="Answer Comparison", show_lines=True)
        table.add_column("Question", style="bold")

        metrics_to_show: List[str] = [str(fn) for fn in self.comparison_fns]

        for short in metrics_to_show:
            table.add_column(short.replace("_", " ").title(), justify="right")

        table.add_column("Answer A", overflow="fold")
        table.add_column("Answer B", overflow="fold")

        for q, metrics in self.comparisons.items():
            # First column: question name plus (question_type) if available
            q_cell = str(q)
            if metrics["question_type"]:
                q_cell = f"{q}\n({metrics['question_type']})"

            row: List[str] = [q_cell]
            for short in metrics_to_show:
                val = metrics[short]
                if isinstance(val, (int, float)):
                    row.append(f"{val:.3f}")
                else:
                    row.append(str(val))

            row.extend([
                AnswerComparison._truncate(metrics.answer_a, 100),
                AnswerComparison._truncate(metrics.answer_b, 100),
            ])

            table.add_row(*row)

        return table





# -----------------------------
# CLI / Demonstration
# -----------------------------


def main() -> None:
    """Demonstrate the comparison framework with a multi-city, multi-model survey.

    This function showcases the complete workflow of the comparison framework:
    1. Creates a multi-question survey about cities (neighborhoods, US location, landmarks)
    2. Runs the survey across multiple cities with different AI models
    3. Uses caching to avoid re-running expensive API calls
    4. Compares results between different AI models for each city
    5. Displays rich comparison tables and exports to scenario lists

    The demo uses:
    - Three cities: London, Paris, Pittsburgh
    - Two AI models: GPT-4o-mini and Gemini-2.0-flash
    - Three question types: FreeText, YesNo, and List
    - Multiple comparison metrics: ExactMatch, CosineSimilarity (2 models), Overlap

    Example output includes:
    - Rich tables showing side-by-side comparisons
    - Similarity scores for semantic analysis
    - Question type and metadata display
    - Structured data export capabilities

    Note:
        Requires EDSL to be properly configured with API credentials for
        both OpenAI and Google models. Uses local caching to avoid
        repeated expensive API calls during development.
    """

    console = Console() if Console else None
    
    from itertools import combinations
    from edsl import QuestionFreeText, ScenarioList, Model, QuestionYesNo, QuestionList

    models = [Model("gpt-4o-mini"), Model("gemini-2.0-flash-exp", service_name = "google")]

    job = (
        QuestionFreeText(
            question_name="neighbourhoods",
            question_text="What are the key neighbourhoods in {{ scenario.city }}?",
        ).add_question(
            QuestionYesNo(
            question_name="in_us",
            question_text="Is {{ scenario.city }} in the United States?",
            )
        ).add_question(
            QuestionList(
            question_name="key_landmarks",
            question_text="What are the key landmarks in {{ scenario.city }}?",
            )
        )).by(ScenarioList.from_list("city", ["London", "Paris", "Pittsburgh"])).by(models)
    
    # Use the simplified context-manager that takes the job directly
    with local_results_cache(job) as results:
        buckets = results.bucket_by("city")

        factory = ComparisonFactory.with_defaults()

        for city, results in buckets.items():
            print("Now comparing", city[0])
            for result_A, result_B in combinations(results, 2):
                print("Comparing", result_A.model.model, "and", result_B.model.model)
                comparison = factory.compare_results(result_A, result_B)
                try:
                    table = comparison.render_table()
                    if console:
                        console.print(table)
                    else:
                        print(table)  # Rich Table has a decent __str__ method
                except ImportError as e:
                    # Fallback to plain text when rich is not available
                    print(f"\nComparison results for {city[0]} ({e}):")
                    print(f"Models: {result_A.model.model} vs {result_B.model.model}")
                    for q, answer_comparison in comparison.items():
                        print(f"\nQuestion: {q}")
                        print(f"  Answer A: {answer_comparison.answer_a}")
                        print(f"  Answer B: {answer_comparison.answer_b}")
                        for metric_name in [str(fn) for fn in factory.comparison_fns]:
                            value = getattr(answer_comparison, metric_name, 'N/A')
                            print(f"  {metric_name}: {value}")

                scenario_list = comparison.to_scenario_list()
  
  

if __name__ == "__main__":
    main()
    