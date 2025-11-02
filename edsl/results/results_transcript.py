"""
Module for generating transcripts from Results objects (multiple Result objects).

This module provides the Transcripts class (plural) which displays interview transcripts
across multiple Results, allowing navigation between different respondents while keeping
the same question in focus.
"""

from typing import TYPE_CHECKING, List
import html as html_module
import json
import uuid

if TYPE_CHECKING:
    from .results import Results


class Transcripts:
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
            results: The Results object containing multiple Result objects
            show_comments: Whether to display comments in the transcripts. Defaults to True.
        """
        self.results = results
        self.show_comments = show_comments
        
    def _get_agent_name(self, result) -> str:
        """Get a displayable name for the agent.
        
        Args:
            result: A Result object
            
        Returns:
            String representation of the agent
        """
        agent = result.agent
        if hasattr(agent, 'name') and agent.name:
            return str(agent.name)
        if hasattr(agent, 'traits') and agent.traits:
            # Create a short identifier from traits
            trait_items = list(agent.traits.items())[:2]  # First 2 traits
            if trait_items:
                return ", ".join(f"{k}={v}" for k, v in trait_items)
        return f"Agent {id(agent) % 10000}"
    
    def _generate_result_options(self, total_results: int, indices_data: List[dict], index_type: str) -> str:
        """Generate HTML options for result dropdown based on index type.
        
        Args:
            total_results: Total number of results
            indices_data: List of index dictionaries for each result
            index_type: Type of index ('agent', 'scenario', or 'model')
            
        Returns:
            HTML string for dropdown options
        """
        options = []
        for i in range(total_results):
            idx_value = indices_data[i].get(index_type, 0)
            options.append(f'<option value="{i}">{idx_value}</option>')
        return '\n'.join(options)
    
    def _generate_question_options(self, question_names: List[str]) -> str:
        """Generate HTML options for question dropdown.
        
        Args:
            question_names: List of question names
            
        Returns:
            HTML string for dropdown options
        """
        options = []
        for i, q_name in enumerate(question_names):
            # Truncate long question names for display
            display_name = q_name if len(q_name) <= 30 else q_name[:27] + '...'
            options.append(f'<option value="{i}">{i+1}. {display_name}</option>')
        return '\n'.join(options)
    
    def _has_multiple_values(self, indices_data: List[dict], index_type: str) -> bool:
        """Check if an index type has multiple different values.
        
        Args:
            indices_data: List of index dictionaries for each result
            index_type: Type of index ('agent', 'scenario', or 'model')
            
        Returns:
            True if there are multiple different values, False if all are the same
        """
        if not indices_data:
            return False
        values = [data.get(index_type, 0) for data in indices_data]
        return len(set(values)) > 1
    
    def _generate_simple(self) -> str:
        """Generate a simple plain-text transcripts view.
        
        Returns:
            Plain-text formatted transcripts string
        """
        lines = []
        
        for i, result in enumerate(self.results):
            agent_name = self._get_agent_name(result)
            lines.append(f"=" * 70)
            lines.append(f"RESPONDENT {i+1}: {agent_name}")
            lines.append(f"=" * 70)
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
            Rich formatted transcripts string
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
                
                # Agent header
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
            HTML formatted transcripts with carousel navigation
        """
        # Generate unique ID for this transcripts viewer
        transcripts_id = f"transcripts_{uuid.uuid4().hex[:8]}"
        
        # Get all question names from the first result
        if len(self.results) == 0:
            return "<p>No results to display</p>"
        
        first_result = self.results[0]
        question_names = list(first_result.answer.keys())
        
        if not question_names:
            return "<p>No questions to display</p>"
        
        # Get plain text version for copying
        plain_text = self._generate_simple().replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')
        
        total_results = len(self.results)
        total_questions = len(question_names)
        
        # Collect agent names and indices for JavaScript arrays FIRST
        agent_names = []
        indices_data = []
        for result in self.results:
            agent_name = self._get_agent_name(result)
            agent_names.append(agent_name)
            # Get indices or default to 0
            result_indices = result.indices if result.indices else {'agent': 0, 'scenario': 0, 'model': 0}
            indices_data.append(result_indices)
        
        # NOW check which index types have multiple values
        show_agent_dropdown = self._has_multiple_values(indices_data, 'agent')
        show_scenario_dropdown = self._has_multiple_values(indices_data, 'scenario')
        show_model_dropdown = self._has_multiple_values(indices_data, 'model')
        
        html_parts = [f'''
<div id="{transcripts_id}" style="
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
    max-width: 800px;
    margin: 16px 0;
">
    <!-- Header -->
    <div style="
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: 1px solid #d4d4d4;
    ">
        <div style="
            font-size: 16px;
            font-weight: bold;
            color: #24292e;
        ">Interview Transcripts</div>
        <button onclick="copyTranscripts_{transcripts_id}()" style="
            background: transparent;
            border: 1px solid #d4d4d4;
            border-radius: 4px;
            color: #24292e;
            cursor: pointer;
            font-size: 13px;
            padding: 4px 10px;
            transition: background 0.2s ease;
        " onmouseover="this.style.background='#f6f8fa';" 
           onmouseout="this.style.background='transparent';">
            📋 Copy
        </button>
    </div>
    
    <!-- Agent Info Tooltip (Hidden by default) -->
    <div id="agent-tooltip-{transcripts_id}" style="
        display: none;
        position: absolute;
        background: #24292e;
        color: #ffffff;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 13px;
        z-index: 1000;
        max-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        pointer-events: none;
    ">
        <div style="
            font-size: 11px;
            color: #8b949e;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        ">Respondent Info</div>
        <div id="agent-tooltip-content-{transcripts_id}"></div>
    </div>
    
    <!-- Carousel Container -->
    <div style="position: relative;">
''']
        
        # Generate slides for each result-question combination
        for result_idx, result in enumerate(self.results):
            agent_name = agent_names[result_idx]
            q_and_a = result.q_and_a()
            
            # Convert q_and_a list to dict keyed by question name for lookup
            q_and_a_dict = {}
            for scenario in q_and_a:
                # Get question name directly from the scenario
                q_name = scenario.get("question_name")
                if q_name:
                    q_and_a_dict[q_name] = scenario
            
            for question_idx, question_name in enumerate(question_names):
                display_style = "block" if result_idx == 0 and question_idx == 0 else "none"
                
                # Get data for this question
                scenario = q_and_a_dict.get(question_name, {})
                q_text = scenario.get("question_text", question_name)
                answer = scenario.get("answer", "N/A")
                comment = scenario.get("comment")
                
                # Get options
                options_html = ""
                options = result.get_question_options(question_name)
                if options:
                    opt_list = [f'{html_module.escape(str(opt))}' for opt in options]
                    options_html = f'<div style="margin-top: 6px; font-size: 13px; color: #57606a; font-style: italic;">Options: {" • ".join(opt_list)}</div>'
                
                html_parts.append(f'''
        <div class="slide-{transcripts_id}" data-result="{result_idx}" data-question="{question_idx}" style="
            display: {display_style};
            border: 1px solid #d4d4d4;
            border-radius: 4px;
            background: transparent;
            height: 350px;
            overflow-y: auto;
        ">
            <!-- Question -->
            <div style="
                padding: 12px;
                background: #f6f8fa;
                border-bottom: 1px solid #d4d4d4;
            ">
                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 6px;
                ">
                    <div style="
                        font-size: 11px;
                        font-weight: bold;
                        color: #57606a;
                        text-transform: uppercase;
                        letter-spacing: 0.5px;
                    ">Question {question_idx+1} of {total_questions}</div>
                    <div 
                        onmouseover="showAgentTooltip_{transcripts_id}(event)"
                        onmouseout="hideAgentTooltip_{transcripts_id}()"
                        style="
                        cursor: help;
                        background: #0969da;
                        color: white;
                        border-radius: 50%;
                        width: 20px;
                        height: 20px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 12px;
                        font-weight: bold;
                        user-select: none;
                    ">ⓘ</div>
                </div>
                <div style="
                    font-size: 14px;
                    color: #24292e;
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">{html_module.escape(str(q_text))} <span style="color: #57606a; font-size: 12px;">({html_module.escape(str(question_name))})</span></div>
                {options_html}
            </div>
            
            <!-- Answer -->
            <div style="
                padding: 12px;
                background: #f0fdf4;
                {'' if not (self.show_comments and comment) else 'border-bottom: 1px solid #d4d4d4;'}
            ">
                <div style="
                    font-size: 11px;
                    font-weight: bold;
                    color: #166534;
                    margin-bottom: 6px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">Answer</div>
                <div style="
                    font-size: 14px;
                    color: #15803d;
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">{html_module.escape(str(answer))}</div>
            </div>
''')
                
                # Add comment if show_comments is True and comment exists
                if self.show_comments and comment:
                    comment_html = html_module.escape(str(comment))
                    html_parts.append(f'''
            <!-- Comment -->
            <div style="
                padding: 12px;
                background: #faf5ff;
            ">
                <div style="
                    font-size: 11px;
                    font-weight: bold;
                    color: #6b21a8;
                    margin-bottom: 6px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">💭 Comment</div>
                <div style="
                    font-size: 13px;
                    color: #7c3aed;
                    font-style: italic;
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">{comment_html}</div>
            </div>
''')
                
                html_parts.append('        </div>')
        
        # Navigation controls with dropdowns and first/last buttons
        
        # Generate dropdown HTML conditionally
        dropdown_html_parts = []
        
        if show_agent_dropdown:
            dropdown_html_parts.append(f'''
                <!-- Agent Index Dropdown -->
                <div style="display: flex; align-items: center; gap: 6px;">
                    <label style="font-size: 12px; color: #57606a; font-weight: 600;">Agent:</label>
                    <select id="agent-select-{transcripts_id}" onchange="goToResult_{transcripts_id}(this.value)" style="
                        font-size: 12px;
                        padding: 4px 8px;
                        border: 1px solid #d4d4d4;
                        border-radius: 4px;
                        background: white;
                        cursor: pointer;
                    ">
                        {self._generate_result_options(total_results, indices_data, 'agent')}
                    </select>
                </div>''')
        
        if show_scenario_dropdown:
            dropdown_html_parts.append(f'''
                <!-- Scenario Index Dropdown -->
                <div style="display: flex; align-items: center; gap: 6px;">
                    <label style="font-size: 12px; color: #57606a; font-weight: 600;">Scenario:</label>
                    <select id="scenario-select-{transcripts_id}" onchange="goToResult_{transcripts_id}(this.value)" style="
                        font-size: 12px;
                        padding: 4px 8px;
                        border: 1px solid #d4d4d4;
                        border-radius: 4px;
                        background: white;
                        cursor: pointer;
                    ">
                        {self._generate_result_options(total_results, indices_data, 'scenario')}
                    </select>
                </div>''')
        
        if show_model_dropdown:
            dropdown_html_parts.append(f'''
                <!-- Model Index Dropdown -->
                <div style="display: flex; align-items: center; gap: 6px;">
                    <label style="font-size: 12px; color: #57606a; font-weight: 600;">Model:</label>
                    <select id="model-select-{transcripts_id}" onchange="goToResult_{transcripts_id}(this.value)" style="
                        font-size: 12px;
                        padding: 4px 8px;
                        border: 1px solid #d4d4d4;
                        border-radius: 4px;
                        background: white;
                        cursor: pointer;
                    ">
                        {self._generate_result_options(total_results, indices_data, 'model')}
                    </select>
                </div>''')
        
        # Always show question dropdown
        dropdown_html_parts.append(f'''
                <!-- Question Dropdown -->
                <div style="display: flex; align-items: center; gap: 6px;">
                    <label style="font-size: 12px; color: #57606a; font-weight: 600;">Question:</label>
                    <select id="question-select-{transcripts_id}" onchange="goToQuestion_{transcripts_id}(this.value)" style="
                        font-size: 12px;
                        padding: 4px 8px;
                        border: 1px solid #d4d4d4;
                        border-radius: 4px;
                        background: white;
                        cursor: pointer;
                        max-width: 200px;
                    ">
                        {self._generate_question_options(question_names)}
                    </select>
                </div>''')
        
        dropdowns_html = '\n'.join(dropdown_html_parts)
        
        # Only show dropdown row if there are any dropdowns to show
        dropdown_row_html = ''
        if dropdown_html_parts:
            dropdown_row_html = f'''
            <!-- Index Dropdowns Row -->
            <div style="display: flex; gap: 12px; margin-bottom: 12px; flex-wrap: wrap;">
{dropdowns_html}
            </div>'''
        
        html_parts.append(f'''
        
        <!-- Navigation Controls -->
        <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #d4d4d4;">
{dropdown_row_html}
            
            <!-- Result Navigation Row -->
            <div style="display: flex; gap: 8px; align-items: center; margin-bottom: 8px;">
                <span style="font-size: 12px; color: #57606a; font-weight: 600;">Respondent:</span>
                <button onclick="firstResult_{transcripts_id}()" title="First" style="
                    background: transparent;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #24292e;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 4px 8px;
                    transition: background 0.2s ease;
                " onmouseover="this.style.background='#f6f8fa';" 
                   onmouseout="this.style.background='transparent';">
                    ⏮
                </button>
                <button onclick="prevResult_{transcripts_id}()" style="
                    background: transparent;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #24292e;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 4px 10px;
                    transition: background 0.2s ease;
                " onmouseover="this.style.background='#f6f8fa';" 
                   onmouseout="this.style.background='transparent';">
                    ← Prev
                </button>
                <div id="result-counter-{transcripts_id}" style="
                    font-size: 12px;
                    color: #57606a;
                    white-space: nowrap;
                    min-width: 60px;
                    text-align: center;
                ">1 / {total_results}</div>
                <button onclick="nextResult_{transcripts_id}()" style="
                    background: transparent;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #24292e;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 4px 10px;
                    transition: background 0.2s ease;
                " onmouseover="this.style.background='#f6f8fa';" 
                   onmouseout="this.style.background='transparent';">
                    Next →
                </button>
                <button onclick="lastResult_{transcripts_id}()" title="Last" style="
                    background: transparent;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #24292e;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 4px 8px;
                    transition: background 0.2s ease;
                " onmouseover="this.style.background='#f6f8fa';" 
                   onmouseout="this.style.background='transparent';">
                    ⏭
                </button>
            </div>
            
            <!-- Question Navigation Row -->
            <div style="display: flex; gap: 8px; align-items: center;">
                <span style="font-size: 12px; color: #57606a; font-weight: 600;">Question:</span>
                <button onclick="firstQuestion_{transcripts_id}()" title="First" style="
                    background: transparent;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #24292e;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 4px 8px;
                    transition: background 0.2s ease;
                " onmouseover="this.style.background='#f6f8fa';" 
                   onmouseout="this.style.background='transparent';">
                    ⏮
                </button>
                <button onclick="prevQuestion_{transcripts_id}()" style="
                    background: transparent;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #24292e;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 4px 10px;
                    transition: background 0.2s ease;
                " onmouseover="this.style.background='#f6f8fa';" 
                   onmouseout="this.style.background='transparent';">
                    ← Prev
                </button>
                <div id="question-counter-{transcripts_id}" style="
                    font-size: 12px;
                    color: #57606a;
                    white-space: nowrap;
                    min-width: 60px;
                    text-align: center;
                ">Q 1 / {total_questions}</div>
                <button onclick="nextQuestion_{transcripts_id}()" style="
                    background: transparent;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #24292e;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 4px 10px;
                    transition: background 0.2s ease;
                " onmouseover="this.style.background='#f6f8fa';" 
                   onmouseout="this.style.background='transparent';">
                    Next →
                </button>
                <button onclick="lastQuestion_{transcripts_id}()" title="Last" style="
                    background: transparent;
                    border: 1px solid #d4d4d4;
                    border-radius: 4px;
                    color: #24292e;
                    cursor: pointer;
                    font-size: 12px;
                    padding: 4px 8px;
                    transition: background 0.2s ease;
                " onmouseover="this.style.background='#f6f8fa';" 
                   onmouseout="this.style.background='transparent';">
                    ⏭
                </button>
            </div>
        </div>
    </div>
</div>

<script>
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
    
    // Update counters
    document.getElementById('result-counter-{transcripts_id}').textContent = 
        `${{resultIdx + 1}} / ${{totalResults_{transcripts_id}}}`;
    document.getElementById('question-counter-{transcripts_id}').textContent = 
        `Q ${{questionIdx + 1}} / ${{totalQuestions_{transcripts_id}}}`;
    
    // Update dropdown selections (only if they exist)
    const agentSelect = document.getElementById('agent-select-{transcripts_id}');
    if (agentSelect) agentSelect.value = resultIdx;
    
    const scenarioSelect = document.getElementById('scenario-select-{transcripts_id}');
    if (scenarioSelect) scenarioSelect.value = resultIdx;
    
    const modelSelect = document.getElementById('model-select-{transcripts_id}');
    if (modelSelect) modelSelect.value = resultIdx;
    
    const questionSelect = document.getElementById('question-select-{transcripts_id}');
    if (questionSelect) questionSelect.value = questionIdx;
}}

function showAgentTooltip_{transcripts_id}(event) {{
    const tooltip = document.getElementById('agent-tooltip-{transcripts_id}');
    const tooltipContent = document.getElementById('agent-tooltip-content-{transcripts_id}');
    
    // Get agent name for current result
    const agentName = agentNames_{transcripts_id}[currentResult_{transcripts_id}] || 'Unknown';
    
    tooltipContent.textContent = agentName;
    tooltip.style.display = 'block';
    
    // Position tooltip near the cursor
    const x = event.pageX;
    const y = event.pageY;
    tooltip.style.left = (x + 10) + 'px';
    tooltip.style.top = (y - 30) + 'px';
}}

function hideAgentTooltip_{transcripts_id}() {{
    const tooltip = document.getElementById('agent-tooltip-{transcripts_id}');
    tooltip.style.display = 'none';
}}

// Result navigation
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

// Question navigation
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
    button.innerHTML = '✓ Copied';
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

// Initialize on load
showSlide_{transcripts_id}(0, 0);
</script>
''')
        
        return ''.join(html_parts)
    
    def __str__(self) -> str:
        """Return simple plain-text representation.
        
        Returns:
            Plain-text formatted transcripts
        """
        return self._generate_simple()

    def __repr__(self) -> str:
        """Return Rich formatted representation for terminal display.
        
        Returns:
            Rich formatted transcripts if available, otherwise simple format
        """
        return self._generate_rich()

    def _repr_html_(self) -> str:
        """Return HTML representation for Jupyter notebook display.
        
        This method is automatically called by Jupyter notebooks to render
        the object as HTML.
        
        Returns:
            HTML formatted transcripts with carousel navigation
        """
        return self._generate_html()

    def to_simple(self) -> str:
        """Explicitly get the simple plain-text format.
        
        Returns:
            Plain-text formatted transcripts
        """
        return self._generate_simple()

    def to_rich(self) -> str:
        """Explicitly get the Rich formatted output.
        
        Returns:
            Rich formatted transcripts
            
        Raises:
            ImportError: If the rich library is not installed
        """
        try:
            from rich.console import Console
            from rich.panel import Panel
        except ImportError as exc:
            raise ImportError(
                "The 'rich' package is required for Rich formatting. Install it with `pip install rich`."
            ) from exc
        
        return self._generate_rich()

    def to_html(self) -> str:
        """Explicitly get the HTML formatted output.
        
        Returns:
            HTML formatted transcripts
        """
        return self._generate_html()

