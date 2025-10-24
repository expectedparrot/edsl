"""Visualization utilities for `EmbeddingsEngine`.

Provides:
- Computation of cosine similarity matrix between engine documents
- SVG heatmap rendering of the similarity matrix
- t-SNE (or PCA fallback) 2D scatter plot as SVG with document labels

External dependencies are optional:
- If scikit-learn is available, t-SNE is used.
- If NumPy is available, PCA is used as a fallback for 2D projection.
- If neither is available, a deterministic pseudo-random layout is used.
"""

from __future__ import annotations

from typing import List, Tuple, Optional, Any
import math
import hashlib
import sys

try:  # Optional dependency
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - optional
    _np = None  # type: ignore

try:  # Optional dependency
    from sklearn.manifold import TSNE as _TSNE  # type: ignore
except Exception:  # pragma: no cover - optional
    _TSNE = None  # type: ignore


class EmbeddingsEngineVisualization:
    """Static helpers to visualize an `EmbeddingsEngine`.

    This module does not mutate the engine; it only reads from it and, when
    necessary, lazily computes any missing embeddings in batch to enable
    visualization.
    """

    # ----------------------- Public API -----------------------
    @staticmethod
    def compute_similarity_matrix(engine: "Any") -> Tuple[List[str], List[List[float]]]:
        """Return document ids and their pairwise cosine similarity matrix.

        Missing embeddings are computed in batch. The similarity is in [-1, 1].
        Returns (ids, matrix) where matrix[i][j] is similarity(doc_i, doc_j).
        """
        EmbeddingsEngineVisualization._ensure_all_embeddings(engine)

        ids: List[str] = [doc.id for doc in engine.documents]
        vectors: List[List[float]] = [doc.embedding for doc in engine.documents]  # type: ignore
        matrix: List[List[float]] = []

        for i in range(len(vectors)):
            row: List[float] = []
            for j in range(len(vectors)):
                sim = engine._cosine_similarity(
                    vectors[i], vectors[j]
                )  # noqa: SLF001 (intentional use)
                row.append(sim)
            matrix.append(row)
        return ids, matrix

    @staticmethod
    def svg_similarity_heatmap(
        engine: "Any",
        cell_size: int = 18,
        label_size: int = 12,
        padding: int = 6,
        show_values: bool = False,
        *,
        upper_triangle: bool = True,
        include_diagonal: bool = False,
        auto_scale: bool = True,
        min_total_pixels: int = 400,
        instant_tooltips: bool = True,
    ) -> str:
        """Render the cosine similarity matrix as an SVG heatmap.

        Args:
            engine: EmbeddingsEngine instance.
            cell_size: Size of each heatmap cell in pixels.
            label_size: Font size for axis labels.
            padding: Padding around the heatmap.
            show_values: If True, overlay the numeric similarity values.
        """
        ids, matrix = EmbeddingsEngineVisualization.compute_similarity_matrix(engine)
        n = len(ids)
        if n == 0:
            return EmbeddingsEngineVisualization._svg_empty("No documents to visualize")

        # Dynamic scaling: ensure overall graphic is reasonably large
        if auto_scale and n > 0:
            target = max(min_total_pixels, n * cell_size)
            # Compute a cell size that yields at least target pixels for the grid
            cell_size = max(cell_size, int(math.ceil(target / n)))

        # Layout dimensions with separate left/top label spaces
        approx_char_w = label_size * 0.6
        # Left labels use ids; estimate width from longest id (up to 18 chars like we display)
        left_label_lengths = [
            len(EmbeddingsEngineVisualization._truncate(doc_id, 18)) for doc_id in ids
        ]
        label_space_left = max(
            int(approx_char_w * (max(left_label_lengths) if left_label_lengths else 1))
            + 14,
            label_size + 2,
            14,
        )
        # Top labels are vertical; estimate required height from longest label (up to 18 chars)
        top_label_lengths = left_label_lengths  # same ids
        label_space_top = max(
            int(approx_char_w * (max(top_label_lengths) if top_label_lengths else 1))
            + 14,
            label_size + 2,
            24,
        )
        width = padding * 2 + label_space_left + cell_size * n
        height = padding * 2 + label_space_top + cell_size * n

        # Build SVG elements
        parts: List[str] = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
            "<rect width='100%' height='100%' fill='white' />",
        ]
        if instant_tooltips:
            parts.append(
                "<style>"
                ".cell .tip{visibility:hidden;opacity:0;transition:opacity 0.05s linear;}"
                ".cell:hover .tip{visibility:visible;opacity:1;}"
                ".cell rect{pointer-events:all;}"
                "</style>"
            )

        # Axis labels
        for i, doc_id in enumerate(ids):
            # Vertical labels centered over each square for consistent spacing
            x = padding + label_space_left + i * cell_size + cell_size / 2
            y = padding + label_space_top - 4
            truncated = EmbeddingsEngineVisualization._truncate(doc_id, 18)
            parts.append(
                f"<text x='{x}' y='{y}' font-size='{label_size}' text-anchor='middle' dominant-baseline='text-before-edge' transform='rotate(-90 {x} {y})'>{EmbeddingsEngineVisualization._escape(truncated)}</text>"
            )

        for i, doc_id in enumerate(ids):
            x = padding + label_space_left - 4
            y = padding + label_space_top + i * cell_size + cell_size * 0.7
            truncated = EmbeddingsEngineVisualization._truncate(doc_id, 18)
            parts.append(
                f"<text x='{x}' y='{y}' font-size='{label_size}' text-anchor='end'>{EmbeddingsEngineVisualization._escape(truncated)}</text>"
            )

        # Preload contents for tooltips
        contents: List[str] = [str(doc.content) for doc in engine.documents]

        # Cells
        for r in range(n):
            for c in range(n):
                if upper_triangle:
                    if c < r:
                        continue
                    if c == r and not include_diagonal:
                        continue
                value = matrix[r][c]
                fill = EmbeddingsEngineVisualization._value_to_color(value)
                x = padding + label_space_left + c * cell_size
                y = padding + label_space_top + r * cell_size
                if instant_tooltips:
                    # Build tooltip with row/col ids and contents
                    row_id = EmbeddingsEngineVisualization._escape(ids[r])
                    col_id = EmbeddingsEngineVisualization._escape(ids[c])
                    row_lines = EmbeddingsEngineVisualization._wrap_text_words(
                        contents[r], words_per_line=10, max_lines=3
                    )
                    col_lines = EmbeddingsEngineVisualization._wrap_text_words(
                        contents[c], words_per_line=10, max_lines=3
                    )
                    row_lines = [
                        EmbeddingsEngineVisualization._escape(line)
                        for line in row_lines
                    ]
                    col_lines = [
                        EmbeddingsEngineVisualization._escape(line)
                        for line in col_lines
                    ]
                    value_text = f"cos={value:.2f}"
                    tooltip_font = max(12, label_size)
                    approx_char_w = tooltip_font * 0.6
                    # Build combined lines with headers
                    lines: List[str] = (
                        [f"{row_id}:"]
                        + [f"  {ln}" for ln in row_lines]
                        + [f"{col_id}:"]
                        + [f"  {ln}" for ln in col_lines]
                        + [value_text]
                    )
                    max_len = max(len(line) for line in lines)
                    box_w = int(12 + approx_char_w * max_len)
                    line_h = tooltip_font + 2
                    box_h = 8 + len(lines) * line_h
                    bx = x + cell_size + 6
                    by = y - box_h - 4
                    # flip/clamp within bounds
                    if bx + box_w > width - 2:
                        bx = x - box_w - 6
                    if bx < 2:
                        bx = 2
                    if by < 2:
                        by = y + cell_size + 4
                    if by + box_h > height - 2:
                        by = max(2, height - box_h - 2)
                    parts.append("<g class='cell'>")
                    # Native tooltip fallback attached to rect for reliable browser behavior
                    parts.append(
                        f"<rect x='{x}' y='{y}' width='{cell_size}' height='{cell_size}' fill='{fill}'><title>{row_id} | {col_id} | {value_text}</title></rect>"
                    )
                    parts.append("<g class='tip'>")
                    parts.append(
                        f"<rect x='{bx}' y='{by}' rx='4' ry='4' width='{box_w}' height='{box_h}' fill='white' stroke='#333' stroke-opacity='0.4' fill-opacity='0.95' />"
                    )
                    ty = by + 6 + tooltip_font
                    for line in lines:
                        parts.append(
                            f"<text x='{bx + 6}' y='{ty}' font-size='{tooltip_font}' fill='#111'>{line}</text>"
                        )
                        ty += line_h
                    parts.append("</g>")
                    if show_values:
                        parts.append(
                            f"<text x='{x + cell_size/2}' y='{y + cell_size*0.65}' font-size='{label_size - 2}' text-anchor='middle' fill='black'>{value:.2f}</text>"
                        )
                    parts.append("</g>")
                else:
                    parts.append(
                        f"<rect x='{x}' y='{y}' width='{cell_size}' height='{cell_size}' fill='{fill}'><title>{row_id} | {col_id} | {value_text}</title></rect>"
                    )
                    if show_values:
                        parts.append(
                            f"<text x='{x + cell_size/2}' y='{y + cell_size*0.65}' font-size='{label_size - 2}' text-anchor='middle' fill='black'>{value:.2f}</text>"
                        )

        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def svg_tsne(
        engine: "Any",
        width: int = 600,
        height: int = 400,
        perplexity: float = 30.0,
        random_state: int = 42,
        label_size: int = 12,
        *,
        instant_tooltips: bool = True,
        cluster_assignments: Optional[dict] = None,
        draw_hulls: Optional[bool] = None,
        hull_min_points: int = 2,
        include_noise_hull: bool = False,
    ) -> str:
        """Render a 2D scatter plot using t-SNE (or PCA fallback) as SVG.

        Args:
            engine: EmbeddingsEngine instance.
            width: SVG width in pixels.
            height: SVG height in pixels.
            perplexity: t-SNE perplexity (ignored if t-SNE is unavailable).
            random_state: RNG seed for reproducibility.
            label_size: Font size for labels.
        """
        (
            ids,
            vectors,
            contents,
        ) = EmbeddingsEngineVisualization._get_ids_vectors_contents(engine)
        n = len(ids)
        if n == 0:
            return EmbeddingsEngineVisualization._svg_empty("No documents to visualize")
        if n == 1:
            # Single point, center it
            return EmbeddingsEngineVisualization._svg_points(
                ids=ids,
                points=[(width / 2.0, height / 2.0)],
                width=width,
                height=height,
                label_size=label_size,
                tooltips=contents,
                instant_tooltips=instant_tooltips,
            )

        # 2D projection
        points_01: List[Tuple[float, float]]
        if _TSNE is not None:
            try:
                # Use scikit-learn t-SNE on raw vectors
                tsne = _TSNE(
                    n_components=2,
                    perplexity=min(perplexity, max(5.0, (n - 1) / 3.0)),
                    random_state=random_state,
                    init="random",
                )
                arr = EmbeddingsEngineVisualization._as_numpy_array(vectors)
                proj = tsne.fit_transform(arr)
                points_01 = EmbeddingsEngineVisualization._normalize_points(proj)  # type: ignore[arg-type]
            except Exception:
                points_01 = EmbeddingsEngineVisualization._pca_or_random(
                    vectors, random_state
                )
        else:
            points_01 = EmbeddingsEngineVisualization._pca_or_random(
                vectors, random_state
            )

        # Scale to SVG dimensions with margins
        margin = 20
        points: List[Tuple[float, float]] = []
        for x01, y01 in points_01:
            x = margin + x01 * (width - 2 * margin)
            y = margin + y01 * (height - 2 * margin)
            points.append((x, y))

        # Colors per id if cluster assignments provided
        colors: Optional[dict] = None
        if cluster_assignments:
            doc_to_cluster = (
                EmbeddingsEngineVisualization._normalize_cluster_assignments(
                    ids, cluster_assignments
                )
            )
            colors = EmbeddingsEngineVisualization._colors_for_clusters(
                ids, doc_to_cluster
            )
        # Default to drawing hulls if clusters provided and draw_hulls not explicitly set
        if draw_hulls is None:
            draw_hulls = cluster_assignments is not None

        return EmbeddingsEngineVisualization._svg_points(
            ids=ids,
            points=points,
            width=width,
            height=height,
            label_size=label_size,
            tooltips=contents,
            instant_tooltips=instant_tooltips,
            colors=colors,
            doc_to_cluster=(doc_to_cluster if cluster_assignments else None),
            draw_hulls=bool(draw_hulls),
            hull_min_points=hull_min_points,
            include_noise_hull=include_noise_hull,
        )

    # ----------------------- Internals -----------------------
    @staticmethod
    def _ensure_all_embeddings(engine: "Any") -> None:
        """Compute missing document embeddings in batch, if any."""
        missing_indices = [
            i for i, d in enumerate(engine.documents) if d.embedding is None
        ]
        if not missing_indices:
            return
        texts = [engine.documents[i].content for i in missing_indices]
        new_embeddings = engine.embedding_function.embed_documents(texts)
        for idx, emb in zip(missing_indices, new_embeddings):
            engine.documents[idx].embedding = emb

    @staticmethod
    def _get_vectors(engine: "Any") -> Tuple[List[str], List[List[float]]]:
        EmbeddingsEngineVisualization._ensure_all_embeddings(engine)
        ids: List[str] = [doc.id for doc in engine.documents]
        vectors: List[List[float]] = [doc.embedding for doc in engine.documents]  # type: ignore
        return ids, vectors

    @staticmethod
    def _get_ids_vectors_contents(
        engine: "Any",
    ) -> Tuple[List[str], List[List[float]], List[str]]:
        EmbeddingsEngineVisualization._ensure_all_embeddings(engine)
        ids: List[str] = [doc.id for doc in engine.documents]
        vectors: List[List[float]] = [doc.embedding for doc in engine.documents]  # type: ignore
        contents: List[str] = [str(doc.content) for doc in engine.documents]
        return ids, vectors, contents

    @staticmethod
    def _as_numpy_array(vectors: List[List[float]]):  # type: ignore[no-untyped-def]
        if _np is None:
            raise RuntimeError(
                "NumPy is required for this operation but is not installed."
            )
        return _np.asarray(vectors, dtype=float)

    @staticmethod
    def _normalize_points(arr) -> List[Tuple[float, float]]:  # type: ignore[no-untyped-def]
        if _np is None:
            # Fallback: min-max over python lists
            xs = [float(row[0]) for row in arr]
            ys = [float(row[1]) for row in arr]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            span_x = (max_x - min_x) or 1.0
            span_y = (max_y - min_y) or 1.0
            return [
                ((x - min_x) / span_x, (y - min_y) / span_y) for x, y in zip(xs, ys)
            ]
        xs = arr[:, 0]
        ys = arr[:, 1]
        min_x, max_x = float(xs.min()), float(xs.max())
        min_y, max_y = float(ys.min()), float(ys.max())
        span_x = (max_x - min_x) or 1.0
        span_y = (max_y - min_y) or 1.0
        xs01 = (xs - min_x) / span_x
        ys01 = (ys - min_y) / span_y
        return [(float(x), float(y)) for x, y in zip(xs01, ys01)]

    @staticmethod
    def _pca_or_random(
        vectors: List[List[float]], seed: int
    ) -> List[Tuple[float, float]]:
        # PCA via NumPy if available, else deterministic pseudo-random positions
        if _np is not None:
            try:
                X = _np.asarray(vectors, dtype=float)
                X = X - X.mean(axis=0, keepdims=True)
                # SVD for top-2 components
                U, S, Vt = _np.linalg.svd(X, full_matrices=False)
                Y = U[:, :2] * S[:2]
                return EmbeddingsEngineVisualization._normalize_points(Y)
            except Exception:
                pass

        # Deterministic positions from hashing ids/content length
        rng = _DeterministicRNG(seed)
        points = [(rng.random(), rng.random()) for _ in vectors]
        return points

    @staticmethod
    def _svg_points(
        ids: List[str],
        points: List[Tuple[float, float]],
        width: int,
        height: int,
        label_size: int,
        tooltips: Optional[List[str]] = None,
        instant_tooltips: bool = True,
        colors: Optional[dict] = None,
        doc_to_cluster: Optional[dict] = None,
        draw_hulls: bool = False,
        hull_min_points: int = 2,
        include_noise_hull: bool = False,
    ) -> str:
        parts: List[str] = [
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>",
            "<rect width='100%' height='100%' fill='white' />",
        ]
        if instant_tooltips:
            parts.append(
                "<style>"
                ".pt .tip{visibility:hidden;opacity:0;transition:opacity 0.05s linear;}"
                ".pt:hover .tip{visibility:visible;opacity:1;}"
                ".tip-overlay .tip{visibility:hidden;opacity:0;transition:opacity 0.05s linear;}"
                ".tip-overlay:hover .tip{visibility:visible;opacity:1;}"
                ".tip-overlay circle.overlay-capture{fill-opacity:0;stroke-opacity:0;pointer-events:all;}"
                "</style>"
            )
        if tooltips is None:
            tooltips = ids
        # Optional: cluster hulls drawn first so points/labels overlay them
        if draw_hulls and doc_to_cluster and colors:
            hull_parts: List[str] = []
            # Build cluster -> list of (x,y)
            cluster_points: dict = {}
            for doc_id, (x, y) in zip(ids, points):
                cid = doc_to_cluster.get(doc_id)
                if cid is None:
                    continue
                if not include_noise_hull and int(cid) == -1:
                    continue
                cluster_points.setdefault(cid, []).append((x, y))
            # Determine color per cluster from first doc's color
            cluster_color: dict = {}
            for doc_id, cid in doc_to_cluster.items():
                if cid not in cluster_color and doc_id in colors:
                    cluster_color[cid] = colors[doc_id]
            # Draw hull for each cluster with >= hull_min_points
            for cid, pts in cluster_points.items():
                color = cluster_color.get(cid, "#999999")
                if len(pts) >= max(3, hull_min_points):
                    hull = EmbeddingsEngineVisualization._convex_hull(pts)
                    if not hull:
                        continue
                    points_attr = " ".join(f"{x:.2f},{y:.2f}" for x, y in hull)
                    hull_parts.append(
                        f"<polygon points='{points_attr}' fill='{color}' fill-opacity='0.08' stroke='{color}' stroke-opacity='0.6' stroke-width='1.5' />"
                    )
                elif len(pts) == 2 and hull_min_points <= 2:
                    (x1, y1), (x2, y2) = pts
                    hull_parts.append(
                        f"<line x1='{x1:.2f}' y1='{y1:.2f}' x2='{x2:.2f}' y2='{y2:.2f}' stroke='{color}' stroke-opacity='0.5' stroke-width='1.5' />"
                    )
                elif len(pts) == 1 and hull_min_points <= 1:
                    (x1, y1) = pts[0]
                    hull_parts.append(
                        f"<circle cx='{x1:.2f}' cy='{y1:.2f}' r='8' fill='none' stroke='{color}' stroke-opacity='0.4' stroke-width='1.2' />"
                    )
            parts.extend(hull_parts)
        # First draw base points/labels
        base_parts: List[str] = []
        for (x, y), doc_id in zip(points, ids):
            label = EmbeddingsEngineVisualization._escape(
                EmbeddingsEngineVisualization._truncate(doc_id, 24)
            )
            fill_color = "#1f77b4"
            if colors and doc_id in colors:
                fill_color = colors[doc_id]
            base_parts.append("<g class='pt'>")
            base_parts.append(
                f"<circle cx='{x:.2f}' cy='{y:.2f}' r='4' fill='{fill_color}' />"
            )
            base_parts.append(
                f"<text x='{x + 6:.2f}' y='{y + 4:.2f}' font-size='{label_size}' fill='#333'>{label}</text>"
            )
            base_parts.append("</g>")

        parts.extend(base_parts)

        if instant_tooltips:
            # Then overlay tooltips so they are on top of everything
            overlay_parts: List[str] = []
            for (x, y), tip in zip(points, tooltips):
                raw = str(tip)
                wrapped_lines = EmbeddingsEngineVisualization._wrap_text_words(
                    raw, words_per_line=10, max_lines=3
                )
                # Escape post-wrapping (line-wise)
                esc_lines = [
                    EmbeddingsEngineVisualization._escape(line)
                    for line in wrapped_lines
                ]
                tooltip_font = max(14, label_size + 2)
                approx_char_w = tooltip_font * 0.6
                max_chars = max((len(line) for line in esc_lines), default=1)
                box_w = int(12 + approx_char_w * max_chars)
                line_h = tooltip_font + 4
                box_h = 10 + len(esc_lines) * line_h
                bx = x + 8
                by = y - box_h - 8
                if bx + box_w > width - 2:
                    bx = x - box_w - 8
                if bx < 2:
                    bx = 2
                if by < 2:
                    by = y + 8
                if by + box_h > height - 2:
                    by = max(2, height - box_h - 2)
                overlay_parts.append("<g class='tip-overlay'>")
                # Invisible hover catcher to ensure overlay receives hover and stays on top
                overlay_parts.append(
                    f"<circle class='overlay-capture' cx='{x:.2f}' cy='{y:.2f}' r='10' fill='white' />"
                )
                overlay_parts.append("<g class='tip'>")
                overlay_parts.append(
                    f"<rect x='{bx:.2f}' y='{by:.2f}' rx='4' ry='4' width='{box_w}' height='{box_h}' fill='white' stroke='#333' stroke-opacity='0.7' fill-opacity='1' />"
                )
                ty = by + 8 + tooltip_font
                for line in esc_lines:
                    overlay_parts.append(
                        f"<text x='{bx + 8:.2f}' y='{ty:.2f}' font-size='{tooltip_font}' fill='#111'>{line}</text>"
                    )
                    ty += line_h
                overlay_parts.append("</g>")
                overlay_parts.append("</g>")
            parts.extend(overlay_parts)
        else:
            # Fallback native tooltips using <title>
            title_parts: List[str] = []
            for (x, y), tip in zip(points, tooltips):
                title = EmbeddingsEngineVisualization._escape(str(tip))
                title_parts.append("<g>")
                title_parts.append(f"<title>{title}</title>")
                title_parts.append(
                    f"<circle cx='{x:.2f}' cy='{y:.2f}' r='4' fill='transparent' />"
                )
                title_parts.append("</g>")
            parts.extend(title_parts)
        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _convex_hull(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """Compute convex hull of a set of 2D points using monotone chain.

        Returns hull as list of points in counter-clockwise order. Points on edges
        may be included or excluded depending on collinearity; sufficient for drawing.
        """
        # Sort by x, then y
        pts = sorted(set((float(x), float(y)) for x, y in points))
        if len(pts) <= 2:
            return pts

        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        lower: List[Tuple[float, float]] = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        upper: List[Tuple[float, float]] = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        # Concatenate lower and upper to get full hull; omit last point of each list (duplicate of starting point)
        return lower[:-1] + upper[:-1]

    @staticmethod
    def _normalize_cluster_assignments(ids: List[str], assignments: dict) -> dict:
        """Return mapping of doc_id -> cluster_id. Accepts either mapping of
        doc_id -> cluster_id or cluster_id -> list of doc_ids.
        """
        # If keys look like doc ids present in ids, assume direct mapping
        if assignments and next(iter(assignments.keys())) in set(ids):
            return {
                doc_id: int(cluster_id)
                for doc_id, cluster_id in assignments.items()
                if doc_id in ids
            }
        # Otherwise assume cluster -> list mapping
        normalized: dict = {}
        for cluster_id, doc_list in assignments.items():  # type: ignore[attr-defined]
            try:
                cid = int(cluster_id)
            except Exception:
                continue
            for doc_id in doc_list:
                if doc_id in ids:
                    normalized[doc_id] = cid
        return normalized

    @staticmethod
    def _colors_for_clusters(ids: List[str], doc_to_cluster: dict) -> dict:
        palette = [
            "#1f77b4",
            "#ff7f0e",
            "#2ca02c",
            "#d62728",
            "#9467bd",
            "#8c564b",
            "#e377c2",
            "#7f7f7f",
            "#bcbd22",
            "#17becf",
        ]
        cluster_to_color: dict = {}
        colors: dict = {}
        for doc_id in ids:
            if doc_id not in doc_to_cluster:
                continue
            cid = int(doc_to_cluster[doc_id])
            if cid not in cluster_to_color:
                cluster_to_color[cid] = palette[len(cluster_to_color) % len(palette)]
            colors[doc_id] = cluster_to_color[cid]
        return colors

    @staticmethod
    def _svg_empty(message: str) -> str:
        width, height = 480, 120
        return (
            f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>"
            "<rect width='100%' height='100%' fill='white' />"
            f"<text x='{width/2}' y='{height/2}' text-anchor='middle' font-size='14' fill='#666'>{EmbeddingsEngineVisualization._escape(message)}</text>"
            "</svg>"
        )

    @staticmethod
    def _escape(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        return text if len(text) <= max_len else text[: max_len - 1] + "…"

    @staticmethod
    def _value_to_color(value: float) -> str:
        """Map similarity in [-1,1] to a diverging blue-white-red color."""
        v = max(-1.0, min(1.0, float(value)))
        if v < 0:
            t = v + 1.0  # 0..1 for negatives
            r, g, b = int(255 * (1.0 - 0.5 * t)), int(255 * (1.0 - 0.8 * t)), 255
        else:
            t = v  # 0..1 for positives
            r, g, b = 255, int(255 * (1.0 - 0.8 * t)), int(255 * (1.0 - 0.5 * t))
        return f"rgb({r},{g},{b})"

    @staticmethod
    def _wrap_text_words(
        text: str, words_per_line: int = 10, max_lines: int = 3
    ) -> List[str]:
        """Wrap text into lines with approximately words_per_line words; truncate with ellipsis.

        The function is character-agnostic and uses whitespace splitting. If the
        text exceeds max_lines when wrapped, the last line ends with an ellipsis.
        """
        words = str(text).split()
        if not words:
            return [""]
        lines: List[str] = []
        for i in range(0, len(words), max(1, words_per_line)):
            lines.append(" ".join(words[i : i + words_per_line]))
            if len(lines) >= max_lines:
                if i + words_per_line < len(words):
                    # Add ellipsis to truncated last line
                    if lines[-1].endswith("…"):
                        pass
                    else:
                        lines[-1] = lines[-1] + " …"
                break
        return lines


class _DeterministicRNG:
    """Simple deterministic RNG based on hashing, used for fallback layouts."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def random(self) -> float:
        self._state = int(hashlib.md5(str(self._state).encode("utf-8")).hexdigest(), 16)
        return (self._state % 10_000) / 10_000.0


class DistanceMatrixView:
    """Helper view for distance matrix visualization.

    Use `.to_svg()` to get SVG markup, `.save(path)` to write it,
    `.open()` to launch the file with the OS default handler, and `.show()`
    to return the SVG string (handy in REPL). In notebooks, the object will
    render via `_repr_html_`.
    """

    def __init__(
        self,
        engine: "Any",
        show_values: bool = False,
        cell_size: int = 18,
        label_size: int = 12,
        padding: int = 6,
        upper_triangle: bool = True,
        include_diagonal: bool = False,
        auto_scale: bool = True,
        min_total_pixels: int = 400,
    ) -> None:
        self._engine = engine
        self._show_values = show_values
        self._cell_size = cell_size
        self._label_size = label_size
        self._padding = padding
        self._upper_triangle = upper_triangle
        self._include_diagonal = include_diagonal
        self._auto_scale = auto_scale
        self._min_total_pixels = min_total_pixels
        self._svg_cache: Optional[str] = None

    def to_svg(self) -> str:
        if self._svg_cache is None:
            self._svg_cache = EmbeddingsEngineVisualization.svg_similarity_heatmap(
                self._engine,
                cell_size=self._cell_size,
                label_size=self._label_size,
                padding=self._padding,
                show_values=self._show_values,
                upper_triangle=self._upper_triangle,
                include_diagonal=self._include_diagonal,
                auto_scale=self._auto_scale,
                min_total_pixels=self._min_total_pixels,
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

        svg_path = path or self.save(
            os.path.join(tempfile.gettempdir(), "embeddings_distance_matrix.svg")
        )
        if path is None:
            # Save to ensure file exists
            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(self.to_svg())
        try:
            if os.name == "nt":
                os.startfile(svg_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":  # macOS
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


class TSNEView:
    """Helper view for t-SNE (or PCA fallback) 2D scatter visualization.

    Use `.to_svg()` to get SVG markup, `.save(path)` to write it,
    `.open()` to launch the file with the OS default handler, and `.show()`
    to return the SVG string (handy in REPL). In notebooks, the object will
    render via `_repr_html_`.
    """

    def __init__(
        self,
        engine: "Any",
        width: int = 600,
        height: int = 400,
        perplexity: float = 30.0,
        random_state: int = 42,
        label_size: int = 12,
        cluster_assignments: Optional[dict] = None,
        instant_tooltips: bool = True,
    ) -> None:
        self._engine = engine
        self._width = width
        self._height = height
        self._perplexity = perplexity
        self._random_state = random_state
        self._label_size = label_size
        self._cluster_assignments = cluster_assignments
        self._instant_tooltips = instant_tooltips
        self._svg_cache: Optional[str] = None

    def to_svg(self) -> str:
        if self._svg_cache is None:
            self._svg_cache = EmbeddingsEngineVisualization.svg_tsne(
                self._engine,
                width=self._width,
                height=self._height,
                perplexity=self._perplexity,
                random_state=self._random_state,
                label_size=self._label_size,
                cluster_assignments=self._cluster_assignments,
                instant_tooltips=self._instant_tooltips,
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

        svg_path = path or self.save(
            os.path.join(tempfile.gettempdir(), "embeddings_tsne.svg")
        )
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
