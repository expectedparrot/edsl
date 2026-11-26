"""Formatting primitives for the read-only Markdown questionnaire."""

import re
from html import escape


def text(value):
    """Keep authored text literal, including unresolved survey piping."""
    value = escape(str(value), quote=False)
    # Underscores inside identifiers are literal in Markdown (and in EDSL piping).
    value = re.sub(r"([\\`*\[\]~|])", r"\\\1", value)
    return re.sub(r"(?<!\w)_|_(?!\w)", r"\\_", value)


def lines(values):
    """Use hard breaks so terminal and browser Markdown keep one item per line."""
    return "  \n".join(values)


def bounds(lower, upper):
    if lower is not None and upper is not None:
        return f" ({text(lower)} to {text(upper)})"
    if lower is not None:
        return f" (at least {text(lower)})"
    if upper is not None:
        return f" (at most {text(upper)})"
    return ""


def select_count(lower, upper):
    if lower == upper and lower is not None:
        return f"Select exactly {lower}."
    if lower and upper is not None:
        return f"Select {lower} to {upper}."
    if lower:
        return f"Select at least {lower}."
    if upper is not None:
        return f"Select up to {upper}."
    return "Select all that apply."


def option_text(value, labels):
    result = text(value)
    if labels:
        label = labels.get(value, labels.get(str(value)))
        if label is not None:
            result += f" — {text(label)}"
    return result


def options(question, marker, notes=None):
    values = question.question_options
    if isinstance(values, str):
        return f"Options from {text(values)}"
    values = list(values)
    other = getattr(question, "other_option_text", None)
    if other is not None and other not in values:
        values.append(other)
    labels = getattr(question, "option_labels", None) or {}
    rows = []
    for index, value in enumerate(values):
        row = f"{marker} {option_text(value, labels)}"
        if other is not None and value == other:
            row += " (write in)"
        if notes and index in notes:
            row += f" → {notes[index]}"
        rows.append(row)
    return lines(rows)


def single_choice(question, notes):
    if getattr(question, "probabilistic_response", None) is not None:
        return "Allocate probabilities totaling 1.\n\n" + options(question, "·")
    return options(question, "○", notes)


def _axis_description(values, labels=None):
    if isinstance(values, str):
        return text(values)
    if isinstance(values, dict):
        return ", ".join(text(v) for v in [values["from"], *values.get("add", [])])
    return ", ".join(option_text(v, labels) for v in values)


def matrix(question, instruction, marker="○"):
    """Render the response grid, leaving piped axes unresolved."""
    from ..utilities.simple_table import simple_table

    rows = question.question_items
    choices = question.question_options
    labels = question.option_labels
    with_text = getattr(question, "items_with_text", ())
    if not isinstance(rows, list) or not isinstance(choices, list):
        parts = [
            instruction,
            f"**Rows** — {_axis_description(rows)}",
            f"**Options** — {_axis_description(choices, labels)}",
        ]
        if with_text:
            parts.append(f"**Text response** — {_axis_description(with_text)}")
        return "\n\n".join(parts)

    # Keep a cell on one line and give even one-character headings a Markdown delimiter.
    headers = [
        "Item",
        *(" ".join(option_text(v, labels).splitlines()).ljust(3) for v in choices),
    ]
    if with_text:
        headers.append("Additional text")
    cells = []
    for row in rows:
        cells_for_row = [" ".join(text(row).splitlines())] + [marker] * len(choices)
        if with_text:
            cells_for_row.append("Free text" if row in with_text else "")
        cells.append(cells_for_row)
    return instruction + "\n\n" + simple_table(headers, cells, fmt="pipe")
