"""Visualization helper for CompositeMacro.

Supports both Mermaid (text-based, no dependencies) and pydot/graphviz backends.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .composite_macro import CompositeMacro


class CompositeMacroVisualization:
    """Helper class for visualizing CompositeMacro flow."""

    def __init__(self, composite_macro: "CompositeMacro"):
        self.composite_macro = composite_macro

    def show(self, filename: Optional[str] = None, renderer: Optional[str] = None) -> None:
        """Show a visualization of the composite macro flow.

        Args:
            filename: Optional path to save the output.
            renderer: "mermaid" or "pydot" (default: auto-detect).
        """
        from edsl.utilities.graph_renderer import DiGraph

        graph = DiGraph(renderer=renderer, direction="LR")

        macro1_name = self.composite_macro.first_macro.display_name
        macro2_name = "?"
        if self.composite_macro.second_macro:
            macro2_name = self.composite_macro.second_macro.display_name

        # Create subgraphs
        graph.add_subgraph("macro1", label=f"Macro 1: {macro1_name}", fill_color="lightblue")

        # Macro1 inputs
        for param in self.composite_macro.first_macro.initial_survey.questions:
            param_name = param.question_name
            is_fixed = param_name in self.composite_macro.fixed["macro1"]
            if is_fixed:
                label = f"{param_name}\n(fixed: {self.composite_macro.fixed['macro1'][param_name]})"
                fill = "yellow"
            else:
                label = param_name
                fill = "white"
            graph.add_node(f"macro1_input_{param_name}", label=label, shape="box", fill_color=fill, subgraph="macro1")

        # Macro1 core
        graph.add_node("macro1_core", label=macro1_name, shape="ellipse", fill_color="lightcyan", subgraph="macro1")

        # Connect inputs to core
        for param in self.composite_macro.first_macro.initial_survey.questions:
            graph.add_edge(f"macro1_input_{param.question_name}", "macro1_core")

        # Macro1 output formatters
        for formatter_name in self.composite_macro.first_macro.output_formatters.mapping.keys():
            graph.add_node(
                f"macro1_output_{formatter_name}", label=formatter_name,
                shape="box", fill_color="lightyellow", subgraph="macro1",
            )
            graph.add_edge("macro1_core", f"macro1_output_{formatter_name}")

        if self.composite_macro.second_macro:
            graph.add_subgraph("macro2", label=f"Macro 2: {macro2_name}", fill_color="lightgreen")

            # Macro2 inputs
            for param in self.composite_macro.second_macro.initial_survey.questions:
                param_name = param.question_name
                is_fixed = param_name in self.composite_macro.fixed["macro2"]
                is_bound = param_name in self.composite_macro.bindings.values()
                if is_fixed:
                    label = f"{param_name}\n(fixed: {self.composite_macro.fixed['macro2'][param_name]})"
                    fill = "yellow"
                elif is_bound:
                    label = param_name
                    fill = "lightgreen"
                else:
                    label = param_name
                    fill = "white"
                graph.add_node(f"macro2_input_{param_name}", label=label, shape="box", fill_color=fill, subgraph="macro2")

            # Macro2 core
            graph.add_node("macro2_core", label=macro2_name, shape="ellipse", fill_color="lightcyan", subgraph="macro2")

            # Connect inputs to core
            for param in self.composite_macro.second_macro.initial_survey.questions:
                graph.add_edge(f"macro2_input_{param.question_name}", "macro2_core")

            # Macro2 output formatters
            for formatter_name in self.composite_macro.second_macro.output_formatters.mapping.keys():
                graph.add_node(
                    f"macro2_output_{formatter_name}", label=formatter_name,
                    shape="box", fill_color="lightyellow", subgraph="macro2",
                )
                graph.add_edge("macro2_core", f"macro2_output_{formatter_name}")

            # Binding edges
            for source_spec, target_param in self.composite_macro.bindings.items():
                if isinstance(source_spec, str):
                    if source_spec.startswith("param:"):
                        macro1_param = source_spec[len("param:"):]
                        source_node = f"macro1_input_{macro1_param}"
                        label = f"param: {macro1_param}"
                    else:
                        source_node = f"macro1_output_{source_spec}"
                        label = f"formatter: {source_spec}"
                elif isinstance(source_spec, dict) and "formatter" in source_spec:
                    formatter_name = source_spec["formatter"]
                    path = source_spec.get("path", "")
                    source_node = f"macro1_output_{formatter_name}"
                    label = f"formatter: {formatter_name}\npath: {path}"
                else:
                    continue

                graph.add_edge(
                    source_node, f"macro2_input_{target_param}",
                    label=label, style="dashed", color="blue", font_color="blue",
                )

        return graph.show(filename=filename)
