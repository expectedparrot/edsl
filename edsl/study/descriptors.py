"""Descriptors for validated Study fields."""

import re

from edsl.study.exceptions import StudyError

# Name: lowercase letter start, alphanumeric/hyphens/underscores, 1-128 chars.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")

# Alias: letters, numbers, hyphens only (matching Coop pattern), 1-128 chars.
_ALIAS_RE = re.compile(r"^[a-zA-Z0-9-]{1,128}$")


class _BaseField:
    """Base descriptor for validated string fields on Study."""

    pattern: re.Pattern
    hint: str

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
    """Study name (directory basename). Must start with a lowercase letter."""

    pattern = _NAME_RE
    hint = (
        "Must be 1-128 chars, start with a lowercase letter, "
        "then lowercase alphanumeric, hyphens, or underscores."
    )


class AliasField(_BaseField):
    """Human-readable alias. Letters, numbers, and hyphens only."""

    pattern = _ALIAS_RE
    hint = "Must be 1-128 chars, letters, numbers, or hyphens only."
