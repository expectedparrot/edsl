"""Navigation methods for Survey class.

This module contains all methods related to navigating through a survey,
including question sequencing, group navigation, and path generation.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from .survey import Survey
    from ..instructions import Instruction

from .base import EndOfSurvey, EndOfSurveyParent
from .exceptions import SurveyError


class SurveyNavigator:
    """Handles navigation logic for Survey objects.

    This class manages all navigation-related operations for surveys, including
    determining the next question based on rules and answers, handling question
    groups, and generating paths through surveys.
    """

    def __init__(self, survey: "Survey"):
        """Initialize the navigator with a survey.

        Args:
            survey: The Survey object to navigate through.
        """
        self.survey = survey

    def _is_instruction(self, item: Any) -> bool:
        """Check if an item is an Instruction.

        Args:
            item: The item to check (can be a QuestionBase, Instruction, or other object).

        Returns:
            True if the item is an Instruction, False otherwise.

        Examples:
            >>> from edsl import Survey, Instruction
            >>> from edsl.questions import QuestionFreeText
            >>> s = Survey([Instruction(name="intro", text="Hello"), QuestionFreeText.example()])
            >>> s._navigator._is_instruction(s.questions[0])
            False
            >>> s._navigator._is_instruction(s._instruction_names_to_instructions["intro"])
            True
        """
        return hasattr(item, "text") and not hasattr(item, "question_name")

    def next_question(
        self,
        current_question: Optional[Union[str, "QuestionBase"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Union["QuestionBase", EndOfSurveyParent]:
        """
        Return the next question in a survey.

        :param current_question: The current question in the survey.
        :param answers: The answers for the survey so far

        - If called with no arguments, it returns the first question in the survey.
        - If no answers are provided for a question with a rule, the next question is returned. If answers are provided, the next question is determined by the rules and the answers.
        - If the next question is the last question in the survey, an EndOfSurvey object is returned.

        >>> from edsl import Survey
        >>> s = Survey.example()
        >>> s.next_question("q0", {"q0.answer": "yes"}).question_name
        'q2'
        >>> s.next_question("q0", {"q0.answer": "no"}).question_name
        'q1'

        """
        answer_dict = answers if answers is not None else {}
        if not self.survey.questions:
            return EndOfSurvey
        candidate = 0
        if current_question is not None:
            if isinstance(current_question, str):
                current_question = self.survey._get_question_by_name(current_question)
            index = self.survey.question_name_to_index[current_question.question_name]
            candidate = self.survey.rule_collection.next_question(
                index, answer_dict
            ).next_q

        index = self._next_renderable_question_index(candidate, answer_dict)
        return EndOfSurvey if index is EndOfSurvey else self.survey.questions[index]

    def next_question_group(
        self,
        current_question: Optional[Union[str, "QuestionBase"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tuple[str, List[Union["QuestionBase", EndOfSurveyParent]]]]:
        """
        Find the next question group and return its name along with all renderable questions in it.

        This method handles the complexity that even if questions within a group have no internal
        dependencies, some questions in the group might be skipped due to rules based on answers
        from previous groups. It returns all non-skipped questions in the group so the UI can
        render them all at once.

        Args:
            current_question: The current question in the survey. If None, finds the first group.
            answers: The answers for the survey so far, used to evaluate skip rules.

        Returns:
            A tuple of (group_name, list_of_renderable_questions) or None if no more groups.
            The list contains all questions in the group that would not be skipped, in order.
            If the entire group is skipped, returns (group_name, [EndOfSurvey]).

        Examples:
            >>> from edsl import Survey
            >>> from edsl.questions import QuestionMultipleChoice
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50", "50+"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female", "Other"])
            >>> survey = Survey([q1, q2])
            >>> _ = survey.create_allowable_groups("section", max_group_size=2)
            >>> result = survey.next_question_group(None, {})  # Get first group
            >>> result[0]  # Group name
            'section_0'
        """
        if not self.survey.question_groups:
            return None

        index = 0
        if current_question is not None:
            if isinstance(current_question, str):
                current_question = self.survey._get_question_by_name(current_question)
            current_index = self.survey.question_name_to_index[
                current_question.question_name
            ]
            group = self._group_containing_question_index(current_index)
            if group is not None:
                # A jump in the remainder of the current page may land partway
                # through a later page.
                _, index = self._questions_in_range(
                    current_index + 1, group[2], answers or {}
                )
                if index is EndOfSurvey:
                    return group[0], [EndOfSurvey]
        return self._questions_from_index(index, answers or {})

    def _questions_from_index(self, index: int, answers: Dict[str, Any]):
        """Return the first reachable group's questions, including mid-group landings."""
        for name, start, end in self._ordered_question_groups():
            if index > end:
                continue
            visible, index = self._questions_in_range(max(index, start), end, answers)
            if visible:
                return name, visible
            if index is EndOfSurvey or index >= len(self.survey.questions):
                return name, [EndOfSurvey]
        return None

    def _questions_in_range(self, start: int, end: int, answers: Dict[str, Any]):
        """Collect visible questions on a page and retain its outbound skip destination."""
        visible = []
        index = start
        while index <= end and index < len(self.survey.questions):
            destination = self.survey.rule_collection.before_rule_destination(
                index, answers
            )
            if destination is EndOfSurvey:
                return visible, EndOfSurvey
            if destination is None:
                visible.append(self.survey.questions[index])
                index += 1
            else:
                index = destination
        return visible, index

    def _ordered_question_groups(self) -> List[Tuple[str, int, int]]:
        """Return question groups ordered by their start index."""
        return sorted(
            (
                (group_name, start_idx, end_idx)
                for group_name, (
                    start_idx,
                    end_idx,
                ) in self.survey.question_groups.items()
            ),
            key=lambda group: group[1],
        )

    def _group_containing_question_index(
        self, question_index: int
    ) -> Optional[Tuple[str, int, int]]:
        """Return the ordered group tuple containing a question index."""
        for group_name, start_idx, end_idx in self._ordered_question_groups():
            if start_idx <= question_index <= end_idx:
                return group_name, start_idx, end_idx
        return None

    def _group_by_name(self, group_name: str) -> Optional[Tuple[str, int, int]]:
        """Return the ordered group tuple with a given name."""
        for candidate_name, start_idx, end_idx in self._ordered_question_groups():
            if candidate_name == group_name:
                return candidate_name, start_idx, end_idx
        return None

    def _previous_group_end(self, start_idx: int) -> int:
        """Return the end index of the group immediately before start_idx."""
        previous_end = -1
        for _, group_start, group_end in self._ordered_question_groups():
            if group_start < start_idx and group_end > previous_end:
                previous_end = group_end
        return previous_end

    def _next_renderable_question_index(
        self, question_index: Union[int, EndOfSurveyParent], answers: Dict[str, Any]
    ) -> Union[int, EndOfSurveyParent]:
        """Follow matching before-rules until a question can be asked."""
        while question_index is not EndOfSurvey and question_index < len(
            self.survey.questions
        ):
            destination = self.survey.rule_collection.before_rule_destination(
                question_index, answers
            )
            if destination is None:
                return question_index
            question_index = destination
        return EndOfSurvey

    def _renderable_group_items(
        self,
        group_name: str,
        start_idx: int,
        end_idx: int,
        answers: Dict[str, Any],
        target_idx: Optional[int] = None,
        include_instructions: bool = True,
    ) -> List[Union["QuestionBase", "Instruction"]]:
        """Collect renderable questions and related instructions for a group."""
        question_start = start_idx if target_idx is None else max(start_idx, target_idx)
        questions, _ = self._questions_in_range(question_start, end_idx, answers)
        renderable_question_names = {q.question_name for q in questions}

        combined_items = self.survey._recombined_questions_and_instructions()
        previous_group_end = self._previous_group_end(start_idx)
        group_items: List[Union["QuestionBase", "Instruction"]] = []

        for item in combined_items:
            item_name = item.name
            if item_name is None:
                continue

            pseudo_index = self.survey._pseudo_indices.get(item_name)
            if pseudo_index is None:
                continue

            if hasattr(item, "question_name"):
                if item.question_name in renderable_question_names:
                    group_items.append(item)
                continue

            if not include_instructions or not self._is_instruction(item):
                continue

            if start_idx == 0 and pseudo_index < question_start:
                group_items.append(item)
            elif previous_group_end < pseudo_index < question_start:
                group_items.append(item)
            elif question_start <= pseudo_index <= end_idx:
                group_items.append(item)

        group_items.sort(
            key=lambda item: self.survey._pseudo_indices.get(item.name, float("inf"))
        )
        return group_items

    def next_group(
        self,
        current_group: Optional[str] = None,
        answers: Optional[Dict[str, Any]] = None,
        include_instructions: bool = True,
    ) -> Dict[str, Any]:
        """Return the next renderable page when presenting a survey by group."""
        answer_dict = answers if answers is not None else {}

        if not self.survey.questions:
            return {
                "group_name": None,
                "items": [EndOfSurvey],
                "question_names": [],
                "is_end": True,
            }

        if not self.survey.question_groups:
            next_item = self.next_question_with_instructions(None, answer_dict)
            if next_item == EndOfSurvey:
                return {
                    "group_name": None,
                    "items": [EndOfSurvey],
                    "question_names": [],
                    "is_end": True,
                }
            question_names = (
                [next_item.question_name] if hasattr(next_item, "question_name") else []
            )
            return {
                "group_name": None,
                "items": [next_item],
                "question_names": question_names,
                "is_end": False,
            }

        if current_group is None:
            target_idx = self._next_renderable_question_index(0, answer_dict)
        else:
            current_group_tuple = self._group_by_name(current_group)
            if current_group_tuple is None:
                raise SurveyError(f"Group name {current_group!r} not found in survey.")

            _, start_idx, end_idx = current_group_tuple
            current_questions, outbound = self._questions_in_range(
                start_idx, end_idx, answer_dict
            )
            if current_questions:
                last_question = current_questions[-1]
                next_question = self.next_question(last_question, answer_dict)
                if next_question == EndOfSurvey:
                    target_idx = EndOfSurvey
                else:
                    target_idx = self.survey.question_name_to_index[
                        next_question.question_name
                    ]
            else:
                target_idx = self._next_renderable_question_index(outbound, answer_dict)

        while target_idx != EndOfSurvey:
            assert isinstance(target_idx, int)
            group_tuple = self._group_containing_question_index(target_idx)
            if group_tuple is None:
                target_idx = self._next_renderable_question_index(
                    target_idx + 1, answer_dict
                )
                continue

            group_name, start_idx, end_idx = group_tuple
            items = self._renderable_group_items(
                group_name,
                start_idx,
                end_idx,
                answer_dict,
                target_idx=target_idx,
                include_instructions=include_instructions,
            )
            question_names = [
                item.question_name for item in items if hasattr(item, "question_name")
            ]

            if question_names:
                return {
                    "group_name": group_name,
                    "items": items,
                    "question_names": question_names,
                    "is_end": False,
                }

            target_idx = self._next_renderable_question_index(end_idx + 1, answer_dict)

        return {
            "group_name": None,
            "items": [EndOfSurvey],
            "question_names": [],
            "is_end": True,
        }

    def get_question_group(self, question: Union[str, "QuestionBase"]) -> Optional[str]:
        """
        Get the group name that contains the specified question.

        Args:
            question: The question to find the group for, either as a question name string
                     or a QuestionBase object.

        Returns:
            The name of the group containing the question, or None if the question
            is not in any group.

        Examples:
            >>> from edsl import Survey
            >>> from edsl.questions import QuestionMultipleChoice
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50", "50+"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female", "Other"])
            >>> q3 = QuestionMultipleChoice(question_name="q3", question_text="Income?", question_options=["Low", "Medium", "High"])
            >>> q4 = QuestionMultipleChoice(question_name="q4", question_text="Location?", question_options=["Urban", "Suburban", "Rural"])
            >>> survey = Survey([q1, q2, q3, q4])
            >>> _ = survey.create_allowable_groups("section", max_group_size=2)
            >>> survey.get_question_group("q1")
            'section_0'
            >>> survey.get_question_group("q3")
            'section_1'
        """
        if isinstance(question, str):
            question_name = question
        else:
            question_name = question.question_name

        try:
            question_index = self.survey.question_name_to_index[question_name]
        except KeyError:
            return None

        # Find which group contains this question
        for group_name, (start_idx, end_idx) in self.survey.question_groups.items():
            if start_idx <= question_index <= end_idx:
                return group_name

        return None

    def next_question_group_with_instructions(
        self,
        current_item: Optional[Union[str, "QuestionBase", "Instruction"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Optional[Tuple[str, List[Union["QuestionBase", EndOfSurveyParent]]]]:
        """
        Find the next question group, handling both questions and instructions.

        This method extends next_question_group to handle instructions as current items.
        If the current item is an instruction, it finds the next question group that comes
        after that instruction in the survey sequence.

        Args:
            current_item: The current question or instruction in the survey. If None, finds the first group.
            answers: The answers for the survey so far, used to evaluate skip rules.

        Returns:
            A tuple of (group_name, list_of_renderable_questions) or None if no more groups.
            The list contains all questions in the group that would not be skipped, in order.
            If the entire group is skipped, returns (group_name, [EndOfSurvey]).

        Examples:
            >>> from edsl import Survey, Instruction
            >>> from edsl.questions import QuestionMultipleChoice
            >>> i = Instruction(name="intro", text="Please answer.")
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female"])
            >>> survey = Survey([i, q1, q2])
            >>> _ = survey.create_allowable_groups("section", max_group_size=2)
            >>> result = survey.next_question_group_with_instructions(i, {})
            >>> result[0]  # Group name
            'section_0'
        """
        if not self.survey.question_groups:
            return None

        # Get the combined list to work with instructions
        combined_items = self.survey._recombined_questions_and_instructions()

        if current_item is None:
            return self.next_question_group(None, answers)
        if isinstance(current_item, str):
            if current_item in self.survey.question_name_to_index:
                return self.next_question_group(current_item, answers)
            if current_item not in self.survey._instruction_names_to_instructions:
                raise SurveyError(f"Item name {current_item} not found in survey.")
            current_item = self.survey._instruction_names_to_instructions[current_item]

        try:
            position = combined_items.index(current_item)
        except ValueError:
            raise SurveyError("Current item not found in survey sequence.")

        if not self._is_instruction(current_item):
            return self.next_question_group(current_item, answers)
        for item in combined_items[position + 1 :]:
            if hasattr(item, "question_name"):
                index = self.survey.question_name_to_index[item.question_name]
                group = self._group_containing_question_index(index)
                if group is not None:
                    return self._questions_from_index(group[1], answers or {})
                return self.next_question_group(item, answers)
        return None

    def next_question_with_instructions(
        self,
        current_item: Optional[Union[str, "QuestionBase", "Instruction"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Union["QuestionBase", "Instruction", EndOfSurveyParent]:
        """
        Return the next question or instruction in a survey, including instructions in sequence.

        This method extends the functionality of next_question to also handle Instructions
        that are interspersed between questions. It follows the proper sequence based on
        pseudo indices and respects survey rules for question flow.

        :param current_item: The current question or instruction in the survey.
        :param answers: The answers for the survey so far

        - If called with no arguments, it returns the first item (question or instruction) in the survey.
        - For instructions, it returns the next item in sequence since instructions don't have answers.
        - For questions, it uses the rule logic to determine the next question, then returns any
          instructions that come before that target question, or the target question itself.
        - If the next item would be past the end of the survey, an EndOfSurvey object is returned.

        Returns:
            Union["QuestionBase", "Instruction", EndOfSurveyParent]: The next question, instruction, or EndOfSurvey.

        Examples:
            With a survey that has instructions:

            >>> from edsl import Survey, Instruction
            >>> s = Survey.example(include_instructions=True)
            >>> # Get the first item (should be the instruction)
            >>> first_item = s.next_question_with_instructions()
            >>> hasattr(first_item, 'text')  # Instructions have text attribute
            True

            >>> # After an instruction, get the next item
            >>> next_item = s.next_question_with_instructions(first_item)
            >>> hasattr(next_item, 'question_name')  # Questions have question_name attribute
            True
        """
        # Get the combined and ordered list of questions and instructions
        combined_items = self.survey._recombined_questions_and_instructions()

        if not combined_items:
            return EndOfSurvey

        if current_item is None:
            if self._is_instruction(combined_items[0]):
                return combined_items[0]
            current_position = -1

        # Handle string input by finding the corresponding item
        if isinstance(current_item, str):
            # Look for it in questions first
            if current_item in self.survey.question_name_to_index:
                current_item = self.survey._get_question_by_name(current_item)
            # Then look for it in instructions
            elif current_item in self.survey._instruction_names_to_instructions:
                current_item = self.survey._instruction_names_to_instructions[
                    current_item
                ]
            else:
                raise SurveyError(f"Item name {current_item} not found in survey.")

        if current_item is not None:
            try:
                current_position = combined_items.index(current_item)
            except ValueError:
                raise SurveyError("Current item not found in survey sequence.")

        if self._is_instruction(current_item):
            # An instruction can sit inside a jump. Its immediate predecessor
            # may have been skipped. Resume from the most recent answered question.
            previous = None
            for item in reversed(combined_items[:current_position]):
                if hasattr(
                    item, "question_name"
                ) and f"{item.question_name}.answer" in (answers or {}):
                    previous = item
                    break
            target = self.next_question(previous, answers)
            position = self.survey._pseudo_indices[current_item.name]
            while (
                target is not EndOfSurvey
                and self.survey._pseudo_indices[target.name] < position
            ):
                target = self.next_question(target, answers)
        else:
            target = self.next_question(current_item, answers)

        # Show intervening instructions on the way to a question. At the end
        # only directly following instructions belong to the current sequence.
        if target is EndOfSurvey:
            following = combined_items[current_position + 1 : current_position + 2]
        else:
            following = combined_items[
                current_position + 1 : combined_items.index(target)
            ]
        for item in following:
            if self._is_instruction(item):
                return item
        return target

    def next_questions_with_instructions(
        self,
        current_item: Optional[Union[str, "QuestionBase", "Instruction"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> List[Union["QuestionBase", "Instruction", EndOfSurveyParent]]:
        """
        Return a list of questions and instructions from the next question group, or the next question/instruction.

        This method first checks for the next question group. If a group exists, it returns all
        questions and instructions (in order) that fall within that group's range. If no group
        exists, it falls back to returning the next single question or instruction.

        Args:
            current_item: The current question or instruction in the survey. If None, finds the first group or item.
            answers: The answers for the survey so far, used to evaluate skip rules.

        Returns:
            A list of QuestionBase and/or Instruction objects from the next question group,
            or a list containing the next single question/instruction if no group exists.
            The list will contain [EndOfSurvey] if the survey has ended.

        Examples:
            >>> from edsl import Survey, Instruction
            >>> from edsl.questions import QuestionMultipleChoice
            >>> q1 = QuestionMultipleChoice(question_name="q1", question_text="Age?", question_options=["18-30", "31-50", "50+"])
            >>> q2 = QuestionMultipleChoice(question_name="q2", question_text="Gender?", question_options=["Male", "Female", "Other"])
            >>> i = Instruction(name="intro", text="Please answer the following questions.")
            >>> survey = Survey([i, q1, q2])
            >>> _ = survey.create_allowable_groups("section", max_group_size=2)
            >>> result = survey.next_questions_with_instructions(None, {})  # Get first group
            >>> len(result)  # Should include instruction and questions from the group
            3
        """
        # First, try to get the next question group (handles instructions natively)
        group_result = self.next_question_group_with_instructions(current_item, answers)

        # If we found a group, collect all questions and instructions in that group
        if group_result is not None:
            group_name, group_questions = group_result

            # Check if the group is EndOfSurvey
            if group_questions and group_questions[0] == EndOfSurvey:
                return [EndOfSurvey]

            # Get the group's start and end indices
            start_idx = None
            end_idx = None
            for g_name, (g_start, g_end) in self.survey.question_groups.items():
                if g_name == group_name:
                    start_idx = g_start
                    end_idx = g_end
                    break

            if start_idx is not None and end_idx is not None:
                # Find the previous group's end index (or -1 if this is the first group)
                prev_group_end = -1
                for g_name, (g_start, g_end) in self.survey.question_groups.items():
                    if g_end < start_idx and g_end > prev_group_end:
                        prev_group_end = g_end

                # Get all items (questions and instructions) that fall within this group's range
                combined_items = self.survey._recombined_questions_and_instructions()
                group_items = []

                for item in combined_items:
                    # Get the pseudo index for this item using the name property
                    # (questions have .name property that returns question_name, instructions have .name attribute)
                    item_name = item.name
                    if item_name is None:
                        continue

                    pseudo_index = self.survey._pseudo_indices.get(item_name)
                    if pseudo_index is None:
                        continue

                    # Check if this item falls within the group's range
                    # Questions have integer pseudo indices, instructions have fractional ones
                    if start_idx <= pseudo_index <= end_idx:
                        group_items.append(item)
                    elif (
                        start_idx == 0
                        and pseudo_index < 0
                        and self._is_instruction(item)
                    ):
                        # Include instructions that come before the first question in the first group
                        group_items.append(item)
                    elif (
                        self._is_instruction(item)
                        and prev_group_end < pseudo_index < start_idx
                    ):
                        # Include instructions that fall between the previous group and this group
                        group_items.append(item)

                # Sort by pseudo index to maintain order
                group_items.sort(
                    key=lambda x: self.survey._pseudo_indices.get(x.name, float("inf"))
                )

                if group_items:
                    return group_items

            # If we couldn't find items by pseudo index, return the questions from the group
            # (this shouldn't normally happen, but is a fallback)
            return list(group_questions) if group_questions else []

        # No group found, fall back to next_question_with_instructions
        next_item = self.next_question_with_instructions(current_item, answers)
        if next_item == EndOfSurvey:
            return [EndOfSurvey]
        return [next_item]

    def gen_path_through_survey(self) -> Generator["QuestionBase", dict, None]:
        """Generate a coroutine that navigates through the survey based on answers.

        This method creates a Python generator that implements the survey flow logic.
        It yields questions and receives answers, handling the branching logic based
        on the rules defined in the survey. This generator is the core mechanism used
        by the Interview process to administer surveys.

        The generator follows these steps:
        1. Yields the first question (or skips it if skip rules apply)
        2. Receives an answer dictionary from the caller via .send()
        3. Updates the accumulated answers
        4. Determines the next question based on the survey rules
        5. Yields the next question
        6. Repeats steps 2-5 until the end of survey is reached

        Returns:
            Generator[QuestionBase, dict, None]: A generator that yields questions and
                receives answer dictionaries. The generator terminates when it reaches
                the end of the survey.

        Examples:
            For the example survey with conditional branching:

            >>> from edsl import Survey
            >>> s = Survey.example()
            >>> s.show_rules()
            Dataset([{'current_q': [0, 0, 1, 2]}, {'expression': ['True', "{{ q0.answer }}== 'yes'", 'True', 'True']}, {'next_q': [1, 2, 2, 3]}, {'priority': [-1, 0, -1, -1]}, {'before_rule': [False, False, False, False]}])

            Path when answering "yes" to first question:

            >>> i = s.gen_path_through_survey()
            >>> next(i)  # Get first question
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])
            >>> i.send({"q0.answer": "yes"})  # Answer "yes" and get next question
            Question('multiple_choice', question_name = \"""q2\""", question_text = \"""Why?\""", question_options = ['**lack*** of killer bees in cafeteria', 'other'])

            Path when answering "no" to first question:

            >>> i2 = s.gen_path_through_survey()
            >>> next(i2)  # Get first question
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])
            >>> i2.send({"q0.answer": "no"})  # Answer "no" and get next question
            Question('multiple_choice', question_name = \"""q1\""", question_text = \"""Why not?\""", question_options = ['killer bees in cafeteria', 'other'])
        """
        # Initialize empty answers dictionary
        self.survey.answers: Dict[str, Any] = {}

        question = self.next_question(answers=self.survey.answers)

        # Continue through the survey until we reach the end
        while not question == EndOfSurvey:
            # Yield the current question and wait for an answer
            answer = yield question

            # Update the accumulated answers with the new answer
            self.survey.answers.update(answer)

            # Determine the next question based on the rules and answers
            # TODO: This should also include survey and agent attributes
            question = self.next_question(question, self.survey.answers)
