"""Module for adding follow-up questions to surveys.

This module provides functionality for automatically creating conditional follow-up questions
based on multiple choice or checkbox question options.
"""

from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ...questions import QuestionBase
    from ..survey import Survey


class FollowupQuestionAdder:
    """Handles adding follow-up questions to a survey based on question options."""

    @staticmethod
    def add_followup_questions(
        survey: "Survey",
        reference_question: Union["QuestionBase", str],
        followup_template: "QuestionBase",
        answer_template_var: str = "answer",
    ) -> "Survey":
        """Add follow-up questions for each option in a reference question with skip logic.

        This method provides syntactical sugar for creating conditional follow-up questions
        based on a multiple choice or checkbox question's options. For each option in the
        reference question, it creates a follow-up question and adds the appropriate skip
        logic to show it only when that option is selected.

        The method automatically:
        1. Creates one follow-up question per option in the reference question
        2. Substitutes the template variable with each option value
        3. Adds skip logic so each follow-up only appears for its corresponding option
        4. Maintains proper survey flow after all follow-ups

        Args:
            survey: The Survey instance to add follow-up questions to.
            reference_question: The question with options (must be MultipleChoice or CheckBox type).
                Can be specified as a QuestionBase object or its question_name string.
            followup_template: A template question to use for follow-ups. The question text
                can include `{{ <ref_name>.<template_var> }}` which will be replaced with
                each option value. For example, `{{ restaurants.answer }}` will be replaced
                with "Italian", "Chinese", etc.
            answer_template_var: The template variable name to replace in the followup text
                (default: "answer"). This is the part after the dot in the template syntax.

        Returns:
            Survey: The modified survey with follow-up questions added.

        Raises:
            ValueError: If the reference question doesn't have options (not MultipleChoice
                or CheckBox type).

        Examples:
            Basic usage with multiple choice question:

            >>> from edsl import QuestionMultipleChoice, QuestionFreeText, Survey
            >>> q_rest = QuestionMultipleChoice(
            ...     question_name="restaurants",
            ...     question_text="Which restaurant do you prefer?",
            ...     question_options=["Italian", "Chinese", "Mexican"]
            ... )
            >>> q_followup = QuestionFreeText(
            ...     question_name="why_restaurant",
            ...     question_text="Why do you like {{ restaurants.answer }}?"
            ... )
            >>> s = Survey([q_rest]).add_followup_questions("restaurants", q_followup)
            >>> len(s.questions)
            4

            The survey will now have 4 questions:
            - restaurants (the original multiple choice)
            - why_restaurant_restaurants_0 (shown only if "Italian" selected)
            - why_restaurant_restaurants_1 (shown only if "Chinese" selected)
            - why_restaurant_restaurants_2 (shown only if "Mexican" selected)

            Each follow-up will have the option value substituted in its text:
            - "Why do you like Italian?"
            - "Why do you like Chinese?"
            - "Why do you like Mexican?"
        """
        # Get the reference question
        if isinstance(reference_question, str):
            ref_q = survey._get_question_by_name(reference_question)
            ref_name = reference_question
        else:
            ref_q = reference_question
            ref_name = ref_q.question_name

        # Check if the question has options
        if not hasattr(ref_q, "question_options"):
            raise ValueError(
                f"Reference question '{ref_name}' must have options "
                f"(e.g., QuestionMultipleChoice or QuestionCheckBox)"
            )

        options = ref_q.question_options

        # Find the index where we should insert follow-up questions (right after reference)
        ref_index = survey._get_question_index(ref_name)
        insert_index = ref_index + 1

        # Create a modified survey
        modified_survey = survey

        # Store the followup question names
        followup_names = []

        # For each option, create a follow-up question
        for i, option in enumerate(options):
            # Clone the followup template
            followup_dict = followup_template.to_dict()

            # Remove edsl_version if present to avoid issues
            followup_dict.pop("edsl_version", None)

            # Create unique name for this followup
            followup_name = f"{followup_template.question_name}_{ref_name}_{i}"
            followup_dict["question_name"] = followup_name
            followup_names.append(followup_name)

            # Replace the template variable in question_text
            template_var = f"{{{{ {ref_name}.{answer_template_var} }}}}"
            if template_var in followup_dict.get("question_text", ""):
                followup_dict["question_text"] = followup_dict["question_text"].replace(
                    template_var, str(option)
                )

            # Create the new question from the modified dict
            new_question = followup_template.__class__.from_dict(followup_dict)

            # Add the question to the survey at the right position
            modified_survey = modified_survey.add_question(
                new_question, index=insert_index + i
            )

        # IMPORTANT: After inserting questions, the default rules got updated incorrectly.
        # The rule from ref_question now points past all the followups to what used to be
        # the next question. We need to fix this so it points to the first followup.
        # Also, the default rules between followup questions point to wrong places.
        #
        # Get the rule collection (we need to modify and save it back)
        rc = modified_survey.rule_collection

        # Fix the default rule from the reference question to point to first followup
        first_followup_index = insert_index
        for rule in rc:
            if (
                rule.current_q == ref_index
                and rule.expression == "True"
                and rule.priority == -1
            ):
                # This is the default rule from the reference question
                # Update it to point to the first followup
                rule.next_q = first_followup_index
                break

        # Fix the default rules between followup questions
        # Each followup should point to the next followup, except the last one
        for i in range(len(options)):
            current_followup_index = insert_index + i
            next_index = insert_index + i + 1

            for rule in rc:
                if (
                    rule.current_q == current_followup_index
                    and rule.expression == "True"
                    and rule.priority == -1
                ):
                    # This is a default rule for a followup question
                    # Update it to point to the next question in sequence
                    rule.next_q = next_index
                    break

        # Save the modified rule collection back to the survey
        modified_survey.rule_collection = rc

        # Now add skip logic for each follow-up
        # Each follow-up should be skipped if the answer doesn't match its option
        for i, option in enumerate(options):
            followup_name = f"{followup_template.question_name}_{ref_name}_{i}"

            # Determine the next question to jump to if this followup should be skipped
            if i < len(options) - 1:
                # Skip to the next followup
                next_followup = f"{followup_template.question_name}_{ref_name}_{i + 1}"
            else:
                # This is the last followup, skip to whatever comes after all followups
                # which is the question at insert_index + len(options)
                next_index = insert_index + len(options)
                if next_index < len(modified_survey.questions):
                    next_followup = modified_survey.questions[next_index]
                else:
                    # No more questions, skip to end of survey
                    from edsl.surveys.navigation_markers import EndOfSurvey

                    next_followup = EndOfSurvey

            # Add before_rule: if answer != this option, skip this followup
            skip_condition = f"{{{{ {ref_name}.answer }}}} != '{option}'"
            modified_survey = modified_survey.add_rule(
                followup_name, skip_condition, next_followup, before_rule=True
            )

        return modified_survey
