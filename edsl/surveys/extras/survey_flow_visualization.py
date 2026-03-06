"""A mixin for visualizing the flow of a survey with parameter nodes.

Supports both Mermaid (text-based, no dependencies) and pydot/graphviz backends.
"""

from typing import Optional, TYPE_CHECKING

from edsl.surveys.base import RulePriority, EndOfSurvey

if TYPE_CHECKING:
    from edsl.surveys.survey import Survey
    from edsl.scenarios import Scenario
    from edsl.agents import Agent


_QUESTION_TYPE_ICONS = {
    "free_text": "✏️",
    "multiple_choice": "◉",
    "checkbox": "☑",
    "linear_scale": "⟷",
    "numerical": "#",
    "yes_no": "Y/N",
    "likert_five": "★5",
    "top_k": "🔝",
    "rank": "↕",
    "budget": "$",
    "extract": "⛏",
    "list": "▤",
    "dropdown": "▾",
    "matrix": "▦",
    "file_upload": "📎",
}


def _question_label(question, max_text_len: int = 40) -> str:
    """Build a rich label for a question node."""
    icon = _QUESTION_TYPE_ICONS.get(getattr(question, "question_type", ""), "?")
    name = question.question_name
    text = getattr(question, "question_text", "") or ""
    if len(text) > max_text_len:
        text = text[:max_text_len] + "…"
    return f"[{icon}] {name}\n{text}"


class SurveyFlowVisualization:
    """Visualize the flow of a survey with parameter visualization."""

    def __init__(
        self,
        survey: "Survey",
        scenario: Optional["Scenario"] = None,
        agent: Optional["Agent"] = None,
    ):
        self.survey = survey
        self.scenario = scenario or {}
        self.agent = agent

    def show_flow(self, filename: Optional[str] = None, renderer: Optional[str] = None):
        """Create a visualization showing the survey flow and question parameters.

        Args:
            filename: Optional path to save the output.
            renderer: "mermaid" or "pydot" (default: auto-detect).
        """
        from edsl.utilities.graph_renderer import DiGraph

        graph = DiGraph(renderer=renderer)

        reference_colors = {
            "answer": "purple",
            "question_text": "red",
            "question_options": "orange",
            "comment": "blue",
            "default": "grey",
        }

        # Build question-to-group mapping
        question_to_group = {}
        if self.survey.question_groups:
            for group_name, (start_idx, end_idx) in self.survey.question_groups.items():
                for q_idx in range(start_idx, end_idx + 1):
                    if q_idx < len(self.survey.questions):
                        question_to_group[q_idx] = group_name

        # Create group subgraphs
        group_colors = [
            "lightblue", "lightgreen", "lightyellow", "lightcyan",
            "lightpink", "lavender", "mistyrose", "honeydew",
        ]
        if self.survey.question_groups:
            for i, (group_name, _) in enumerate(self.survey.question_groups.items()):
                color = group_colors[i % len(group_colors)]
                graph.add_subgraph(
                    f"cluster_{group_name}",
                    label=f"Group: {group_name}",
                    fill_color=color,
                )

        # Collect parameters and references
        params_and_refs = set()
        param_to_questions = {}
        reference_types = {}

        for index, question in enumerate(self.survey.questions):
            subgraph = None
            if index in question_to_group:
                subgraph = f"cluster_{question_to_group[index]}"

            graph.add_node(
                f"Q{index}",
                label=_question_label(question),
                shape="box",
                subgraph=subgraph,
            )

            if hasattr(question, "detailed_parameters"):
                for param in question.detailed_parameters:
                    if "agent." in param or "scenario." in param:
                        params_and_refs.add(param)
                        param_to_questions.setdefault(param, []).append(index)
                    elif "." in param:
                        source_q, ref_type = param.split(".", 1)
                        reference_types.setdefault(ref_type, set()).add((source_q, index))
                    else:
                        params_and_refs.add(param)
                        param_to_questions.setdefault(param, []).append(index)

        # Add reference edges
        for ref_type, references in reference_types.items():
            color = reference_colors.get(ref_type, reference_colors["default"])
            for source_q_name, target_q_index in references:
                try:
                    source_q_index = next(
                        i for i, q in enumerate(self.survey.questions)
                        if q.question_name == source_q_name
                    )
                except StopIteration:
                    continue
                graph.add_edge(
                    f"Q{source_q_index}", f"Q{target_q_index}",
                    label=f".{ref_type}", style="dashed", color=color, font_color=color,
                )

        # Add parameter nodes
        for param in params_and_refs:
            node_id = f"param_{param}"
            if param.startswith("agent."):
                graph.add_node(node_id, label=f"Agent Trait\n{{{{ {param} }}}}", shape="box", fill_color="lightpink")
            elif self.scenario and param.startswith("scenario."):
                graph.add_node(node_id, label=f"Scenario\n{{{{ {param} }}}}", shape="box", fill_color="lightgreen")
            else:
                graph.add_node(node_id, label=f"{{{{ {param} }}}}", shape="box", fill_color="lightgrey")

            for q_index in param_to_questions[param]:
                graph.add_edge(node_id, f"Q{q_index}", style="dotted")

        # End of survey node
        graph.add_node("EndOfSurvey", label="End of Survey", shape="box", fill_color="lightgrey")

        # Normal flow edges
        num_questions = len(self.survey.questions)
        for index in range(num_questions - 1):
            graph.add_edge(f"Q{index}", f"Q{index + 1}")
        if num_questions > 0:
            graph.add_edge(f"Q{num_questions - 1}", "EndOfSurvey")

        # Rule edges
        relevant_rules = [
            rule for rule in self.survey.rule_collection
            if rule.priority > RulePriority.DEFAULT.value
        ]
        colors = ["blue", "red", "orange", "purple", "brown", "cyan", "darkgreen"]

        for i, rule in enumerate(relevant_rules):
            color = colors[i % len(colors)]
            target = (
                f"Q{rule.next_q}"
                if rule.next_q != EndOfSurvey and rule.next_q < num_questions
                else "EndOfSurvey"
            )
            graph.add_edge(
                f"Q{rule.current_q}", target,
                label=f"if {rule.expression}", color=color, font_color=color,
            )

        return graph.show(filename=filename)
