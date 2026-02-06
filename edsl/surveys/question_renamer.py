"""Module for renaming questions in surveys.

This module provides functionality for renaming questions in a survey and automatically
updating all references throughout the survey structure.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey


class QuestionRenamer:
    """Handles renaming questions and updating all references in a survey."""

    @staticmethod
    def with_renamed_question(
        survey: "Survey", old_name: str, new_name: str
    ) -> "Survey":
        """Return a new survey with a question renamed and all references updated.

        This method creates a new survey with the specified question renamed. It also
        updates all references to the old question name in:
        - Rules and expressions (both old format 'q1' and new format '{{ q1.answer }}')
        - Memory plans (focal questions and prior questions)
        - Question text piping (e.g., {{ old_name.answer }})
        - Question options that use piping
        - Instructions that reference the question
        - Question groups (keys only, not ranges since those use indices)

        Args:
            survey: The Survey instance to rename a question in.
            old_name: The current name of the question to rename
            new_name: The new name for the question

        Returns:
            Survey: A new survey with the question renamed and all references updated

        Raises:
            SurveyError: If old_name doesn't exist, new_name already exists, or new_name is invalid

        Examples:
            >>> from edsl import Survey
            >>> s = Survey.example()
            >>> s_renamed = s.with_renamed_question("q0", "school_preference")
            >>> s_renamed.get("school_preference").question_name
            'school_preference'

            >>> # Rules are also updated
            >>> s_renamed.show_rules()  # doctest: +SKIP
        """
        from .exceptions import SurveyError

        # Validate inputs
        if old_name not in survey.question_name_to_index:
            raise SurveyError(f"Question '{old_name}' not found in survey.")

        if new_name in survey.question_name_to_index:
            raise SurveyError(f"Question name '{new_name}' already exists in survey.")

        if not new_name.isidentifier():
            raise SurveyError(
                f"New question name '{new_name}' is not a valid Python identifier."
            )

        # Create a copy of the survey to work with
        new_survey = survey.duplicate()

        # 1. Update the question name itself
        question_index = new_survey.question_name_to_index[old_name]
        target_question = new_survey.questions[question_index]
        target_question.question_name = new_name

        # 2. Update all rules that reference the old question name
        for rule in new_survey.rule_collection:
            # Update expressions - handle both old format (q1) and new format ({{ q1.answer }})
            # Old format: 'q1' or 'q1.answer' (standalone references)
            rule.expression = re.sub(
                rf"\b{re.escape(old_name)}\.answer\b",
                f"{new_name}.answer",
                rule.expression,
            )
            rule.expression = re.sub(
                rf"\b{re.escape(old_name)}\b(?!\.)", new_name, rule.expression
            )

            # New format: {{ q1.answer }} (Jinja2 template references)
            rule.expression = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\.answer\s*\}}\}}",
                f"{{{{ {new_name}.answer }}}}",
                rule.expression,
            )
            rule.expression = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\s*\}}\}}",
                f"{{{{ {new_name} }}}}",
                rule.expression,
            )

        # Update the shared question_name_to_index mapping (all rules share this)
        shared_map = new_survey.rule_collection.question_name_to_index
        if old_name in shared_map:
            index = shared_map.pop(old_name)
            shared_map[new_name] = index

        # 3. Update memory plans
        new_memory_plan_data = {}
        for focal_question, memory in new_survey.memory_plan.data.items():
            # Update focal question name if it matches
            new_focal = new_name if focal_question == old_name else focal_question

            # Update prior questions list (Memory class stores questions in data attribute)
            if hasattr(memory, "data"):
                new_prior_questions = [
                    new_name if prior_q == old_name else prior_q
                    for prior_q in memory.data
                ]
                # Create new memory object with updated prior questions
                from .memory.memory import Memory

                new_memory = Memory(prior_questions=new_prior_questions)
                new_memory_plan_data[new_focal] = new_memory
            else:
                new_memory_plan_data[new_focal] = memory

        new_survey.memory_plan.data = new_memory_plan_data

        # Update the memory plan's internal question name list
        if hasattr(new_survey.memory_plan, "survey_question_names"):
            new_survey.memory_plan.survey_question_names = [
                new_name if q_name == old_name else q_name
                for q_name in new_survey.memory_plan.survey_question_names
            ]

        # 4. Update piping references in all questions
        def update_piping_in_text(text: str) -> str:
            """Update piping references in text strings."""
            # Handle {{ old_name.answer }} format
            text = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\.answer\s*\}}\}}",
                f"{{{{ {new_name}.answer }}}}",
                text,
            )
            # Handle {{ old_name }} format
            text = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\s*\}}\}}",
                f"{{{{ {new_name} }}}}",
                text,
            )
            return text

        for question in new_survey.questions:
            # Update question text
            question.question_text = update_piping_in_text(question.question_text)

            # Update question options if they exist
            if hasattr(question, "question_options") and question.question_options:
                question.question_options = [
                    update_piping_in_text(option) if isinstance(option, str) else option
                    for option in question.question_options
                ]

        # 5. Update instructions
        for (
            instruction_name,
            instruction,
        ) in new_survey._instruction_names_to_instructions.items():
            if hasattr(instruction, "text"):
                instruction.text = update_piping_in_text(instruction.text)

        # 6. Update question groups - only if the renamed question is a key (not just in ranges)
        # Question groups use indices for ranges, so we don't need to update those
        # But if someone created a group with the same name as a question, we should handle that
        if old_name in new_survey.question_groups:
            group_range = new_survey.question_groups.pop(old_name)
            new_survey.question_groups[new_name] = group_range

        # 7. Update pseudo indices
        if old_name in new_survey._pseudo_indices:
            pseudo_index = new_survey._pseudo_indices.pop(old_name)
            new_survey._pseudo_indices[new_name] = pseudo_index

        return new_survey
