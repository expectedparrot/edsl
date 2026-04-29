"""Module for generating rich formatted survey representations.

This module provides functionality for creating visually formatted string
representations of Survey objects using the Rich library.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey


def _highlight_jinja(text: str) -> "Text":
    """Return a ``rich.text.Text`` with ``{{ ... }}`` spans styled bold blue."""
    from rich.text import Text

    styled = Text()
    parts = re.split(r"(\{\{.*?\}\})", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("{{") and part.endswith("}}"):
            styled.append(part.replace(" ", "\u00a0"), style="bold blue")
        else:
            styled.append(part)
    return styled


def _question_details(question) -> str:
    """Build a compact details string for any question type.

    Covers options, numerical bounds, selection constraints, option labels,
    weight, list-item limits, and include_comment.
    """
    parts: list[str] = []

    if hasattr(question, "question_options") and question.question_options:
        parts.append(", ".join(str(o) for o in question.question_options))

    if hasattr(question, "option_labels") and question.option_labels:
        labels = ", ".join(
            f"{k}: {v}" for k, v in question.option_labels.items()
        )
        parts.append(f"labels: {{{labels}}}")

    bounds: list[str] = []
    if hasattr(question, "min_value") and question.min_value is not None:
        bounds.append(f"min={question.min_value}")
    if hasattr(question, "max_value") and question.max_value is not None:
        bounds.append(f"max={question.max_value}")
    if bounds:
        parts.append(", ".join(bounds))

    sel: list[str] = []
    if hasattr(question, "min_selections") and question.min_selections is not None:
        sel.append(f"min_sel={question.min_selections}")
    if hasattr(question, "max_selections") and question.max_selections is not None:
        sel.append(f"max_sel={question.max_selections}")
    if hasattr(question, "num_selections") and question.num_selections is not None:
        sel.append(f"num_sel={question.num_selections}")
    if sel:
        parts.append(", ".join(sel))

    if hasattr(question, "max_list_items") and question.max_list_items is not None:
        parts.append(f"max_items={question.max_list_items}")

    if hasattr(question, "weight") and question.weight is not None:
        parts.append(f"weight={question.weight}")

    data_dict = question.to_dict(add_edsl_version=False)
    if "include_comment" in data_dict and not data_dict["include_comment"]:
        parts.append("no comment")

    return "\n".join(parts)


def generate_summary_repr(
    survey: "Survey", max_text_preview: int = 60, max_items: int = 500
) -> str:
    """Generate a summary representation of the Survey as a Rich table.

    Args:
        survey: The Survey object to represent
        max_text_preview: (unused, kept for API compat)
        max_items: Maximum number of question rows before truncating

    Returns:
        A rich-formatted string representation of the survey
    """
    from ..utilities.summary_table import ColumnDef, render_summary_table
    from .base import EndOfSurvey

    num_questions = len(survey.questions)

    rules_by_q: dict[int, list] = defaultdict(list)
    for rule in survey.rule_collection.non_default_rules:
        rules_by_q[rule.current_q].append(rule)

    captions: list[str] = []
    if survey._instruction_names_to_instructions:
        n = len(survey._instruction_names_to_instructions)
        captions.append(f"{n} instruction{'s' if n != 1 else ''}")
    if survey.question_groups:
        captions.append(f"groups: {list(survey.question_groups.keys())}")
    if survey.questions_to_randomize:
        captions.append(f"randomized: {survey.questions_to_randomize}")

    title = f"Survey ({num_questions} question{'s' if num_questions != 1 else ''})"

    columns = [
        ColumnDef("#", style="dim", no_wrap=True, justify="right"),
        ColumnDef("Name", style="bold green", no_wrap=True),
        ColumnDef("Type", style="dim", no_wrap=True),
        ColumnDef("Question Text"),
        ColumnDef("Details", style="dim"),
    ]
    if rules_by_q:
        columns.append(ColumnDef("Skip Logic", style="bold yellow"))

    rows: list[tuple] = []
    for idx, question in enumerate(survey.questions):
        q_type = question.to_dict().get("question_type", "")
        q_text = _highlight_jinja(question.question_text)
        details = _question_details(question)

        row: list = [str(idx), question.question_name, q_type, q_text, details]

        if rules_by_q:
            if idx in rules_by_q:
                lines = []
                for rule in rules_by_q[idx]:
                    if rule.next_q == EndOfSurvey or rule.next_q >= num_questions:
                        target = "END"
                    else:
                        target = survey.questions[rule.next_q].question_name
                    lines.append(f"if {rule.expression} → {target}")
                row.append("\n".join(lines))
            else:
                row.append("")

        rows.append(tuple(row))

    return render_summary_table(
        title=title,
        columns=columns,
        rows=rows,
        caption=", ".join(captions) if captions else None,
        max_rows=max_items,
    )
