"""Compare two EmbeddingsEngine instances with cross-distance and joint views."""

from __future__ import annotations

from typing import List, Tuple, Optional, Any, Dict
import math

from .embeddings_visualization import EmbeddingsEngineVisualization as Viz


class EmbeddingsComparison:
    """Comparison helper for two engines: left (e1) and right (e2)."""

    def __init__(self, left: "Any", right: "Any") -> None:
        self.left = left
        self.right = right

    # --- Data helpers ---
    def ids_vectors(self) -> Tuple[List[str], List[List[float]], List[str], List[List[float]]]:
        ids1, vecs1 = self._get_ids_vectors(self.left)
        ids2, vecs2 = self._get_ids_vectors(self.right)
        return ids1, vecs1, ids2, vecs2

    def cross_similarity_matrix(self) -> Tuple[List[str], List[str], List[List[float]]]:
        ids1, vecs1, ids2, vecs2 = self.ids_vectors()
        matrix: List[List[float]] = []
        for v1 in vecs1:
            row: List[float] = []
            for v2 in vecs2:
                row.append(self.left._cosine_similarity(v1, v2))  # noqa: SLF001
            matrix.append(row)
        return ids1, ids2, matrix

    # --- Views ---
    def cross_distance_heatmap(self, **kwargs: Any) -> "CrossDistanceHeatmapView":
        """Return a view for left-vs-right cosine similarities heatmap.

        The view supports to_svg/save/open/show and auto-renders in notebooks.
        """
        return CrossDistanceHeatmapView(self, **kwargs)

    def bipartite_nearest_neighbors(self, width: int = 900, height: int = 600, label_size: int = 12) -> str:
        """Draw bipartite graph: left ids on left, right ids on right; arrows to nearest neighbor across sets."""
        ids1, vecs1, ids2, vecs2 = self.ids_vectors()
        # Layout: left column x=120, right column x=width-120, spread vertically
        margin = 20
        left_x = 120
        right_x = width - 120
        def spread(n: int) -> List[float]:
            if n <= 1:
                return [height/2]
            top = margin + 40
            bottom = height - margin - 40
            return [top + i*(bottom-top)/(n-1) for i in range(n)]

        left_y = spread(len(ids1))
        right_y = spread(len(ids2))

        # For each left, find nearest right
        def cosine(a: List[float], b: List[float]) -> float:
            return self.left._cosine_similarity(a, b)  # noqa: SLF001

        arrows: List[Tuple[Tuple[float,float], Tuple[float,float], str, str, float]] = []
        for i, v1 in enumerate(vecs1):
            best_j = None
            best_sim = -2.0
            for j, v2 in enumerate(vecs2):
                sim = cosine(v1, v2)
                if sim > best_sim:
                    best_sim, best_j = sim, j
            if best_j is not None:
                arrows.append(((left_x, left_y[i]), (right_x, right_y[best_j]), ids1[i], ids2[best_j], best_sim))

        parts: List[str] = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
            "<rect width='100%' height='100%' fill='white' />",
        ]
        # Draw nodes
        for x, y, doc_id in [(left_x, left_y[i], ids1[i]) for i in range(len(ids1))]:
            label = Viz._escape(Viz._truncate(doc_id, 24))
            parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='#1f77b4' />")
            parts.append(f"<text x='{x - 8:.1f}' y='{y + 4:.1f}' font-size='{label_size}' text-anchor='end' fill='#333'>{label}</text>")
        for x, y, doc_id in [(right_x, right_y[i], ids2[i]) for i in range(len(ids2))]:
            label = Viz._escape(Viz._truncate(doc_id, 24))
            parts.append(f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='#ff7f0e' />")
            parts.append(f"<text x='{x + 8:.1f}' y='{y + 4:.1f}' font-size='{label_size}' text-anchor='start' fill='#333'>{label}</text>")

        # Draw arrows with width mapped to similarity
        for (x1, y1), (x2, y2), idl, idr, sim in arrows:
            stroke_w = 0.5 + 2.0 * max(0.0, sim)  # 0..2.5
            opacity = 0.25 + 0.5 * max(0.0, sim)
            parts.append(
                f"<line x1='{x1:.1f}' y1='{y1:.1f}' x2='{x2:.1f}' y2='{y2:.1f}' stroke='#444' stroke-opacity='{opacity:.2f}' stroke-width='{stroke_w:.2f}' marker-end='url(#arrow)' />"
            )

        # Arrow marker definition
        parts.insert(1, "<defs><marker id='arrow' markerWidth='10' markerHeight='7' refX='10' refY='3.5' orient='auto'><polygon points='0 0, 10 3.5, 0 7' fill='#444' /></marker></defs>")

        parts.append("</svg>")
        return "".join(parts)

    def joint_tsne(self, **kwargs: Any) -> str:
        """Run t-SNE over concatenated embeddings, color left vs right, draw hulls for each side."""
        ids1, vecs1, ids2, vecs2 = self.ids_vectors()
        # Create a fake engine-like object to reuse Viz.svg_tsne on concatenated data
        class _EngineLike:
            def __init__(self, ids: List[str], vecs: List[List[float]]):
                self.documents = [type("D", (), {"id": id_, "content": id_, "embedding": vec})() for id_, vec in zip(ids, vecs)]

        ids = [f"L:{i}" for i in ids1] + [f"R:{i}" for i in ids2]
        vecs = vecs1 + vecs2
        eng_like = _EngineLike(ids, vecs)
        # Build cluster assignments: 0 for left, 1 for right
        assignments = {id_: (0 if id_.startswith("L:") else 1) for id_ in ids}
        return Viz.svg_tsne(eng_like, cluster_assignments=assignments, draw_hulls=True, **kwargs)

    # --- internals ---
    @staticmethod
    def _get_ids_vectors(engine: "Any") -> Tuple[List[str], List[List[float]]]:
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
    def _get_ids_vectors_contents(engine: "Any") -> Tuple[List[str], List[List[float]], List[str]]:
        # ensure embeddings present
        missing = [i for i, d in enumerate(engine.documents) if d.embedding is None]
        if missing:
            texts = [engine.documents[i].content for i in missing]
            new_embeddings = engine.embedding_function.embed_documents(texts)
            for idx, emb in zip(missing, new_embeddings):
                engine.documents[idx].embedding = emb
        ids: List[str] = [doc.id for doc in engine.documents]
        vectors: List[List[float]] = [doc.embedding for doc in engine.documents]  # type: ignore
        contents: List[str] = [str(doc.content) for doc in engine.documents]
        return ids, vectors, contents


def _svg_cross_heatmap(
    ids_left: List[str],
    ids_right: List[str],
    matrix: List[List[float]],
    cell_size: int = 18,
    label_size: int = 12,
    padding: int = 6,
    *,
    left_labels: Optional[List[str]] = None,
    right_labels: Optional[List[str]] = None,
    left_tooltips: Optional[List[str]] = None,
    right_tooltips: Optional[List[str]] = None,
) -> str:
    nL, nR = len(ids_left), len(ids_right)
    if left_labels is None:
        left_labels = ids_left
    if right_labels is None:
        right_labels = ids_right

    # No wrapping; simple fixed spaces with vertical top labels
    approx_char_w = label_size * 0.6
    max_left_chars = max((len(lbl) for lbl in left_labels), default=1)
    label_space_left = max(int(approx_char_w * max_left_chars) + 14, label_size + 2, 24)
    # Ensure at least ~30 characters are visible above the grid for vertical labels
    min_visible_chars = 30
    top_height = int(approx_char_w * min_visible_chars) + 14
    label_space_top = max(top_height, label_size + 10, 60)
    width = padding * 2 + label_space_left + cell_size * nR
    height = padding * 2 + label_space_top + cell_size * nL
    parts: List[str] = [
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
        "<rect width='100%' height='100%' fill='white' />",
    ]
    # Draw cells first so labels render on top and are not covered
    for i in range(nL):
        for j in range(nR):
            val = float(matrix[i][j])
            fill = Viz._value_to_color(val)
            x = padding + label_space_left + j * cell_size
            y = padding + label_space_top + i * cell_size
            parts.append(f"<rect x='{x}' y='{y}' width='{cell_size}' height='{cell_size}' fill='{fill}' />")
    # Column labels (right ids) vertical with uniform origin and baseline
    for j, doc_id in enumerate(ids_right):
        # Pivot at the top-left of each column so the START of all strings aligns
        x = padding + label_space_left + j * cell_size
        y = padding + label_space_top
        text = Viz._escape(right_labels[j])
        title = Viz._escape(right_tooltips[j]) if right_tooltips and j < len(right_tooltips) else None
        parts.append(f"<g transform='translate({x},{y}) rotate(-90)'>")
        if title:
            parts.append(f"<text font-size='{label_size}' text-anchor='start' dominant-baseline='text-before-edge'><title>{title}</title>{text}</text>")
        else:
            parts.append(f"<text font-size='{label_size}' text-anchor='start' dominant-baseline='text-before-edge'>{text}</text>")
        parts.append("</g>")
    # Row labels (left ids)
    for i, doc_id in enumerate(ids_left):
        x = padding + label_space_left - 4
        y = padding + label_space_top + i * cell_size + cell_size * 0.7
        text = Viz._escape(left_labels[i])
        title = Viz._escape(left_tooltips[i]) if left_tooltips and i < len(left_tooltips) else None
        if title:
            parts.append(f"<text x='{x}' y='{y}' font-size='{label_size}' text-anchor='end'><title>{title}</title>{text}</text>")
        else:
            parts.append(f"<text x='{x}' y='{y}' font-size='{label_size}' text-anchor='end'>{text}</text>")
    # (cells were already drawn before labels)
    parts.append("</svg>")
    return "".join(parts)


class CrossDistanceHeatmapView:
    """Notebook-friendly view for cross-distance heatmap between two engines.

    Usage: EmbeddingsComparison(e1, e2).cross_distance_heatmap(...)
    """

    def __init__(
        self,
        comparison: EmbeddingsComparison,
        *,
        cell_size: int = 18,
        label_size: int = 12,
        padding: int = 6,
        show_snippets: bool = True,
        snippet_words: int = 8,
    ) -> None:
        self._cmp = comparison
        self._cell_size = cell_size
        self._label_size = label_size
        self._padding = padding
        self._show_snippets = show_snippets
        self._snippet_words = snippet_words
        self._svg_cache: Optional[str] = None

    def to_svg(self) -> str:
        if self._svg_cache is None:
            ids1, vecs1, contents1 = EmbeddingsComparison._get_ids_vectors_contents(self._cmp.left)
            ids2, vecs2, contents2 = EmbeddingsComparison._get_ids_vectors_contents(self._cmp.right)
            # recompute matrix using vecs to avoid double compute
            matrix: List[List[float]] = []
            for v1 in vecs1:
                row: List[float] = []
                for v2 in vecs2:
                    row.append(self._cmp.left._cosine_similarity(v1, v2))  # noqa: SLF001
                matrix.append(row)

            if self._show_snippets:
                def wrap_snip(text: str) -> str:
                    words = str(text).split()
                    if len(words) <= self._snippet_words:
                        return str(text)
                    return " ".join(words[: self._snippet_words]) + " …"
                left_labels = [wrap_snip(t) for t in contents1]
                right_labels = [wrap_snip(t) for t in contents2]
            else:
                left_labels = ids1
                right_labels = ids2

            self._svg_cache = _svg_cross_heatmap(
                ids1,
                ids2,
                matrix,
                cell_size=self._cell_size,
                label_size=self._label_size,
                padding=self._padding,
                left_labels=left_labels,
                right_labels=right_labels,
                left_tooltips=contents1,
                right_tooltips=contents2,
            )
        return self._svg_cache

    def save(self, path: str) -> str:
        svg = self.to_svg()
        if not path.lower().endswith(".svg"):
            path = path + ".svg"
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        return path

    def open(self, path: Optional[str] = None) -> str:
        import os
        import tempfile
        import subprocess
        svg_path = path or self.save(os.path.join(tempfile.gettempdir(), "embeddings_cross_distance.svg"))
        if path is None:
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(self.to_svg())
        try:
            if os.name == "nt":
                os.startfile(svg_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", svg_path])
            else:
                subprocess.Popen(["xdg-open", svg_path])
        except Exception:
            pass
        return svg_path

    def show(self) -> str:
        return self.to_svg()

    def _repr_html_(self) -> str:
        return self.to_svg()


