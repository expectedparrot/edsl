"""Clustering utilities for EmbeddingsEngine documents.

Provides DBSCAN clustering with optional search to approximate a target number
of clusters by sweeping eps and selecting the setting with closest cluster count
to the target (excluding noise).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

try:  # Optional dependency
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover
    _np = None  # type: ignore

try:  # Optional dependency
    from sklearn.cluster import DBSCAN as _DBSCAN  # type: ignore
except Exception:  # pragma: no cover
    _DBSCAN = None  # type: ignore


@dataclass
class DBSCANClusteringResult:
    labels: List[int]
    clusters: Dict[int, List[int]]
    noise_indices: List[int]
    params: Dict[str, Any]
    doc_ids: List[str]
    clusters_doc_ids: Dict[int, List[str]]
    noise_doc_ids: List[str]

    def summary(self) -> Dict[str, Any]:
        return {
            "num_clusters": len(self.clusters),
            "cluster_sizes": {cid: len(ixs) for cid, ixs in self.clusters.items()},
            "num_noise": len(self.noise_indices),
            "params": self.params,
        }


class EmbeddingsClustering:
    """Static entry points for clustering engine documents."""

    @staticmethod
    def dbscan(
        engine: "Any",
        eps: Optional[float] = None,
        min_samples: int = 3,
        metric: str = "cosine",
        target_num_clusters: Optional[int] = None,
        eps_grid: Optional[List[float]] = None,
        random_state: Optional[int] = 42,
    ) -> DBSCANClusteringResult:
        """Run DBSCAN on document embeddings.

        If `target_num_clusters` is provided and eps is None, sweep eps over
        a grid to approximate the target cluster count (noise excluded).
        """
        if _DBSCAN is None:
            raise ImportError("scikit-learn is required for DBSCAN clustering.")
        ids, vectors = EmbeddingsClustering._get_vectors(engine)
        if not vectors:
            return DBSCANClusteringResult(labels=[], clusters={}, noise_indices=[], params={})

        if eps is None and target_num_clusters is not None:
            if eps_grid is None:
                eps_grid = EmbeddingsClustering._default_eps_grid(len(ids))
            best = None
            for candidate in eps_grid:
                labels = EmbeddingsClustering._fit_dbscan(vectors, candidate, min_samples, metric)
                num_clusters = EmbeddingsClustering._count_clusters(labels)
                score = abs(num_clusters - target_num_clusters)
                if best is None or score < best[0]:
                    best = (score, candidate, labels)
            assert best is not None
            _, eps, labels = best
        else:
            if eps is None:
                eps = 0.5
            labels = EmbeddingsClustering._fit_dbscan(vectors, eps, min_samples, metric)

        clusters: Dict[int, List[int]] = {}
        noise_indices: List[int] = []
        for idx, label in enumerate(labels):
            if label == -1:
                noise_indices.append(idx)
            else:
                clusters.setdefault(label, []).append(idx)

        clusters_doc_ids: Dict[int, List[str]] = {cid: [ids[i] for i in ix] for cid, ix in clusters.items()}
        noise_doc_ids: List[str] = [ids[i] for i in noise_indices]

        return DBSCANClusteringResult(
            labels=labels,
            clusters=clusters,
            noise_indices=noise_indices,
            params={
                "eps": eps,
                "min_samples": min_samples,
                "metric": metric,
                "target_num_clusters": target_num_clusters,
            },
            doc_ids=ids,
            clusters_doc_ids=clusters_doc_ids,
            noise_doc_ids=noise_doc_ids,
        )

    @staticmethod
    def _fit_dbscan(vectors: List[List[float]], eps: float, min_samples: int, metric: str) -> List[int]:
        if _np is None:
            raise ImportError("NumPy is required for clustering.")
        X = _np.asarray(vectors, dtype=float)
        # Cosine distance handled via metric='cosine' in sklearn DBSCAN with precomputed? We use metric=cosine directly.
        model = _DBSCAN(eps=eps, min_samples=min_samples, metric=metric)
        labels = model.fit_predict(X)  # type: ignore[arg-type]
        return labels.tolist()

    @staticmethod
    def _count_clusters(labels: List[int]) -> int:
        return len({label for label in labels if label != -1})

    @staticmethod
    def _get_vectors(engine: "Any") -> Tuple[List[str], List[List[float]]]:
        # Ensure embeddings present
        missing = [i for i, d in enumerate(engine.documents) if d.embedding is None]
        if missing:
            texts = [engine.documents[i].content for i in missing]
            new_embeddings = engine.embedding_function.embed_documents(texts)
            for idx, emb in zip(missing, new_embeddings):
                engine.documents[idx].embedding = emb
        ids: List[str] = [doc.id for doc in engine.documents]
        vectors: List[List[float]] = [doc.embedding for doc in engine.documents]  # type: ignore
        return ids, vectors

    @staticmethod
    def _default_eps_grid(n: int) -> List[float]:
        # Reasonable default sweep
        return [0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7]


