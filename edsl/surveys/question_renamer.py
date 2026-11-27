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
            >>> from edsl import Survey  # doctest: +SKIP
            >>> s = Survey.example()  # doctest: +SKIP
            >>> s_renamed = s.with_renamed_question("q0", "school_preference")  # doctest: +SKIP
            >>> s_renamed.get("school_preference").question_name  # doctest: +SKIP
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

        if (
            new_name in survey.question_groups
            or new_name in survey._instruction_names_to_instructions
        ):
            raise SurveyError(
                f"Name {new_name!r} already belongs to a group or instruction."
            )

        if not new_name.isidentifier():
            raise SurveyError(
                f"New question name '{new_name}' is not a valid Python identifier."
            )

        # Work on serialized data so construction rebuilds rule and name caches.
        from copy import deepcopy

        data = deepcopy(survey.to_dict())

        def rename(name):
            return new_name if name == old_name else name

        def rename_keys(mapping):
            return {rename(name): value for name, value in mapping.items()}

        def rename_names(names):
            return [rename(name) for name in names]

        # Match literals first. An answer label or an attribute with the same
        # spelling as the question is data, not a reference to the question.
        tokens = re.compile(
            r"""'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|[.|]\s*\w+|\b\w+\b"""
        )

        def expression(text):
            return tokens.sub(lambda match: rename(match.group()), text)

        def piping(text):
            return re.sub(
                r"\{\{.*?\}\}|\{%.*?%\}",
                lambda m: expression(m.group()),
                text,
                flags=re.S,
            )

        def update_templates(value):
            if isinstance(value, str):
                return piping(value)
            if isinstance(value, list):
                return [update_templates(item) for item in value]
            if isinstance(value, dict):
                return {key: update_templates(item) for key, item in value.items()}
            return value

        items = data["questions"] = update_templates(data["questions"])
        for item in items:
            if item.get("question_name") == old_name:
                item["question_name"] = new_name

        data["question_groups"] = rename_keys(data["question_groups"])
        collection = data["rule_collection"]
        collection["question_name_to_index"] = rename_keys(
            collection["question_name_to_index"]
        )
        for rule in collection["rules"]:
            # Templates can also appear within quoted strings in rule expressions.
            rule["expression"] = expression(piping(rule["expression"]))
            rule["question_name_to_index"] = rename_keys(rule["question_name_to_index"])

        memory = data["memory_plan"]
        memory["survey_question_names"] = rename_names(memory["survey_question_names"])
        memory["survey_question_texts"] = [
            item["question_text"] for item in items if "question_name" in item
        ]
        memory["data"] = rename_keys(memory["data"])
        for entry in memory["data"].values():
            entry["prior_questions"] = rename_names(entry["prior_questions"])

        if "questions_to_randomize" in data:
            data["questions_to_randomize"] = rename_names(
                data["questions_to_randomize"]
            )
        if "options_to_pin" in data:
            data["options_to_pin"] = rename_keys(data["options_to_pin"])
        if "scale_direction_randomization" in data:
            policy = data["scale_direction_randomization"]
            policy["questions"] = rename_names(policy["questions"])
        if "question_sampling" in data:
            policy = data["question_sampling"]
            for key in ("eligible_questions", "required_questions"):
                policy[key] = rename_names(policy[key])
        for block in data.get("question_order", {}).get("blocks", []):
            block["questions"] = rename_names(block["questions"])

        def rename_answer_refs(value):
            if isinstance(value, list):
                return [rename_answer_refs(item) for item in value]
            if isinstance(value, dict):
                if set(value) == {"$answer"}:
                    return {"$answer": rename(value["$answer"])}
                return {key: rename_answer_refs(item) for key, item in value.items()}
            return value

        for stage, anchors in data.get("state_steps", {}).items():
            data["state_steps"][stage] = rename_answer_refs(rename_keys(anchors))
        return type(survey).from_dict(data)
