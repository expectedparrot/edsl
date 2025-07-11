"""Visualization utilities for showing the execution flow of a `Jobs` object.

This module is inspired by `edsl.surveys.survey_flow_visualization` and provides
similar functionality but for `Jobs` instances.  In particular, it visualises:

1. The dependency chain created via the `Jobs.to(...)` method (internally
   represented by the private attribute `_depends_on`).
2. The sequence of post-run result transformations stored in
   `Jobs._post_run_methods`.

Example
-------
>>> from edsl.jobs import Jobs
>>> job = Jobs.example()
>>> # Chain another job that depends on the first and add some post-run methods
>>> job2 = job.to(job).select('how_feeling').to_pandas()
>>> from edsl.jobs.job_flow_visualization import JobsFlowVisualization
>>> JobsFlowVisualization(job2).show_flow()  # doctest: +SKIP

This will open a window (or display inline in notebooks) with a graph showing
`job` feeding into `job2`, followed by "select" and "to_pandas" transformations.
"""

from __future__ import annotations

import tempfile
from typing import Optional, Dict, Set

import pydot

# Lazy import inside functions where possible to avoid heavy imports unless the
# visualisation is actually invoked.


class JobsFlowVisualization:
    """Create a flowchart diagram for a :class:`edsl.jobs.jobs.Jobs` instance."""

    # ――― Public interface -------------------------------------------------

    def __init__(self, job: "Jobs") -> None:  # noqa: F821 – forward ref
        from edsl.jobs.jobs import Jobs  # local import to avoid circularity

        if not isinstance(job, Jobs):  # pragma: no cover – defensive
            raise TypeError("Expected an `edsl.jobs.jobs.Jobs` instance.")

        self.job = job

    # ---------------------------------------------------------------------
    def show_flow(self, filename: Optional[str] = None) -> None:
        """Render or save a flowchart for *self.job*.

        If *filename* is provided, a PNG will be written to that path. If not,
        a temporary file is created and opened with the default image viewer
        or displayed inline when inside a Jupyter notebook.
        """

        graph = self._build_graph()

        if filename is not None:
            graph.write_png(filename)
            print(f"Flowchart saved to {filename}")
            return

        # Fallback – create a temporary file and attempt to open/display it.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            try:
                graph.write_png(tmp.name)
            except FileNotFoundError:
                self._graphviz_not_installed_warning()
                return

            # Display depending on environment (notebook vs. regular shell)
            from edsl.utilities.is_notebook import is_notebook  # lazy import

            if is_notebook():
                from IPython.display import Image, display  # type: ignore

                display(Image(tmp.name))
            else:
                import os
                import sys

                if os.name == "nt":  # Windows
                    os.system(f"start {tmp.name}")
                elif os.name == "posix":  # macOS, Linux
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    os.system(f"{opener} {tmp.name}")

    # ――― Internal helpers -------------------------------------------------

    @staticmethod
    def _graphviz_not_installed_warning() -> None:
        print(
            """GraphViz executables not found. Please install GraphViz to enable\n"
            "visualisation (e.g. `brew install graphviz` on macOS,\n"
            "`sudo apt-get install graphviz` on Ubuntu)."""
        )

    # ------------------------------------------------------------------
    def _build_graph(self) -> pydot.Dot:
        """Return a *pydot.Dot* graph representing the job flow."""

        graph = pydot.Dot(graph_type="digraph", rankdir="LR", fontsize="10")

        # Build nodes recursively for dependencies and collect edges.
        visited: Dict[int, str] = {}  # job id -> node name
        self._add_job_subgraph(self.job, graph, visited)
        return graph

    # --------------------------------------------------------------
    def _add_job_subgraph(
        self,
        job: "Jobs",  # noqa: F821 – forward ref
        graph: pydot.Dot,
        visited: Dict[int, str],
    ) -> str:
        """Recursively add *job* and its dependencies to *graph*.

        Returns the node name corresponding to *job* so that callers can draw
        edges to it.
        """
        job_id = id(job)
        if job_id in visited:
            return visited[job_id]

        # Create a node representing the *job* itself
        node_name = f"job_{job_id}"
        label = self._job_label(job)
        job_node = pydot.Node(
            node_name,
            label=label,
            shape="box",
            style="filled",
            fillcolor="lightblue",
            fontsize="10",
        )
        graph.add_node(job_node)
        visited[job_id] = node_name

        # 1. Handle dependency via `job._depends_on`
        if getattr(job, "_depends_on", None) is not None:
            dep_node_name = self._add_job_subgraph(job._depends_on, graph, visited)
            edge = pydot.Edge(dep_node_name, node_name, label="to", fontsize="8")
            graph.add_edge(edge)

        # 2. Handle post-run methods (stored sequentially)
        prev = node_name
        for idx, method_info in enumerate(getattr(job, "_post_run_methods", [])):
            if isinstance(method_info, str):
                method_name = method_info
            else:
                method_name = method_info[0]  # (name, args, kwargs)

            meth_node_name = f"{node_name}_meth_{idx}"
            meth_label = method_name
            meth_node = pydot.Node(
                meth_node_name,
                label=meth_label,
                shape="ellipse",
                style="filled",
                fillcolor="khaki",
                fontsize="10",
            )
            graph.add_node(meth_node)
            graph.add_edge(pydot.Edge(prev, meth_node_name, style="dashed"))
            prev = meth_node_name

        return node_name

    # --------------------------------------------------------------
    @staticmethod
    def _job_label(job: "Jobs") -> str:  # noqa: F821 – forward ref
        """Return a compact label for *job* suitable for graph nodes."""
        summary = job._summary()  # type: ignore[attr-defined]
        return (
            f"Jobs\nquestions: {summary['questions']},\n"
            f"agents: {summary['agents']}, models: {summary['models']},\n"
            f"scenarios: {summary['scenarios']}"
        ) 