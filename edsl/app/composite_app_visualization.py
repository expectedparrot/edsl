"""Visualization helper for CompositeApp."""

from typing import Optional, TYPE_CHECKING
import tempfile

if TYPE_CHECKING:
    from .composite_app import CompositeApp


class CompositeAppVisualization:
    """Helper class for visualizing CompositeApp flow."""

    def __init__(self, composite_app: "CompositeApp"):
        self.composite_app = composite_app

    def show(self, filename: Optional[str] = None) -> None:
        """Show a visualization of the composite app flow.

        This creates a graph showing:
        - The two apps (app1 and app2) as boxes
        - Input parameters for each app
        - Output formatters for each app
        - Bindings between app1 outputs/params and app2 inputs
        - Fixed parameters

        Args:
            filename: Optional path to save the image. If None, displays in notebook or opens viewer.
        """
        try:
            import pydot
        except ImportError:
            print("pydot is required for visualization. Install with: pip install pydot")
            return

        FONT_SIZE = "10"
        graph = pydot.Dot(graph_type="digraph", rankdir="LR", fontsize=FONT_SIZE)

        # Create subgraphs for each app
        # Extract display names (now simple strings)
        app1_name = self.composite_app.first_app.display_name
        app2_name = "?"
        if self.composite_app.second_app:
            app2_name = self.composite_app.second_app.display_name

        cluster_app1 = pydot.Cluster(
            "app1",
            label=f"App 1: {app1_name}",
            style="filled",
            fillcolor="lightblue",
        )
        cluster_app2 = pydot.Cluster(
            "app2",
            label=f"App 2: {app2_name}",
            style="filled",
            fillcolor="lightgreen",
        )

        # Add App1 inputs
        for param in self.composite_app.first_app.initial_survey.questions:
            param_name = param.question_name
            is_fixed = param_name in self.composite_app.fixed["app1"]

            node_attrs = {
                "label": f"{param_name}",
                "shape": "box",
                "style": "filled",
                "fillcolor": "yellow" if is_fixed else "white",
                "fontsize": FONT_SIZE,
            }
            if is_fixed:
                node_attrs["label"] = f"{param_name}\n(fixed: {self.composite_app.fixed['app1'][param_name]})"

            node = pydot.Node(f"app1_input_{param_name}", **node_attrs)
            cluster_app1.add_node(node)

        # Add App1 core
        app1_core = pydot.Node(
            "app1_core",
            label=f"{app1_name}",
            shape="ellipse",
            style="filled",
            fillcolor="lightcyan",
            fontsize=FONT_SIZE,
        )
        cluster_app1.add_node(app1_core)

        # Connect inputs to core
        for param in self.composite_app.first_app.initial_survey.questions:
            param_name = param.question_name
            edge = pydot.Edge(f"app1_input_{param_name}", "app1_core", style="solid", fontsize=FONT_SIZE)
            cluster_app1.add_edge(edge)

        # Add App1 output formatters
        for formatter_name in self.composite_app.first_app.output_formatters.mapping.keys():
            node = pydot.Node(
                f"app1_output_{formatter_name}",
                label=f"{formatter_name}",
                shape="box",
                style="filled",
                fillcolor="lightyellow",
                fontsize=FONT_SIZE,
            )
            cluster_app1.add_node(node)
            edge = pydot.Edge("app1_core", f"app1_output_{formatter_name}", style="solid", fontsize=FONT_SIZE)
            cluster_app1.add_edge(edge)

        graph.add_subgraph(cluster_app1)

        if self.composite_app.second_app:
            # Add App2 inputs
            for param in self.composite_app.second_app.initial_survey.questions:
                param_name = param.question_name
                is_fixed = param_name in self.composite_app.fixed["app2"]
                is_bound = param_name in self.composite_app.bindings.values()

                node_attrs = {
                    "label": f"{param_name}",
                    "shape": "box",
                    "style": "filled",
                    "fillcolor": "yellow" if is_fixed else ("lightgreen" if is_bound else "white"),
                    "fontsize": FONT_SIZE,
                }
                if is_fixed:
                    node_attrs["label"] = f"{param_name}\n(fixed: {self.composite_app.fixed['app2'][param_name]})"

                node = pydot.Node(f"app2_input_{param_name}", **node_attrs)
                cluster_app2.add_node(node)

            # Add App2 core
            app2_core = pydot.Node(
                "app2_core",
                label=f"{app2_name}",
                shape="ellipse",
                style="filled",
                fillcolor="lightcyan",
                fontsize=FONT_SIZE,
            )
            cluster_app2.add_node(app2_core)

            # Connect inputs to core
            for param in self.composite_app.second_app.initial_survey.questions:
                param_name = param.question_name
                edge = pydot.Edge(f"app2_input_{param_name}", "app2_core", style="solid", fontsize=FONT_SIZE)
                cluster_app2.add_edge(edge)

            # Add App2 output formatters
            for formatter_name in self.composite_app.second_app.output_formatters.mapping.keys():
                node = pydot.Node(
                    f"app2_output_{formatter_name}",
                    label=f"{formatter_name}",
                    shape="box",
                    style="filled",
                    fillcolor="lightyellow",
                    fontsize=FONT_SIZE,
                )
                cluster_app2.add_node(node)
                edge = pydot.Edge("app2_core", f"app2_output_{formatter_name}", style="solid", fontsize=FONT_SIZE)
                cluster_app2.add_edge(edge)

            graph.add_subgraph(cluster_app2)

            # Add binding edges between app1 and app2
            for source_spec, target_param in self.composite_app.bindings.items():
                if isinstance(source_spec, str):
                    if source_spec.startswith("param:"):
                        # Binding from app1 input parameter
                        app1_param = source_spec[len("param:") :]
                        source_node = f"app1_input_{app1_param}"
                        label = f"param: {app1_param}"
                    else:
                        # Binding from app1 output formatter
                        source_node = f"app1_output_{source_spec}"
                        label = f"formatter: {source_spec}"
                elif isinstance(source_spec, dict) and "formatter" in source_spec:
                    # Binding from app1 formatter with path
                    formatter_name = source_spec["formatter"]
                    path = source_spec.get("path", "")
                    source_node = f"app1_output_{formatter_name}"
                    label = f"formatter: {formatter_name}\npath: {path}"
                else:
                    continue

                target_node = f"app2_input_{target_param}"
                edge = pydot.Edge(
                    source_node,
                    target_node,
                    label=label,
                    style="dashed",
                    color="blue",
                    fontcolor="blue",
                    fontsize=FONT_SIZE,
                    constraint="false",  # Allow cross-cluster edges to be more flexible
                )
                graph.add_edge(edge)

        # Save or display
        if filename is not None:
            graph.write_png(filename)
            print(f"Composite app visualization saved to {filename}")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            try:
                graph.write_png(tmp_file.name)
            except FileNotFoundError:
                print(
                    """File not found. Most likely it's because you don't have graphviz installed. Please install it and try again.
                    On Ubuntu, you can install it by running:
                    $ sudo apt-get install graphviz
                    On Mac, you can install it by running:
                    $ brew install graphviz
                    On Windows, you can install it by running:
                    $ choco install graphviz
                    """
                )
                return

            from edsl.utilities.is_notebook import is_notebook

            if is_notebook():
                from IPython.display import Image, display

                display(Image(tmp_file.name))
            else:
                import os
                import sys

                if os.name == "nt":  # Windows
                    os.system(f"start {tmp_file.name}")
                elif os.name == "posix":  # macOS, Linux, Unix, etc.
                    os.system(
                        f"open {tmp_file.name}" if sys.platform == "darwin" else f"xdg-open {tmp_file.name}"
                    )
