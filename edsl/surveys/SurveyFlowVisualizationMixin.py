"""A mixin for visualizing the flow of a survey."""
import pydot
import tempfile
from IPython.display import Image
from edsl.utilities import is_notebook
from edsl.surveys.base import RulePriority, EndOfSurvey


class SurveyFlowVisualizationMixin:
    """A mixin for visualizing the flow of a survey."""

    def show_flow(self):
        """Create an image showing the flow of users through the survey."""
        # Create a graph object
        graph = pydot.Dot(graph_type="digraph")

        # Add nodes
        for index, question in enumerate(self.questions):
            graph.add_node(
                pydot.Node(
                    f"Q{index}", label=f"{question.question_name}", shape="ellipse"
                )
            )

        # Add an "EndOfSurvey" node
        graph.add_node(
            pydot.Node("EndOfSurvey", label="End of Survey", shape="rectangle")
        )

        # Add edges for normal flow
        num_questions = len(self.questions)
        for index in range(num_questions - 1):  # From Q1 to Q3
            graph.add_edge(pydot.Edge(f"Q{index}", f"Q{index+1}"))

        graph.add_edge(pydot.Edge(f"Q{num_questions-1}", "EndOfSurvey"))

        relevant_rules = [
            rule
            for rule in self.rule_collection
            if rule.priority > RulePriority.DEFAULT.value
        ]

        colors = [
            "blue",
            "red",
            "purple",
            "orange",
            "pink",
            "brown",
            "grey",
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
                f"Q{rule.next_q}" if rule.next_q != EndOfSurvey else "EndOfSurvey"
            )
            edge = pydot.Edge(
                source_node, target_node, label=edge_label, color=color, fontcolor=color
            )
            graph.add_edge(edge)

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

            if is_notebook():
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
