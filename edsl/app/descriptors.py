from __future__ import annotations
from typing import Any, TypedDict
import re


# TypedDict definitions
class ApplicationName(TypedDict):
    """TypedDict for application name with pretty name and alias.

    Attributes:
        name: Human-readable pretty name (e.g., "Persona Generator").
        alias: Valid Python identifier for the app (e.g., "persona_generator").
    """
    name: str
    alias: str


class Description(TypedDict):
    """TypedDict for application description with short and long forms.

    Attributes:
        short: Single sentence description ending with a period.
        long: Longer paragraph description of the application.
    """
    short: str
    long: str


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
    """Descriptor that validates and normalizes App.application_name.

    Accepts either:
    - A string (auto-generates alias from the string)
    - An ApplicationName TypedDict with 'name' and 'alias' keys
    - None (defaults to class name)

    Validates:
    - Name length does not exceed MAX_NAME_LENGTH
    - Alias is a valid Python identifier

    Stores an ApplicationName TypedDict internally.
    """

    MAX_NAME_LENGTH = 100  # Maximum character length for pretty name

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        stored = getattr(instance, self.private_name, None)
        if stored is None and owner is not None:
            # Default: use class name
            default_name = owner.__name__
            return ApplicationName(name=default_name, alias=self._name_to_alias(default_name))
        return stored

    def __set__(self, instance: Any, value: Any) -> None:
        from .exceptions import ApplicationNameError

        # None or empty string: use class name as default
        if value is None or value == "":
            class_name = instance.__class__.__name__
            normalized = ApplicationName(
                name=class_name,
                alias=self._name_to_alias(class_name)
            )
        # String: convert to ApplicationName TypedDict
        elif isinstance(value, str):
            if len(value) > self.MAX_NAME_LENGTH:
                raise ApplicationNameError(
                    f"Application name '{value}' exceeds maximum length of {self.MAX_NAME_LENGTH} characters"
                )
            normalized = ApplicationName(
                name=value,
                alias=self._name_to_alias(value)
            )
        # Dict: validate as ApplicationName
        elif isinstance(value, dict):
            if "name" not in value or "alias" not in value:
                raise ApplicationNameError(
                    "application_name dict must contain 'name' and 'alias' keys"
                )
            name = value["name"]
            alias = value["alias"]

            if not isinstance(name, str) or not isinstance(alias, str):
                raise ApplicationNameError(
                    "Both 'name' and 'alias' must be strings"
                )

            if len(name) > self.MAX_NAME_LENGTH:
                raise ApplicationNameError(
                    f"Application name '{name}' exceeds maximum length of {self.MAX_NAME_LENGTH} characters"
                )

            if not self._is_valid_identifier(alias):
                raise ApplicationNameError(
                    f"Alias '{alias}' must be a valid Python identifier"
                )

            normalized = ApplicationName(name=name, alias=alias)
        else:
            raise ApplicationNameError(
                "application_name must be a string, dict with 'name' and 'alias' keys, or None"
            )

        setattr(instance, self.private_name, normalized)

    @staticmethod
    def _name_to_alias(name: str) -> str:
        """Convert a pretty name to a valid Python identifier alias.

        Examples:
            "Persona Generator" -> "persona_generator"
            "Twitter Thread Splitter" -> "twitter_thread_splitter"
            "My-App!" -> "my_app"
        """
        # Convert to lowercase
        alias = name.lower()
        # Replace spaces and hyphens with underscores
        alias = re.sub(r'[\s\-]+', '_', alias)
        # Remove any non-alphanumeric characters except underscores
        alias = re.sub(r'[^\w]', '', alias)
        # Ensure it doesn't start with a digit
        if alias and alias[0].isdigit():
            alias = f"app_{alias}"
        # Ensure it's not empty
        if not alias:
            alias = "app"
        return alias

    @staticmethod
    def _is_valid_identifier(s: str) -> bool:
        """Check if a string is a valid Python identifier."""
        return s.isidentifier()


class DescriptionDescriptor:
    """Descriptor that validates and normalizes App.description.

    Accepts either:
    - A string (used as both short and long description)
    - A Description TypedDict with 'short' and 'long' keys
    - None (defaults to empty descriptions)

    Validates:
    - Short description is a single sentence ending with a period
    - Long description is provided

    Stores a Description TypedDict internally.
    """

    def __set_name__(self, owner, name):
        self.private_name = f"_{name}"

    def __get__(self, instance: Any, owner: type | None = None):
        if instance is None:
            return self
        stored = getattr(instance, self.private_name, None)
        if stored is None:
            # Default: empty descriptions
            return Description(short="No description provided.", long="No description provided.")
        return stored

    def __set__(self, instance: Any, value: Any) -> None:
        from .exceptions import DescriptionError

        # None or empty string: use default
        if value is None or value == "":
            normalized = Description(
                short="No description provided.",
                long="No description provided."
            )
        # String: use as both short and long (validate short is single sentence)
        elif isinstance(value, str):
            # Ensure it ends with a period
            short = value.strip()
            if not short.endswith('.'):
                short = f"{short}."

            # Validate it's a single sentence (no multiple periods except at end)
            sentence_count = short[:-1].count('.') + 1
            if sentence_count > 1:
                raise DescriptionError(
                    f"Short description must be a single sentence. Found {sentence_count} sentences: '{short}'"
                )

            normalized = Description(short=short, long=value.strip())
        # Dict: validate as Description
        elif isinstance(value, dict):
            if "short" not in value or "long" not in value:
                raise DescriptionError(
                    "description dict must contain 'short' and 'long' keys"
                )

            short = value["short"]
            long_desc = value["long"]

            if not isinstance(short, str) or not isinstance(long_desc, str):
                raise DescriptionError(
                    "Both 'short' and 'long' descriptions must be strings"
                )

            # Validate short description
            short = short.strip()
            if not short.endswith('.'):
                short = f"{short}."

            # Check for single sentence
            sentence_count = short[:-1].count('.') + 1
            if sentence_count > 1:
                raise DescriptionError(
                    f"Short description must be a single sentence. Found {sentence_count} sentences: '{short}'"
                )

            normalized = Description(short=short, long=long_desc.strip())
        else:
            raise DescriptionError(
                "description must be a string, dict with 'short' and 'long' keys, or None"
            )

        setattr(instance, self.private_name, normalized)


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

