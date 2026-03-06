"""
Graph rendering abstraction with pluggable backends.

Provides a builder-style API for constructing directed graphs with nodes,
edges, and subgraph clusters. Two backends are included:

- MermaidRenderer: produces Mermaid diagram text (no dependencies)
- PydotRenderer: produces PNG via pydot/graphviz (requires pydot + graphviz)

Usage:
    graph = DiGraph(renderer="mermaid")  # or "pydot"
    graph.add_node("A", label="Start", shape="box")
    graph.add_node("B", label="End", shape="ellipse")
    graph.add_edge("A", "B", label="next")
    result = graph.render()  # returns MermaidGraph or writes PNG
"""

from __future__ import annotations

import tempfile
from typing import Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

class NodeDef:
    __slots__ = ("id", "label", "shape", "fill_color", "font_size", "style", "subgraph")

    def __init__(
        self,
        id: str,
        label: str = "",
        shape: str = "box",
        fill_color: str | None = None,
        font_size: str = "10",
        style: str | None = None,
        subgraph: str | None = None,
    ):
        self.id = id
        self.label = label or id
        self.shape = shape
        self.fill_color = fill_color
        self.font_size = font_size
        self.style = style
        self.subgraph = subgraph


class EdgeDef:
    __slots__ = ("src", "dst", "label", "style", "color", "font_color", "font_size")

    def __init__(
        self,
        src: str,
        dst: str,
        label: str = "",
        style: str = "solid",
        color: str | None = None,
        font_color: str | None = None,
        font_size: str = "10",
    ):
        self.src = src
        self.dst = dst
        self.label = label
        self.style = style
        self.color = color
        self.font_color = font_color
        self.font_size = font_size


class SubgraphDef:
    __slots__ = ("id", "label", "fill_color")

    def __init__(self, id: str, label: str = "", fill_color: str | None = None):
        self.id = id
        self.label = label or id
        self.fill_color = fill_color


# ---------------------------------------------------------------------------
# Renderer protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class GraphRendererProtocol(Protocol):
    """Protocol for graph rendering backends."""

    def render(
        self,
        nodes: list[NodeDef],
        edges: list[EdgeDef],
        subgraphs: list[SubgraphDef],
        *,
        direction: str = "TB",
    ) -> "RenderedGraph":
        ...


# ---------------------------------------------------------------------------
# Rendered graph wrapper
# ---------------------------------------------------------------------------

class RenderedGraph:
    """Wrapper around rendered graph output.

    Provides display methods for different environments (notebook, terminal, file).
    """

    def __init__(self, text: str | None = None, png_path: str | None = None):
        self._text = text
        self._png_path = png_path

    @property
    def text(self) -> str | None:
        return self._text

    @property
    def png_path(self) -> str | None:
        return self._png_path

    def _repr_html_(self) -> str:
        """HTML display for Jupyter notebooks."""
        if self._text is not None:
            # Mermaid: use a <pre> with mermaid class for rendering
            import html
            return (
                f'<pre class="mermaid">\n{html.escape(self._text)}\n</pre>\n'
                '<script type="module">'
                'import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";'
                "mermaid.initialize({startOnLoad:true});"
                "</script>"
            )
        if self._png_path is not None:
            import base64

            with open(self._png_path, "rb") as f:
                data = base64.b64encode(f.read()).decode()
            return f'<img src="data:image/png;base64,{data}" />'
        return "<p>No graph rendered</p>"

    def __repr__(self) -> str:
        if self._text is not None:
            return self._text
        if self._png_path is not None:
            return f"RenderedGraph(png_path={self._png_path!r})"
        return "RenderedGraph(empty)"

    def save(self, filename: str) -> None:
        """Save the rendered graph to a file."""
        if self._text is not None:
            with open(filename, "w") as f:
                f.write(self._text)
        elif self._png_path is not None:
            import shutil
            shutil.copy(self._png_path, filename)

    def show(self) -> None:
        """Display the graph in the current environment."""
        from edsl.utilities.is_notebook import is_notebook
        import sys

        if is_notebook():
            if "marimo" in sys.modules and self._png_path:
                from PIL import Image as PILImage
                img = PILImage.open(self._png_path)
                return img
            else:
                from IPython.display import display, HTML
                display(HTML(self._repr_html_()))
        elif self._png_path:
            import os
            if os.name == "nt":
                os.system(f"start {self._png_path}")
            elif os.name == "posix":
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                os.system(f"{opener} {self._png_path}")
        else:
            print(self._text)


# ---------------------------------------------------------------------------
# Mermaid backend
# ---------------------------------------------------------------------------

