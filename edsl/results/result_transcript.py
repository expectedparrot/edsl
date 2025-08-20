"""
Module for generating transcripts from Result objects.

This module provides functionality to convert Result objects into human-readable
transcripts showing questions, options (if any), and answers in either simple
plain-text format or rich formatted output.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .result import Result


class ResultTranscript:
    """Handles transcript generation for Result objects."""

    def __init__(self, result: "Result"):
        """Initialize with a Result object.

        Args:
            result: The Result object to generate transcripts for
        """
        self.result = result

    def generate(self, format: str = "simple") -> str:
        """Return the questions and answers in a human-readable transcript.

        Parameters
        ----------
        format : str, optional (``'simple'`` or ``'rich'``)
            ``'simple'`` (default) returns plain-text:

            QUESTION: <question text>
            OPTIONS: <opt1 / opt2 / ...>   # only when options are available
            ANSWER:   <answer>

            Each block is separated by a blank line.

            ``'rich'`` uses the *rich* library (if installed) to wrap each Q&A block in a
            ``Panel`` and returns the coloured/boxed string. Attempting to use the *rich*
            format without the dependency available raises ``ImportError``.
        """

        if format not in {"simple", "rich"}:
            raise ValueError("format must be either 'simple' or 'rich'")

        # Helper to extract question text, options, answer value
        def _components(q_name):
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

        # SIMPLE (plain-text) format -------------------------------------
        if format == "simple":
            lines: list[str] = []
            for q_name in self.result.answer:
                q_text, opt_str, ans_val = _components(q_name)
                lines.append(f"QUESTION: {q_text}")
                if opt_str is not None:
                    lines.append(f"OPTIONS: {opt_str}")
                lines.append(f"ANSWER: {ans_val}")
                lines.append("")

            if lines and lines[-1] == "":
                lines.pop()  # trailing blank line

            return "\n".join(lines)

        # RICH format ----------------------------------------------------
        try:
            from rich.console import Console
            from rich.panel import Panel
        except ImportError as exc:
            raise ImportError(
                "The 'rich' package is required for format='rich'. Install it with `pip install rich`."
            ) from exc

        console = Console()
        with console.capture() as capture:
            for q_name in self.result.answer:
                q_text, opt_str, ans_val = _components(q_name)

                block_lines = [f"[bold]QUESTION:[/bold] {q_text}"]
                if opt_str is not None:
                    block_lines.append(f"[italic]OPTIONS:[/italic] {opt_str}")
                block_lines.append(f"[bold]ANSWER:[/bold] {ans_val}")

                console.print(Panel("\n".join(block_lines), expand=False))
                console.print()  # blank line between panels

        return capture.get()


def generate_transcript(result: "Result", format: str = "simple") -> str:
    """Convenience function to generate a transcript from a Result object.

    Args:
        result: The Result object to generate a transcript for
        format: The format for the transcript ('simple' or 'rich')

    Returns:
        The generated transcript as a string
    """
    transcript_generator = ResultTranscript(result)
    return transcript_generator.generate(format)
