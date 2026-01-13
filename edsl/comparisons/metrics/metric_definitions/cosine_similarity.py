from __future__ import annotations

"""Cosine similarity comparison metric for EDSL answers."""

from typing import List, Any, TYPE_CHECKING
from ..metrics_abc import ComparisonFunction, optional_import

if TYPE_CHECKING:
    import numpy as np


# Defer imports until needed - check availability without importing
def _check_sentence_transformers_available():
    """Check if sentence_transformers is available without importing it."""
    try:
        import importlib.util

        spec = importlib.util.find_spec("sentence_transformers")
        return spec is not None
    except (ImportError, ValueError):
        return False


# Simple availability checks (without importing)
SENTENCE_TRANSFORMERS_AVAILABLE = _check_sentence_transformers_available()


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
        # Lazy import - only load when actually instantiating
        sentence_transformers = optional_import(
            "sentence_transformers",
            install_name="sentence-transformers",
            description="sentence-transformers (required for semantic similarity)",
        )
        SentenceTransformer = getattr(
            sentence_transformers, "SentenceTransformer", None
        )
        self.model = SentenceTransformer(
            model_name
        )  # Will raise ImportError with helpful message if missing

    def __str__(self) -> str:
        """Return string representation including model name."""
        return f"{self.short_name} ({self.model_name})"

    def _get_init_params(self) -> dict[str, Any]:
        """Return initialization parameters for serialization."""
        return {"model_name": self.model_name}

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

        import numpy as np

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