# Named color -> hex mapping for common colors used in the visualizations
_COLOR_HEX = {
    "lightblue": "#ADD8E6",
    "lightgreen": "#90EE90",
    "lightyellow": "#FFFFE0",
    "lightcyan": "#E0FFFF",
    "lightpink": "#FFB6C1",
    "lightgrey": "#D3D3D3",
    "lavender": "#E6E6FA",
    "mistyrose": "#FFE4E1",
    "honeydew": "#F0FFF0",
    "khaki": "#F0E68C",
    "yellow": "#FFFF00",
    "white": "#FFFFFF",
}

_MERMAID_SHAPES = {
    "box": ("[", "]"),
    "rectangle": ("[", "]"),
    "ellipse": ("([", "])"),
    "circle": ("((", "))"),
    "diamond": ("{", "}"),
    "hexagon": ("{{", "}}"),
}


class MermaidRenderer:
    """Render a graph as Mermaid diagram text."""

    def render(
        self,
        nodes: list[NodeDef],
        edges: list[EdgeDef],
        subgraphs: list[SubgraphDef],
        *,
        direction: str = "TB",
    ) -> RenderedGraph:
        lines: list[str] = [f"graph {direction}"]

        # Collect nodes by subgraph
        subgraph_nodes: dict[str, list[NodeDef]] = {sg.id: [] for sg in subgraphs}
        top_level_nodes: list[NodeDef] = []
        for node in nodes:
            if node.subgraph and node.subgraph in subgraph_nodes:
                subgraph_nodes[node.subgraph].append(node)
            else:
                top_level_nodes.append(node)

        # Emit subgraphs
        for sg in subgraphs:
            lines.append(f"    subgraph {sg.id}[{_mermaid_escape(sg.label)}]")
            for node in subgraph_nodes[sg.id]:
                lines.append(f"        {_mermaid_node(node)}")
            lines.append("    end")

        # Emit top-level nodes
        for node in top_level_nodes:
            lines.append(f"    {_mermaid_node(node)}")

        # Emit edges
        for edge in edges:
            lines.append(f"    {_mermaid_edge(edge)}")

        # Emit styles
        style_lines = _mermaid_styles(nodes, subgraphs)
        lines.extend(f"    {sl}" for sl in style_lines)

        return RenderedGraph(text="\n".join(lines))


def _mermaid_escape(text: str) -> str:
    """Escape text for mermaid labels."""
    # Replace quotes and newlines
    text = text.replace('"', "'")
    text = text.replace("\n", "<br/>")
    return f'"{text}"'


def _mermaid_node(node: NodeDef) -> str:
    """Format a single node definition."""
    open_br, close_br = _MERMAID_SHAPES.get(node.shape, ("[", "]"))
    label = node.label.replace('"', "'").replace("\n", "<br/>")
    return f'{node.id}{open_br}"{label}"{close_br}'


def _mermaid_edge(edge: EdgeDef) -> str:
    """Format a single edge."""
    arrow = "--->" if edge.style == "solid" else "-.->"
    if edge.label:
        label = edge.label.replace('"', "'").replace("\n", "<br/>")
        return f'{edge.src} {arrow}|"{label}"| {edge.dst}'
    return f"{edge.src} {arrow} {edge.dst}"


def _mermaid_styles(nodes: list[NodeDef], subgraphs: list[SubgraphDef]) -> list[str]:
    """Generate classDef and style statements for colored nodes/subgraphs."""
    lines: list[str] = []

    # Group nodes by fill_color to minimize classDef statements
    color_to_nodes: dict[str, list[str]] = {}
    for node in nodes:
        if node.fill_color:
            hex_color = _COLOR_HEX.get(node.fill_color, node.fill_color)
            color_to_nodes.setdefault(hex_color, []).append(node.id)

    for i, (color, node_ids) in enumerate(color_to_nodes.items()):
        class_name = f"fill{i}"
        lines.append(f"classDef {class_name} fill:{color},stroke:#333")
        lines.append(f"class {','.join(node_ids)} {class_name}")

    # Style subgraphs
    for sg in subgraphs:
        if sg.fill_color:
            hex_color = _COLOR_HEX.get(sg.fill_color, sg.fill_color)
            lines.append(f"style {sg.id} fill:{hex_color},stroke:#333")

    return lines


# ---------------------------------------------------------------------------
# Pydot backend
# ---------------------------------------------------------------------------

