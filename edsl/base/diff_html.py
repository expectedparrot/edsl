from __future__ import annotations

"""Utility for rendering ``BaseDiff`` and ``BaseDiffCollection`` objects as HTML.

This helper makes it easy to visually inspect differences between two EDSL objects
inside a browser or Jupyter‐like environment.  The generated document uses native
``<details>``/``<summary>`` tags so that sections can be expanded / collapsed without
requiring any external JavaScript or CSS frameworks.

Example
-------
>>> diff = obj1 - obj2
>>> from edsl.base.diff_html import DiffHTMLExplorer
>>> html_text = DiffHTMLExplorer(diff).generate_html()
>>> # Save or display in notebook
"""

from html import escape
from typing import Any, Dict, Iterable, List, Tuple, Union, Optional

# Using forward refs to avoid a hard import at module import time to prevent
# circular dependencies.  We will resolve types at runtime in type hints only.
try:
    from edsl.base.base_class import BaseDiff, BaseDiffCollection  # type: ignore
except ImportError:
    # During type-checking or partial imports this might fail – we ignore here.
    BaseDiff = "BaseDiff"  # type: ignore
    BaseDiffCollection = "BaseDiffCollection"  # type: ignore


class DiffHTMLExplorer:
    """Render a :class:`edsl.base.base_class.BaseDiff` (or collection) to HTML."""

    def __init__(
        self,
        diff: Union["BaseDiff", "BaseDiffCollection"],
        *,
        title: str = "EDSL Object Diff",
        collapse_large_sections: bool = True,
    ) -> None:
        self.diff = diff
        self.title = title
        self._collapse = collapse_large_sections

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------

    def generate_html(self) -> str:
        """Return the full HTML document as a **string**."""
        parts: List[str] = []
        parts.append("<html><head>")
        parts.append(f"<title>{escape(self.title)}</title>")
        parts.append("<meta charset='utf-8'>")
        parts.append("<style>" + self._css() + "</style>")
        parts.append("</head><body>")
        parts.append(f"<h2>{escape(self.title)}</h2>")
        parts.append(self._render_diff(self.diff))
        parts.append("</body></html>")
        return "\n".join(parts)

    # Alias for Jupyter rich display
    def _repr_html_(self) -> str:  # pragma: no cover
        return self.generate_html()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _css(self) -> str:
        """Minimal CSS – keeps everything self-contained."""
        return """
        body { font-family: sans-serif; margin: 1rem; }
        table { border-collapse: collapse; margin-bottom: 1rem; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 0.4rem 0.6rem; }
        th { background: #f6f8fa; text-align: left; }
        .added   { background: #e8f5e9; }
        .removed { background: #ffebee; }
        .changed-old { background: #fff8e1; }
        .changed-new { background: #e3f2fd; }
        pre { margin: 0; font-family: monospace; white-space: pre-wrap; }
        details { margin-bottom: 0.6rem; }
        summary { cursor: pointer; font-weight: 600; }
        """

    # -------------------------------------------------------------
    # Recursive renderers
    # -------------------------------------------------------------

    def _render_diff(self, diff: Union["BaseDiff", "BaseDiffCollection"], level: int = 0) -> str:
        if self._is_collection(diff):
            # Render each sub-diff in its own collapsible block
            coll_parts: List[str] = []
            coll_parts.append("<div class='diff-collection'>")
            for i, sub in enumerate(diff):  # type: ignore[arg-type]
                coll_parts.append("<details open>")
                coll_parts.append(f"<summary>Step {i + 1}</summary>")
                coll_parts.append(self._render_single_diff(sub, level + 1))
                coll_parts.append("</details>")
            coll_parts.append("</div>")
            return "\n".join(coll_parts)
        else:
            return self._render_single_diff(diff, level)

    def _render_single_diff(self, diff: "BaseDiff", level: int = 0) -> str:
        parts: List[str] = []
        indent = "  " * level

        # Added ------------------------------------------------------
        if diff.added:
            parts.append(f"{indent}<details {'open' if not self._collapse else ''}>")
            parts.append(f"{indent}  <summary>Added ({len(diff.added)})</summary>")
            parts.append(self._render_key_value_table(diff.added, row_class="added", indent=indent + "    "))
            parts.append(f"{indent}</details>")

        # Removed ----------------------------------------------------
        if diff.removed:
            parts.append(f"{indent}<details {'open' if not self._collapse else ''}>")
            parts.append(f"{indent}  <summary>Removed ({len(diff.removed)})</summary>")
            parts.append(self._render_key_value_table(diff.removed, row_class="removed", indent=indent + "    "))
            parts.append(f"{indent}</details>")

        # Modified ---------------------------------------------------
        if diff.modified:
            parts.append(f"{indent}<details {'open' if not self._collapse else ''}>")
            parts.append(f"{indent}  <summary>Modified ({len(diff.modified)})</summary>")
            parts.append(self._render_modified_table(diff.modified, indent=indent + "    "))
            parts.append(f"{indent}</details>")

        if not parts:
            parts.append(f"{indent}<p><em>No differences.</em></p>")
        return "\n".join(parts)

    # -------------------------------------------------------------
    # Table render helpers
    # -------------------------------------------------------------

    def _render_key_value_table(self, mapping: Dict[Any, Any], *, row_class: str = "", indent: str = "") -> str:
        lines: List[str] = []
        lines.append(f"{indent}<table>")
        lines.append(f"{indent}  <tr><th>Key</th><th>Value</th></tr>")
        for key, val in mapping.items():
            lines.append(
                f"{indent}  <tr class='{row_class}'><td>{escape(str(key))}</td><td>{escape(str(val))}</td></tr>"
            )
        lines.append(f"{indent}</table>")
        return "\n".join(lines)

    def _render_modified_table(self, modified: Dict[Any, Tuple[Any, Any, Any]], *, indent: str = "") -> str:
        lines: List[str] = []
        lines.append(f"{indent}<table>")
        lines.append(
            f"{indent}  <tr><th>Key</th><th>Old value</th><th>New value</th><th>Details</th></tr>"
        )
        for key, (old, new, details) in modified.items():
            # Render details
            details_html = self._render_details(details, indent=indent + "    ")
            lines.append(
                f"{indent}  <tr><td>{escape(str(key))}</td><td class='changed-old'>{escape(str(old))}</td>"
                f"<td class='changed-new'>{escape(str(new))}</td><td>{details_html}</td></tr>"
            )
        lines.append(f"{indent}</table>")
        return "\n".join(lines)

    def _render_details(self, details: Any, *, indent: str = "") -> str:
        """Render the *details* field of a modified entry, handling nested diff objects or iterable lines."""
        if details is None or details == "":
            return ""

        # Nested diff
        if self._is_diff(details):
            nested_html = self._render_diff(details, level=0)
            return nested_html

        # Iterable of diff lines
        if isinstance(details, (list, tuple, Iterable)):
            inner_lines: List[str] = []
            inner_lines.append(f"{indent}<pre>")
            for line in details:
                cls = "added" if line.startswith("+") else "removed" if line.startswith("-") else ""  # type: ignore
                inner_lines.append(f"{indent}  <span class='{cls}'>{escape(line)}</span>")
            inner_lines.append(f"{indent}</pre>")
            return "\n".join(inner_lines)

        # Fallback – just string-ify
        return escape(str(details))

    # -------------------------------------------------------------
    # Type helpers
    # -------------------------------------------------------------

    @staticmethod
    def _is_diff(obj: Any) -> bool:
        return obj.__class__.__name__ == "BaseDiff" or obj.__class__.__name__ == "BaseDiffCollection"

    @staticmethod
    def _is_collection(obj: Any) -> bool:
        return obj.__class__.__name__ == "BaseDiffCollection" 