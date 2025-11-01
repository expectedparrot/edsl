"""Abstract embedding function interface for dependency injection."""

from abc import ABC, abstractmethod
import math
import hashlib
import random
import os
from typing import List, Dict, Type, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..key_management import KeyLookup

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None


class EmbeddingFunction(ABC):
    """Abstract base class for embedding functions.

    This allows for dependency injection of different embedding providers.
    """

    _registry: Dict[str, Type["EmbeddingFunction"]] = {}

    # Subclasses MUST define a unique short_name string
    short_name: str  # type: ignore[assignment]

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Do not enforce for the abstract base itself
        if cls is EmbeddingFunction:
            return
        name = getattr(cls, "short_name", None)
        if not isinstance(name, str) or not name:
            raise TypeError(
                f"{cls.__name__} must define a non-empty class attribute 'short_name'"
            )
        # Register subclass by short name
        EmbeddingFunction._registry[name] = cls

    @classmethod
    def get_class_by_name(cls, name: str) -> Type["EmbeddingFunction"]:
        """Return the EmbeddingFunction subclass registered for this short name."""
        if name not in cls._registry:
            raise KeyError(f"No embedding function registered under name '{name}'")
        return cls._registry[name]

    @classmethod
    def create_by_name(cls, name: str, **kwargs: Any) -> "EmbeddingFunction":
        """Instantiate a registered embedding function by its short name."""
        subclass = cls.get_class_by_name(name)
        return subclass(**kwargs)

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of documents.

        Args:
            texts: List of text documents to embed

        Returns:
            List of embedding vectors, one for each input text
        """
        pass

    @abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single query text.

        Args:
            text: Query text to embed

        Returns:
            Embedding vector for the query
        """
        pass