class PydotRenderer:
    """Render a graph as PNG via pydot/graphviz."""

    def render(
        self,
        nodes: list[NodeDef],
        edges: list[EdgeDef],
        subgraphs: list[SubgraphDef],
        *,
        direction: str = "TB",
    ) -> RenderedGraph:
        import pydot

        rankdir = "LR" if direction == "LR" else "TB"
        graph = pydot.Dot(graph_type="digraph", rankdir=rankdir, fontsize="10")

        # Create clusters
        clusters: dict[str, pydot.Cluster] = {}
        for sg in subgraphs:
            cluster = pydot.Cluster(
                sg.id,
                label=sg.label,
                style="filled" if sg.fill_color else "",
                fillcolor=sg.fill_color or "",
                color="black",
                fontsize="12",
                fontname="Arial Bold",
            )
            clusters[sg.id] = cluster

        # Add nodes
        for node in nodes:
            attrs = {
                "label": node.label,
                "shape": node.shape,
                "fontsize": node.font_size,
            }
            if node.fill_color:
                attrs["style"] = "filled"
                attrs["fillcolor"] = node.fill_color
            if node.style:
                attrs["style"] = node.style

            pydot_node = pydot.Node(node.id, **attrs)

            if node.subgraph and node.subgraph in clusters:
                clusters[node.subgraph].add_node(pydot_node)
            else:
                graph.add_node(pydot_node)

        # Add clusters to graph
        for cluster in clusters.values():
            graph.add_subgraph(cluster)

        # Add edges
        for edge in edges:
            attrs = {"fontsize": edge.font_size}
            if edge.label:
                attrs["label"] = edge.label
            if edge.style == "dashed":
                attrs["style"] = "dashed"
            elif edge.style == "dotted":
                attrs["style"] = "dotted"
            if edge.color:
                attrs["color"] = edge.color
            if edge.font_color:
                attrs["fontcolor"] = edge.font_color

            graph.add_edge(pydot.Edge(edge.src, edge.dst, **attrs))

        # Render to temp PNG
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        try:
            graph.write_png(tmp.name)
        except FileNotFoundError:
            print(
                "Graphviz not found. Install with: brew install graphviz (macOS), "
                "apt-get install graphviz (Ubuntu), or choco install graphviz (Windows)"
            )
            return RenderedGraph()
        return RenderedGraph(png_path=tmp.name)


# ---------------------------------------------------------------------------
# DiGraph builder
# ---------------------------------------------------------------------------

def _default_renderer() -> str:
    """Pick the best available renderer."""
    try:
        import pydot
        return "pydot"
    except ImportError:
        return "mermaid"


class DiGraph:
    """Builder for directed graphs with pluggable rendering backend.

    Args:
        renderer: "mermaid", "pydot", or a GraphRendererProtocol instance.
        direction: Graph direction - "TB" (top-bottom) or "LR" (left-right).
    """

    def __init__(
        self,
        renderer: str | GraphRendererProtocol | None = None,
        direction: str = "TB",
    ):
        self._nodes: list[NodeDef] = []
        self._edges: list[EdgeDef] = []
        self._subgraphs: list[SubgraphDef] = []
        self._node_ids: set[str] = set()
        self.direction = direction

        if renderer is None:
            renderer = _default_renderer()
        if isinstance(renderer, str):
            self._renderer = _make_renderer(renderer)
        else:
            self._renderer = renderer

    def add_subgraph(
        self,
        id: str,
        label: str = "",
        fill_color: str | None = None,
    ) -> DiGraph:
        """Add a subgraph cluster."""
        self._subgraphs.append(SubgraphDef(id=id, label=label, fill_color=fill_color))
        return self

    def add_node(
        self,
        id: str,
        label: str = "",
        shape: str = "box",
        fill_color: str | None = None,
        font_size: str = "10",
        style: str | None = None,
        subgraph: str | None = None,
    ) -> DiGraph:
        """Add a node to the graph."""
        self._nodes.append(NodeDef(
            id=id, label=label, shape=shape, fill_color=fill_color,
            font_size=font_size, style=style, subgraph=subgraph,
        ))
        self._node_ids.add(id)
        return self

    def add_edge(
        self,
        src: str,
        dst: str,
        label: str = "",
        style: str = "solid",
        color: str | None = None,
        font_color: str | None = None,
        font_size: str = "10",
    ) -> DiGraph:
        """Add an edge between two nodes."""
        self._edges.append(EdgeDef(
            src=src, dst=dst, label=label, style=style,
            color=color, font_color=font_color, font_size=font_size,
        ))
        return self

    def render(self) -> RenderedGraph:
        """Render the graph using the configured backend."""
        return self._renderer.render(
            self._nodes, self._edges, self._subgraphs,
            direction=self.direction,
        )

    def show(self, filename: str | None = None) -> RenderedGraph | None:
        """Render and display/save the graph."""
        result = self.render()
        if filename:
            result.save(filename)
            print(f"Graph saved to {filename}")
            return result
        result.show()
        return result


def _make_renderer(name: str) -> GraphRendererProtocol:
    """Create a renderer by name."""
    if name == "mermaid":
        return MermaidRenderer()
    elif name == "pydot":
        return PydotRenderer()
    else:
        raise ValueError(f"Unknown renderer: {name!r}. Use 'mermaid' or 'pydot'.")
