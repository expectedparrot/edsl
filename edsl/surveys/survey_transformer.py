"""Survey transformation functionality.

This module provides the SurveyTransformer class which handles all transformation logic
for surveys, including question renaming with comprehensive reference updates.
This separation allows for cleaner Survey class code and more focused transformation logic.
"""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey


class SurveyTransformer:
    """Handles transformation logic for Survey objects.
    
    This class is responsible for transforming surveys, particularly renaming questions
    and updating all references throughout the survey structure including rules,
    memory plans, piping references, instructions, and question groups.
    """
    
    def __init__(self, survey: "Survey"):
        """Initialize the transformer.
        
        Args:
            survey: The survey to handle transformations for.
        """
        self.survey = survey
    
    def with_renamed_question(self, old_name: str, new_name: str) -> "Survey":
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
            old_name: The current name of the question to rename
            new_name: The new name for the question

        Returns:
            Survey: A new survey with the question renamed and all references updated

        Raises:
            SurveyError: If old_name doesn't exist, new_name already exists, or new_name is invalid

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> transformer = SurveyTransformer(s)
            >>> s_renamed = transformer.with_renamed_question("q0", "school_preference")
            >>> s_renamed.get("school_preference").question_name
            'school_preference'

            >>> # Rules are also updated
            >>> s_renamed.show_rules()  # doctest: +SKIP
        """
        from .exceptions import SurveyError

        # Validate inputs
        if old_name not in self.survey.question_name_to_index:
            raise SurveyError(f"Question '{old_name}' not found in survey.")

        if new_name in self.survey.question_name_to_index:
            raise SurveyError(f"Question name '{new_name}' already exists in survey.")

        if not new_name.isidentifier():
            raise SurveyError(
                f"New question name '{new_name}' is not a valid Python identifier."
            )

        # Create a copy of the survey to work with
        new_survey = self.survey.duplicate()

        # 1. Update the question name itself
        self._update_question_name(new_survey, old_name, new_name)
        
        # 2. Update all rules that reference the old question name
        self._update_rules(new_survey, old_name, new_name)
        
        # 3. Update memory plans
        self._update_memory_plans(new_survey, old_name, new_name)
        
        # 4. Update piping references in all questions
        self._update_question_piping(new_survey, old_name, new_name)
        
        # 5. Update instructions
        self._update_instructions(new_survey, old_name, new_name)
        
        # 6. Update question groups
        self._update_question_groups(new_survey, old_name, new_name)
        
        # 7. Update pseudo indices
        self._update_pseudo_indices(new_survey, old_name, new_name)

        return new_survey

    def _update_question_name(self, survey: "Survey", old_name: str, new_name: str) -> None:
        """Update the question name itself."""
        question_index = survey.question_name_to_index[old_name]
        target_question = survey.questions[question_index]
        target_question.question_name = new_name

    def _update_rules(self, survey: "Survey", old_name: str, new_name: str) -> None:
        """Update all rules that reference the old question name."""
        for rule in survey.rule_collection:
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

            # Update the question_name_to_index mapping in the rule
            if old_name in rule.question_name_to_index:
                index = rule.question_name_to_index.pop(old_name)
                rule.question_name_to_index[new_name] = index

    def _update_memory_plans(self, survey: "Survey", old_name: str, new_name: str) -> None:
        """Update memory plans with new question name."""
        new_memory_plan_data = {}
        for focal_question, memory in survey.memory_plan.data.items():
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

        survey.memory_plan.data = new_memory_plan_data

        # Update the memory plan's internal question name list
        if hasattr(survey.memory_plan, "survey_question_names"):
            survey.memory_plan.survey_question_names = [
                new_name if q_name == old_name else q_name
                for q_name in survey.memory_plan.survey_question_names
            ]

    def _update_question_piping(self, survey: "Survey", old_name: str, new_name: str) -> None:
        """Update piping references in all questions."""
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

        for question in survey.questions:
            # Update question text
            question.question_text = update_piping_in_text(question.question_text)

            # Update question options if they exist
            if hasattr(question, "question_options") and question.question_options:
                question.question_options = [
                    update_piping_in_text(option) if isinstance(option, str) else option
                    for option in question.question_options
                ]

    def _update_instructions(self, survey: "Survey", old_name: str, new_name: str) -> None:
        """Update instructions that reference the question."""
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

        for (
            instruction_name,
            instruction,
        ) in survey._instruction_names_to_instructions.items():
            if hasattr(instruction, "text"):
                instruction.text = update_piping_in_text(instruction.text)

    def _update_question_groups(self, survey: "Survey", old_name: str, new_name: str) -> None:
        """Update question groups - only if the renamed question is a key."""
        # Question groups use indices for ranges, so we don't need to update those
        # But if someone created a group with the same name as a question, we should handle that
        if old_name in survey.question_groups:
            group_range = survey.question_groups.pop(old_name)
            survey.question_groups[new_name] = group_range

    def _update_pseudo_indices(self, survey: "Survey", old_name: str, new_name: str) -> None:
        """Update pseudo indices mapping."""
        if old_name in survey._pseudo_indices:
            pseudo_index = survey._pseudo_indices.pop(old_name)
            survey._pseudo_indices[new_name] = pseudo_index

    def validate_rename_operation(self, old_name: str, new_name: str) -> None:
        """Validate that a rename operation is valid.
        
        Args:
            old_name: The current name of the question to rename
            new_name: The new name for the question
            
        Raises:
            SurveyError: If the rename operation is invalid
        """
        from .exceptions import SurveyError

        if old_name not in self.survey.question_name_to_index:
            raise SurveyError(f"Question '{old_name}' not found in survey.")

        if new_name in self.survey.question_name_to_index:
            raise SurveyError(f"Question name '{new_name}' already exists in survey.")

        if not new_name.isidentifier():
            raise SurveyError(
                f"New question name '{new_name}' is not a valid Python identifier."
            )

    def get_question_references(self, question_name: str) -> dict:
        """Get all places where a question is referenced in the survey.
        
        Args:
            question_name: The name of the question to find references for
            
        Returns:
            dict: A dictionary describing where the question is referenced:
                - rules: List of rules that reference the question
                - memory_plans: List of memory plans that reference the question
                - question_piping: List of questions that reference this question in their text/options
                - instructions: List of instructions that reference the question
                - question_groups: List of question groups that use this name as a key
                - pseudo_indices: Whether the question has a pseudo index
        """
        references = {
            "rules": [],
            "memory_plans": [],
            "question_piping": [],
            "instructions": [],
            "question_groups": [],
            "pseudo_indices": question_name in self.survey._pseudo_indices
        }
        
        # Check rules
        for rule in self.survey.rule_collection:
            if question_name in rule.expression:
                references["rules"].append(rule.expression)
        
        # Check memory plans
        for focal_q, memory in self.survey.memory_plan.data.items():
            if focal_q == question_name:
                references["memory_plans"].append(f"focal: {focal_q}")
            if hasattr(memory, "data") and question_name in memory.data:
                references["memory_plans"].append(f"prior: {focal_q}")
        
        # Check question piping
        pattern = rf"\{{\{{\s*{re.escape(question_name)}(\.\w+)?\s*\}}\}}"
        for q in self.survey.questions:
            if re.search(pattern, q.question_text):
                references["question_piping"].append(f"text: {q.question_name}")
            if hasattr(q, "question_options") and q.question_options:
                for option in q.question_options:
                    if isinstance(option, str) and re.search(pattern, option):
                        references["question_piping"].append(f"option: {q.question_name}")
        
        # Check instructions
        for inst_name, instruction in self.survey._instruction_names_to_instructions.items():
            if hasattr(instruction, "text") and re.search(pattern, instruction.text):
                references["instructions"].append(inst_name)
        
        # Check question groups
        if question_name in self.survey.question_groups:
            references["question_groups"].append(question_name)
            
        return references

    @classmethod
    def create_for_survey(cls, survey: "Survey") -> "SurveyTransformer":
        """Factory method to create a transformer for a specific survey.
        
        Args:
            survey: The survey to create a transformer for.
            
        Returns:
            SurveyTransformer: A new transformer instance for the given survey.
        """
        return cls(survey)
