"""Visualization helper for CompositeMacro."""

from typing import Optional, TYPE_CHECKING
import tempfile

if TYPE_CHECKING:
    from .composite_macro import CompositeMacro


class CompositeMacroVisualization:
    """Helper class for visualizing CompositeMacro flow."""

    def __init__(self, composite_macro: "CompositeMacro"):
        self.composite_macro = composite_macro

    def show(self, filename: Optional[str] = None) -> None:
        """Show a visualization of the composite macro flow.

        This creates a graph showing:
        - The two macros (macro1 and macro2) as boxes
        - Input parameters for each macro
        - Output formatters for each macro
        - Bindings between macro1 outputs/params and macro2 inputs
        - Fixed parameters

        Args:
            filename: Optional path to save the image. If None, displays in notebook or opens viewer.
        """
        try:
            import pydot
        except ImportError:
            print(
                "pydot is required for visualization. Install with: pip install pydot"
            )
            return

        FONT_SIZE = "10"
        graph = pydot.Dot(graph_type="digraph", rankdir="LR", fontsize=FONT_SIZE)

        # Create subgraphs for each macro
        # Extract display names (now simple strings)
        macro1_name = self.composite_macro.first_macro.display_name
        macro2_name = "?"
        if self.composite_macro.second_macro:
            macro2_name = self.composite_macro.second_macro.display_name

        cluster_macro1 = pydot.Cluster(
            "macro1",
            label=f"Macro 1: {macro1_name}",
            style="filled",
            fillcolor="lightblue",
        )
        cluster_macro2 = pydot.Cluster(
            "macro2",
            label=f"Macro 2: {macro2_name}",
            style="filled",
            fillcolor="lightgreen",
        )

        # Add Macro1 inputs
        for param in self.composite_macro.first_macro.initial_survey.questions:
            param_name = param.question_name
            is_fixed = param_name in self.composite_macro.fixed["macro1"]

            node_attrs = {
                "label": f"{param_name}",
                "shape": "box",
                "style": "filled",
                "fillcolor": "yellow" if is_fixed else "white",
                "fontsize": FONT_SIZE,
            }
            if is_fixed:
                node_attrs["label"] = (
                    f"{param_name}\n(fixed: {self.composite_macro.fixed['macro1'][param_name]})"
                )

            node = pydot.Node(f"macro1_input_{param_name}", **node_attrs)
            cluster_macro1.add_node(node)

        # Add Macro1 core
        macro1_core = pydot.Node(
            "macro1_core",
            label=f"{macro1_name}",
            shape="ellipse",
            style="filled",
            fillcolor="lightcyan",
            fontsize=FONT_SIZE,
        )
        cluster_macro1.add_node(macro1_core)

        # Connect inputs to core
        for param in self.composite_macro.first_macro.initial_survey.questions:
            param_name = param.question_name
            edge = pydot.Edge(
                f"macro1_input_{param_name}",
                "macro1_core",
                style="solid",
                fontsize=FONT_SIZE,
            )
            cluster_macro1.add_edge(edge)

        # Add Macro1 output formatters
        for (
            formatter_name
        ) in self.composite_macro.first_macro.output_formatters.mapping.keys():
            node = pydot.Node(
                f"macro1_output_{formatter_name}",
                label=f"{formatter_name}",
                shape="box",
                style="filled",
                fillcolor="lightyellow",
                fontsize=FONT_SIZE,
            )
            cluster_macro1.add_node(node)
            edge = pydot.Edge(
                "macro1_core",
                f"macro1_output_{formatter_name}",
                style="solid",
                fontsize=FONT_SIZE,
            )
            cluster_macro1.add_edge(edge)

        graph.add_subgraph(cluster_macro1)

        if self.composite_macro.second_macro:
            # Add Macro2 inputs
            for param in self.composite_macro.second_macro.initial_survey.questions:
                param_name = param.question_name
                is_fixed = param_name in self.composite_macro.fixed["macro2"]
                is_bound = param_name in self.composite_macro.bindings.values()

                node_attrs = {
                    "label": f"{param_name}",
                    "shape": "box",
                    "style": "filled",
                    "fillcolor": (
                        "yellow"
                        if is_fixed
                        else ("lightgreen" if is_bound else "white")
                    ),
                    "fontsize": FONT_SIZE,
                }
                if is_fixed:
                    node_attrs["label"] = (
                        f"{param_name}\n(fixed: {self.composite_macro.fixed['macro2'][param_name]})"
                    )

                node = pydot.Node(f"macro2_input_{param_name}", **node_attrs)
                cluster_macro2.add_node(node)

            # Add Macro2 core
            macro2_core = pydot.Node(
                "macro2_core",
                label=f"{macro2_name}",
                shape="ellipse",
                style="filled",
                fillcolor="lightcyan",
                fontsize=FONT_SIZE,
            )
            cluster_macro2.add_node(macro2_core)

            # Connect inputs to core
            for param in self.composite_macro.second_macro.initial_survey.questions:
                param_name = param.question_name
                edge = pydot.Edge(
                    f"macro2_input_{param_name}",
                    "macro2_core",
                    style="solid",
                    fontsize=FONT_SIZE,
                )
                cluster_macro2.add_edge(edge)

            # Add Macro2 output formatters
            for (
                formatter_name
            ) in self.composite_macro.second_macro.output_formatters.mapping.keys():
                node = pydot.Node(
                    f"macro2_output_{formatter_name}",
                    label=f"{formatter_name}",
                    shape="box",
                    style="filled",
                    fillcolor="lightyellow",
                    fontsize=FONT_SIZE,
                )
                cluster_macro2.add_node(node)
                edge = pydot.Edge(
                    "macro2_core",
                    f"macro2_output_{formatter_name}",
                    style="solid",
                    fontsize=FONT_SIZE,
                )
                cluster_macro2.add_edge(edge)

            graph.add_subgraph(cluster_macro2)

            # Add binding edges between macro1 and macro2
            for source_spec, target_param in self.composite_macro.bindings.items():
                if isinstance(source_spec, str):
                    if source_spec.startswith("param:"):
                        # Binding from macro1 input parameter
                        macro1_param = source_spec[len("param:") :]
                        source_node = f"macro1_input_{macro1_param}"
                        label = f"param: {macro1_param}"
                    else:
                        # Binding from macro1 output formatter
                        source_node = f"macro1_output_{source_spec}"
                        label = f"formatter: {source_spec}"
                elif isinstance(source_spec, dict) and "formatter" in source_spec:
                    # Binding from macro1 formatter with path
                    formatter_name = source_spec["formatter"]
                    path = source_spec.get("path", "")
                    source_node = f"macro1_output_{formatter_name}"
                    label = f"formatter: {formatter_name}\npath: {path}"
                else:
                    continue

                target_node = f"macro2_input_{target_param}"
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
            print(f"Composite macro visualization saved to {filename}")
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
                        f"open {tmp_file.name}"
                        if sys.platform == "darwin"
                        else f"xdg-open {tmp_file.name}"
                    )
