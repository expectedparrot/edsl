"""
Survey Mermaid Visualization for generating flowchart diagrams.

This module provides a SurveyMermaidVisualization class that creates Mermaid
flowchart diagrams showing survey structure, skip logic, navigation rules,
and piping dependencies.
"""

import re
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ..survey import Survey

from ..navigation_markers import EndOfSurvey


class SurveyMermaidVisualization:
    """Generates Mermaid flowchart diagrams for survey visualization.

    This class creates Mermaid markdown that visualizes:
    - Questions as nodes with type, truncated text, and options
    - Normal sequential flow as arrows
    - Skip logic rules as dashed arrows (evaluated before question)
    - Navigation rules as solid arrows (evaluated after question)
    - Stop rules as arrows leading to End node
    - Piping dependencies as dotted arrows
    """

    def __init__(
        self,
        survey: "Survey",
        max_text_length: int = 40,
        show_options: bool = True,
        show_piping: bool = True,
        show_default_flow: bool = True,
    ):
        """Initialize the visualization with a survey.

        Args:
            survey: The Survey object to visualize.
            max_text_length: Maximum characters for question text display.
            show_options: Whether to show question options for multiple choice.
            show_piping: Whether to show piping dependency arrows.
            show_default_flow: Whether to show sequential flow arrows.
        """
        self.survey = survey
        self.max_text_length = max_text_length
        self.show_options = show_options
        self.show_piping = show_piping
        self.show_default_flow = show_default_flow

    def _sanitize_node_id(self, name: str) -> str:
        """Sanitize question name for Mermaid node ID.

        Mermaid IDs must be alphanumeric with underscores.
        """
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)
        if sanitized and sanitized[0].isdigit():
            sanitized = f"q_{sanitized}"
        return sanitized or "unnamed"

    def _truncate_text(self, text: str, max_length: Optional[int] = None) -> str:
        """Truncate text and escape for Mermaid."""
        if max_length is None:
            max_length = self.max_text_length

        clean_text = text.replace('"', "'").replace("\n", " ").replace("#", "")
        # Escape HTML entities that might interfere
        clean_text = clean_text.replace("<", "&lt;").replace(">", "&gt;")

        if len(clean_text) > max_length:
            return clean_text[: max_length - 3] + "..."
        return clean_text

    def _truncate_options(self, options: list, max_options: int = 3) -> str:
        """Format options for display."""
        if not options:
            return ""
        if len(options) <= max_options:
            return ", ".join(str(o) for o in options)
        return (
            ", ".join(str(o) for o in options[:max_options])
            + f", ... (+{len(options) - max_options})"
        )

    def _escape_label(self, text: str, max_length: int = 50) -> str:
        """Escape text for Mermaid edge labels."""
        escaped = text.replace('"', "'").replace("|", "/").replace("\n", " ")
        escaped = escaped.replace("#", "")
        if len(escaped) > max_length:
            escaped = escaped[: max_length - 3] + "..."
        return escaped

    def _generate_node(self, index: int, question) -> str:
        """Generate a Mermaid node for a question."""
        node_id = self._sanitize_node_id(question.question_name)
        q_type = getattr(question, "question_type", "unknown")
        q_text = self._truncate_text(question.question_text)

        content_parts = [
            f"<b>{question.question_name}</b>",
            f"Type: {q_type}",
            q_text,
        ]

        if self.show_options and hasattr(question, "question_options"):
            options = getattr(question, "question_options", None)
            if options:
                options_display = self._truncate_options(options)
                content_parts.append(f"Options: {options_display}")

        content = "<br/>".join(content_parts)
        return f'    {node_id}["{content}"]'

    def _generate_default_flow_edges(self) -> List[str]:
        """Generate sequential flow edges (Q0 --> Q1 --> Q2 ...)."""
        edges = []
        questions = self.survey.questions

        for i in range(len(questions) - 1):
            from_id = self._sanitize_node_id(questions[i].question_name)
            to_id = self._sanitize_node_id(questions[i + 1].question_name)
            edges.append(f"    {from_id} --> {to_id}")

        if questions:
            last_id = self._sanitize_node_id(questions[-1].question_name)
            edges.append(f"    {last_id} --> EndOfSurvey")

        return edges

    def _generate_rule_edges(self) -> List[str]:
        """Generate edges from non-default rules."""
        edges = []
        rule_collection = self.survey.rule_collection
        q_name_to_idx = self.survey.question_name_to_index
        idx_to_name = {v: k for k, v in q_name_to_idx.items()}

        for rule in rule_collection.non_default_rules:
            current_idx = rule.current_q
            next_q = rule.next_q
            expression = rule.expression
            before_rule = rule.before_rule

            from_name = idx_to_name.get(current_idx, f"q{current_idx}")
            from_id = self._sanitize_node_id(from_name)

            if next_q == EndOfSurvey:
                to_id = "EndOfSurvey"
            else:
                to_name = idx_to_name.get(next_q, f"q{next_q}")
                to_id = self._sanitize_node_id(to_name)

            label = self._escape_label(expression) if expression else "always"

            if before_rule:
                # Skip rule - dashed with "skip" prefix
                edges.append(f'    {from_id} -.->|"skip: {label}"| {to_id}')
            elif next_q == EndOfSurvey:
                # Stop rule
                edges.append(f'    {from_id} -->|"stop: {label}"| {to_id}')
            else:
                # Navigation rule
                edges.append(f'    {from_id} -->|"{label}"| {to_id}')

        return edges

    def _generate_piping_edges(self) -> List[str]:
        """Generate edges showing piping dependencies."""
        edges = []
        params_by_q = self.survey.parameters_by_question
        q_name_to_idx = self.survey.question_name_to_index

        for q_name, dependencies in params_by_q.items():
            if not dependencies:
                continue

            to_id = self._sanitize_node_id(q_name)

            for dep in dependencies:
                if dep in q_name_to_idx:
                    from_id = self._sanitize_node_id(dep)
                    edges.append(f'    {from_id} -.->|"pipes"| {to_id}')

        return edges

    def _generate_styles(self) -> List[str]:
        """Generate Mermaid style definitions."""
        styles = [
            "",
            "    %% Styling",
            "    classDef question fill:#e3f2fd,stroke:#1976d2,stroke-width:2px",
            "    classDef startEnd fill:#e8f5e9,stroke:#388e3c,stroke-width:3px,font-weight:bold",
            "",
            "    class Start,EndOfSurvey startEnd",
        ]

        for q in self.survey.questions:
            node_id = self._sanitize_node_id(q.question_name)
            styles.append(f"    class {node_id} question")

        return styles

    def to_mermaid(self) -> str:
        """Generate the complete Mermaid flowchart.

        Returns:
            str: Mermaid markdown that can be rendered in markdown viewers.
        """
        questions = self.survey.questions

        if not questions:
            return 'flowchart TD\n    Start(("Start")) --> EndOfSurvey(("End"))'

        lines = ["flowchart TD"]

        # Start node
        lines.append('    Start(("Start"))')

        # Question nodes
        for i, question in enumerate(questions):
            lines.append(self._generate_node(i, question))

        # End node
        lines.append('    EndOfSurvey(("End"))')

        lines.append("")

        # Connect Start to first question
        first_q_id = self._sanitize_node_id(questions[0].question_name)
        lines.append(f"    Start --> {first_q_id}")

        # Default sequential flow
        if self.show_default_flow:
            for edge in self._generate_default_flow_edges():
                lines.append(edge)

        lines.append("")

        # Rule-based edges
        rule_edges = self._generate_rule_edges()
        if rule_edges:
            lines.append("    %% Skip and navigation rules")
            for edge in rule_edges:
                lines.append(edge)

        # Piping dependency edges
        if self.show_piping:
            piping_edges = self._generate_piping_edges()
            if piping_edges:
                lines.append("")
                lines.append("    %% Piping dependencies")
                for edge in piping_edges:
                    lines.append(edge)

        # Styling
        lines.extend(self._generate_styles())

        return "\n".join(lines)

    def _repr_html_(self) -> str:
        """Generate HTML representation for Jupyter notebook display.

        Returns:
            str: HTML containing a mermaid diagram.
        """
        mermaid_code = self.to_mermaid()

        html_content = f"""
        <div id="mermaid-{id(self)}" class="mermaid">
            {mermaid_code}
        </div>
        <script>
            // Load mermaid if not already loaded
            if (typeof mermaid === 'undefined') {{
                var script = document.createElement('script');
                script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js';
                script.onload = function() {{
                    mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
                    mermaid.init(undefined, '#mermaid-{id(self)}');
                }};
                document.head.appendChild(script);
            }} else {{
                mermaid.init(undefined, '#mermaid-{id(self)}');
            }}
        </script>
        <style>
            .mermaid {{
                text-align: center;
                margin: 20px 0;
            }}
        </style>
        <details style="margin-top: 10px;">
            <summary>Show raw Mermaid code</summary>
            <pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto;">
{mermaid_code}
            </pre>
        </details>
        """
        return html_content

    def __str__(self) -> str:
        """Return raw Mermaid markdown."""
        return self.to_mermaid()

    def __repr__(self) -> str:
        """Generate repr string for the object."""
        try:
            from IPython import get_ipython

            ipy = get_ipython()
            if ipy is not None and hasattr(ipy, "kernel"):
                num_questions = len(self.survey.questions)
                num_rules = len(self.survey.rule_collection.non_default_rules)
                return f"SurveyMermaidVisualization({num_questions} questions, {num_rules} rules)"
        except ImportError:
            pass

        return self.to_mermaid()
