"""
MarkdownResponse: A response type for displaying markdown content.

This class provides rich display capabilities:
- In Jupyter notebooks: renders as formatted Markdown
- In terminal: uses Rich library for styled output
- Also stores metadata like code executed, reasoning, etc.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class MarkdownResponse:
    """
    A response object that displays markdown content appropriately
    based on the environment (Jupyter vs terminal).

    Attributes:
        answer: The main answer/response text (markdown formatted)
        question: The original question asked
        code_executed: List of code snippets that were executed
        reasoning: The agent's reasoning process
        data_summary: Summary of the data analyzed
        raw_result: The complete raw result dict

    Example:
        >>> response = MarkdownResponse(
        ...     answer="The average is **42**",
        ...     question="What is the average?",
        ... )
        >>> # In Jupyter: displays as rendered Markdown
        >>> # In terminal: displays with Rich formatting
    """

    def __init__(
        self,
        answer: str,
        question: Optional[str] = None,
        code_executed: Optional[List[Dict[str, Any]]] = None,
        reasoning: Optional[str] = None,
        data_summary: Optional[Dict[str, Any]] = None,
        raw_result: Optional[Dict[str, Any]] = None,
    ):
        self.answer = answer
        self.question = question
        self.code_executed = code_executed or []
        self.reasoning = reasoning
        self.data_summary = data_summary
        self.raw_result = raw_result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarkdownResponse":
        """Create a MarkdownResponse from a service result dict."""
        return cls(
            answer=data.get("answer", ""),
            question=data.get("question"),
            code_executed=data.get("code_executed"),
            reasoning=data.get("reasoning"),
            data_summary=data.get("data_summary"),
            raw_result=data,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "answer": self.answer,
            "question": self.question,
            "code_executed": self.code_executed,
            "reasoning": self.reasoning,
            "data_summary": self.data_summary,
        }

    def _is_notebook(self) -> bool:
        """Check if running in a Jupyter notebook."""
        try:
            from edsl.utilities.is_notebook import is_notebook

            return is_notebook()
        except ImportError:
            # Fallback detection
            try:
                from IPython import get_ipython

                shell = get_ipython().__class__.__name__
                return shell == "ZMQInteractiveShell"
            except (ImportError, AttributeError):
                return False

    def _repr_markdown_(self) -> str:
        """
        Jupyter notebook representation - renders as Markdown.

        This method is automatically called by Jupyter to display the object.
        """
        return self.answer

    def __repr__(self) -> str:
        """
        Terminal representation - uses Rich for styled output.

        Falls back to plain text if Rich is not available.
        """
        if self._is_notebook():
            # In notebook, return simple repr - _repr_markdown_ handles display
            return f"MarkdownResponse(answer='{self.answer[:50]}...')"

        # Terminal: use Rich
        try:
            return self._rich_repr()
        except ImportError:
            return self._plain_repr()

    def _rich_repr(self) -> str:
        """Generate Rich-formatted terminal output."""
        from rich.console import Console
        from rich.markdown import Markdown
        import io

        console = Console(file=io.StringIO(), force_terminal=True)
        md = Markdown(self.answer)
        console.print(md)

        return console.file.getvalue()

    def _plain_repr(self) -> str:
        """Plain text fallback representation."""
        return self.answer

    def show(self) -> None:
        """
        Explicitly display the response.

        In Jupyter: displays rendered markdown
        In terminal: prints Rich-formatted output
        """
        if self._is_notebook():
            from IPython.display import display, Markdown

            display(Markdown(self._repr_markdown_()))
        else:
            print(self._rich_repr() if self._has_rich() else self._plain_repr())

    def _has_rich(self) -> bool:
        """Check if Rich library is available."""
        import importlib.util

        return importlib.util.find_spec("rich") is not None

    @property
    def text(self) -> str:
        """Get the plain text answer."""
        return self.answer

    def __str__(self) -> str:
        """String representation returns just the answer."""
        return self.answer
