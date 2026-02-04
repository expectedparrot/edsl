"""
Base class and data structures for transcript generation.

This module provides the abstract base class and shared data structures
used by both Transcript (single Result) and Transcripts (multiple Results).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class QAItem:
    """Represents a single question-answer pair."""

    question_name: str
    question_text: str
    answer: str
    comment: Optional[str] = None
    options: Optional[List[str]] = None
    question_index: int = 0


@dataclass
class TranscriptConfig:
    """Configuration for transcript rendering."""

    transcript_id: str
    show_comments: bool = True
    carousel: bool = True
    total_questions: int = 0
    total_results: int = 1
    title: str = "Interview Transcript"


class TranscriptBase(ABC):
    """Abstract base class for transcript viewers.

    This class provides shared rendering logic for both single-Result
    and multi-Result transcript viewers.
    """

    def __init__(self, show_comments: bool = True):
        """Initialize the transcript viewer.

        Args:
            show_comments: Whether to display comments in the transcript.
        """
        self.show_comments = show_comments

    @abstractmethod
    def _get_qa_items(self) -> List[QAItem]:
        """Extract question-answer items from the underlying data.

        Returns:
            List of QAItem objects representing the Q&A data.
        """
        pass

    @abstractmethod
    def _generate_simple(self) -> str:
        """Generate a simple plain-text transcript.

        Returns:
            Plain-text formatted transcript string.
        """
        pass

    @abstractmethod
    def _generate_rich(self) -> str:
        """Generate Rich formatted transcript for terminal display.

        Returns:
            Rich formatted transcript string.
        """
        pass

    @abstractmethod
    def _generate_html(self) -> str:
        """Generate HTML formatted transcript.

        Returns:
            HTML formatted transcript string.
        """
        pass

    def __str__(self) -> str:
        """Return simple plain-text representation."""
        return self._generate_simple()

    def __repr__(self) -> str:
        """Return Rich formatted representation for terminal display."""
        return self._generate_rich()

    def _repr_html_(self) -> str:
        """Return HTML representation for Jupyter notebook display."""
        return self._generate_html()

    def to_simple(self) -> str:
        """Explicitly get the simple plain-text format.

        Returns:
            Plain-text formatted transcript.
        """
        return self._generate_simple()

    def to_rich(self) -> str:
        """Explicitly get the Rich formatted output.

        Returns:
            Rich formatted transcript.

        Raises:
            ImportError: If the rich library is not installed.
        """
        try:
            from rich.console import Console  # noqa: F401
            from rich.panel import Panel  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "The 'rich' package is required for Rich formatting. "
                "Install it with `pip install rich`."
            ) from exc

        return self._generate_rich()

    def to_html(self) -> str:
        """Explicitly get the HTML formatted output.

        Returns:
            HTML formatted transcript.
        """
        return self._generate_html()


def escape_for_js(text: str) -> str:
    """Escape text for embedding in JavaScript strings.

    Args:
        text: The text to escape.

    Returns:
        Escaped text safe for JavaScript string literals.
    """
    return text.replace("'", "\\'").replace('"', '\\"').replace("\n", "\\n")
