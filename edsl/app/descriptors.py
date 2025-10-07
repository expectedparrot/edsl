from __future__ import annotations
from typing import Any
import re


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
    """Descriptor that validates App.application_name as a valid Python identifier.
    
    Used for the 'alias' in deployment; must be a valid Python identifier.
    """

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        stored = getattr(instance, self.private_name, None)
        if stored is None and owner is not None:
            # Default: use class name converted to identifier
            return self._to_identifier(owner.__name__)
        return stored

    def __set__(self, instance: Any, value: Any) -> None:
        from .exceptions import ApplicationNameError

        if value is None or value == "":
            # Default to class name
            value = self._to_identifier(instance.__class__.__name__)
        elif not isinstance(value, str):
            raise ApplicationNameError("application_name must be a string")
        
        # Validate it's a valid Python identifier
        if not value.isidentifier():
            raise ApplicationNameError(
                f"application_name '{value}' must be a valid Python identifier"
            )
        
        setattr(instance, self.private_name, value)

    @staticmethod
    def _to_identifier(name: str) -> str:
        """Convert a name to a valid Python identifier.
        
        Examples:
            "PersonaGenerator" -> "personagenerator"
            "My App" -> "my_app"
        """
        # Convert to lowercase
        identifier = name.lower()
        # Replace spaces and hyphens with underscores
        identifier = re.sub(r'[\s\-]+', '_', identifier)
        # Remove any non-alphanumeric characters except underscores
        identifier = re.sub(r'[^\w]', '', identifier)
        # Ensure it doesn't start with a digit
        if identifier and identifier[0].isdigit():
            identifier = f"app_{identifier}"
        # Ensure it's not empty
        if not identifier:
            identifier = "app"
        return identifier


class DisplayNameDescriptor:
    """Descriptor for App.display_name - human-readable name (no constraints)."""

    MAX_LENGTH = 100

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return getattr(instance, self.private_name, "Unnamed App")

    def __set__(self, instance: Any, value: Any) -> None:
        from .exceptions import ApplicationNameError

        if value is None or value == "":
            value = "Unnamed App"
        elif not isinstance(value, str):
            raise ApplicationNameError("display_name must be a string")
        
        if len(value) > self.MAX_LENGTH:
            raise ApplicationNameError(
                f"display_name '{value}' exceeds maximum length of {self.MAX_LENGTH} characters"
            )
        
        setattr(instance, self.private_name, value.strip())


class ShortDescriptionDescriptor:
    """Descriptor for App.short_description - one sentence description."""

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return getattr(instance, self.private_name, "No description provided.")

    def __set__(self, instance: Any, value: Any) -> None:
        from .exceptions import DescriptionError

        if value is None or value == "":
            value = "No description provided."
        elif not isinstance(value, str):
            raise DescriptionError("short_description must be a string")
        
        # Ensure it ends with a period
        value = value.strip()
        if not value.endswith('.'):
            value = f"{value}."

        # Validate it's a single sentence (no multiple periods except at end)
        sentence_count = value[:-1].count('.') + 1
        if sentence_count > 1:
            raise DescriptionError(
                f"short_description must be a single sentence. Found {sentence_count} sentences: '{value}'"
            )
        
        setattr(instance, self.private_name, value)


class LongDescriptionDescriptor:
    """Descriptor for App.long_description - longer description."""

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        return getattr(instance, self.private_name, "No description provided.")

    def __set__(self, instance: Any, value: Any) -> None:
        from .exceptions import DescriptionError

        if value is None or value == "":
            value = "No description provided."
        elif not isinstance(value, str):
            raise DescriptionError("long_description must be a string")
        
        setattr(instance, self.private_name, value.strip())


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

