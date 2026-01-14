"""
Event classes for event-sourced Macro operations.

Macro tracks references to independently-versioned components (Survey, Jobs)
rather than containing them directly for Survey and Jobs. OutputFormatters
and attachment formatters are embedded since they are not GitMixin-enabled.

Each component already has its own event-sourced Store with a commit_hash.
Macro stores these commit_hashes as refs, enabling:
- Lightweight serialization (refs instead of full data)
- Component reuse across multiple Macros
- Independent versioning of each component

Created: 2026-01-14
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.store import Store

# Import base Event class from store
from edsl.store.events import Event


# =============================================================================
# Metadata Events
# =============================================================================


@dataclass(frozen=True)
class SetApplicationNameEvent(Event):
    """Event that sets the application name."""

    application_name: str


@dataclass(frozen=True)
class SetDisplayNameEvent(Event):
    """Event that sets the display name."""

    display_name: str


@dataclass(frozen=True)
class SetShortDescriptionEvent(Event):
    """Event that sets the short description."""

    description: str


@dataclass(frozen=True)
class SetLongDescriptionEvent(Event):
    """Event that sets the long description."""

    description: str


@dataclass(frozen=True)
class SetDefaultParamsEvent(Event):
    """Event that sets default parameters."""

    params: Tuple[Tuple[str, Any], ...]  # Tuple for hashability


@dataclass(frozen=True)
class SetFixedParamsEvent(Event):
    """Event that sets fixed parameters."""

    params: Tuple[Tuple[str, Any], ...]  # Tuple for hashability


# =============================================================================
# Component Reference Events
# =============================================================================


@dataclass(frozen=True)
class SetInitialSurveyRefEvent(Event):
    """Event that sets the initial survey reference."""

    ref: Optional[str]  # Survey's commit_hash


@dataclass(frozen=True)
class SetJobsObjectRefEvent(Event):
    """Event that sets the jobs object reference."""

    ref: Optional[str]  # Jobs' commit_hash


# =============================================================================
# Formatter Events
# =============================================================================


@dataclass(frozen=True)
class AddOutputFormatterEvent(Event):
    """Event that adds an output formatter."""

    formatter_name: str
    formatter_data: Tuple[Tuple[str, Any], ...]  # Serialized OutputFormatter as tuple


@dataclass(frozen=True)
class RemoveOutputFormatterEvent(Event):
    """Event that removes an output formatter."""

    formatter_name: str


@dataclass(frozen=True)
class SetDefaultFormatterEvent(Event):
    """Event that sets the default formatter name."""

    formatter_name: Optional[str]


@dataclass(frozen=True)
class SetAttachmentFormattersEvent(Event):
    """Event that sets the attachment formatters."""

    formatters: Tuple[Tuple[Tuple[str, Any], ...], ...]  # Tuple of serialized formatter dicts


@dataclass(frozen=True)
class ReplaceAllOutputFormattersEvent(Event):
    """Event that replaces all output formatters."""

    formatters: Tuple[Tuple[str, Tuple[Tuple[str, Any], ...]], ...]  # Tuple of (name, formatter_data) tuples as dict items


# =============================================================================
# Mode Events
# =============================================================================


@dataclass(frozen=True)
class SetClientModeEvent(Event):
    """Event that sets client mode."""

    enabled: bool


@dataclass(frozen=True)
class SetPseudoRunEvent(Event):
    """Event that sets pseudo run mode."""

    enabled: bool


# =============================================================================
# Composite Events
# =============================================================================


@dataclass(frozen=True)
class InitializeMacroEvent(Event):
    """Event that initializes a Macro with all state at once.

    This is used when creating a new Macro or when loading from serialized format.
    """

    application_name: str
    display_name: str
    short_description: str
    long_description: str
    initial_survey_ref: Optional[str]
    jobs_object_ref: Optional[str]
    output_formatters: Tuple[Tuple[str, Tuple[Tuple[str, Any], ...]], ...]  # Tuple of (name, formatter_data)
    attachment_formatters: Tuple[Tuple[Tuple[str, Any], ...], ...]  # Tuple of serialized formatter dicts
    default_params: Tuple[Tuple[str, Any], ...]
    fixed_params: Tuple[Tuple[str, Any], ...]
    default_formatter_name: Optional[str]
    client_mode: bool = False
    pseudo_run: bool = False


# =============================================================================
# Event Dispatcher
# =============================================================================


def apply_macro_event(event: Event, store: "Store") -> "Store":
    """Apply a Macro event to a store, returning the modified store.

    Macro uses the store.meta dict to track component refs and configuration.
    The store.entries list holds the output formatters.

    Args:
        event: The event to apply.
        store: The store to modify.

    Returns:
        The modified store (same instance, mutated in-place).

    Raises:
        ValueError: If the event type is unknown.
    """
    match event:
        # Metadata Events
        case SetApplicationNameEvent():
            store.meta["application_name"] = event.application_name
            return store

        case SetDisplayNameEvent():
            store.meta["display_name"] = event.display_name
            return store

        case SetShortDescriptionEvent():
            store.meta["short_description"] = event.description
            return store

        case SetLongDescriptionEvent():
            store.meta["long_description"] = event.description
            return store

        case SetDefaultParamsEvent():
            store.meta["default_params"] = dict(event.params)
            return store

        case SetFixedParamsEvent():
            store.meta["fixed_params"] = dict(event.params)
            return store

        # Component Reference Events
        case SetInitialSurveyRefEvent():
            store.meta["initial_survey_ref"] = event.ref
            return store

        case SetJobsObjectRefEvent():
            store.meta["jobs_object_ref"] = event.ref
            return store

        # Formatter Events
        case AddOutputFormatterEvent():
            if "output_formatters" not in store.meta:
                store.meta["output_formatters"] = {}
            store.meta["output_formatters"][event.formatter_name] = dict(event.formatter_data)
            return store

        case RemoveOutputFormatterEvent():
            if "output_formatters" in store.meta:
                store.meta["output_formatters"].pop(event.formatter_name, None)
            return store

        case SetDefaultFormatterEvent():
            store.meta["default_formatter_name"] = event.formatter_name
            return store

        case SetAttachmentFormattersEvent():
            store.meta["attachment_formatters"] = [dict(f) for f in event.formatters]
            return store

        case ReplaceAllOutputFormattersEvent():
            store.meta["output_formatters"] = {
                name: dict(data)
                for name, data in event.formatters
            }
            return store

        # Mode Events
        case SetClientModeEvent():
            store.meta["client_mode"] = event.enabled
            return store

        case SetPseudoRunEvent():
            store.meta["pseudo_run"] = event.enabled
            return store

        # Composite Events
        case InitializeMacroEvent():
            store.meta.update({
                "application_name": event.application_name,
                "display_name": event.display_name,
                "short_description": event.short_description,
                "long_description": event.long_description,
                "initial_survey_ref": event.initial_survey_ref,
                "jobs_object_ref": event.jobs_object_ref,
                "output_formatters": {
                    name: dict(data)
                    for name, data in event.output_formatters
                },
                "attachment_formatters": [dict(f) for f in event.attachment_formatters],
                "default_params": dict(event.default_params),
                "fixed_params": dict(event.fixed_params),
                "default_formatter_name": event.default_formatter_name,
                "client_mode": event.client_mode,
                "pseudo_run": event.pseudo_run,
            })
            return store

        case _:
            raise ValueError(f"Unknown Macro event type: {type(event)}")


# =============================================================================
# Event Registry
# =============================================================================

# Macro-specific events registry
MACRO_EVENT_REGISTRY: Dict[str, type] = {}


def _build_macro_registry():
    """Build the Macro event registry from all Event subclasses in this module."""
    import inspect

    for name, obj in globals().items():
        if (
            inspect.isclass(obj)
            and issubclass(obj, Event)
            and obj is not Event
            and name.endswith("Event")
        ):
            MACRO_EVENT_REGISTRY[obj.__name__] = obj


_build_macro_registry()


def get_macro_event_class(event_name: str) -> type:
    """Get a Macro event class by name.

    Args:
        event_name: Either the class name (e.g., 'SetApplicationNameEvent')
                   or snake_case name (e.g., 'set_application_name')

    Returns:
        The event class.

    Raises:
        ValueError: If event name is not found.
    """
    # Try direct class name lookup first
    if event_name in MACRO_EVENT_REGISTRY:
        return MACRO_EVENT_REGISTRY[event_name]

    # Try snake_case to class name conversion
    class_name = "".join(word.capitalize() for word in event_name.split("_")) + "Event"
    if class_name in MACRO_EVENT_REGISTRY:
        return MACRO_EVENT_REGISTRY[class_name]

    raise ValueError(
        f"Unknown Macro event: {event_name}. "
        f"Available events: {list(MACRO_EVENT_REGISTRY.keys())}"
    )
