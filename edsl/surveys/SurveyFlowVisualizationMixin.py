"""A mixin for visualizing the flow of a survey with parameter nodes."""

from typing import Optional
from edsl.surveys.base import RulePriority, EndOfSurvey
import tempfile
import os


class SurveyFlowVisualizationMixin:
    """A mixin for visualizing the flow of a survey with parameter visualization."""

    def show_flow(self, filename: Optional[str] = None):
        """Create an image showing the flow of users through the survey and question parameters."""
        # Create a graph object
        import pydot

        graph = pydot.Dot(graph_type="digraph")

        # First collect all unique parameters and answer references
        params_and_refs = set()
        param_to_questions = {}  # Keep track of which questions use each parameter
        answer_refs = set()  # Track answer references between questions

        # First pass: collect parameters and their question associations
        for index, question in enumerate(self.questions):
            # Add the main question node
            question_node = pydot.Node(
                f"Q{index}", label=f"{question.question_name}", shape="ellipse"
            )
            graph.add_node(question_node)

            if hasattr(question, "parameters"):
                for param in question.parameters:
                    # Check if this is an answer reference (contains '.answer')
                    if ".answer" in param:
                        answer_refs.add((param.split(".")[0], index))
                    else:
                        params_and_refs.add(param)
                        if param not in param_to_questions:
                            param_to_questions[param] = []
                        param_to_questions[param].append(index)

        # Create parameter nodes and connect them to questions
        for param in params_and_refs:
            param_node_name = f"param_{param}"
            param_node = pydot.Node(
                param_node_name,
                label=f"{{{{ {param} }}}}",
                shape="box",
                style="filled",
                fillcolor="lightgrey",
                fontsize="10",
            )
            graph.add_node(param_node)

            # Connect this parameter to all questions that use it
            for q_index in param_to_questions[param]:
                param_edge = pydot.Edge(
                    param_node_name,
                    f"Q{q_index}",
                    style="dotted",
                    color="grey",
                    arrowsize="0.5",
                )
                graph.add_edge(param_edge)

        # Add edges for answer references
        for source_q_name, target_q_index in answer_refs:
            # Find the source question index by name
            source_q_index = next(
                i
                for i, q in enumerate(self.questions)
                if q.question_name == source_q_name
            )
            ref_edge = pydot.Edge(
                f"Q{source_q_index}",
                f"Q{target_q_index}",
                style="dashed",
                color="purple",
                label="answer reference",
            )
            graph.add_edge(ref_edge)

        # Add an "EndOfSurvey" node
        graph.add_node(
            pydot.Node("EndOfSurvey", label="End of Survey", shape="rectangle")
        )

        # Add edges for normal flow through the survey
        num_questions = len(self.questions)
        for index in range(num_questions - 1):
            graph.add_edge(pydot.Edge(f"Q{index}", f"Q{index+1}"))

        graph.add_edge(pydot.Edge(f"Q{num_questions-1}", "EndOfSurvey"))

        relevant_rules = [
            rule
            for rule in self.rule_collection
            if rule.priority > RulePriority.DEFAULT.value
        ]

        # edge-colors to cycle through
        colors = [
            "blue",
            "red",
            "orange",
            "purple",
            "brown",
            "cyan",
            "green",
        ]
        rule_colors = {
            rule: colors[i % len(colors)] for i, rule in enumerate(relevant_rules)
        }

        for rule in relevant_rules:
            color = rule_colors[rule]
            edge_label = f"if {rule.expression}"
            source_node = f"Q{rule.current_q}"
            target_node = (
                f"Q{rule.next_q}"
                if rule.next_q != EndOfSurvey and rule.next_q < num_questions
                else "EndOfSurvey"
            )
            if rule.before_rule:
                edge = pydot.Edge(
                    source_node,
                    target_node,
                    label=edge_label,
                    color=color,
                    fontcolor=color,
                    tailport="n",
                    headport="n",
                )
            else:
                edge = pydot.Edge(
                    source_node,
                    target_node,
                    label=edge_label,
                    color=color,
                    fontcolor=color,
                )

            graph.add_edge(edge)

        if filename is not None:
            graph.write_png(filename)
            print(f"Flowchart saved to {filename}")
            return

        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_file:
            try:
                graph.write_png(tmp_file.name)
            except FileNotFoundError:
                print(
                    """File not found. Most likely it's because you don't have graphviz installed. Please install it and try again.
                        It's 
                        $ sudo apt-get install graphviz 
                        on Ubuntu.
                    """
                )
            from edsl.utilities.utilities import is_notebook

            if is_notebook():
                from IPython.display import Image

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
