"""Formatting primitives for the read-only Markdown questionnaire."""

import re
from dataclasses import dataclass
from html import escape

from ..utilities.simple_table import simple_table


@dataclass(frozen=True)
class AnswerView:
    """Display settings shared by question-specific Markdown renderers."""

    option_notes: dict[int, str] | None
    expand_options: bool


def text(value):
    """Keep authored text literal, including unresolved survey piping."""
    value = escape(str(value), quote=False)
    # Underscores inside identifiers are literal in Markdown (and in EDSL piping).
    value = re.sub(r"([\\`*\[\]~|])", r"\\\1", value)
    return re.sub(r"(?<!\w)_|_(?!\w)", r"\\_", value)


def question_text(source: str) -> str:
    """Highlight authored Jinja tags without substituting or executing them."""
    if "{{" not in source and "{%" not in source:
        return text(source)

    from jinja2 import TemplateSyntaxError
    from ..utilities.jinja import make_environment

    # The lexer normalizes line endings and can discard whitespace for trim tags.
    # Locate tokens in the original prose so that whitespace outside tags survives.
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    cursor = 0
    start = 0
    spans = []
    try:
        for _, kind, value in make_environment(keep_trailing_newline=True).lex(source):
            offset = source.index(value, cursor)
            cursor = offset + len(value)
            if kind in ("variable_begin", "block_begin", "raw_begin", "raw_end"):
                start = offset
            if kind in ("variable_end", "block_end", "raw_begin", "raw_end"):
                end = offset + len(value.rstrip())
                # Touching Markdown delimiters would otherwise become one backtick run.
                if spans and spans[-1][1] == start:
                    start = spans.pop()[0]
                spans.append((start, end))
    except TemplateSyntaxError:
        return text(source)

    output = []
    cursor = 0
    for start, end in spans:
        output.append(text(source[cursor:start]))
        tag = source[start:end].replace("\n", " ")
        longest = max((len(run) for run in re.findall(r"`+", tag)), default=0)
        fence = "`" * (longest + 1)
        output.append(f"{fence}{tag}{fence}")
        cursor = end
    output.append(text(source[cursor:]))
    return "".join(output)


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
    if isinstance(values, (str, dict)):
        result = f"Options from {option_list(values)}"
        other = getattr(question, "other_option_text", None)
        if other is not None:
            result += f"  \n{marker} {text(other)} ______"
        return result
    values = list(values)
    other = getattr(question, "other_option_text", None)
    if other is not None and other not in values:
        values.append(other)
    labels = getattr(question, "option_labels", None) or {}
    rows = []
    for index, value in enumerate(values):
        row = f"{marker} {option_text(value, labels)}"
        if other is not None and value == other:
            row += " ______"
        if notes and index in notes:
            row += f" → {notes[index]}"
        rows.append(row)
    return lines(rows)


def single_choice(question, view):
    if getattr(question, "probabilistic_response", None) is not None:
        return "Allocate probabilities totaling 1.\n\n" + options(question, "·")
    return options(question, "○", view.option_notes)


def option_list(values, labels=None):
    if isinstance(values, str):
        return text(values)
    if isinstance(values, dict):
        return ", ".join(text(v) for v in [values["from"], *values.get("add", [])])
    return ", ".join(option_text(v, labels) for v in values)


def fill_in_table(headers, values):
    """Leave one empty answer cell beside each authored item or price."""
    if not isinstance(values, list):
        return f"**{headers[0]}** — {option_list(values)}"
    rows = [(" ".join(text(value).splitlines()), "") for value in values]
    return simple_table(headers, rows, fmt="pipe")


def ordinal(number):
    if 11 <= number % 100 <= 13:
        return f"{number}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def matrix(question, instruction, marker="○"):
    """Render the response grid, leaving piped axes unresolved."""
    rows = question.question_items
    choices = question.question_options
    labels = question.option_labels
    with_text = getattr(question, "items_with_text", ())
    if not isinstance(rows, list) or not isinstance(choices, list):
        parts = [
            instruction,
            f"**Rows** — {option_list(rows)}",
            f"**Options** — {option_list(choices, labels)}",
        ]
        if with_text:
            parts.append(f"**Text response** — {option_list(with_text)}")
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
