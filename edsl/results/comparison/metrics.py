"""Metric functions for comparing two answers.

Each metric is a plain function: (a, b) -> float | bool | None.
MetricsCollection bundles metrics and computes all of them for a pair.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Callable, Dict, Optional, Union

Metric = Callable[[Any, Any], Optional[Union[float, bool]]]


def exact_match(a: Any, b: Any) -> bool:
    """Return True if a == b.

    >>> exact_match("yes", "yes")
    True
    >>> exact_match("yes", "no")
    False
    >>> exact_match(1, 1)
    True
    """
    return a == b


def _is_sequence(obj: Any) -> bool:
    return isinstance(obj, Iterable) and not isinstance(obj, (str, bytes))


def overlap(a: Any, b: Any) -> Optional[float]:
    """Intersection / min(len(a), len(b)) for iterables; None for non-iterables.

    >>> overlap(["a", "b", "c"], ["b", "c", "d"])
    0.6666666666666666
    >>> overlap("hello", "world") is None
    True
    >>> overlap([], ["a"])
    0.0
    >>> overlap(["a", "b"], ["a", "b"])
    1.0
    """
    if not (_is_sequence(a) and _is_sequence(b)):
        return None
    set_a, set_b = set(a), set(b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / min(len(set_a), len(set_b))


def jaccard_similarity(a: Any, b: Any) -> Optional[float]:
    """Intersection / union for iterables; None for non-iterables.

    >>> jaccard_similarity(["a", "b", "c"], ["b", "c", "d"])
    0.5
    >>> jaccard_similarity("hello", "world") is None
    True
    >>> jaccard_similarity([], [])
    1.0
    >>> jaccard_similarity([], ["a"])
    0.0
    """
    if not (_is_sequence(a) and _is_sequence(b)):
        return None
    set_a, set_b = set(a), set(b)
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


EmbedFn = Callable[[str], Any]  # returns a vector (list/ndarray)


def _cosine_sim(vec_a, vec_b) -> float:
    from numpy import dot
    from numpy.linalg import norm

    return float(dot(vec_a, vec_b) / (norm(vec_a) * norm(vec_b)))


def cosine_metric_from_embed_fn(embed_fn: EmbedFn) -> Metric:
    """Build a cosine-similarity metric from any embedding function.

    ``embed_fn`` should accept a string and return a vector (list or ndarray).

    Usage::

        # OpenAI
        metrics["cosine"] = cosine_metric_from_embed_fn(my_openai_embed)

        # Any custom embedder
        metrics["cosine"] = cosine_metric_from_embed_fn(lambda s: my_model.encode(s))

    >>> import numpy as np
    >>> dummy_embed = lambda s: np.array([1.0, 0.0]) if s == "hello" else np.array([0.0, 1.0])
    >>> metric = cosine_metric_from_embed_fn(dummy_embed)
    >>> metric("hello", "hello")
    1.0
    >>> metric("hello", "world")
    0.0
    >>> metric(123, "hello") is None
    True
    """

    def cosine_similarity(a: Any, b: Any) -> Optional[float]:
        if not isinstance(a, str) or not isinstance(b, str):
            return None
        return _cosine_sim(embed_fn(a), embed_fn(b))

    return cosine_similarity


def make_cosine_metric(model_name: str = "all-MiniLM-L6-v2") -> Metric:
    """Return a cosine-similarity metric using sentence-transformers.

    Usage::

        metrics = default_metrics()
        metrics["cosine"] = make_cosine_metric()
        mc = MetricsCollection(metrics)
    """
    _model = None

    def embed(text: str):
        nonlocal _model
        if _model is None:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(model_name)
        return _model.encode(text)

    return cosine_metric_from_embed_fn(embed)


def make_openai_cosine_metric(
    model: str = "text-embedding-3-small",
    client: Any = None,
) -> Metric:
    """Return a cosine-similarity metric using OpenAI embeddings.

    Usage::

        metrics = default_metrics()
        metrics["cosine"] = make_openai_cosine_metric()
        mc = MetricsCollection(metrics)

        # Or with a custom client
        from openai import OpenAI
        metrics["cosine"] = make_openai_cosine_metric(client=OpenAI(api_key="..."))
    """
    _client = client

    def embed(text: str):
        nonlocal _client
        if _client is None:
            from openai import OpenAI

            _client = OpenAI()
        response = _client.embeddings.create(input=text, model=model)
        return response.data[0].embedding

    return cosine_metric_from_embed_fn(embed)


def default_metrics() -> Dict[str, Metric]:
    """Return the default set of metrics."""
    return {
        "exact_match": exact_match,
        "overlap": overlap,
        "jaccard_similarity": jaccard_similarity,
    }


class MetricsCollection:
    """Thin wrapper: holds a dict of {name: metric_fn}, computes all metrics for a pair.

    >>> mc = MetricsCollection()
    >>> result = mc.compute("hello", "hello")
    >>> result["exact_match"]
    True
    >>> result["overlap"] is None
    True
    """

    def __init__(self, metrics: Dict[str, Metric] | None = None):
        self.metrics = metrics if metrics is not None else default_metrics()

    def compute(self, a: Any, b: Any) -> Dict[str, Any]:
        return {name: fn(a, b) for name, fn in self.metrics.items()}

    @property
    def metric_names(self) -> list[str]:
        return list(self.metrics.keys())


if __name__ == "__main__":
    import doctest

    doctest.testmod()