class MockEmbeddingFunction(EmbeddingFunction):
    """Mock embedding function that generates random vectors.

    By default, this produces 1536-dimensional vectors to match common
    OpenAI embedding sizes (e.g., ``text-embedding-3-small``).

    Args:
        embedding_dim: Length of the embedding vectors to generate.
        normalize: If ``True``, L2-normalize each generated vector.

    Examples:
        Deterministic per-text embeddings and expected shapes:

        >>> f = MockEmbeddingFunction(embedding_dim=5)
        >>> v1 = f.embed_query("hello")
        >>> v2 = f.embed_query("hello")
        >>> v1 == v2
        True
        >>> len(v1)
        5
        >>> f.embed_query("hello") == f.embed_query("world")
        False

        Show a concise view of the beginning and end of the vector:

        >>> f = MockEmbeddingFunction(embedding_dim=6)
        >>> v = f.embed_query("x")
        >>> print(f"{v[:2]} ... {v[-2:]}")  # doctest: +ELLIPSIS
        [..., ...] ... [..., ...]

        Normalized embeddings have unit L2 norm (approximately 1.0):

        >>> f = MockEmbeddingFunction(embedding_dim=5, normalize=True)
        >>> v = f.embed_query("hello")
        >>> round(sum(x*x for x in v), 1)
        1.0
    """

    # Registry short name for serialization/deserialization
    short_name = "mock"

    def __init__(
        self,
        embedding_dim: int = 1536,
        normalize: bool = False,
    ) -> None:
        self.embedding_dim = embedding_dim
        self._normalize = normalize

    def _rng_for_text(self, text: str) -> random.Random:
        """Create a deterministic RNG seeded from md5(text)."""
        digest = hashlib.md5(text.encode("utf-8")).hexdigest()
        seed_int = int(digest, 16)
        return random.Random(seed_int)

    def _generate_vector(self, rng: random.Random) -> List[float]:
        vector = [rng.random() for _ in range(self.embedding_dim)]
        if self._normalize:
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vector = [value / norm for value in vector]
        return vector

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of documents.

        Args:
            texts: List of text documents to embed.

        Returns:
            List of embedding vectors, one for each input text.

        Examples:
            >>> f = MockEmbeddingFunction(embedding_dim=4)
            >>> docs = ["alpha", "beta"]
            >>> embs = f.embed_documents(docs)
            >>> len(embs), len(embs[0]), len(embs[1])
            (2, 4, 4)
            >>> embs[0] == f.embed_query("alpha")
            True
        """
        return [self._generate_vector(self._rng_for_text(text)) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        """Generate an embedding for a single query text.

        Examples:
            >>> f = MockEmbeddingFunction(embedding_dim=5)
            >>> v = f.embed_query("hello")
            >>> len(v)
            5
            >>> f.embed_query("hello") == f.embed_query("hello")
            True
        """
        return self._generate_vector(self._rng_for_text(text))


class OpenAIEmbeddingFunction(EmbeddingFunction):
    """OpenAI embedding function using the official OpenAI SDK.

    API key can be provided via EDSL's KeyLookup system, explicit parameter, or environment variable.
    Optionally reads from a ``.env`` file if python-dotenv is installed.

    Args:
        model: OpenAI embedding model name, e.g., ``text-embedding-3-small``.
        api_key: Explicit API key. If not provided, uses KeyLookup system or ``OPENAI_API_KEY`` env var.
        organization: Optional OpenAI organization.
        normalize: If ``True``, L2-normalize each returned vector.
        key_lookup: EDSL KeyLookup instance for retrieving API credentials.

    Examples:
        >>> # Using EDSL's KeyLookup system
        >>> from edsl.key_management import KeyLookupBuilder
        >>> from .embedding_function import OpenAIEmbeddingFunction  # doctest: +SKIP
        >>> key_lookup = KeyLookupBuilder().build()  # doctest: +SKIP
        >>> f = OpenAIEmbeddingFunction(key_lookup=key_lookup)  # doctest: +SKIP
        >>> v = f.embed_query("hello")  # doctest: +SKIP
        >>> isinstance(v, list) and isinstance(v[0], float)  # doctest: +SKIP
        True
    """

    short_name = "openai"

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        normalize: bool = False,
        key_lookup: Optional["KeyLookup"] = None,
    ) -> None:
        # Attempt to load .env if available
        if load_dotenv is not None:
            try:
                load_dotenv()
            except Exception:
                pass

        # Lazily import to avoid hard dependency when unused
        try:
            from openai import OpenAI  # type: ignore
        except Exception as e:  # pragma: no cover - depends on env
            raise ImportError(
                "The 'openai' package is required for OpenAIEmbeddingFunction. Install with 'pip install openai'."
            ) from e

        self.model = model
        self._normalize = normalize

        # Use KeyLookup system if available, fall back to direct API key or env var
        if key_lookup is not None:
            try:
                openai_info = key_lookup.get("openai")
                if openai_info is not None:
                    resolved_api_key = openai_info.api_token
                else:
                    resolved_api_key = None
            except (KeyError, AttributeError):
                resolved_api_key = None
        else:
            resolved_api_key = None

        # Fall back to explicit api_key parameter or environment variable
        if not resolved_api_key:
            resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not resolved_api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY not found. Provide via KeyLookup, api_key parameter, or environment variable."
            )

        # Create client with explicit credentials if provided
        client_kwargs: Dict[str, Any] = {"api_key": resolved_api_key}
        if organization:
            client_kwargs["organization"] = organization
        self._client = OpenAI(**client_kwargs)  # type: ignore

    def _maybe_normalize(self, vectors: List[List[float]]) -> List[List[float]]:
        if not self._normalize:
            return vectors
        normalized: List[List[float]] = []
        for vector in vectors:
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            normalized.append([value / norm for value in vector])
        return normalized

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        resp = self._client.embeddings.create(model=self.model, input=texts)  # type: ignore[attr-defined]
        vectors = [item.embedding for item in resp.data]
        return self._maybe_normalize(vectors)

    def embed_query(self, text: str) -> List[float]:
        resp = self._client.embeddings.create(model=self.model, input=[text])  # type: ignore[attr-defined]
        vector = resp.data[0].embedding
        if self._normalize:
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vector = [value / norm for value in vector]
        return vector


if __name__ == "__main__":
    """Quick demo: compute cosine similarity between sentences using OpenAI embeddings.

    Uses EDSL's KeyLookup system or falls back to OPENAI_API_KEY environment variable.
    """
    try:
        from ..key_management import KeyLookupBuilder

        key_lookup = KeyLookupBuilder().build()
        embedder = OpenAIEmbeddingFunction(
            model="text-embedding-3-small", normalize=True, key_lookup=key_lookup
        )
    except Exception as exc:  # pragma: no cover - runtime/demo-only
        print(f"Failed to initialize OpenAIEmbeddingFunction: {exc}")
        raise SystemExit(1)

    sentences = [
        "A man is eating food.",
        "A man is eating a piece of bread.",
        "The weather is sunny today.",
    ]
    vectors = embedder.embed_documents(sentences)

    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        if getattr(embedder, "_normalize", False):
            return dot_product
        mag1 = math.sqrt(sum(a * a for a in vec1))
        mag2 = math.sqrt(sum(a * a for a in vec2))
        denom = (mag1 * mag2) or 1.0
        return dot_product / denom

    pairs = [(0, 1), (0, 2), (1, 2)]
    for i, j in pairs:
        sim = cosine_similarity(vectors[i], vectors[j])
        print(f"cosine({sentences[i]!r}, {sentences[j]!r}) = {sim:.4f}")
