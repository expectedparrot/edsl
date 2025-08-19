"""Survey question management functionality.

This module provides the SurveyQuestionManager class which handles all question management
operations for surveys, including adding, deleting, moving, grouping, and accessing questions.
This separation allows for cleaner Survey class code and more focused question management logic.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey
    from ..questions import QuestionBase


class SurveyQuestionManager:
    """Handles question management operations for Survey objects.
    
    This class provides a clean interface for all question-related operations
    including CRUD operations, grouping, filtering, and access methods.
    """
    
    def __init__(self, survey: "Survey"):
        """Initialize the question manager.
        
        Args:
            survey: The survey to manage questions for.
        """
        self.survey = survey
    
    def add(self, question: "QuestionBase", index: Optional[int] = None) -> "Survey":
        """Add a question to the survey.

        Args:
            question: The question to add to the survey.
            index: The index to add the question at. If not provided, the question is appended to the end.

        Returns:
            Survey: The updated Survey object.

        Raises:
            SurveyCreationError: If the question name is already in the survey.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> from edsl import QuestionMultipleChoice
            >>> s = Survey.example()
            >>> q = QuestionMultipleChoice(question_text="New question?", question_options=["yes", "no"], question_name="new_q")
            >>> s_updated = s.question_manager.add(q)
            >>> len(s_updated.questions)
            4
        """
        from .edit_survey import EditSurvey
        return EditSurvey(self.survey).add_question(question, index)

    def delete(self, identifier: Union[str, int]) -> "Survey":
        """Delete a question from the survey.

        Args:
            identifier: The name or index of the question to delete.

        Returns:
            Survey: The updated Survey object.

        Raises:
            SurveyError: If the question name is not found in the survey.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s_updated = s.question_manager.delete("q1")
            >>> len(s_updated.questions)
            2
            >>> s_updated2 = s.question_manager.delete(0)
            >>> len(s_updated2.questions)
            2
        """
        from .edit_survey import EditSurvey
        return EditSurvey(self.survey).delete_question(identifier)

    def move(self, identifier: Union[str, int], new_index: int) -> "Survey":
        """Move a question to a new index.

        Args:
            identifier: The name or index of the question to move.
            new_index: The new index for the question.

        Returns:
            Survey: The updated Survey object.

        Raises:
            SurveyError: If the question name is not found in the survey.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s.question_names
            ['q0', 'q1', 'q2']
            >>> s_moved = s.question_manager.move("q0", 2)
            >>> s_moved.question_names
            ['q1', 'q2', 'q0']
        """
        from .edit_survey import EditSurvey
        return EditSurvey(self.survey).move_question(identifier, new_index)

    def get(self, question_name: str) -> "QuestionBase":
        """Return the question object given the question name.
        
        Args:
            question_name: The name of the question to get.

        Returns:
            QuestionBase: The question object.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> q = s.question_manager.get("q0")
            >>> q.question_name
            'q0'
        """
        if question_name not in self.survey.question_name_to_index:
            from .exceptions import SurveyError
            raise SurveyError(f"Question name {question_name} not found in survey.")
        return self.survey.questions[self.survey.question_name_to_index[question_name]]

    def get_by_index(self, index: int) -> "QuestionBase":
        """Return the question object at the given index.
        
        Args:
            index: The index of the question to get.

        Returns:
            QuestionBase: The question object.

        Raises:
            IndexError: If the index is out of range.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> q = s.question_manager.get_by_index(0)
            >>> q.question_name
            'q0'
        """
        return self.survey.questions[index]

    def add_group(
        self,
        start_question: Union["QuestionBase", str],
        end_question: Union["QuestionBase", str],
        group_name: str,
    ) -> "Survey":
        """Create a logical group of questions within the survey.

        Question groups allow you to organize questions into meaningful sections,
        which can be useful for:
        - Analysis (analyzing responses by section)
        - Navigation (jumping between sections)
        - Presentation (displaying sections with headers)

        Groups are defined by a contiguous range of questions from start_question
        to end_question, inclusive. Groups cannot overlap with other groups.

        Args:
            start_question: The first question in the group, specified either as a
                QuestionBase object or its question_name string.
            end_question: The last question in the group, specified either as a
                QuestionBase object or its question_name string.
            group_name: A name for the group. Must be a valid Python identifier
                and must not conflict with existing group or question names.

        Returns:
            Survey: The modified survey instance (allows for method chaining).

        Raises:
            SurveyCreationError: If the group name is invalid, already exists,
                conflicts with a question name, if start comes after end,
                or if the group overlaps with an existing group.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s_grouped = s.question_manager.add_group("q0", "q1", "intro_group")
            >>> s_grouped.question_groups
            {'intro_group': (0, 1)}
        """
        from .exceptions import SurveyCreationError
        from .base import EndOfSurvey
        
        if not group_name.isidentifier():
            raise SurveyCreationError(
                f"Group name {group_name} is not a valid identifier."
            )

        if group_name in self.survey.question_groups:
            raise SurveyCreationError(
                f"Group name {group_name} already exists in the survey."
            )

        if group_name in self.survey.question_name_to_index:
            raise SurveyCreationError(
                f"Group name {group_name} already exists as a question name in the survey."
            )

        start_index = self.survey._get_question_index(start_question)
        end_index = self.survey._get_question_index(end_question)

        # Check if either index is the EndOfSurvey object
        if start_index is EndOfSurvey or end_index is EndOfSurvey:
            raise SurveyCreationError(
                "Cannot use EndOfSurvey as a boundary for question groups."
            )

        # Now we know both are integers
        assert isinstance(start_index, int) and isinstance(end_index, int)

        if start_index > end_index:
            raise SurveyCreationError(
                f"Start index {start_index} is greater than end index {end_index}."
            )

        # Check for overlaps with existing groups
        for existing_group_name, (
            exist_start,
            exist_end,
        ) in self.survey.question_groups.items():
            # Ensure the existing indices are integers (they should be, but for type checking)
            assert isinstance(exist_start, int) and isinstance(exist_end, int)

            # Check containment and overlap cases
            if start_index < exist_start and end_index > exist_end:
                raise SurveyCreationError(
                    f"Group {existing_group_name} is contained within the new group."
                )
            if start_index > exist_start and end_index < exist_end:
                raise SurveyCreationError(
                    f"New group would be contained within existing group {existing_group_name}."
                )
            if start_index < exist_start and end_index > exist_start:
                raise SurveyCreationError(
                    f"New group overlaps with the start of existing group {existing_group_name}."
                )
            if start_index < exist_end and end_index > exist_end:
                raise SurveyCreationError(
                    f"New group overlaps with the end of existing group {existing_group_name}."
                )

        # Create a copy of the survey and add the group
        new_survey = self.survey.duplicate()
        new_survey.question_groups[group_name] = (start_index, end_index)
        return new_survey

    def select(self, *question_names: str) -> "Survey":
        """Create a new Survey with questions selected by name.
        
        Args:
            *question_names: Variable number of question names to select from the survey.

        Returns:
            Survey: A new Survey instance with the specified questions selected.
            
        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s_selected = s.question_manager.select('q0', 'q2')
            >>> s_selected.question_names
            ['q0', 'q2']
        """
        if not question_names:
            raise ValueError("At least one question name must be provided")

        kept_questions = [self.get(name) for name in question_names]
        return self.survey.__class__(questions=kept_questions)

    def drop(self, *question_names: str) -> "Survey":
        """Create a new Survey with specified questions removed by name.

        This method creates a new Survey instance that contains all questions
        except those specified in the question_names parameter.

        Args:
            *question_names: Variable number of question names to remove from the survey.

        Returns:
            Survey: A new Survey instance with the specified questions removed.

        Raises:
            ValueError: If no question names are provided.
            KeyError: If any specified question name is not found in the survey.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s_dropped = s.question_manager.drop('q1')
            >>> s_dropped.question_names
            ['q0', 'q2']
        """
        if not question_names:
            raise ValueError("At least one question name must be provided")

        # Validate that all question names exist
        question_map = self.survey.question_names_to_questions()
        for name in question_names:
            if name not in question_map:
                raise KeyError(
                    f"Question '{name}' not found in survey. Available questions: {list(question_map.keys())}"
                )

        # Get all questions except the ones to drop
        kept_questions = [
            q for q in self.survey.questions if q.question_name not in question_names
        ]

        return self.survey._create_subsurvey(kept_questions)

    def get_index(self, question: Union["QuestionBase", str]) -> Union[int, "EndOfSurveyParent"]:
        """Return the index of the question.

        Args:
            question: The question or question name to get the index of. Can be:
                - str: The question name
                - QuestionBase: A question object

        Returns:
            int: The index of the question.

        Raises:
            SurveyError: If the question name is not found in the survey.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s.question_manager.get_index("q0")
            0
        """
        return self.survey._get_question_index(question)

    def exists(self, question_name: str) -> bool:
        """Check if a question with the given name exists in the survey.
        
        Args:
            question_name: The name of the question to check for.
            
        Returns:
            bool: True if the question exists, False otherwise.
            
        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s.question_manager.exists("q0")
            True
            >>> s.question_manager.exists("nonexistent")
            False
        """
        return question_name in self.survey.question_name_to_index

    def count(self) -> int:
        """Return the number of questions in the survey.
        
        Returns:
            int: The number of questions.
            
        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s.question_manager.count()
            3
        """
        return len(self.survey.questions)

    def names(self) -> List[str]:
        """Return a list of question names in the survey.
        
        Returns:
            List[str]: List of question names in order.
            
        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s.question_manager.names()
            ['q0', 'q1', 'q2']
        """
        return self.survey.question_names

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        """Return a dictionary mapping question names to question attributes.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of question attributes.
            
        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> attrs = s.question_manager.to_dict()
            >>> 'q0' in attrs
            True
        """
        return self.survey.question_to_attributes()

    def validate_names(self) -> bool:
        """Check if all question names are valid.
        
        Returns:
            bool: True if all question names are valid, False otherwise.
            
        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> s.question_manager.validate_names()
            True
        """
        return all(q.is_valid_question_name() for q in self.survey.questions)

    @classmethod
    def create_for_survey(cls, survey: "Survey") -> "SurveyQuestionManager":
        """Factory method to create a question manager for a specific survey.
        
        Args:
            survey: The survey to create a question manager for.
            
        Returns:
            SurveyQuestionManager: A new question manager instance for the given survey.
        """
        return cls(survey)
