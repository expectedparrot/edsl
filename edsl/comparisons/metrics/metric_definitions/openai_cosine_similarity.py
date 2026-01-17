from __future__ import annotations

"""OpenAI embeddings-based cosine similarity metric for EDSL answers."""

from typing import List, Any, Optional
from ..metrics_abc import ComparisonFunction


class OpenAICosineSimilarity(ComparisonFunction):
    """Computes semantic similarity using OpenAI embeddings and cosine similarity.

    This comparison function uses OpenAI's text embedding models to convert
    text answers into high-dimensional embeddings, then computes cosine similarity
    between corresponding answer pairs. Values range from 0 to 1, where higher
    values indicate more similar meaning.

    Unlike the sentence-transformers based CosineSimilarity, this metric:
    - Requires an OpenAI API key
    - Has no heavy local dependencies
    - Uses OpenAI's high-quality embeddings

    Args:
        api_key: OpenAI API key (required)
        model: Embedding model to use (default: "text-embedding-3-small")

    Examples:
        Basic semantic similarity:

        >>> # Requires OPENAI_API_KEY
        >>> cosine = OpenAICosineSimilarity(api_key="sk-...")
        >>> answers_A = ["The cat is happy", "I like pizza"]
        >>> answers_B = ["A happy feline", "Pizza is delicious"]
        >>> similarities = cosine.execute(answers_A, answers_B)
        >>> len(similarities) == 2
        True
        >>> all(0.0 <= sim <= 1.0 for sim in similarities)
        True
    """

    short_name = "openai_cosine_similarity"

    SUPPORTED_MODELS = {
        "text-embedding-3-small": {"dimensions": 1536},
        "text-embedding-3-large": {"dimensions": 3072},
        "text-embedding-ada-002": {"dimensions": 1536},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
    ):
        """Initialize with OpenAI API key and model.

        Args:
            api_key: OpenAI API key
            model: Embedding model name. Options:
                   - "text-embedding-3-small": Fast, 1536-dim, good quality (default)
                   - "text-embedding-3-large": Slower, 3072-dim, best quality
                   - "text-embedding-ada-002": Legacy model, 1536-dim
        """
        if not api_key:
            raise ValueError("api_key is required for OpenAICosineSimilarity")

        self.api_key = api_key
        self.model = model
        self._client = None  # Lazy initialization

    def _get_client(self):
        """Get or create OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai is required for OpenAICosineSimilarity. "
                    "Install with: pip install openai"
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def __str__(self) -> str:
        """Return string representation including model name."""
        return f"{self.short_name} ({self.model})"

    def _get_init_params(self) -> dict[str, Any]:
        """Return initialization parameters for serialization.

        Note: api_key is intentionally excluded for security.
        """
        return {"model": self.model}

    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[float]:
        """Compute cosine similarity between corresponding answer pairs using OpenAI embeddings.

        Args:
            answers_A: First list of text answers
            answers_B: Second list of text answers
            questions: Unused in this implementation

        Returns:
            List of cosine similarity scores between 0 and 1, where:
            - 1.0: Identical semantic meaning
            - 0.5: Low semantic relationship
            - 0.0: No semantic relationship
        """
        import math

        # Convert all answers to strings
        def to_string(answer):
            if isinstance(answer, list):
                return ", ".join(str(item) for item in answer)
            return str(answer) if answer is not None else ""

        answers_A_str = [to_string(a) for a in answers_A]
        answers_B_str = [to_string(b) for b in answers_B]

        # Batch all texts together for efficiency
        all_texts = answers_A_str + answers_B_str

        # Get embeddings from OpenAI
        client = self._get_client()
        response = client.embeddings.create(model=self.model, input=all_texts)

        # Extract embedding vectors
        embeddings = [emb.embedding for emb in response.data]
        n = len(answers_A)

        # Compute cosine similarity for each pair
        def cosine_sim(a: List[float], b: List[float]) -> float:
            dot = sum(x * y for x, y in zip(a, b))
            mag_a = math.sqrt(sum(x * x for x in a))
            mag_b = math.sqrt(sum(x * x for x in b))
            if mag_a == 0 or mag_b == 0:
                return 0.0
            return dot / (mag_a * mag_b)

        similarities: List[float] = []
        for i in range(n):
            ea = embeddings[i]
            eb = embeddings[i + n]
            # Cosine similarity already in [0, 1] for normalized embeddings
            # but can be [-1, 1] in general, so normalize
            raw_sim = cosine_sim(ea, eb)
            # Normalize from [-1, 1] to [0, 1]
            normalized_sim = (raw_sim + 1.0) / 2.0
            similarities.append(normalized_sim)

        return similarities
