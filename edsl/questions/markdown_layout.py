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
        label = labels.get(value, labels.get(str(value))) if labels else None
        row = f"{marker} {text(value)}"
        if label is not None:
            row += f" — {text(label)}"
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


def matrix(question, instruction):
    rows = question.question_items
    if isinstance(rows, str):
        rows = [rows]
    with_text = getattr(question, "items_with_text", None) or []
    items = lines(
        f"- {text(row)}" + (" (with a text response)" if row in with_text else "")
        for row in rows
    )
    return f"{instruction}\n\n{items}\n\n**Options**\n\n{options(question, '·')}"
