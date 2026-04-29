"""Visualization utilities for showing the execution flow of a `Jobs` object.

This module visualises:
1. The dependency chain created via the `Jobs.to(...)` method.
2. The sequence of post-run result transformations stored in `Jobs._post_run_methods`.

Supports both Mermaid (text-based, no dependencies) and pydot/graphviz backends.
"""

from __future__ import annotations

from typing import Optional, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.jobs.jobs import Jobs


class JobsFlowVisualization:
    """Create a flowchart diagram for a :class:`edsl.jobs.jobs.Jobs` instance."""

    def __init__(self, job: "Jobs") -> None:
        from edsl.jobs.jobs import Jobs

        if not isinstance(job, Jobs):
            raise TypeError("Expected an `edsl.jobs.jobs.Jobs` instance.")
        self.job = job

    def show_flow(
        self, filename: Optional[str] = None, renderer: Optional[str] = None
    ) -> None:
        """Render or save a flowchart for *self.job*.

        Args:
            filename: Optional path to save the output.
            renderer: "mermaid" or "pydot" (default: auto-detect).
        """
        from edsl.utilities.graph_renderer import DiGraph

        graph = DiGraph(renderer=renderer, direction="LR")

        visited: Dict[int, str] = {}
        self._add_job_subgraph(self.job, graph, visited)

        return graph.show(filename=filename)

    def _add_job_subgraph(
        self, job: "Jobs", graph, visited: Dict[int, str]
    ) -> str:
        """Recursively add *job* and its dependencies to *graph*.

        Returns the node name corresponding to *job*.
        """
        job_id = id(job)
        if job_id in visited:
            return visited[job_id]

        node_name = f"job_{job_id}"
        label = self._job_label(job)
        graph.add_node(node_name, label=label, shape="box", fill_color="lightblue")
        visited[job_id] = node_name

        # Handle dependency via job._depends_on
        if getattr(job, "_depends_on", None) is not None:
            dep_node_name = self._add_job_subgraph(job._depends_on, graph, visited)
            graph.add_edge(dep_node_name, node_name, label="to")

        # Handle post-run methods
        prev = node_name
        for idx, method_info in enumerate(getattr(job, "_post_run_methods", [])):
            method_name = method_info if isinstance(method_info, str) else method_info[0]
            meth_node_name = f"{node_name}_meth_{idx}"
            graph.add_node(meth_node_name, label=method_name, shape="ellipse", fill_color="khaki")
            graph.add_edge(prev, meth_node_name, style="dashed")
            prev = meth_node_name

        return node_name

    @staticmethod
    def _job_label(job: "Jobs") -> str:
        summary = job._summary()
        return (
            f"Jobs\nquestions: {summary['questions']},\n"
            f"agents: {summary['agents']}, models: {summary['models']},\n"
            f"scenarios: {summary['scenarios']}"
        )
