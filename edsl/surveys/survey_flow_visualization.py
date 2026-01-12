"""A mixin for visualizing the flow of a survey with parameter nodes."""

from typing import Optional
from edsl.surveys.base import RulePriority, EndOfSurvey
import tempfile


# Import types for annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..surveys.survey import Survey
    from ..scenarios import Scenario
    from ..agents import Agent


class SurveyFlowVisualization:
    """A mixin for visualizing the flow of a survey with parameter visualization."""

    def __init__(
        self,
        survey: "Survey",
        scenario: Optional["Scenario"] = None,
        agent: Optional["Agent"] = None,
    ):
        self.survey = survey
        self.scenario = scenario or {}
        self.agent = agent
        # from edsl import Scenario
        # self.scenario = Scenario({'hello': 'world'})

    def show_flow(self, filename: Optional[str] = None):
        """Create an image showing the flow of users through the survey and question parameters.

        In marimo notebooks, returns a PIL Image that will be displayed automatically.
        In Jupyter/Colab, displays the image inline using IPython.display.
        Otherwise, opens the image in the system viewer.
        """
        # Create a graph object
        import pydot

        FONT_SIZE = "10"

        graph = pydot.Dot(graph_type="digraph", fontsize=FONT_SIZE)

        # First collect all unique parameters and different types of references
        params_and_refs = set()
        param_to_questions = {}  # Keep track of which questions use each parameter
        reference_types = {}  # Dictionary to store different types of references
        reference_colors = {
            "answer": "purple",
            "question_text": "red",
            "question_options": "orange",
            "comment": "blue",
            "default": "grey",
        }

        # Build a mapping of questions to their groups
        question_to_group = {}
        if self.survey.question_groups:
            for group_name, (start_idx, end_idx) in self.survey.question_groups.items():
                for q_idx in range(start_idx, end_idx + 1):
                    if q_idx < len(self.survey.questions):
                        question_to_group[q_idx] = group_name

        # Create question groups as subgraph clusters first
        group_colors = [
            "lightblue",
            "lightgreen",
            "lightyellow",
            "lightcyan",
            "lightpink",
            "lavender",
            "mistyrose",
            "honeydew",
        ]

        group_clusters = {}
        if self.survey.question_groups:
            for i, (group_name, (start_idx, end_idx)) in enumerate(
                self.survey.question_groups.items()
            ):
                color = group_colors[i % len(group_colors)]

                # Create a subgraph cluster for the group
                cluster = pydot.Cluster(
                    f"cluster_{group_name}",
                    label=f"Group: {group_name}",
                    style="filled",
                    fillcolor=color,
                    color="black",
                    fontsize=str(int(FONT_SIZE) + 2),
                    fontname="Arial Bold",
                )
                group_clusters[group_name] = cluster

        # First pass: collect parameters and their question associations
        for index, question in enumerate(self.survey.questions):
            question_node = pydot.Node(
                f"Q{index}",
                label=f"{question.question_name}",
                shape="ellipse",
                fontsize=FONT_SIZE,
            )

            # Add node to appropriate cluster or main graph
            if index in question_to_group:
                group_name = question_to_group[index]
                group_clusters[group_name].add_node(question_node)
            else:
                graph.add_node(question_node)

            if hasattr(question, "detailed_parameters"):
                for param in question.detailed_parameters:
                    if "agent." in param:
                        # Handle agent trait references
                        # trait_name = param.replace("agent.", "")
                        params_and_refs.add(param)
                        if param not in param_to_questions:
                            param_to_questions[param] = []
                        param_to_questions[param].append(index)
                    if "scenario." in param:
                        params_and_refs.add(param)
                        if param not in param_to_questions:
                            param_to_questions[param] = []
                        param_to_questions[param].append(index)
                    elif "." in param:
                        source_q, ref_type = param.split(".", 1)
                        if ref_type not in reference_types:
                            reference_types[ref_type] = set()
                        reference_types[ref_type].add((source_q, index))
                    else:
                        params_and_refs.add(param)
                        if param not in param_to_questions:
                            param_to_questions[param] = []
                        param_to_questions[param].append(index)

        # Add group clusters to the graph
        for cluster in group_clusters.values():
            graph.add_subgraph(cluster)

        # Add edges for all reference types
        for ref_type, references in reference_types.items():
            color = reference_colors.get(ref_type, reference_colors["default"])
            for source_q_name, target_q_index in references:
                # Find the source question index by name
                try:
                    source_q_index = next(
                        i
                        for i, q in enumerate(self.survey.questions)
                        if q.question_name == source_q_name
                    )
                except StopIteration:
                    print(f"Source question {source_q_name} not found in survey.")
                    continue

                ref_edge = pydot.Edge(
                    f"Q{source_q_index}",
                    f"Q{target_q_index}",
                    style="dashed",
                    color=color,
                    label=f".{ref_type}",
                    fontcolor=color,
                    fontname="Courier",
                    fontsize=FONT_SIZE,
                )
                graph.add_edge(ref_edge)

        # Create parameter nodes and connect them to questions
        for param in params_and_refs:
            param_node_name = f"param_{param}"
            node_attrs = {
                "label": f"{{{{ {param} }}}}",
                "shape": "box",
                "style": "filled",
                "fillcolor": "lightgrey",
                "fontsize": FONT_SIZE,
            }

            # Special handling for agent traits
            if param.startswith("agent."):
                node_attrs.update(
                    {
                        "fillcolor": "lightpink",
                        "label": f"Agent Trait\n{{{{ {param} }}}}",
                    }
                )
            # Check if parameter exists in scenario
            elif self.scenario and param.startswith("scenario."):
                node_attrs.update(
                    {"fillcolor": "lightgreen", "label": f"Scenario\n{{{{ {param} }}}}"}
                )

            param_node = pydot.Node(param_node_name, **node_attrs)
            graph.add_node(param_node)

            # Connect this parameter to all questions that use it
            for q_index in param_to_questions[param]:
                param_edge = pydot.Edge(
                    param_node_name,
                    f"Q{q_index}",
                    style="dotted",
                    arrowsize="0.5",
                    fontsize=FONT_SIZE,
                )
                graph.add_edge(param_edge)

        # Add an "EndOfSurvey" node
        graph.add_node(
            pydot.Node(
                "EndOfSurvey",
                label="End of Survey",
                shape="rectangle",
                fontsize=FONT_SIZE,
                style="filled",
                fillcolor="lightgrey",
            )
        )

        # Add edges for normal flow through the survey
        num_questions = len(self.survey.questions)
        for index in range(num_questions - 1):
            graph.add_edge(pydot.Edge(f"Q{index}", f"Q{index+1}", fontsize=FONT_SIZE))

        graph.add_edge(
            pydot.Edge(f"Q{num_questions-1}", "EndOfSurvey", fontsize=FONT_SIZE)
        )

        relevant_rules = [
            rule
            for rule in self.survey.rule_collection
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
            "darkgreen",
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
                    fontname="Courier",
                    fontsize=FONT_SIZE,
                )
            else:
                edge = pydot.Edge(
                    source_node,
                    target_node,
                    label=edge_label,
                    color=color,
                    fontcolor=color,
                    fontname="Courier",
                    fontsize=FONT_SIZE,
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
                        On Ubuntu, you can install it by running:
                        $ sudo apt-get install graphviz 
                        On Mac, you can install it by running:
                        $ brew install graphviz
                        On Windows, you can install it by running:
                        $ choco install graphviz
                    """
                )
            from edsl.utilities.is_notebook import is_notebook
            import sys

            if is_notebook():
                # Check if we're in marimo
                if "marimo" in sys.modules:
                    # marimo can display PIL Images directly
                    from PIL import Image as PILImage

                    img = PILImage.open(tmp_file.name)
                    return img
                else:
                    # Jupyter/Colab: use IPython display
                    try:
                        from IPython.display import Image, display
                        display(Image(tmp_file.name))
                    except ImportError:
                        # Fall back to opening the file directly
                        import os
                        if os.name == "nt":
                            os.system(f"start {tmp_file.name}")
                        elif sys.platform == "darwin":
                            os.system(f"open {tmp_file.name}")
                        else:
                            os.system(f"xdg-open {tmp_file.name}")
            else:
                import os

                if os.name == "nt":  # Windows
                    os.system(f"start {tmp_file.name}")
                elif os.name == "posix":  # macOS, Linux, Unix, etc.
                    os.system(
                        f"open {tmp_file.name}"
                        if sys.platform == "darwin"
                        else f"xdg-open {tmp_file.name}"
                    )
