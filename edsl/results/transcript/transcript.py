"""
Transcript class for generating transcripts from a single Result object.

This module provides the Transcript class which displays questions and answers
from a single Result with support for terminal (Rich), plain text, and HTML output.
"""

from typing import TYPE_CHECKING, List
import uuid

from .base import TranscriptBase, QAItem, escape_for_js
from . import html_builder

if TYPE_CHECKING:
    from ..result import Result


class Transcript(TranscriptBase):
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

    def __init__(
        self, result: "Result", show_comments: bool = True, carousel: bool = True
    ):
        """Initialize a Transcript with a Result object.

        Args:
            result: The Result object to generate transcripts for.
            show_comments: Whether to display comments in the transcript.
            carousel: Whether to display as a carousel in HTML (one Q&A at a time).
        """
        super().__init__(show_comments)
        self.result = result
        self.carousel = carousel

    def _get_qa_items(self) -> List[QAItem]:
        """Extract question-answer items from the Result.

        Returns:
            List of QAItem objects representing the Q&A data.
        """
        items = []
        q_and_a = self.result.q_and_a()

        for i, scenario in enumerate(q_and_a):
            q_name = scenario.get("question_name")
            options = None
            if q_name:
                raw_options = self.result.get_question_options(q_name)
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

        return items

    def _generate_simple(self) -> str:
        """Generate a simple plain-text transcript.

        Returns:
            Plain-text formatted transcript string.
        """
        lines: List[str] = []
        items = self._get_qa_items()

        for item in items:
            lines.append(f"QUESTION: {item.question_text} ({item.question_name})")

            if item.options:
                opt_str = " / ".join(item.options)
                lines.append(f"OPTIONS: {opt_str}")

            lines.append(f"ANSWER: {item.answer}")

            if self.show_comments and item.comment:
                lines.append(f"COMMENT: {item.comment}")

            lines.append("")

        if lines and lines[-1] == "":
            lines.pop()

        return "\n".join(lines)

    def _generate_rich(self) -> str:
        """Generate Rich formatted transcript for terminal display.

        Returns:
            Rich formatted transcript string with colors and panels.
        """
        try:
            from rich.console import Console
            from rich.panel import Panel
        except ImportError:
            return self._generate_simple()

        console = Console()
        items = self._get_qa_items()

        with console.capture() as capture:
            for item in items:
                block_lines = [
                    f"[bold]QUESTION:[/bold] {item.question_text} [dim]({item.question_name})[/dim]"
                ]

                if item.options:
                    opt_str = " / ".join(item.options)
                    block_lines.append(f"[italic]OPTIONS:[/italic] {opt_str}")

                block_lines.append(f"[bold]ANSWER:[/bold] {item.answer}")

                if self.show_comments and item.comment:
                    block_lines.append(f"[dim]COMMENT:[/dim] {item.comment}")

                console.print(Panel("\n".join(block_lines), expand=False))
                console.print()

        return capture.get()

    def _generate_html(self) -> str:
        """Generate HTML formatted transcript.

        Returns:
            HTML formatted transcript string with styling.
        """
        if self.carousel:
            return self._generate_html_carousel()
        else:
            return self._generate_html_list()

    def _generate_html_list(self) -> str:
        """Generate HTML as a list of Q&A cards."""
        transcript_id = f"transcript_{uuid.uuid4().hex[:8]}"
        plain_text = escape_for_js(self._generate_simple())
        items = self._get_qa_items()

        html_parts = [
            f'<div id="{transcript_id}" style="{html_builder.TRANSCRIPT_STYLES}">',
            html_builder.build_header(
                transcript_id, "Interview Transcript", f"copyTranscript_{transcript_id}"
            ),
            '    <div style="display: flex; flex-direction: column; gap: 16px; max-height: 500px; overflow-y: auto;">',
        ]

        for i, item in enumerate(items):
            card = html_builder.build_qa_card(
                item,
                show_comments=self.show_comments,
                question_label=f"Question {i + 1}",
            )
            html_parts.append(card)

        html_parts.append("    </div>")
        html_parts.append("</div>")
        html_parts.append("<script>")
        html_parts.append(html_builder.build_copy_script(transcript_id, plain_text))
        html_parts.append("</script>")

        return "\n".join(html_parts)

    def _generate_html_carousel(self) -> str:
        """Generate HTML as a carousel with navigation."""
        transcript_id = f"transcript_{uuid.uuid4().hex[:8]}"
        plain_text = escape_for_js(self._generate_simple())
        items = self._get_qa_items()
        total = len(items)

        html_parts = [
            f'<div id="{transcript_id}" style="{html_builder.TRANSCRIPT_STYLES}">',
            html_builder.build_header(
                transcript_id, "Interview Transcript", f"copyTranscript_{transcript_id}"
            ),
            '    <div style="position: relative;">',
        ]

        for i, item in enumerate(items):
            display = "block" if i == 0 else "none"
            card = html_builder.build_qa_card(
                item,
                show_comments=self.show_comments,
                question_label=f"Question {i + 1}",
                display_style=display,
                card_class=f"carousel-slide-{transcript_id}",
                fixed_height=True,
            )
            html_parts.append(card)

        html_parts.append(html_builder.build_carousel_nav(transcript_id, total))
        html_parts.append("    </div>")
        html_parts.append("</div>")
        html_parts.append("<script>")
        html_parts.append(html_builder.build_carousel_script(transcript_id, total))
        html_parts.append(html_builder.build_copy_script(transcript_id, plain_text))
        html_parts.append("</script>")

        return "\n".join(html_parts)


def generate_transcript(result: "Result", format: str = "simple") -> str:
    """Generate a transcript from a Result object (legacy function).

    This function is maintained for backward compatibility. New code should use
    Result.transcript() which returns a Transcript object with intelligent
    display formatting.

    Args:
        result: The Result object to generate a transcript for.
        format: The format for the transcript ('simple' or 'rich').

    Returns:
        The generated transcript as a string.

    Raises:
        ValueError: If format is not 'simple' or 'rich'.
    """
    transcript = Transcript(result)
    if format == "simple":
        return transcript.to_simple()
    elif format == "rich":
        return transcript.to_rich()
    else:
        raise ValueError("format must be either 'simple' or 'rich'")
