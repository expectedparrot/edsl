"""
Survey Vibe Accessor: Provides a namespace for vibe-based survey methods.

This module provides the SurveyVibeAccessor class that enables the
`survey.vibe.edit()`, `survey.vibe.add()`, and `survey.vibe.describe()`
interface pattern.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..survey import Survey
    from ...scenarios import Scenario


class SurveyVibeAccessor:
    """
    Accessor class for vibe-based survey editing methods.

    This class provides a namespace for all vibe-related survey methods,
    enabling the `survey.vibe.*` interface pattern.

    Examples
    --------
    >>> survey = Survey.from_vibes("Customer satisfaction survey")  # doctest: +SKIP
    >>> survey.vibe.edit("Translate to Spanish")  # doctest: +SKIP
    >>> survey.vibe.add("Add age question")  # doctest: +SKIP
    >>> survey.vibe.describe()  # doctest: +SKIP
    """

    def __init__(self, survey: "Survey"):
        """
        Initialize the accessor with a survey instance.

        Args:
            survey: The Survey instance to operate on
        """
        self._survey = survey

    def edit(
        self,
        edit_instructions: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        remote: bool = False,
    ) -> "Survey":
        """Edit the survey using natural language instructions.

        Uses an LLM to modify an existing survey based on natural language
        instructions. It can translate questions, change wording, drop questions,
        or make other modifications as requested.

        Args:
            edit_instructions: Natural language description of the edits to apply.
                Examples:
                - "Translate all questions to Spanish"
                - "Make the language more formal"
                - "Remove the third question"
                - "Change all likert scales to multiple choice questions"
            model: OpenAI model to use for editing (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            remote: Force remote execution (default: False)

        Returns:
            Survey: A new Survey instance with the edited questions

        Examples:
            >>> survey = Survey.from_vibes("Customer satisfaction survey")  # doctest: +SKIP
            >>> edited = survey.vibe.edit("Translate to Spanish")  # doctest: +SKIP
            >>> formal = survey.vibe.edit("Make the language more formal")  # doctest: +SKIP
        """
        from .vibes_dispatcher import default_dispatcher

        return default_dispatcher.dispatch(
            target="survey",
            method="vibe_edit",
            survey=self._survey,
            edit_instructions=edit_instructions,
            model=model,
            temperature=temperature,
            remote=remote,
        )

    def add(
        self,
        add_instructions: str,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        remote: bool = False,
    ) -> "Survey":
        """Add new questions to the survey using natural language instructions.

        Uses an LLM to add new questions to an existing survey based on
        natural language instructions. It can add simple questions, questions
        with skip logic, or multiple related questions.

        Args:
            add_instructions: Natural language description of what to add.
                Examples:
                - "Add a question asking their age"
                - "Add a follow-up question about satisfaction if they answered yes to q0"
                - "Add questions about demographics: age, gender, and location"
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            remote: Force remote execution (default: False)

        Returns:
            Survey: A new Survey instance with the original questions plus the new ones

        Examples:
            >>> survey = Survey.from_vibes("Customer satisfaction survey")  # doctest: +SKIP
            >>> expanded = survey.vibe.add("Add a question asking their age")  # doctest: +SKIP
            >>> with_skip = survey.vibe.add(
            ...     "Add a question about purchase frequency, but only if they answered 'yes' to q0"
            ... )  # doctest: +SKIP
        """
        from .vibes_dispatcher import default_dispatcher

        return default_dispatcher.dispatch(
            target="survey",
            method="vibe_add",
            survey=self._survey,
            add_instructions=add_instructions,
            model=model,
            temperature=temperature,
            remote=remote,
        )

    def describe(
        self,
        *,
        model: str = "gpt-4o",
        temperature: float = 0.7,
        remote: bool = False,
    ) -> "Scenario":
        """Generate a title and description for the survey.

        Uses an LLM to analyze the survey questions and generate
        a descriptive title and detailed description of what the survey is about.

        Args:
            model: OpenAI model to use for generation (default: "gpt-4o")
            temperature: Temperature for generation (default: 0.7)
            remote: Force remote execution (default: False)

        Returns:
            Scenario: A Scenario with keys:
                - "proposed_title": A single sentence title for the survey
                - "description": A paragraph-length description of the survey

        Examples:
            >>> survey = Survey.from_vibes("Customer satisfaction survey")  # doctest: +SKIP
            >>> info = survey.vibe.describe()  # doctest: +SKIP
            >>> print(info["proposed_title"])  # doctest: +SKIP
            >>> print(info["description"])  # doctest: +SKIP
        """
        from .vibes_dispatcher import default_dispatcher

        d = default_dispatcher.dispatch(
            target="survey",
            method="vibe_describe",
            survey=self._survey,
            model=model,
            temperature=temperature,
            remote=remote,
        )
        from ...scenarios import Scenario

        return Scenario(**d)
