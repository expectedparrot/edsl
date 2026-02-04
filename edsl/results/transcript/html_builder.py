"""
HTML builder utilities for transcript generation.

This module provides shared HTML, CSS, and JavaScript components
used by both Transcript and Transcripts classes.
"""

import html
from typing import List, Optional

from .base import QAItem

# Shared CSS styles
TRANSCRIPT_STYLES = """
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', 'Arial', sans-serif;
    max-width: 800px;
    margin: 16px 0;
"""

HEADER_STYLES = """
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 8px;
    border-bottom: 1px solid #d4d4d4;
"""

COPY_BUTTON_STYLES = """
    background: transparent;
    border: 1px solid #d4d4d4;
    border-radius: 4px;
    color: #24292e;
    cursor: pointer;
    font-size: 13px;
    padding: 4px 10px;
    transition: background 0.2s ease;
"""

NAV_BUTTON_STYLES = """
    background: transparent;
    border: 1px solid #d4d4d4;
    border-radius: 4px;
    color: #24292e;
    cursor: pointer;
    font-size: 13px;
    padding: 6px 12px;
    transition: background 0.2s ease;
"""

CARD_STYLES = """
    border: 1px solid #d4d4d4;
    border-radius: 4px;
    background: transparent;
"""

QUESTION_SECTION_STYLES = """
    padding: 12px;
    background: #f6f8fa;
    border-bottom: 1px solid #d4d4d4;
"""

ANSWER_SECTION_STYLES = """
    padding: 12px;
    background: #f0fdf4;
"""

COMMENT_SECTION_STYLES = """
    padding: 12px;
    background: #faf5ff;
"""

LABEL_STYLES = """
    font-size: 11px;
    font-weight: bold;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
"""


def build_header(transcript_id: str, title: str, copy_func_name: str) -> str:
    """Build the transcript header with title and copy button.

    Args:
        transcript_id: Unique identifier for this transcript.
        title: Title to display in the header.
        copy_func_name: JavaScript function name for copy action.

    Returns:
        HTML string for the header.
    """
    return f"""
    <!-- Header with Copy Button -->
    <div style="{HEADER_STYLES}">
        <div style="
            font-size: 16px;
            font-weight: bold;
            color: #24292e;
        ">{html.escape(title)}</div>
        <button onclick="{copy_func_name}()" style="{COPY_BUTTON_STYLES}"
            onmouseover="this.style.background='#f6f8fa';"
            onmouseout="this.style.background='transparent';">
            Copy
        </button>
    </div>
"""


def build_qa_card(
    item: QAItem,
    show_comments: bool,
    question_label: str = "Question",
    display_style: str = "block",
    card_class: str = "",
    data_attrs: str = "",
    fixed_height: bool = False,
) -> str:
    """Build an HTML card for a single Q&A item.

    Args:
        item: The QAItem to render.
        show_comments: Whether to show the comment section.
        question_label: Label for the question (e.g., "Question 1").
        display_style: CSS display value (block/none).
        card_class: CSS class for the card div.
        data_attrs: Additional data attributes for the card.
        fixed_height: Whether to use fixed height (for carousel).

    Returns:
        HTML string for the Q&A card.
    """
    q_text = html.escape(str(item.question_text))
    q_name = html.escape(str(item.question_name)) if item.question_name else ""
    answer = html.escape(str(item.answer))

    # Build options HTML
    options_html = ""
    if item.options:
        opt_list = [html.escape(str(opt)) for opt in item.options]
        options_html = f'<div style="margin-top: 6px; font-size: 13px; color: #57606a; font-style: italic;">Options: {" &bull; ".join(opt_list)}</div>'

    has_comment = show_comments and item.comment
    answer_border = "border-bottom: 1px solid #d4d4d4;" if has_comment else ""

    height_style = "height: 400px; overflow-y: auto;" if fixed_height else ""
    class_attr = f'class="{card_class}"' if card_class else ""

    card_html = f"""
        <div {class_attr} {data_attrs} style="
            display: {display_style};
            {CARD_STYLES}
            {height_style}
        ">
            <!-- Question -->
            <div style="{QUESTION_SECTION_STYLES}">
                <div style="{LABEL_STYLES} color: #57606a;">{question_label}</div>
                <div style="
                    font-size: 14px;
                    color: #24292e;
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">{q_text} <span style="color: #57606a; font-size: 12px;">({q_name})</span></div>
                {options_html}
            </div>

            <!-- Answer -->
            <div style="
                {ANSWER_SECTION_STYLES}
                {answer_border}
            ">
                <div style="{LABEL_STYLES} color: #166534;">Answer</div>
                <div style="
                    font-size: 14px;
                    color: #15803d;
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">{answer}</div>
            </div>
"""

    # Add comment if present
    if has_comment:
        comment_html = html.escape(str(item.comment))
        card_html += f"""
            <!-- Comment -->
            <div style="{COMMENT_SECTION_STYLES}">
                <div style="{LABEL_STYLES} color: #6b21a8;">Comment</div>
                <div style="
                    font-size: 13px;
                    color: #7c3aed;
                    font-style: italic;
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-wrap: break-word;
                ">{comment_html}</div>
            </div>
"""

    card_html += "        </div>"
    return card_html


def build_copy_script(
    transcript_id: str, plain_text: str, func_suffix: str = ""
) -> str:
    """Build the JavaScript for copy functionality.

    Args:
        transcript_id: Unique identifier for this transcript.
        plain_text: Pre-escaped plain text content to copy.
        func_suffix: Optional suffix for function names.

    Returns:
        JavaScript code for copy functionality.
    """
    func_name = f"copyTranscript_{transcript_id}"
    feedback_name = f"showCopyFeedback_{transcript_id}"

    return f"""
function {func_name}() {{
    const text = "{plain_text}";

    if (navigator.clipboard && window.isSecureContext) {{
        navigator.clipboard.writeText(text).then(() => {{
            {feedback_name}();
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
            {feedback_name}();
        }} catch (err) {{
            console.error('Failed to copy:', err);
        }}
        document.body.removeChild(textArea);
    }}
}}

function {feedback_name}() {{
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


def build_carousel_nav(transcript_id: str, total_items: int) -> str:
    """Build navigation controls for a simple carousel.

    Args:
        transcript_id: Unique identifier for this transcript.
        total_items: Total number of items in the carousel.

    Returns:
        HTML string for navigation controls.
    """
    return f"""
        <!-- Navigation Controls -->
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 16px;
            padding-top: 12px;
            border-top: 1px solid #d4d4d4;
        ">
            <button onclick="prevSlide_{transcript_id}()" style="{NAV_BUTTON_STYLES}"
                onmouseover="this.style.background='#f6f8fa';"
                onmouseout="this.style.background='transparent';">
                Prev
            </button>

            <div id="carousel-counter-{transcript_id}" style="
                font-size: 13px;
                color: #57606a;
            ">1 of {total_items}</div>

            <button onclick="nextSlide_{transcript_id}()" style="{NAV_BUTTON_STYLES}"
                onmouseover="this.style.background='#f6f8fa';"
                onmouseout="this.style.background='transparent';">
                Next
            </button>
        </div>
"""


def build_carousel_script(transcript_id: str, total_items: int) -> str:
    """Build JavaScript for carousel navigation.

    Args:
        transcript_id: Unique identifier for this transcript.
        total_items: Total number of items in the carousel.

    Returns:
        JavaScript code for carousel navigation.
    """
    return f"""
let currentSlide_{transcript_id} = 0;
const totalSlides_{transcript_id} = {total_items};

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
"""
