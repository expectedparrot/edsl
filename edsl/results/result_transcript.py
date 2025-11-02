"""
Module for generating transcripts from Result objects.

This module provides functionality to convert Result objects into human-readable
transcripts showing questions, options (if any), and answers. The Transcript class
provides different display formats for terminal (rich formatting) vs Jupyter
notebooks (HTML).
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .result import Result


class Transcript:
    """A transcript object that displays questions and answers from a Result.
    
    This class provides intelligent display formatting that adapts to the environment:
    - In terminal/console: Uses Rich formatting with colored panels
    - In Jupyter notebooks: Provides HTML formatted output
    - When converted to string: Returns simple plain-text format
    
    The Transcript object is returned by the Result.transcript() method and automatically
    displays appropriately based on the context.
    
    Example:
        Create a transcript from a Result::
        
            result = Result.example()
            transcript = result.transcript()
            
            # In terminal: displays with Rich formatting
            # In Jupyter: displays as HTML
            # As string: plain text
            text = str(transcript)
    """

    def __init__(self, result: "Result", show_comments: bool = True, carousel: bool = True):
        """Initialize a Transcript with a Result object.

        Args:
            result: The Result object to generate transcripts for
            show_comments: Whether to display comments in the transcript. Defaults to True.
            carousel: Whether to display as a carousel in HTML (one Q&A at a time). Defaults to True.
        """
        self.result = result
        self.show_comments = show_comments
        self.carousel = carousel

    def _get_components(self, q_name):
        """Extract question text, options, and answer value for a question.
        
        Args:
            q_name: The question name
            
        Returns:
            Tuple of (question_text, options_string, answer_value)
        """
        meta = self.result["question_to_attributes"].get(q_name, {})
        q_text = meta.get("question_text", q_name)
        options = meta.get("question_options")

        # stringify options if they exist
        opt_str: str | None
        if options:
            if isinstance(options, (list, tuple)):
                opt_str = " / ".join(map(str, options))
            elif isinstance(options, dict):
                opt_str = " / ".join(f"{k}: {v}" for k, v in options.items())
            else:
                opt_str = str(options)
        else:
            opt_str = None

        ans_val = self.result.answer[q_name]
        if not isinstance(ans_val, str):
            ans_val = str(ans_val)

        return q_text, opt_str, ans_val

    def _generate_simple(self) -> str:
        """Generate a simple plain-text transcript.
        
        Returns:
            Plain-text formatted transcript string
        """
        lines: list[str] = []
        q_and_a = self.result.q_and_a()
        
        for scenario in q_and_a:
            q_name = scenario.get("question_name")
            q_text = scenario.get("question_text", "")
            answer = scenario.get("answer", "")
            comment = scenario.get("comment")
            
            lines.append(f"QUESTION: {q_text} ({q_name})")
            
            # Add options if available
            if q_name:
                options = self.result.get_question_options(q_name)
                if options:
                    opt_str = " / ".join(map(str, options))
                    lines.append(f"OPTIONS: {opt_str}")
            
            lines.append(f"ANSWER: {answer}")
            
            # Add comment if show_comments is True and comment exists
            if self.show_comments and comment:
                lines.append(f"COMMENT: {comment}")
            
            lines.append("")

        if lines and lines[-1] == "":
            lines.pop()  # trailing blank line

        return "\n".join(lines)

    def _generate_rich(self) -> str:
        """Generate a Rich formatted transcript for terminal display.
        
        Returns:
            Rich formatted transcript string with colors and panels
        """
        try:
            from rich.console import Console
            from rich.panel import Panel
        except ImportError:
            # Fall back to simple format if rich is not available
            return self._generate_simple()

        console = Console()
        q_and_a = self.result.q_and_a()
        
        with console.capture() as capture:
            for scenario in q_and_a:
                q_name = scenario.get("question_name")
                q_text = scenario.get("question_text", "")
                answer = scenario.get("answer", "")
                comment = scenario.get("comment")

                block_lines = [f"[bold]QUESTION:[/bold] {q_text} [dim]({q_name})[/dim]"]
                
                # Add options if available
                if q_name:
                    options = self.result.get_question_options(q_name)
                    if options:
                        opt_str = " / ".join(map(str, options))
                        block_lines.append(f"[italic]OPTIONS:[/italic] {opt_str}")
                
                block_lines.append(f"[bold]ANSWER:[/bold] {answer}")
                
                # Add comment if show_comments is True and comment exists
                if self.show_comments and comment:
                    block_lines.append(f"[dim]COMMENT:[/dim] {comment}")

                console.print(Panel("\n".join(block_lines), expand=False))
                console.print()  # blank line between panels

        return capture.get()

    def _generate_html(self) -> str:
        """Generate HTML formatted transcript for Jupyter notebook display.
        
        Returns:
            HTML formatted transcript string with styling and copy button
        """
        if self.carousel:
            return self._generate_html_carousel()
        else:
            return self._generate_html_list()

    def _generate_html_list(self) -> str:
        """Generate HTML as a list of Q&A cards."""
        import html
        import uuid
        
        # Generate unique ID for this transcript
        transcript_id = f"transcript_{uuid.uuid4().hex[:8]}"
        
        # Get plain text version for copying
        plain_text = self._generate_simple().replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')
        
        q_and_a = self.result.q_and_a()
        
        html_parts = [f'''
<div id="{transcript_id}" style="
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
    max-width: 800px;
    margin: 16px 0;
">
    <!-- Header with Copy Button -->
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
        ">Interview Transcript</div>
        <button onclick="copyTranscript_{transcript_id}()" style="
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
    
    <!-- Q&A Cards -->
    <div style="display: flex; flex-direction: column; gap: 16px; max-height: 500px; overflow-y: auto;">
''']
        
        # Add each Q&A as a card
        for i, scenario in enumerate(q_and_a):
            q_name = scenario.get("question_name")
            q_text = html.escape(str(scenario.get("question_text", "")))
            answer = html.escape(str(scenario.get("answer", "")))
            comment = scenario.get("comment")
            
            # Build options HTML inline with question
            options_html = ""
            if q_name:
                options = self.result.get_question_options(q_name)
                if options:
                    opt_list = [f'{html.escape(str(opt))}' for opt in options]
                    options_html = f'<div style="margin-top: 6px; font-size: 13px; color: #57606a; font-style: italic;">Options: {" • ".join(opt_list)}</div>'
            
            # Start card
            html_parts.append(f'''
        <div style="
            border: 1px solid #d4d4d4;
            border-radius: 4px;
            background: transparent;
        ">
            <!-- Question -->
            <div style="
                padding: 12px;
                background: #f6f8fa;
                border-bottom: 1px solid #d4d4d4;
            ">
                <div style="
                    font-size: 11px;
                    font-weight: bold;
                    color: #57606a;
                    margin-bottom: 6px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">Question {i+1}</div>
                <div style="
                    font-size: 14px;
                    color: #24292e;
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">{q_text} <span style="color: #57606a; font-size: 12px;">({html.escape(str(q_name)) if q_name else ''})</span></div>
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
                ">{answer}</div>
            </div>
''')
            
            # Add comment if show_comments is True and comment exists
            if self.show_comments and comment:
                comment_html = html.escape(str(comment))
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
            
            # Close card
            html_parts.append('        </div>')
        
        # Close container and add JavaScript for copy functionality
        html_parts.append(f'''
    </div>
</div>

<script>
function copyTranscript_{transcript_id}() {{
    const text = "{plain_text}";
    
    if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(text).then(() => {{
            showCopyFeedback_{transcript_id}();
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
            showCopyFeedback_{transcript_id}();
        }} catch (err) {{
            console.error('Failed to copy:', err);
        }}
        document.body.removeChild(textArea);
    }}
}}

function showCopyFeedback_{transcript_id}() {{
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
</script>
''')
        
        return ''.join(html_parts)

    def _generate_html_carousel(self) -> str:
        """Generate HTML as a carousel with navigation."""
        import html
        import uuid
        
        # Generate unique ID for this transcript
        transcript_id = f"transcript_{uuid.uuid4().hex[:8]}"
        
        # Get plain text version for copying
        plain_text = self._generate_simple().replace("'", "\\'").replace('"', '\\"').replace('\n', '\\n')
        
        q_and_a = self.result.q_and_a()
        total_questions = len(q_and_a)
        
        html_parts = [f'''
<div id="{transcript_id}" style="
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
        ">Interview Transcript</div>
        <button onclick="copyTranscript_{transcript_id}()" style="
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
    
    <!-- Carousel Container -->
    <div style="position: relative;">
        <!-- Q&A Cards (all hidden except first) -->
''']
        
        # Add each Q&A as a carousel slide
        for i, scenario in enumerate(q_and_a):
            q_name = scenario.get("question_name")
            q_text = html.escape(str(scenario.get("question_text", "")))
            answer = html.escape(str(scenario.get("answer", "")))
            comment = scenario.get("comment")
            
            # Build options HTML inline with question
            options_html = ""
            if q_name:
                options = self.result.get_question_options(q_name)
                if options:
                    opt_list = [f'{html.escape(str(opt))}' for opt in options]
                    options_html = f'<div style="margin-top: 6px; font-size: 13px; color: #57606a; font-style: italic;">Options: {" • ".join(opt_list)}</div>'
            
            display_style = "block" if i == 0 else "none"
            
            # Card for this Q&A
            html_parts.append(f'''
        <div class="carousel-slide-{transcript_id}" style="
            display: {display_style};
            border: 1px solid #d4d4d4;
            border-radius: 4px;
            background: transparent;
            height: 400px;
            overflow-y: auto;
        ">
            <!-- Question -->
            <div style="
                padding: 12px;
                background: #f6f8fa;
                border-bottom: 1px solid #d4d4d4;
            ">
                <div style="
                    font-size: 11px;
                    font-weight: bold;
                    color: #57606a;
                    margin-bottom: 6px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">Question {i+1}</div>
                <div style="
                    font-size: 14px;
                    color: #24292e;
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">{q_text} <span style="color: #57606a; font-size: 12px;">({html.escape(str(q_name)) if q_name else ''})</span></div>
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
                ">{answer}</div>
            </div>
''')
            
            # Add comment if show_comments is True and comment exists
            if self.show_comments and comment:
                comment_html = html.escape(str(comment))
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
        
        # Navigation controls
        html_parts.append(f'''
        
        <!-- Navigation Controls -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 16px;
            padding-top: 12px;
            border-top: 1px solid #d4d4d4;
        ">
            <button onclick="prevSlide_{transcript_id}()" style="
                background: transparent;
                border: 1px solid #d4d4d4;
                border-radius: 4px;
                color: #24292e;
                cursor: pointer;
                font-size: 13px;
                padding: 6px 12px;
                transition: background 0.2s ease;
            " onmouseover="this.style.background='#f6f8fa';" 
               onmouseout="this.style.background='transparent';">
                ← Previous
            </button>
            
            <div id="carousel-counter-{transcript_id}" style="
                font-size: 13px;
                color: #57606a;
            ">1 of {total_questions}</div>
            
            <button onclick="nextSlide_{transcript_id}()" style="
                background: transparent;
                border: 1px solid #d4d4d4;
                border-radius: 4px;
                color: #24292e;
                cursor: pointer;
                font-size: 13px;
                padding: 6px 12px;
                transition: background 0.2s ease;
            " onmouseover="this.style.background='#f6f8fa';" 
               onmouseout="this.style.background='transparent';">
                Next →
            </button>
        </div>
    </div>
</div>

<script>
let currentSlide_{transcript_id} = 0;
const totalSlides_{transcript_id} = {total_questions};

function showSlide_{transcript_id}(index) {{
    const slides = document.querySelectorAll('.carousel-slide-{transcript_id}');
    slides.forEach((slide, i) => {{
        slide.style.display = i === index ? 'block' : 'none';
    }});
    
    // Update counter
    document.getElementById('carousel-counter-{transcript_id}').textContent = 
        `${{index + 1}} of ${{totalSlides_{transcript_id}}}`;
}}

function nextSlide_{transcript_id}() {{
    currentSlide_{transcript_id} = (currentSlide_{transcript_id} + 1) % totalSlides_{transcript_id};
    showSlide_{transcript_id}(currentSlide_{transcript_id});
}}

function prevSlide_{transcript_id}() {{
    currentSlide_{transcript_id} = (currentSlide_{transcript_id} - 1 + totalSlides_{transcript_id}) % totalSlides_{transcript_id};
    showSlide_{transcript_id}(currentSlide_{transcript_id});
}}

function copyTranscript_{transcript_id}() {{
    const text = "{plain_text}";
    
    if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(text).then(() => {{
            showCopyFeedback_{transcript_id}();
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
            showCopyFeedback_{transcript_id}();
        }} catch (err) {{
            console.error('Failed to copy:', err);
        }}
        document.body.removeChild(textArea);
    }}
}}

function showCopyFeedback_{transcript_id}() {{
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
</script>
''')
        
        return ''.join(html_parts)

    def __str__(self) -> str:
        """Return simple plain-text representation.
        
        Returns:
            Plain-text formatted transcript
        """
        return self._generate_simple()

    def __repr__(self) -> str:
        """Return Rich formatted representation for terminal display.
        
        Returns:
            Rich formatted transcript if available, otherwise simple format
        """
        return self._generate_rich()

    def _repr_html_(self) -> str:
        """Return HTML representation for Jupyter notebook display.
        
        This method is automatically called by Jupyter notebooks to render
        the object as HTML.
        
        Returns:
            HTML formatted transcript
        """
        return self._generate_html()

    def to_simple(self) -> str:
        """Explicitly get the simple plain-text format.
        
        Returns:
            Plain-text formatted transcript
        """
        return self._generate_simple()

    def to_rich(self) -> str:
        """Explicitly get the Rich formatted output.
        
        Returns:
            Rich formatted transcript
            
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
            HTML formatted transcript
        """
        return self._generate_html()


# Keep the legacy function for backward compatibility
def generate_transcript(result: "Result", format: str = "simple") -> str:
    """Generate a transcript from a Result object (legacy function).
    
    This function is maintained for backward compatibility. New code should use
    Result.transcript() which returns a Transcript object with intelligent
    display formatting.

    Args:
        result: The Result object to generate a transcript for
        format: The format for the transcript ('simple' or 'rich')

    Returns:
        The generated transcript as a string
    """
    transcript = Transcript(result)
    if format == "simple":
        return transcript.to_simple()
    elif format == "rich":
        return transcript.to_rich()
    else:
        raise ValueError("format must be either 'simple' or 'rich'")
