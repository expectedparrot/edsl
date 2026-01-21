"""This module contains the descriptors for the classes in the edsl package."""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # Not using any imported types in this file


class BaseDescriptor(ABC):
    """ABC for something."""

    @abstractmethod
    def validate(self, value: Any) -> None:
        """Validate the value. If it is invalid, raise an exception. If it is valid, do nothing."""
        pass

    def __get__(self, instance, owner):
        """Get the value of the attribute."""
        return instance.__dict__[self.name]

    def __set__(self, instance, value: Any) -> None:
        """Set the value of the attribute."""
        self.validate(value, instance)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name


class QuestionsDescriptor(BaseDescriptor):
    """Descriptor for questions."""

    def __get__(self, instance, owner):
        """Get the value of the attribute."""
        return instance.__dict__[self.name]

    def validate(self, value: Any, instance) -> None:
        """Validate the value. If it is invalid, raise an exception. If it is valid, do nothing."""
        from ..questions import QuestionBase
        from .exceptions import DuplicateQuestionNameError

        if not isinstance(value, list):
            raise TypeError("Questions must be a list.")
        if not all(isinstance(question, QuestionBase) for question in value):
            raise TypeError("Questions must be a list of Question objects.")
        question_names = [question.question_name for question in value]
        if len(question_names) != len(set(question_names)):
            # Find which names are duplicated
            seen = set()
            duplicates = set()
            for name in question_names:
                if name in seen:
                    duplicates.add(name)
                else:
                    seen.add(name)

            duplicate_list = sorted(list(duplicates))
            raise DuplicateQuestionNameError(
                f"Question names must be unique. Duplicate names found: {duplicate_list}"
            )

    def __set__(self, instance, value: Any) -> None:
        """Set the value of the attribute.

        Optimized to set all questions at once in O(n) instead of
        calling add_question() for each question which was O(n²).
        The validate() method already checks for duplicates.
        """
        from .pseudo_indices import PseudoIndices

        self.validate(value, instance)

        # Set all questions at once - O(n)
        instance.__dict__[self.name] = list(value) if value else []

        # Build pseudo_indices in one pass - O(n)
        instance._pseudo_indices = PseudoIndices(
            {q.question_name: i for i, q in enumerate(value or [])}
        )

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name


class QuestionsToRandomizeDescriptor(BaseDescriptor):
    """Descriptor for questions_to_randomize list.

    This descriptor validates that:
    1. The value is a list (or None, which is converted to [])
    2. All items in the list are strings
    3. All question names exist in the survey
    """

    def __get__(self, instance, owner):
        """Get the value of the attribute."""
        if instance is None:
            return self
        return instance.__dict__.get(self.name, [])

    def validate(self, value: Any, instance) -> None:
        """Validate the questions_to_randomize list.

        Args:
            value: The list of question names to randomize
            instance: The Survey instance

        Raises:
            SurveyQuestionsToRandomizeError: If validation fails
        """
        from .exceptions import SurveyQuestionsToRandomizeError

        if value is None:
            return  # Will be converted to [] in __set__

        if not isinstance(value, list):
            raise SurveyQuestionsToRandomizeError(
                f"questions_to_randomize must be a list of strings. "
                f"Got type: {type(value).__name__}"
            )

        # Check that each element is a string
        for item in value:
            if not isinstance(item, str):
                raise SurveyQuestionsToRandomizeError(
                    f"questions_to_randomize must be a list of strings. "
                    f"Found non-string value: {item!r} (type: {type(item).__name__})"
                )

        # Check that each question name exists in the survey
        # Only validate if questions are already set
        if hasattr(instance, "_questions") and instance._questions:
            question_names_in_survey = {q.question_name for q in instance._questions}

            for question_name in value:
                if question_name not in question_names_in_survey:
                    raise SurveyQuestionsToRandomizeError(
                        f"questions_to_randomize contains question name '{question_name}' "
                        f"which is not present in the survey. "
                        f"Valid question names are: {sorted(question_names_in_survey)}"
                    )

    def __set__(self, instance, value: Any) -> None:
        """Set the value of the attribute, converting None to []."""
        # Convert None to empty list
        if value is None:
            value = []

        self.validate(value, instance)
        instance.__dict__[self.name] = value

    def __set_name__(self, owner, name: str) -> None:
        """Set the name of the attribute."""
        self.name = "_" + name
