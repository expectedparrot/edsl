"""Checked authoring-time interpolation for EDSL question stems.

``Stem`` turns a Python format-style template and typed references into the
ordinary Jinja string consumed by existing EDSL question renderers.
"""

from __future__ import annotations

import json
import string
from dataclasses import dataclass
from typing import Any

from edsl.sharedstate.refs import AnswerRef, ContextRef


class StemError(ValueError):
    """Raised when a Stem cannot be checked or lowered safely."""


@dataclass(frozen=True)
class Literal:
    """An explicit scalar literal to interpolate into a Stem."""

    value: str | int | float | bool


def literal(value: str | int | float | bool) -> Literal:
    """Mark a scalar value for explicit literal interpolation."""
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError("Stem literals must be strings, numbers, or booleans")
    return Literal(value)


def _ref_expression(value: Any) -> str:
    """Return the Jinja expression for a supported reference."""
    if isinstance(value, AnswerRef):
        if not value.question_name.isidentifier():
            raise StemError(f"Invalid question name {value.question_name!r}")
        return f"{value.question_name}.answer"
    if isinstance(value, ContextRef):
        if not value.path:
            raise StemError("Use a specific current context field, such as current.agent.name")
        root, *parts = value.path
        if root not in {"agent", "scenario", "run", "interview_id"}:
            raise StemError(f"Unsupported current context root {root!r}")
        if not all(part.isidentifier() for part in parts):
            raise StemError(f"Invalid current context path {'.'.join(value.path)!r}")
        return ".".join((root, *parts))
    raise TypeError(
        f"Unsupported Stem binding {type(value).__name__}; use a question answer, "
        "current context reference, or literal(value)"
    )


class CompiledStem(str):
    """A lowered Stem, represented as a normal Jinja-compatible string."""


class Stem(str):
    """Compose question text from checked references.

    Bind each ``{placeholder}`` to a question answer (``q.answer``), a context
    field (``current.agent.name``), or an explicit scalar via ``literal``.
    Literal braces use Python formatting escapes, ``{{`` and ``}}``.

    Example::

        Stem("Hi {name}, you selected {choice}.",
             name=current.agent.name, choice=q_choice.answer)
    """

    def __new__(cls, template: str, **bindings: Any):
        if not isinstance(template, str):
            raise TypeError("Stem template must be a string")
        parsed = list(string.Formatter().parse(template))
        names = [field for _, field, _, _ in parsed if field is not None]
        if any(not name or not name.isidentifier() for name in names):
            raise StemError("Stem placeholders must be simple identifiers")
        missing = sorted(set(names) - set(bindings))
        unused = sorted(set(bindings) - set(names))
        if missing or unused:
            details = []
            if missing:
                details.append(f"missing bindings: {', '.join(missing)}")
            if unused:
                details.append(f"unused bindings: {', '.join(unused)}")
            raise StemError("Stem placeholders and bindings must match (" + "; ".join(details) + ")")

        pieces = []
        for text, field, format_spec, conversion in parsed:
            if format_spec or conversion:
                raise StemError("Stem placeholders do not support conversions or format specs")
            if text:
                # JSON string quoting is valid Jinja string syntax and prevents
                # braces or template delimiters in authored text becoming code.
                pieces.append("{{ " + json.dumps(text, ensure_ascii=False) + " }}")
            if field is not None:
                value = bindings[field]
                if isinstance(value, Literal):
                    expression = json.dumps(value.value, ensure_ascii=False)
                else:
                    expression = _ref_expression(value)
                pieces.append("{{ " + expression + " }}")
        result = str.__new__(cls, "".join(pieces))
        result._stem_question_reads = tuple(
            sorted(
                {
                    value.question_name
                    for value in bindings.values()
                    if isinstance(value, AnswerRef)
                }
            )
        )
        return result

    def compile(self) -> CompiledStem:
        """Return the ordinary Jinja string for a question's ``question_text``."""
        compiled = CompiledStem(self)
        compiled._stem_question_reads = self._stem_question_reads
        return compiled

    def __str__(self) -> str:
        return str.__str__(self)


# Avoid importing question classes here; the object is intentionally a small
# authoring helper and ``str`` keeps it compatible with all question types.
