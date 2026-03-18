"""Manager for survey question groups.

Handles creation, validation, and computation of dependency-aware
question groups within a Survey.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from .base import EndOfSurvey, EndOfSurveyParent
from .exceptions import SurveyCreationError

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from .survey import Survey


class QuestionGroupManager:
    """Encapsulates all question-group logic for a Survey."""

    def __init__(self, survey: "Survey") -> None:
        self._survey = survey

    def add_question_group(
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
        """
        survey = self._survey

        if not group_name.isidentifier():
            raise SurveyCreationError(
                f"Group name {group_name} is not a valid identifier."
            )

        if group_name in survey.question_groups:
            raise SurveyCreationError(
                f"Group name {group_name} already exists in the survey."
            )

        if group_name in survey.question_name_to_index:
            raise SurveyCreationError(
                f"Group name {group_name} already exists as a question name in the survey."
            )

        start_index = survey._get_question_index(start_question)
        end_index = survey._get_question_index(end_question)

        if start_index is EndOfSurvey or end_index is EndOfSurvey:
            raise SurveyCreationError(
                "Cannot use EndOfSurvey as a boundary for question groups."
            )

        assert isinstance(start_index, int) and isinstance(end_index, int)

        if start_index > end_index:
            raise SurveyCreationError(
                f"Start index {start_index} is greater than end index {end_index}."
            )

        # Check for overlaps with existing groups
        for existing_group_name, (
            exist_start,
            exist_end,
        ) in survey.question_groups.items():
            assert isinstance(exist_start, int) and isinstance(exist_end, int)

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

        self._validate_group_dependencies(start_index, end_index, group_name)

        survey.question_groups[group_name] = (start_index, end_index)
        return survey

    def _validate_group_dependencies(
        self, start_index: int, end_index: int, group_name: str
    ) -> None:
        """Validate that questions in a group don't have dependencies on each other."""
        survey = self._survey
        dag = survey.dag()
        group_indices = set(range(start_index, end_index + 1))

        violations = []
        for question_idx in group_indices:
            dependencies = dag.get(question_idx, set())
            internal_deps = dependencies.intersection(group_indices)

            if internal_deps:
                question_name = survey.questions[question_idx].question_name
                dep_names = [
                    survey.questions[dep_idx].question_name for dep_idx in internal_deps
                ]
                violations.append(f"Question '{question_name}' depends on {dep_names}")

        if violations:
            error_msg = (
                f"Group '{group_name}' contains questions with internal dependencies:\n"
                + "\n".join(f"  - {violation}" for violation in violations)
                + "\n\nQuestions in a group must be able to render independently of other questions in the same group."
            )
            raise SurveyCreationError(error_msg)

    def compute_dependency_groups(
        self,
        group_name_prefix: str = "group",
        max_group_size: Optional[int] = None,
    ) -> dict:
        """Compute contiguous question groups that respect dependency constraints.

        Args:
            group_name_prefix: Prefix for group names.
            max_group_size: Maximum questions per group. None means unlimited.

        Returns:
            A dict mapping group names to (start_idx, end_idx) tuples.
        """
        survey = self._survey
        dag = survey.dag()
        grouped_questions: set = set()
        groups: dict = {}
        group_counter = 0

        for i in range(len(survey.questions)):
            if i in grouped_questions:
                continue

            current_group = [i]
            grouped_questions.add(i)

            j = i + 1
            while j < len(survey.questions):
                if j in grouped_questions:
                    j += 1
                    continue
                if max_group_size is not None and len(current_group) >= max_group_size:
                    break

                candidate_deps = dag.get(j, set())
                current_group_set = set(current_group)

                if candidate_deps.intersection(current_group_set):
                    break
                if any(
                    j in dag.get(member, set()) for member in current_group_set
                ):
                    break

                current_group.append(j)
                grouped_questions.add(j)
                j += 1

            if current_group:
                group_name = f"{group_name_prefix}_{group_counter}"
                groups[group_name] = (current_group[0], current_group[-1])
                group_counter += 1

        return groups

    def suggest_dependency_aware_groups(self, group_name_prefix: str = "group") -> dict:
        """Suggest valid question groups that respect dependency constraints."""
        return self.compute_dependency_groups(group_name_prefix)

    def create_allowable_groups(
        self, group_name_prefix: str = "group", max_group_size: Optional[int] = None
    ) -> "Survey":
        """Create and apply allowable question groups that respect dependency constraints."""
        survey = self._survey
        survey.question_groups.clear()

        groups = self.compute_dependency_groups(group_name_prefix, max_group_size)
        for group_name, (start_idx, end_idx) in groups.items():
            start_question = survey.questions[start_idx].question_name
            end_question = survey.questions[end_idx].question_name
            self.add_question_group(start_question, end_question, group_name)

        return survey
