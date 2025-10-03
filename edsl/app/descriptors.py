from __future__ import annotations
from typing import Any


class InitialSurveyDescriptor:
    """Descriptor enforcing App.initial_survey invariants and type checks.

    Usage:
        class App:
            initial_survey = InitialSurveyDescriptor()
    """

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return getattr(instance, self.private_name, None)

    def __set__(self, instance: Any, value: Any) -> None:
        # Null forbidden
        if value is None:
            raise ValueError(
                "An initial_survey is required for all apps. The initial survey fully determines parameter names and EDSL object inputs."
            )
        # Basic shape check: must be Survey-like (duck-typed: iterable of questions)
        try:
            iter(value)
        except Exception:
            raise TypeError("initial_survey must be an iterable of questions")

        # Optional: presence of question-like attributes (len/iteration)
        try:
            _ = list(value)
        except Exception:
            # Still store if iterable but not materializable; fail fast to be explicit
            raise TypeError("initial_survey must support iteration over questions")

        setattr(instance, self.private_name, value)


class OutputFormattersDescriptor:
    """Descriptor that normalizes and validates App.output_formatters.

    Accepts dict[str, OutputFormatter], OutputFormatters, or None.
    Always stores an OutputFormatters instance and ensures a 'raw_results' formatter exists.
    Lists are not accepted; callers must provide a name->formatter mapping.
    """

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return getattr(instance, self.private_name, None)

    def __set__(self, instance: Any, value: Any) -> None:
        from .output_formatter import OutputFormatters

        if isinstance(value, OutputFormatters):
            ofs = value
        elif isinstance(value, dict):
            ofs = OutputFormatters(value)
        elif value is None:
            ofs = OutputFormatters([])
        elif isinstance(value, list):
            raise TypeError(
                "output_formatters must be a dict[str, OutputFormatter] or OutputFormatters"
            )
        else:
            raise TypeError("output_formatters must be a dict[str, OutputFormatter] or OutputFormatters")

        # OutputFormatters ensures 'raw_results' via _ensure_raw_results in its ctor
        setattr(instance, self.private_name, ofs)


class AttachmentFormattersDescriptor:
    """Descriptor that normalizes App.attachment_formatters to a list of ObjectFormatter.

    Accepts a single ObjectFormatter or a list; stores a list (possibly empty).
    """

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return getattr(instance, self.private_name, [])

    def __set__(self, instance: Any, value: Any) -> None:
        if value is None:
            normalized = []
        elif isinstance(value, list):
            normalized = value
        else:
            normalized = [value]
        setattr(instance, self.private_name, normalized)


class AppTypeRegistryDescriptor:
    """Descriptor managing the App subclass registry keyed by application_type.

    Provides a read-only mapping via attribute access and a .register(cls)
    helper to enforce type validity and uniqueness.
    """

    def __init__(self) -> None:
        self._map: dict[str, type[Any]] = {}

    def __get__(self, instance: Any, owner: type | None = None):
        return self._map

    def __set__(self, instance: Any, value: Any) -> None:
        raise AttributeError("Registry is read-only; use register() to add entries")

    def register(self, app_subclass: type[Any]) -> None:
        app_type = getattr(app_subclass, "application_type", None)
        if not isinstance(app_type, str) or not app_type.strip():
            raise TypeError(
                f"{app_subclass.__name__} must define a non-empty 'application_type' class attribute."
            )
        existing = self._map.get(app_type)
        if existing is not None and existing is not app_subclass:
            raise ValueError(
                f"Duplicate application_type '{app_type}' for {app_subclass.__name__}; already registered by {existing.__name__}."
            )
        self._map[app_type] = app_subclass


class ApplicationNameDescriptor:
    """Descriptor that validates and defaults App.application_name.

    - If None or falsy, defaults to the class name of the instance
    - Otherwise must be a string
    """

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return getattr(instance, self.private_name, owner.__name__ if owner is not None else None)

    def __set__(self, instance: Any, value: Any) -> None:
        if value is None or value == "":
            setattr(instance, self.private_name, instance.__class__.__name__)
            return
        if not isinstance(value, str):
            raise TypeError("application_name must be a string if provided")
        setattr(instance, self.private_name, value)


# New: Descriptor to manage App.fixed_params with normalization and survey pruning
class FixedParamsDescriptor:
    """Descriptor that normalizes and applies fixed parameters on an App instance.

    - Stores a normalized dict on the instance
    - Prunes overlapping question names from the instance.initial_survey
    """

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return getattr(instance, self.private_name, {})

    def __set__(self, instance: Any, value: Any) -> None:
        # Normalize to a dict
        if value is None:
            normalized: dict[str, Any] = {}
        elif isinstance(value, dict):
            normalized = dict(value)
        else:
            raise TypeError("fixed_params must be a dict[str, Any] if provided")

        setattr(instance, self.private_name, normalized)

        # If there are fixed params, prune overlapping questions from the initial_survey
        if normalized:
            try:
                survey_names = {q.question_name for q in instance.initial_survey}
            except Exception:
                survey_names = set()

            overlapping = [k for k in normalized.keys() if k in survey_names]
            if overlapping:
                try:
                    instance.initial_survey = instance.initial_survey.drop(*overlapping)
                except Exception:
                    raise ValueError(
                        f"Failed to prune fixed parameters from initial_survey: {sorted(overlapping)}"
                    )

