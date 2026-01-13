"""Module for renaming questions in surveys.

This module provides functionality for renaming questions in a survey and automatically
updating all references throughout the survey structure.
"""

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..survey import Survey


class QuestionRenamer:
    """Handles renaming questions and updating all references in a survey."""

    @staticmethod
    def compute_renamed_state(
        survey: "Survey", old_name: str, new_name: str
    ) -> tuple[tuple[dict[str, Any], ...], tuple[tuple[str, Any], ...]]:
        """Compute the new state for a survey with a question renamed.

        Returns:
            Tuple of (new_entries, meta_updates) suitable for ReplaceEntriesAndMetaEvent
        """
        from ..exceptions import SurveyError
        from ..memory.memory import Memory

        # Validate inputs
        if old_name not in survey.question_name_to_index:
            raise SurveyError(f"Question '{old_name}' not found in survey.")

        if new_name in survey.question_name_to_index:
            raise SurveyError(f"Question name '{new_name}' already exists in survey.")

        if not new_name.isidentifier():
            raise SurveyError(
                f"New question name '{new_name}' is not a valid Python identifier."
            )

        # Helper function for updating piping references in text
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

        # 1. Build new entries (questions) with the renamed question
        question_index = survey.question_name_to_index[old_name]
        new_entries = []
        for i, entry in enumerate(survey.store.entries):
            entry_copy = dict(entry)
            if i == question_index:
                # Rename this question
                entry_copy["question_name"] = new_name
            # Update question_text piping references
            if "question_text" in entry_copy:
                entry_copy["question_text"] = update_piping_in_text(
                    entry_copy["question_text"]
                )
            # Update question_options if they exist
            if "question_options" in entry_copy and entry_copy["question_options"]:
                entry_copy["question_options"] = [
                    update_piping_in_text(opt) if isinstance(opt, str) else opt
                    for opt in entry_copy["question_options"]
                ]
            new_entries.append(entry_copy)

        # 2. Build new rule_collection with updated references
        rule_collection = survey.rule_collection
        new_rules = []
        for rule in rule_collection:
            rule_dict = rule.to_dict(add_edsl_version=False)
            # Update expression
            expression = rule_dict.get("expression", "")
            # Old format: 'q1.answer' (standalone references)
            expression = re.sub(
                rf"\b{re.escape(old_name)}\.answer\b",
                f"{new_name}.answer",
                expression,
            )
            expression = re.sub(
                rf"\b{re.escape(old_name)}\b(?!\.)", new_name, expression
            )
            # New format: {{ q1.answer }} (Jinja2 template references)
            expression = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\.answer\s*\}}\}}",
                f"{{{{ {new_name}.answer }}}}",
                expression,
            )
            expression = re.sub(
                rf"\{{\{{\s*{re.escape(old_name)}\s*\}}\}}",
                f"{{{{ {new_name} }}}}",
                expression,
            )
            rule_dict["expression"] = expression
            # Update question_name_to_index
            q_name_to_idx = dict(rule_dict.get("question_name_to_index", {}))
            if old_name in q_name_to_idx:
                idx = q_name_to_idx.pop(old_name)
                q_name_to_idx[new_name] = idx
            rule_dict["question_name_to_index"] = q_name_to_idx
            new_rules.append(rule_dict)

        new_rule_collection = {
            "rules": new_rules,
            "num_questions": rule_collection.num_questions,
        }

        # 3. Build new memory_plan with updated references
        memory_plan = survey.memory_plan
        new_memory_plan_data = {}
        for focal_question, memory in memory_plan.data.items():
            # Update focal question name if it matches
            new_focal = new_name if focal_question == old_name else focal_question

            # Update prior questions list
            if hasattr(memory, "data"):
                new_prior_questions = [
                    new_name if prior_q == old_name else prior_q
                    for prior_q in memory.data
                ]
                new_memory_plan_data[new_focal] = {
                    "prior_questions": new_prior_questions
                }
            else:
                # Keep as-is
                new_memory_plan_data[new_focal] = (
                    memory.to_dict() if hasattr(memory, "to_dict") else {}
                )

        # Update survey_question_names
        old_question_names = getattr(memory_plan, "survey_question_names", [])
        new_question_names = [
            new_name if q_name == old_name else q_name for q_name in old_question_names
        ]

        old_question_texts = getattr(memory_plan, "question_texts", [])

        new_memory_plan = {
            "survey_question_names": new_question_names,
            "survey_question_texts": list(old_question_texts),
            "data": new_memory_plan_data,
        }

        # 4. Update pseudo_indices
        pseudo_indices = dict(survey._pseudo_indices)
        if old_name in pseudo_indices:
            idx_value = pseudo_indices.pop(old_name)
            pseudo_indices[new_name] = idx_value

        # 5. Update question_groups
        question_groups = dict(survey.question_groups)
        if old_name in question_groups:
            group_range = question_groups.pop(old_name)
            question_groups[new_name] = group_range

        # 6. Update instructions
        instructions = survey._instruction_names_to_instructions
        new_instructions = {}
        for inst_name, inst in instructions.items():
            inst_dict = (
                inst.to_dict(add_edsl_version=False)
                if hasattr(inst, "to_dict")
                else dict(inst)
            )
            if "text" in inst_dict:
                inst_dict["text"] = update_piping_in_text(inst_dict["text"])
            new_instructions[inst_name] = inst_dict

        # Build meta updates
        meta_updates = (
            ("rule_collection", new_rule_collection),
            ("memory_plan", new_memory_plan),
            ("pseudo_indices", pseudo_indices),
            ("question_groups", question_groups),
            ("instruction_names_to_instructions", new_instructions),
            # Preserve other meta fields
            ("questions_to_randomize", list(survey.questions_to_randomize)),
            ("name", survey.name),
        )

        return (tuple(new_entries), meta_updates)

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
        from edsl.store import ReplaceEntriesAndMetaEvent

        # Compute the new state
        new_entries, meta_updates = QuestionRenamer.compute_renamed_state(
            survey, old_name, new_name
        )

        # Create the event
        event = ReplaceEntriesAndMetaEvent(
            entries=new_entries, meta_updates=meta_updates
        )

        # Apply the event via the Survey's event system
        # We need to mimic what the @event decorator does
        survey._ensure_git_init()

        # Apply event to a copy of the store
        from edsl.store import Store

        new_store = Store.from_dict(survey.store.to_dict())
        from edsl.store.events import apply_event

        apply_event(event, new_store)

        # Create new instance from the modified state
        new_survey = survey._from_state(new_store.to_dict())

        # Stage for git
        if new_survey._git is not None:
            new_survey._git.stage(event)

        return new_survey
