"""Descriptors for validated Study fields.

Each descriptor enforces field-specific rules on assignment. All allow None
for lazy initialisation.
"""

import re

from edsl.study.exceptions import StudyError

# Shared slug: lowercase alphanumeric, hyphens, underscores; 1-128 chars;
# must start with a letter or digit.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")

# Name is a bit stricter: no leading digits (must start with a letter).
_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")

# Owner allows dots for org-style names like "acme.corp".
_OWNER_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")

# Topic allows slashes for hierarchical versioning like "rag/v2".
_TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9_/.-]{0,127}$")


class _BaseField:
    """Base descriptor for validated string fields on Study."""

    pattern: re.Pattern
    hint: str  # human-readable description of what's allowed

    def __set_name__(self, owner, name):
        self.field_name = name
        self.attr = f"_field_{name}"

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return getattr(obj, self.attr, None)

    def __set__(self, obj, value):
        if value is None:
            setattr(obj, self.attr, None)
            return
        if not isinstance(value, str):
            raise StudyError(
                f"{self.field_name} must be a string, got {type(value).__name__}"
            )
        if not self.pattern.match(value):
            raise StudyError(
                f"Invalid {self.field_name}: {value!r}. {self.hint}"
            )
        setattr(obj, self.attr, value)


class NameField(_BaseField):
    """Study name. Must start with a lowercase letter; allows lowercase
    alphanumeric, hyphens, underscores. 1-128 chars."""

    pattern = _NAME_RE
    hint = (
        "Must be 1-128 chars, start with a lowercase letter, "
        "then lowercase alphanumeric, hyphens, or underscores."
    )


class OwnerField(_BaseField):
    """Owner identifier (person or org). Allows lowercase alphanumeric,
    hyphens, underscores, and dots. 1-128 chars."""

    pattern = _OWNER_RE
    hint = (
        "Must be 1-128 chars, lowercase alphanumeric, hyphens, underscores, "
        "or dots, starting with a letter or digit."
    )


class ProjectField(_BaseField):
    """Project identifier. Allows lowercase alphanumeric, hyphens,
    underscores. 1-128 chars."""

    pattern = _SLUG_RE
    hint = (
        "Must be 1-128 chars, lowercase alphanumeric, hyphens, or underscores, "
        "starting with a letter or digit."
    )


class TopicField(_BaseField):
    """Topic or version tag. Allows lowercase alphanumeric, hyphens,
    underscores, dots, and forward slashes. 1-128 chars."""

    pattern = _TOPIC_RE
    hint = (
        "Must be 1-128 chars, lowercase alphanumeric, hyphens, underscores, "
        "dots, or slashes, starting with a letter or digit."
    )
