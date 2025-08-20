"""Survey navigation functionality.

This module provides the SurveyNavigation class which handles all navigation logic
for surveys, including question flow, instruction handling, and path generation.
This separation allows for cleaner Survey class code and more focused navigation logic.
"""

from __future__ import annotations
from typing import Any, Dict, Generator, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey
    from ..questions import QuestionBase
    from ..instructions import Instruction
    from .base import EndOfSurveyParent
    from .dag import DAG


class SurveyNavigation:
    """Handles navigation logic for Survey objects.
    
    This class is responsible for determining question flow, handling instructions,
    generating survey paths, and creating DAG representations of survey structure.
    """
    
    def __init__(self, survey: "Survey"):
        """Initialize the navigation handler.
        
        Args:
            survey: The survey to handle navigation for.
        """
        self.survey = survey
    
    def next_question(
        self,
        current_question: Optional[Union[str, "QuestionBase"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Union["QuestionBase", "EndOfSurveyParent"]:
        """
        Return the next question in a survey.

        :param current_question: The current question in the survey.
        :param answers: The answers for the survey so far

        - If called with no arguments, it returns the first question in the survey.
        - If no answers are provided for a question with a rule, the next question is returned. If answers are provided, the next question is determined by the rules and the answers.
        - If the next question is the last question in the survey, an EndOfSurvey object is returned.

        >>> from edsl.surveys.survey import Survey
        >>> s = Survey.example()
        >>> nav = SurveyNavigation(s)
        >>> nav.next_question("q0", {"q0.answer": "yes"}).question_name
        'q2'
        >>> nav.next_question("q0", {"q0.answer": "no"}).question_name
        'q1'

        """
        from .base import EndOfSurvey
        from .exceptions import SurveyHasNoRulesError
        
        if current_question is None:
            return self.survey.questions[0]

        if isinstance(current_question, str):
            current_question = self.survey._get_question_by_name(current_question)

        question_index = self.survey.question_name_to_index[current_question.question_name]
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
                return self.survey.questions[next_question_object.next_q]

    def next_question_with_instructions(
        self,
        current_item: Optional[Union[str, "QuestionBase", "Instruction"]] = None,
        answers: Optional[Dict[str, Any]] = None,
    ) -> Union["QuestionBase", "Instruction", "EndOfSurveyParent"]:
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
            Union["QuestionBase", "Instruction", "EndOfSurveyParent"]: The next question, instruction, or EndOfSurvey.

        Examples:
            With a survey that has instructions:

            >>> from edsl.surveys.survey import Survey
            >>> from edsl import Instruction
            >>> s = Survey.example(include_instructions=True)
            >>> nav = SurveyNavigation(s)
            >>> # Get the first item (should be the instruction)
            >>> first_item = nav.next_question_with_instructions()
            >>> hasattr(first_item, 'text')  # Instructions have text attribute
            True

            >>> # After an instruction, get the next item
            >>> next_item = nav.next_question_with_instructions(first_item)
            >>> hasattr(next_item, 'question_name')  # Questions have question_name attribute
            True
        """
        from .base import EndOfSurvey
        from .exceptions import SurveyError, SurveyHasNoRulesError
        
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
                current_item = self.survey._instruction_names_to_instructions[current_item]
            else:
                raise SurveyError(f"Item name {current_item} not found in survey.")

        # Find the current item's position in the combined list
        try:
            current_position = combined_items.index(current_item)
        except ValueError:
            raise SurveyError("Current item not found in survey sequence.")

        # If this is an instruction, determine what comes next
        if hasattr(current_item, "text") and not hasattr(current_item, "question_name"):
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
                prev_q_index = self.survey.question_name_to_index[prev_question.question_name]
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
                        target_question = self.survey.questions[next_question_object.next_q]
                        target_position = combined_items.index(target_question)

                        # If the target is after this instruction, continue toward it
                        if target_position > current_position:
                            # Look for the next question that should be shown
                            next_position = current_position + 1
                            while next_position < target_position:
                                next_item = combined_items[next_position]
                                if hasattr(next_item, "text") and not hasattr(
                                    next_item, "question_name"
                                ):
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
                if hasattr(next_item, "text") and not hasattr(
                    next_item, "question_name"
                ):
                    return next_item
            return EndOfSurvey

        if next_question_object.next_q >= len(self.survey.questions):
            # Check if there are any instructions after the current question before ending
            next_position = current_position + 1
            if next_position < len(combined_items):
                next_item = combined_items[next_position]
                if hasattr(next_item, "text") and not hasattr(
                    next_item, "question_name"
                ):
                    return next_item
            return EndOfSurvey

        # Find the target question in the combined list
        target_question = self.survey.questions[next_question_object.next_q]
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
            if hasattr(next_item, "text") and not hasattr(next_item, "question_name"):
                return next_item
            next_position += 1

        # If we've gone through all items between current and target without finding
        # an instruction, return the target question
        return target_question

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
            Generator["QuestionBase", dict, None]: A generator that yields questions and
                receives answer dictionaries. The generator terminates when it reaches
                the end of the survey.

        Examples:
            For the example survey with conditional branching:

            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> nav = SurveyNavigation(s)
            >>> s.show_rules()
            Dataset([{'current_q': [0, 0, 1, 2]}, {'expression': ['True', "{{ q0.answer }}== 'yes'", 'True', 'True']}, {'next_q': [1, 2, 2, 3]}, {'priority': [-1, 0, -1, -1]}, {'before_rule': [False, False, False, False]}])

            Path when answering "yes" to first question:

            >>> i = nav.gen_path_through_survey()
            >>> next(i)  # Get first question
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])
            >>> i.send({"q0.answer": "yes"})  # Answer "yes" and get next question
            Question('multiple_choice', question_name = \"""q2\""", question_text = \"""Why?\""", question_options = ['**lack*** of killer bees in cafeteria', 'other'])

            Path when answering "no" to first question:

            >>> i2 = nav.gen_path_through_survey()
            >>> next(i2)  # Get first question
            Question('multiple_choice', question_name = \"""q0\""", question_text = \"""Do you like school?\""", question_options = ['yes', 'no'])
            >>> i2.send({"q0.answer": "no"})  # Answer "no" and get next question
            Question('multiple_choice', question_name = \"""q1\""", question_text = \"""Why not?\""", question_options = ['killer bees in cafeteria', 'other'])
        """
        from .base import EndOfSurvey
        
        # Initialize empty answers dictionary on the survey object
        # This is needed for compatibility with the simulator which expects survey.answers
        self.survey.answers: Dict[str, Any] = {}

        # Start with the first question
        question = self.survey.questions[0]

        # Check if the first question should be skipped based on skip rules
        if self.survey.rule_collection.skip_question_before_running(0, self.survey.answers):
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

    def dag(self, textify: bool = False) -> "DAG":
        """Return a Directed Acyclic Graph (DAG) representation of the survey flow.

        This method constructs a DAG that represents the possible paths through the survey,
        taking into account both skip logic and memory relationships. The DAG is useful
        for visualizing and analyzing the structure of the survey.

        Args:
            textify: If True, the DAG will use question names as nodes instead of indices.
                This makes the DAG more human-readable but less compact.

        Returns:
            DAG: A dictionary where keys are question indices (or names if textify=True)
                and values are sets of prerequisite questions. For example, {2: {0, 1}}
                means question 2 depends on questions 0 and 1.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> nav = SurveyNavigation(s)
            >>> d = nav.dag()
            >>> d
            {1: {0}, 2: {0}}

            With textify=True:

            >>> dag = nav.dag(textify=True)
            >>> sorted([(k, sorted(list(v))) for k, v in dag.items()])
            [('q1', ['q0']), ('q2', ['q0'])]
        """
        from .dag import ConstructDAG

        return ConstructDAG(self.survey).dag(textify)

    @classmethod
    def create_for_survey(cls, survey: "Survey") -> "SurveyNavigation":
        """Factory method to create a navigation handler for a specific survey.
        
        Args:
            survey: The survey to create a navigation handler for.
            
        Returns:
            SurveyNavigation: A new navigation handler instance for the given survey.
        """
        return cls(survey)
