"""Module for generating rich formatted survey representations.

This module provides functionality for creating visually formatted string
representations of Survey objects using the Rich library.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey


def generate_summary_repr(survey: "Survey", max_text_preview: int = 60, max_items: int = 50) -> str:
    """Generate a summary representation of the Survey with Rich formatting.

    Args:
        survey: The Survey object to represent
        max_text_preview: Maximum characters to show for question text previews
        max_items: Maximum number of items to show in lists before truncating

    Returns:
        A rich-formatted string representation of the survey
    """
    from rich.console import Console
    from rich.text import Text
    import io
    from .base import EndOfSurvey
    from edsl.config import RICH_STYLES

    # Build the Rich text
    output = Text()
    output.append("Survey(\n", style=RICH_STYLES["primary"])
    output.append(f"    num_questions={len(survey.questions)},\n", style=RICH_STYLES["default"])

    # Show if survey has non-default rules (skip logic)
    has_rules = len(survey.rule_collection.non_default_rules) > 0
    if has_rules:
        output.append(
            f"    has_skip_logic=True ({len(survey.rule_collection.non_default_rules)} rules),\n",
            style=RICH_STYLES["secondary"],
        )

    # Show if survey has instructions
    has_instructions = len(survey._instruction_names_to_instructions) > 0
    if has_instructions:
        output.append(
            f"    has_instructions=True ({len(survey._instruction_names_to_instructions)} instructions),\n",
            style=RICH_STYLES["secondary"],
        )

    # Show question groups if any
    if survey.question_groups:
        output.append(
            f"    question_groups={list(survey.question_groups.keys())},\n",
            style=RICH_STYLES["secondary"],
        )

    # Show questions to randomize if any
    if survey.questions_to_randomize:
        output.append(
            f"    questions_to_randomize={survey.questions_to_randomize},\n",
            style=RICH_STYLES["key"],
        )

    # Show question information using each question's _summary_repr
    if survey.questions:
        output.append("    questions: [\n", style=RICH_STYLES["default"])

        # Build a mapping of question index to skip logic rules
        skip_rules_by_question = {}
        for rule in survey.rule_collection.non_default_rules:
            if rule.current_q not in skip_rules_by_question:
                skip_rules_by_question[rule.current_q] = []
            skip_rules_by_question[rule.current_q].append(rule)

        # Show up to max_items questions using their own _summary_repr
        for idx, question in enumerate(survey.questions[:max_items]):
            # Get the question's own summary representation
            question_repr = (
                question._summary_repr()
                if hasattr(question, "_summary_repr")
                else repr(question)
            )

            # Add indentation to each line of the question's repr
            indented_repr = "        " + question_repr.replace("\n", "\n        ")
            output.append(indented_repr, style=RICH_STYLES["default"])

            # Add skip logic indicator if this question has skip rules
            if idx in skip_rules_by_question:
                rules = skip_rules_by_question[idx]
                for rule in rules:
                    output.append("\n            ", style=RICH_STYLES["default"])
                    if rule.before_rule:
                        output.append("↳ skip_rule: ", style=f"{RICH_STYLES['secondary']} italic")
                    else:
                        output.append("↳ jump_rule: ", style=f"{RICH_STYLES['secondary']} italic")

                    # Format the rule description
                    next_q_name = "EndOfSurvey"
                    if rule.next_q != EndOfSurvey and rule.next_q < len(survey.questions):
                        next_q_name = survey.questions[rule.next_q].question_name

                    rule_desc = f"if {rule.expression} → {next_q_name}"
                    output.append(rule_desc, style=RICH_STYLES["secondary"])

            output.append(",\n", style=RICH_STYLES["default"])

        if len(survey.questions) > max_items:
            output.append(
                f"        ... ({len(survey.questions) - max_items} more)\n",
                style=RICH_STYLES["dim"],
            )

        output.append("    ]\n", style=RICH_STYLES["default"])

    output.append(")", style=RICH_STYLES["primary"])

    # Render to string
    console = Console(file=io.StringIO(), force_terminal=True, width=120)
    console.print(output, end="")
    return console.file.getvalue()
