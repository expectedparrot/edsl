"""Navigation methods for Survey class.

This module contains all methods related to navigating through a survey,
including question sequencing, group navigation, and path generation.
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Dict, Generator, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from ...questions import QuestionBase
    from ..survey import Survey
    from ...instructions import Instruction

from ..navigation_markers import EndOfSurvey, EndOfSurveyParent
from ..exceptions import SurveyHasNoRulesError, SurveyError


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
        if current_question is None:
            return self.survey.questions[0]

        if isinstance(current_question, str):
            current_question = self.survey._get_question_by_name(current_question)

        question_index = self.survey.question_name_to_index[
            current_question.question_name
        ]
        # Ensure we have a non-None answers dict
        answer_dict = answers if answers is not None else {}
        next_question_object = self.survey.rule_collection.next_question(
            question_index, answer_dict
        )

        if next_question_object.num_rules_found == 0:
            raise SurveyHasNoRulesError("No rules found for this question")

        if next_question_object.next_q == EndOfSurvey:
            return EndOfSurvey
        else:
            if next_question_object.next_q >= len(self.survey.questions):
                return EndOfSurvey
            else:
                # Check if the next question has any "before rules" (skip rules)
                candidate_next_q = next_question_object.next_q

                # Keep checking for skip rules until we find a question that shouldn't be skipped
                while candidate_next_q < len(self.survey.questions):
                    # Check if this question should be skipped (has before rules that evaluate to True)
                    if self.survey.rule_collection.skip_question_before_running(
                        candidate_next_q, answer_dict
                    ):
                        # This question should be skipped, find where it should go
                        try:
                            skip_result = self.survey.rule_collection.next_question(
                                candidate_next_q, answer_dict
                            )
                            if skip_result.next_q == EndOfSurvey:
                                return EndOfSurvey
                            elif skip_result.next_q >= len(self.survey.questions):
                                return EndOfSurvey
                            else:
                                candidate_next_q = skip_result.next_q
                        except Exception:
                            # If there's an error finding where to skip to, just go to next question
                            candidate_next_q += 1
                    else:
                        # This question should not be skipped, use it
                        break

                if candidate_next_q >= len(self.survey.questions):
                    return EndOfSurvey
                else:
                    return self.survey.questions[candidate_next_q]

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
            >>> survey = survey.create_allowable_groups("section", max_group_size=2)
            >>> result = survey.next_question_group(None, {})  # Get first group
            >>> result[0]  # Group name
            'section_0'
        """
        if not self.survey.question_groups:
            return None

        # Get current question index
        if current_question is None:
            current_index = -1  # Before the first question
        else:
            if isinstance(current_question, str):
                current_question = self.survey._get_question_by_name(current_question)
            current_index = self.survey.question_name_to_index[
                current_question.question_name
            ]

        # Find which group contains the current question (if any)
        current_group_end = -1
        for group_name, (start_idx, end_idx) in self.survey.question_groups.items():
            if start_idx <= current_index <= end_idx:
                current_group_end = end_idx
                break

        # Find the next group after the current one
        next_group = None
        min_start_idx = float("inf")

        for group_name, (start_idx, end_idx) in self.survey.question_groups.items():
            if start_idx > current_group_end and start_idx < min_start_idx:
                min_start_idx = start_idx
                next_group = (group_name, start_idx, end_idx)

        if next_group is None:
            return None  # No more groups

        group_name, start_idx, end_idx = next_group

        # Collect all non-skipped questions in this group
        answers = answers or {}
        renderable_questions = []

        for question_idx in range(start_idx, end_idx + 1):
            if question_idx >= len(self.survey.questions):
                continue

            # Check if this question would be skipped
            if not self.survey.rule_collection.skip_question_before_running(
                question_idx, answers
            ):
                # This question would not be skipped, add it to renderable list
                renderable_questions.append(self.survey.questions[question_idx])

        # If we found renderable questions, return them
        if renderable_questions:
            return (group_name, renderable_questions)

        # If we get here, all questions in the group would be skipped
        # Find where the skip rules would take us and continue recursively
        for question_idx in range(start_idx, end_idx + 1):
            if question_idx >= len(self.survey.questions):
                continue

            try:
                # Use the same logic as next_question to find where skipped questions go
                skip_result = self.survey.rule_collection.next_question(
                    question_idx, answers
                )
                if skip_result.next_q == EndOfSurvey:
                    return (group_name, [EndOfSurvey])
                elif skip_result.next_q >= len(self.survey.questions):
                    return (group_name, [EndOfSurvey])
                else:
                    # The skip takes us to another question
                    # Check if that question is in a different group or past our current group
                    if skip_result.next_q > end_idx:
                        # Skip takes us past this group, recursively find the next group
                        if skip_result.next_q < len(self.survey.questions):
                            return self.next_question_group(
                                self.survey.questions[skip_result.next_q - 1], answers
                            )
                        else:
                            return (group_name, [EndOfSurvey])
            except Exception:
                continue

        # If no rules found, the group leads to the next sequential question
        next_sequential = end_idx + 1
        if next_sequential >= len(self.survey.questions):
            return (group_name, [EndOfSurvey])
        else:
            # Recursively check the next group
            return self.next_question_group(
                self.survey.questions[next_sequential - 1], answers
            )

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
            >>> survey = survey.create_allowable_groups("section", max_group_size=2)
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
            >>> survey = survey.create_allowable_groups("section", max_group_size=2)
            >>> result = survey.next_question_group_with_instructions(i, {})
            >>> result[0]  # Group name
            'section_0'
        """
        if not self.survey.question_groups:
            return None

        # Get the combined list to work with instructions
        combined_items = self.survey._recombined_questions_and_instructions()

        # Track if we started from an instruction
        was_instruction = False

        # Determine the current question index
        if current_item is None:
            current_index = -1  # Before the first question
        else:
            # Handle string input
            if isinstance(current_item, str):
                if current_item in self.survey.question_name_to_index:
                    current_item = self.survey._get_question_by_name(current_item)
                elif current_item in self.survey._instruction_names_to_instructions:
                    current_item = self.survey._instruction_names_to_instructions[
                        current_item
                    ]
                else:
                    raise SurveyError(f"Item name {current_item} not found in survey.")

            # Find the position in the combined list
            try:
                current_position = combined_items.index(current_item)
            except ValueError:
                raise SurveyError("Current item not found in survey sequence.")

            # If it's an instruction, find the next question after it
            if self._is_instruction(current_item):
                was_instruction = True
                # This is an instruction, find the next question
                for i in range(current_position + 1, len(combined_items)):
                    item = combined_items[i]
                    if hasattr(item, "question_name"):
                        current_item = item
                        break
                else:
                    # No question found after instruction
                    return None

            # Now we have a question, get its index
            current_index = self.survey.question_name_to_index[
                current_item.question_name
            ]

        # Find which group contains the current question (if any)
        current_group_end = -1
        current_group = None
        for group_name, (start_idx, end_idx) in self.survey.question_groups.items():
            if start_idx <= current_index <= end_idx:
                current_group_end = end_idx
                current_group = (group_name, start_idx, end_idx)
                break

        # If we started from an instruction and found a group containing the next question,
        # return that group directly (it's the "next" group from the instruction's perspective)
        if was_instruction and current_group is not None:
            next_group = current_group
        else:
            # Find the next group after the current one
            next_group = None
            min_start_idx = float("inf")

            for group_name, (start_idx, end_idx) in self.survey.question_groups.items():
                if start_idx > current_group_end and start_idx < min_start_idx:
                    min_start_idx = start_idx
                    next_group = (group_name, start_idx, end_idx)

            if next_group is None:
                return None  # No more groups

        group_name, start_idx, end_idx = next_group

        # Collect all non-skipped questions in this group
        answers = answers or {}
        renderable_questions = []

        for question_idx in range(start_idx, end_idx + 1):
            if question_idx >= len(self.survey.questions):
                continue

            # Check if this question would be skipped
            if not self.survey.rule_collection.skip_question_before_running(
                question_idx, answers
            ):
                # This question would not be skipped, add it to renderable list
                renderable_questions.append(self.survey.questions[question_idx])

        # If we found renderable questions, return them
        if renderable_questions:
            return (group_name, renderable_questions)

        # If we get here, all questions in the group would be skipped
        # Find where the skip rules would take us and continue recursively
        for question_idx in range(start_idx, end_idx + 1):
            if question_idx >= len(self.survey.questions):
                continue

            try:
                # Use the same logic as next_question to find where skipped questions go
                skip_result = self.survey.rule_collection.next_question(
                    question_idx, answers
                )
                if skip_result.next_q == EndOfSurvey:
                    return (group_name, [EndOfSurvey])
                elif skip_result.next_q >= len(self.survey.questions):
                    return (group_name, [EndOfSurvey])
                else:
                    # The skip takes us to another question
                    # Check if that question is in a different group or past our current group
                    if skip_result.next_q > end_idx:
                        # Skip takes us past this group, recursively find the next group
                        if skip_result.next_q < len(self.survey.questions):
                            return self.next_question_group_with_instructions(
                                self.survey.questions[skip_result.next_q - 1], answers
                            )
                        else:
                            return (group_name, [EndOfSurvey])
            except Exception:
                continue

        # If no rules found, the group leads to the next sequential question
        next_sequential = end_idx + 1
        if next_sequential >= len(self.survey.questions):
            return (group_name, [EndOfSurvey])
        else:
            # Recursively check the next group
            return self.next_question_group_with_instructions(
                self.survey.questions[next_sequential - 1], answers
            )

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

        # If no current item specified, return the first item
        if current_item is None:
            return combined_items[0]

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

        # Find the current item's position in the combined list
        try:
            current_position = combined_items.index(current_item)
        except ValueError:
            raise SurveyError("Current item not found in survey sequence.")

        # If this is an instruction, determine what comes next
        if self._is_instruction(current_item):
            # This is an instruction
            if current_position + 1 >= len(combined_items):
                return EndOfSurvey

            # Check if this instruction is between questions that have rule-based navigation
            # We need to figure out what question would have led to this instruction
            prev_question = None
            for i in range(current_position - 1, -1, -1):
                item = combined_items[i]
                if hasattr(item, "question_name"):
                    prev_question = item
                    break

            if prev_question is not None:
                # Check if there are rules from this previous question that would jump over the next sequential question
                prev_q_index = self.survey.question_name_to_index[
                    prev_question.question_name
                ]
                answer_dict = answers if answers is not None else {}

                try:
                    next_question_object = self.survey.rule_collection.next_question(
                        prev_q_index, answer_dict
                    )
                    if (
                        next_question_object.num_rules_found > 0
                        and next_question_object.next_q != EndOfSurvey
                    ):
                        # There's a rule that determined the next question
                        target_question = self.survey.questions[
                            next_question_object.next_q
                        ]
                        target_position = combined_items.index(target_question)

                        # If the target is after this instruction, continue toward it
                        if target_position > current_position:
                            # Look for the next question that should be shown
                            next_position = current_position + 1
                            while next_position < target_position:
                                next_item = combined_items[next_position]
                                if self._is_instruction(next_item):
                                    # Another instruction before target
                                    return next_item
                                next_position += 1
                            # No more instructions, return the target
                            return target_question
                except (SurveyHasNoRulesError, IndexError):
                    # No rules or error, fall back to sequential
                    pass

            # Default: return next item in sequence
            return combined_items[current_position + 1]

        # This is a question - use rule logic to determine the target next question
        if not hasattr(current_item, "question_name"):
            raise SurveyError("Current item is neither a question nor an instruction.")

        question_index = self.survey.question_name_to_index[current_item.question_name]
        answer_dict = answers if answers is not None else {}

        next_question_object = self.survey.rule_collection.next_question(
            question_index, answer_dict
        )

        if next_question_object.num_rules_found == 0:
            raise SurveyHasNoRulesError("No rules found for this question")

        # Handle end of survey case
        if next_question_object.next_q == EndOfSurvey:
            # Check if there are any instructions after the current question before ending
            next_position = current_position + 1
            if next_position < len(combined_items):
                next_item = combined_items[next_position]
                if self._is_instruction(next_item):
                    return next_item
            return EndOfSurvey

        if next_question_object.next_q >= len(self.survey.questions):
            # Check if there are any instructions after the current question before ending
            next_position = current_position + 1
            if next_position < len(combined_items):
                next_item = combined_items[next_position]
                if self._is_instruction(next_item):
                    return next_item
            return EndOfSurvey

        # Check if the next question has any "before rules" (skip rules)
        candidate_next_q = next_question_object.next_q

        # Keep checking for skip rules until we find a question that shouldn't be skipped
        while candidate_next_q < len(self.survey.questions):
            # Check if this question should be skipped (has before rules that evaluate to True)
            if self.survey.rule_collection.skip_question_before_running(
                candidate_next_q, answer_dict
            ):
                # This question should be skipped, find where it should go
                try:
                    skip_result = self.survey.rule_collection.next_question(
                        candidate_next_q, answer_dict
                    )
                    if skip_result.next_q == EndOfSurvey:
                        # Check if there are any instructions after the current question before ending
                        next_position = current_position + 1
                        if next_position < len(combined_items):
                            next_item = combined_items[next_position]
                            if self._is_instruction(next_item):
                                return next_item
                        return EndOfSurvey
                    elif skip_result.next_q >= len(self.survey.questions):
                        # Check if there are any instructions after the current question before ending
                        next_position = current_position + 1
                        if next_position < len(combined_items):
                            next_item = combined_items[next_position]
                            if self._is_instruction(next_item):
                                return next_item
                        return EndOfSurvey
                    else:
                        candidate_next_q = skip_result.next_q
                except Exception:
                    # If there's an error finding where to skip to, just go to next question
                    candidate_next_q += 1
            else:
                # This question should not be skipped, use it
                break

        if candidate_next_q >= len(self.survey.questions):
            # Check if there are any instructions after the current question before ending
            next_position = current_position + 1
            if next_position < len(combined_items):
                next_item = combined_items[next_position]
                if self._is_instruction(next_item):
                    return next_item
            return EndOfSurvey

        # Find the target question in the combined list
        target_question = self.survey.questions[candidate_next_q]
        try:
            target_position = combined_items.index(target_question)
        except ValueError:
            # This shouldn't happen, but handle gracefully
            return target_question

        # Look for any instructions between current position and target position
        # Start checking from the position after current
        next_position = current_position + 1

        # If we're already at or past the end, return EndOfSurvey
        if next_position >= len(combined_items):
            return EndOfSurvey

        # If the target question is the very next item, return it
        if next_position == target_position:
            return target_question

        # If there are items between current and target, check if any are instructions
        # that should be shown before reaching the target question
        while next_position < target_position:
            next_item = combined_items[next_position]
            # If it's an instruction, return it (caller should pass target when calling again)
            if self._is_instruction(next_item):
                return next_item
            next_position += 1

        # If we've gone through all items between current and target without finding
        # an instruction, return the target question
        return target_question

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
            >>> survey = survey.create_allowable_groups("section", max_group_size=2)
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

        # Start with the first question
        question = self.survey.questions[0]

        # Check if the first question should be skipped based on skip rules
        if self.survey.rule_collection.skip_question_before_running(
            0, self.survey.answers
        ):
            question = self.next_question(question, self.survey.answers)

        # Continue through the survey until we reach the end
        while not question == EndOfSurvey:
            # Yield the current question and wait for an answer
            answer = yield question

            # Update the accumulated answers with the new answer
            self.survey.answers.update(answer)

            # Determine the next question based on the rules and answers
            # TODO: This should also include survey and agent attributes
            question = self.next_question(question, self.survey.answers)
