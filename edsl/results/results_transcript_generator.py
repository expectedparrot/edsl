"""Transcript generation for Results objects."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .results import Results
    from .results_transcript import Transcripts


class TranscriptsGenerator:
    """Generates Transcripts viewers from a Results object.

    Instantiated with a reference to a Results instance; provides the
    ``transcripts`` method that creates a carousel-style viewer for
    navigating interview responses across multiple respondents.
    """

    def __init__(self, results: "Results") -> None:
        self._results = results

    def transcripts(self, show_comments: bool = True) -> "Transcripts":
        """Return a Transcripts object for viewing interview responses across multiple respondents.

        This method creates a carousel-style viewer that allows navigation across different
        Result objects (respondents) while keeping the same question in focus. This is useful
        for comparing how different respondents answered the same question.

        The Transcripts viewer provides:
        - Navigation between respondents (Result objects)
        - Navigation between questions
        - Agent name display for each respondent
        - Synchronized question viewing across respondents
        - Copy button for plain text export

        In HTML/Jupyter, displays as an interactive carousel with:
        - "Prev/Next Respondent" buttons to navigate between agents
        - "Prev Q/Next Q" buttons to navigate between questions

        In terminal, displays Rich formatted output with agent headers and Q&A pairs.

        Args:
            show_comments: Whether to include respondent comments in the transcripts.
                Defaults to True.

        Returns:
            A Transcripts object that adapts its display to the environment.

        Examples:
            >>> from edsl.results import Results
            >>> results = Results.example()
            >>> transcripts = results.transcripts()
            >>> # In Jupyter: Interactive carousel navigation
            >>> # In terminal: Rich formatted display
            >>> # As string: Plain text format

            >>> # Without comments
            >>> transcripts_no_comments = results.transcripts(show_comments=False)
        """
        from .results_transcript import Transcripts

        return Transcripts(self._results, show_comments=show_comments)
