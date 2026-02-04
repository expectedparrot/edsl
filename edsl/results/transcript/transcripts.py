"""
Transcripts class for generating transcripts from multiple Result objects.

This module provides the Transcripts class (plural) which displays interview transcripts
across multiple Results, allowing navigation between different respondents while keeping
the same question in focus.
"""

from typing import TYPE_CHECKING, List, Dict, Any
import html as html_module
import json
import uuid

from .base import TranscriptBase, QAItem, escape_for_js
from . import html_builder

if TYPE_CHECKING:
    from ..results import Results


class Transcripts(TranscriptBase):
    """A transcripts viewer that navigates across multiple Result objects.

    This class displays interview transcripts from multiple Result objects in a carousel
    format. Unlike the Transcript class (singular) which navigates through questions
    within a single Result, this Transcripts class (plural) navigates across different
    Results (respondents) while keeping the same question in focus.

    Features:
    - Navigate between different respondents (Result objects)
    - Stay on the same question across respondents
    - Show agent name/identifier for each respondent
    - Carousel-style navigation in HTML/Jupyter
    - Plain text and Rich formatted output for terminal

    Example:
        Create transcripts from multiple Results::

            results = Results.example()
            transcripts = results.transcripts()

            # In Jupyter: Shows carousel with Result navigation
            # In terminal: Shows Rich formatted output
            # As string: Plain text format
    """

    def __init__(self, results: "Results", show_comments: bool = True):
        """Initialize Transcripts with a Results object.

        Args:
            results: The Results object containing multiple Result objects.
            show_comments: Whether to display comments in the transcripts.
        """
        super().__init__(show_comments)
        self.results = results

    def _get_qa_items(self) -> List[List[QAItem]]:
        """Extract question-answer items from all Results.

        Returns:
            List of lists of QAItem objects, one list per Result.
        """
        all_items = []
        for result in self.results:
            items = []
            q_and_a = result.q_and_a()
            for i, scenario in enumerate(q_and_a):
                q_name = scenario.get("question_name")
                options = None
                if q_name:
                    raw_options = result.get_question_options(q_name)
                    if raw_options:
                        options = [str(opt) for opt in raw_options]

                items.append(
                    QAItem(
                        question_name=q_name or "",
                        question_text=scenario.get("question_text", ""),
                        answer=str(scenario.get("answer", "")),
                        comment=scenario.get("comment"),
                        options=options,
                        question_index=i,
                    )
                )
            all_items.append(items)
        return all_items

    def _get_agent_name(self, result) -> str:
        """Get a displayable name for the agent.

        Args:
            result: A Result object.

        Returns:
            String representation of the agent.
        """
        agent = result.agent
        if hasattr(agent, "name") and agent.name:
            return str(agent.name)
        if hasattr(agent, "traits") and agent.traits:
            trait_items = list(agent.traits.items())[:2]
            if trait_items:
                return ", ".join(f"{k}={v}" for k, v in trait_items)
        return f"Agent {id(agent) % 10000}"

    def _has_multiple_values(self, indices_data: List[dict], index_type: str) -> bool:
        """Check if an index type has multiple different values.

        Args:
            indices_data: List of index dictionaries for each result.
            index_type: Type of index ('agent', 'scenario', or 'model').

        Returns:
            True if there are multiple different values.
        """
        if not indices_data:
            return False
        values = [data.get(index_type, 0) for data in indices_data]
        return len(set(values)) > 1

    def _generate_result_options(
        self, total_results: int, indices_data: List[dict], index_type: str
    ) -> str:
        """Generate HTML options for result dropdown.

        Args:
            total_results: Total number of results.
            indices_data: List of index dictionaries for each result.
            index_type: Type of index.

        Returns:
            HTML string for dropdown options.
        """
        options = []
        for i in range(total_results):
            idx_value = indices_data[i].get(index_type, 0)
            options.append(f'<option value="{i}">{idx_value}</option>')
        return "\n".join(options)

    def _generate_question_options(self, question_names: List[str]) -> str:
        """Generate HTML options for question dropdown.

        Args:
            question_names: List of question names.

        Returns:
            HTML string for dropdown options.
        """
        options = []
        for i, q_name in enumerate(question_names):
            display_name = q_name if len(q_name) <= 30 else q_name[:27] + "..."
            options.append(f'<option value="{i}">{i+1}. {display_name}</option>')
        return "\n".join(options)

    def _generate_simple(self) -> str:
        """Generate a simple plain-text transcripts view.

        Returns:
            Plain-text formatted transcripts string.
        """
        lines = []

        for i, result in enumerate(self.results):
            agent_name = self._get_agent_name(result)
            lines.append("=" * 70)
            lines.append(f"RESPONDENT {i+1}: {agent_name}")
            lines.append("=" * 70)
            lines.append("")

            q_and_a = result.q_and_a()
            for scenario in q_and_a:
                q_text = scenario.get("question_text", "")
                answer = scenario.get("answer", "")
                comment = scenario.get("comment")
                q_name = scenario.get("question_name", "")

                lines.append(f"Q: {q_text} ({q_name})")
                lines.append(f"A: {answer}")

                if self.show_comments and comment:
                    lines.append(f"Comment: {comment}")

                lines.append("")

            lines.append("")

        return "\n".join(lines)

    def _generate_rich(self) -> str:
        """Generate Rich formatted transcripts for terminal display.

        Returns:
            Rich formatted transcripts string.
        """
        try:
            from rich.console import Console
            from rich.panel import Panel
            from rich.text import Text
        except ImportError:
            return self._generate_simple()

        console = Console()

        with console.capture() as capture:
            for i, result in enumerate(self.results):
                agent_name = self._get_agent_name(result)

                header = Text()
                header.append(f"Respondent {i+1}: ", style="bold cyan")
                header.append(agent_name, style="bold yellow")
                console.print(Panel(header, expand=False))
                console.print()

                q_and_a = result.q_and_a()
                for scenario in q_and_a:
                    q_name = scenario.get("question_name", "")
                    q_text = scenario.get("question_text", "")
                    answer = scenario.get("answer", "")
                    comment = scenario.get("comment")

                    block_lines = [f"[bold]Q:[/bold] {q_text} [dim]({q_name})[/dim]"]
                    block_lines.append(f"[bold green]A:[/bold green] {answer}")

                    if self.show_comments and comment:
                        block_lines.append(f"[dim]Comment:[/dim] {comment}")

                    console.print(Panel("\n".join(block_lines), expand=False))

                console.print()

        return capture.get()

    def _generate_html(self) -> str:
        """Generate HTML formatted transcripts for Jupyter notebook display.

        Returns:
            HTML formatted transcripts with carousel navigation.
        """
        if len(self.results) == 0:
            return "<p>No results to display</p>"

        first_result = self.results[0]
        question_names = list(first_result.answer.keys())

        if not question_names:
            return "<p>No questions to display</p>"

        transcripts_id = f"transcripts_{uuid.uuid4().hex[:8]}"
        plain_text = escape_for_js(self._generate_simple())

        total_results = len(self.results)
        total_questions = len(question_names)

        # Collect agent names and indices
        agent_names = []
        indices_data = []
        for result in self.results:
            agent_names.append(self._get_agent_name(result))
            result_indices = (
                result.indices
                if result.indices
                else {"agent": 0, "scenario": 0, "model": 0}
            )
            indices_data.append(result_indices)

        # Check which dropdowns to show
        show_agent_dropdown = self._has_multiple_values(indices_data, "agent")
        show_scenario_dropdown = self._has_multiple_values(indices_data, "scenario")
        show_model_dropdown = self._has_multiple_values(indices_data, "model")

        html_parts = [
            f'<div id="{transcripts_id}" style="{html_builder.TRANSCRIPT_STYLES}">',
            html_builder.build_header(
                transcripts_id,
                "Interview Transcripts",
                f"copyTranscripts_{transcripts_id}",
            ),
            '    <div style="position: relative;">',
        ]

        # Generate slides for each result-question combination
        for result_idx, result in enumerate(self.results):
            q_and_a = result.q_and_a()
            q_and_a_dict = {s.get("question_name"): s for s in q_and_a if s.get("question_name")}

            for question_idx, question_name in enumerate(question_names):
                display_style = (
                    "block" if result_idx == 0 and question_idx == 0 else "none"
                )

                scenario = q_and_a_dict.get(question_name, {})
                q_text = scenario.get("question_text", question_name)
                answer = scenario.get("answer", "N/A")
                comment = scenario.get("comment")

                options = None
                raw_options = result.get_question_options(question_name)
                if raw_options:
                    options = [str(opt) for opt in raw_options]

                item = QAItem(
                    question_name=question_name,
                    question_text=str(q_text),
                    answer=str(answer),
                    comment=comment,
                    options=options,
                    question_index=question_idx,
                )

                card = html_builder.build_qa_card(
                    item,
                    show_comments=self.show_comments,
                    question_label=f"Question {question_idx + 1} of {total_questions}",
                    display_style=display_style,
                    card_class=f"slide-{transcripts_id}",
                    data_attrs=f'data-result="{result_idx}" data-question="{question_idx}"',
                    fixed_height=True,
                )
                html_parts.append(card)

        # Build navigation controls
        html_parts.append(self._build_navigation_html(
            transcripts_id,
            total_results,
            total_questions,
            question_names,
            indices_data,
            show_agent_dropdown,
            show_scenario_dropdown,
            show_model_dropdown,
        ))

        html_parts.append("    </div>")
        html_parts.append("</div>")

        # JavaScript
        html_parts.append("<script>")
        html_parts.append(self._build_navigation_script(
            transcripts_id,
            total_results,
            total_questions,
            agent_names,
            indices_data,
        ))
        html_parts.append(self._build_copy_script(transcripts_id, plain_text))
        html_parts.append("</script>")

        return "\n".join(html_parts)

    def _build_navigation_html(
        self,
        transcripts_id: str,
        total_results: int,
        total_questions: int,
        question_names: List[str],
        indices_data: List[dict],
        show_agent: bool,
        show_scenario: bool,
        show_model: bool,
    ) -> str:
        """Build the navigation controls HTML."""
        dropdown_parts = []

        dropdown_style = """
            font-size: 12px;
            padding: 4px 8px;
            border: 1px solid #d4d4d4;
            border-radius: 4px;
            background: white;
            cursor: pointer;
        """

        if show_agent:
            dropdown_parts.append(f"""
                <div style="display: flex; align-items: center; gap: 6px;">
                    <label style="font-size: 12px; color: #57606a; font-weight: 600;">Agent:</label>
                    <select id="agent-select-{transcripts_id}" onchange="goToResult_{transcripts_id}(this.value)" style="{dropdown_style}">
                        {self._generate_result_options(total_results, indices_data, 'agent')}
                    </select>
                </div>""")

        if show_scenario:
            dropdown_parts.append(f"""
                <div style="display: flex; align-items: center; gap: 6px;">
                    <label style="font-size: 12px; color: #57606a; font-weight: 600;">Scenario:</label>
                    <select id="scenario-select-{transcripts_id}" onchange="goToResult_{transcripts_id}(this.value)" style="{dropdown_style}">
                        {self._generate_result_options(total_results, indices_data, 'scenario')}
                    </select>
                </div>""")

        if show_model:
            dropdown_parts.append(f"""
                <div style="display: flex; align-items: center; gap: 6px;">
                    <label style="font-size: 12px; color: #57606a; font-weight: 600;">Model:</label>
                    <select id="model-select-{transcripts_id}" onchange="goToResult_{transcripts_id}(this.value)" style="{dropdown_style}">
                        {self._generate_result_options(total_results, indices_data, 'model')}
                    </select>
                </div>""")

        dropdown_parts.append(f"""
                <div style="display: flex; align-items: center; gap: 6px;">
                    <label style="font-size: 12px; color: #57606a; font-weight: 600;">Question:</label>
                    <select id="question-select-{transcripts_id}" onchange="goToQuestion_{transcripts_id}(this.value)" style="{dropdown_style} max-width: 200px;">
                        {self._generate_question_options(question_names)}
                    </select>
                </div>""")

        dropdown_row = ""
        if dropdown_parts:
            dropdown_row = f"""
            <div style="display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap;">
                {"".join(dropdown_parts)}
            </div>"""

        nav_btn = """
            background: transparent;
            border: 1px solid #d4d4d4;
            border-radius: 4px;
            color: #24292e;
            cursor: pointer;
            font-size: 12px;
            padding: 4px 10px;
            transition: background 0.2s ease;
        """

        return f"""
        <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #d4d4d4;">
            {dropdown_row}

            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 12px; color: #57606a; font-weight: 600;">Respondent:</span>
                <button onclick="firstResult_{transcripts_id}()" style="{nav_btn}" onmouseover="this.style.background='#f6f8fa';" onmouseout="this.style.background='transparent';">First</button>
                <button onclick="prevResult_{transcripts_id}()" style="{nav_btn}" onmouseover="this.style.background='#f6f8fa';" onmouseout="this.style.background='transparent';">Prev</button>
                <div id="result-counter-{transcripts_id}" style="font-size: 12px; color: #57606a; min-width: 60px; text-align: center;">1 / {total_results}</div>
                <button onclick="nextResult_{transcripts_id}()" style="{nav_btn}" onmouseover="this.style.background='#f6f8fa';" onmouseout="this.style.background='transparent';">Next</button>
                <button onclick="lastResult_{transcripts_id}()" style="{nav_btn}" onmouseover="this.style.background='#f6f8fa';" onmouseout="this.style.background='transparent';">Last</button>
            </div>

            <div style="display: flex; gap: 8px; align-items: center;">
                <span style="font-size: 12px; color: #57606a; font-weight: 600;">Question:</span>
                <button onclick="firstQuestion_{transcripts_id}()" style="{nav_btn}" onmouseover="this.style.background='#f6f8fa';" onmouseout="this.style.background='transparent';">First</button>
                <button onclick="prevQuestion_{transcripts_id}()" style="{nav_btn}" onmouseover="this.style.background='#f6f8fa';" onmouseout="this.style.background='transparent';">Prev</button>
                <div id="question-counter-{transcripts_id}" style="font-size: 12px; color: #57606a; min-width: 60px; text-align: center;">Q 1 / {total_questions}</div>
                <button onclick="nextQuestion_{transcripts_id}()" style="{nav_btn}" onmouseover="this.style.background='#f6f8fa';" onmouseout="this.style.background='transparent';">Next</button>
                <button onclick="lastQuestion_{transcripts_id}()" style="{nav_btn}" onmouseover="this.style.background='#f6f8fa';" onmouseout="this.style.background='transparent';">Last</button>
            </div>
        </div>
"""

    def _build_navigation_script(
        self,
        transcripts_id: str,
        total_results: int,
        total_questions: int,
        agent_names: List[str],
        indices_data: List[dict],
    ) -> str:
        """Build the navigation JavaScript."""
        return f"""
let currentResult_{transcripts_id} = 0;
let currentQuestion_{transcripts_id} = 0;
const totalResults_{transcripts_id} = {total_results};
const totalQuestions_{transcripts_id} = {total_questions};
const agentNames_{transcripts_id} = {json.dumps(agent_names)};
const indicesData_{transcripts_id} = {json.dumps(indices_data)};

function showSlide_{transcripts_id}(resultIdx, questionIdx) {{
    const slides = document.querySelectorAll('.slide-{transcripts_id}');

    slides.forEach((slide) => {{
        const slideResult = parseInt(slide.dataset.result);
        const slideQuestion = parseInt(slide.dataset.question);

        if (slideResult === resultIdx && slideQuestion === questionIdx) {{
            slide.style.display = 'block';
        }} else {{
            slide.style.display = 'none';
        }}
    }});

    document.getElementById('result-counter-{transcripts_id}').textContent =
        `${{resultIdx + 1}} / ${{totalResults_{transcripts_id}}}`;
    document.getElementById('question-counter-{transcripts_id}').textContent =
        `Q ${{questionIdx + 1}} / ${{totalQuestions_{transcripts_id}}}`;

    const agentSelect = document.getElementById('agent-select-{transcripts_id}');
    if (agentSelect) agentSelect.value = resultIdx;
    const scenarioSelect = document.getElementById('scenario-select-{transcripts_id}');
    if (scenarioSelect) scenarioSelect.value = resultIdx;
    const modelSelect = document.getElementById('model-select-{transcripts_id}');
    if (modelSelect) modelSelect.value = resultIdx;
    const questionSelect = document.getElementById('question-select-{transcripts_id}');
    if (questionSelect) questionSelect.value = questionIdx;
}}

function firstResult_{transcripts_id}() {{
    currentResult_{transcripts_id} = 0;
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function prevResult_{transcripts_id}() {{
    currentResult_{transcripts_id} = (currentResult_{transcripts_id} - 1 + totalResults_{transcripts_id}) % totalResults_{transcripts_id};
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function nextResult_{transcripts_id}() {{
    currentResult_{transcripts_id} = (currentResult_{transcripts_id} + 1) % totalResults_{transcripts_id};
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function lastResult_{transcripts_id}() {{
    currentResult_{transcripts_id} = totalResults_{transcripts_id} - 1;
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function goToResult_{transcripts_id}(idx) {{
    currentResult_{transcripts_id} = parseInt(idx);
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function firstQuestion_{transcripts_id}() {{
    currentQuestion_{transcripts_id} = 0;
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function prevQuestion_{transcripts_id}() {{
    currentQuestion_{transcripts_id} = (currentQuestion_{transcripts_id} - 1 + totalQuestions_{transcripts_id}) % totalQuestions_{transcripts_id};
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function nextQuestion_{transcripts_id}() {{
    currentQuestion_{transcripts_id} = (currentQuestion_{transcripts_id} + 1) % totalQuestions_{transcripts_id};
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function lastQuestion_{transcripts_id}() {{
    currentQuestion_{transcripts_id} = totalQuestions_{transcripts_id} - 1;
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

function goToQuestion_{transcripts_id}(idx) {{
    currentQuestion_{transcripts_id} = parseInt(idx);
    showSlide_{transcripts_id}(currentResult_{transcripts_id}, currentQuestion_{transcripts_id});
}}

showSlide_{transcripts_id}(0, 0);
"""

    def _build_copy_script(self, transcripts_id: str, plain_text: str) -> str:
        """Build the copy functionality JavaScript."""
        return f"""
function copyTranscripts_{transcripts_id}() {{
    const text = "{plain_text}";

    if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(text).then(() => {{
            showCopyFeedback_{transcripts_id}();
        }}).catch(err => {{
            console.error('Failed to copy:', err);
        }});
    }} else {{
        const textArea = document.createElement("textarea");
        textArea.value = text;
        textArea.style.position = "fixed";
        textArea.style.left = "-999999px";
        document.body.appendChild(textArea);
        textArea.select();
        try {{
            document.execCommand('copy');
            showCopyFeedback_{transcripts_id}();
        }} catch (err) {{
            console.error('Failed to copy:', err);
        }}
        document.body.removeChild(textArea);
    }}
}}

function showCopyFeedback_{transcripts_id}() {{
    const button = event.target.closest('button');
    const originalContent = button.innerHTML;
    button.innerHTML = 'Copied';
    button.style.background = '#f0fdf4';
    button.style.borderColor = '#16a34a';
    button.style.color = '#166534';

    setTimeout(() => {{
        button.innerHTML = originalContent;
        button.style.background = 'transparent';
        button.style.borderColor = '#d4d4d4';
        button.style.color = '#24292e';
    }}, 2000);
}}
"""
