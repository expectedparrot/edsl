"""
Event classes for event-sourced Jobs operations.

Jobs is a "manifest" that tracks references to independently-versioned components
(Survey, AgentList, ModelList, ScenarioList) rather than containing them directly.

Each component already has its own event-sourced Store with a commit_hash.
Jobs stores these commit_hashes as refs, enabling:
- Lightweight serialization (refs instead of full data)
- Component reuse across multiple Jobs
- Independent versioning of each component

Created: 2026-01-14
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from edsl.store import Store


# Import base Event class from store
from edsl.store.events import Event


# =============================================================================
# Component Reference Events
# =============================================================================


@dataclass(frozen=True)
class SetSurveyRefEvent(Event):
    """Event that sets the survey component reference."""

    ref: str  # Survey's commit_hash


@dataclass(frozen=True)
class SetAgentsRefEvent(Event):
    """Event that sets the agents component reference."""

    ref: str  # AgentList's commit_hash


@dataclass(frozen=True)
class SetModelsRefEvent(Event):
    """Event that sets the models component reference."""

    ref: str  # ModelList's commit_hash


@dataclass(frozen=True)
class SetScenariosRefEvent(Event):
    """Event that sets the scenarios component reference."""

    ref: str  # ScenarioList's commit_hash


# =============================================================================
# Config Events
# =============================================================================


@dataclass(frozen=True)
class AddWhereClauseEvent(Event):
    """Event that adds a where clause for filtering."""

    clause: str


@dataclass(frozen=True)
class ClearWhereClausesEvent(Event):
    """Event that clears all where clauses."""

    pass


@dataclass(frozen=True)
class SetIncludeExpressionEvent(Event):
    """Event that sets the Jinja2 include expression."""

    expression: Optional[str]


@dataclass(frozen=True)
class AddPostRunMethodEvent(Event):
    """Event that adds a method to run after job completion."""

    method_chain: tuple[Any, ...]  # Tuple for hashability


@dataclass(frozen=True)
class ClearPostRunMethodsEvent(Event):
    """Event that clears all post-run methods."""

    pass


@dataclass(frozen=True)
class SetDependsOnRefEvent(Event):
    """Event that sets the upstream Jobs dependency reference."""

    ref: Optional[str]  # Another Jobs' commit_hash, or None


# =============================================================================
# Composite Events
# =============================================================================


@dataclass(frozen=True)
class InitializeJobsEvent(Event):
    """Event that initializes a Jobs with all component refs at once.

    This is used when creating a new Jobs or when loading from serialized format.
    """

    survey_ref: str
    agents_ref: str
    models_ref: str
    scenarios_ref: str
    where_clauses: tuple[str, ...] = ()
    include_expression: Optional[str] = None
    post_run_methods: tuple[Any, ...] = ()
    depends_on_ref: Optional[str] = None


# =============================================================================
# Event Dispatcher
# =============================================================================


def apply_jobs_event(event: Event, store: "Store") -> "Store":
    """Apply a Jobs event to a store, returning the modified store.

    Jobs uses the store.meta dict to track component refs and configuration.
    The store.entries list is unused (empty) since Jobs doesn't have "rows".

    Args:
        event: The event to apply.
        store: The store to modify.

    Returns:
        The modified store (same instance, mutated in-place).

    Raises:
        ValueError: If the event type is unknown.
    """
    match event:
        # Component Reference Events
        case SetSurveyRefEvent():
            store.meta["survey_ref"] = event.ref
            return store

        case SetAgentsRefEvent():
            store.meta["agents_ref"] = event.ref
            return store

        case SetModelsRefEvent():
            store.meta["models_ref"] = event.ref
            return store

        case SetScenariosRefEvent():
            store.meta["scenarios_ref"] = event.ref
            return store

        # Config Events
        case AddWhereClauseEvent():
            clauses = list(store.meta.get("where_clauses", []))
            clauses.append(event.clause)
            store.meta["where_clauses"] = clauses
            return store

        case ClearWhereClausesEvent():
            store.meta["where_clauses"] = []
            return store

        case SetIncludeExpressionEvent():
            store.meta["include_expression"] = event.expression
            return store

        case AddPostRunMethodEvent():
            methods = list(store.meta.get("post_run_methods", []))
            methods.append(event.method_chain)
            store.meta["post_run_methods"] = methods
            return store

        case ClearPostRunMethodsEvent():
            store.meta["post_run_methods"] = []
            return store

        case SetDependsOnRefEvent():
            store.meta["depends_on_ref"] = event.ref
            return store

        # Composite Events
        case InitializeJobsEvent():
            store.meta["survey_ref"] = event.survey_ref
            store.meta["agents_ref"] = event.agents_ref
            store.meta["models_ref"] = event.models_ref
            store.meta["scenarios_ref"] = event.scenarios_ref
            store.meta["where_clauses"] = list(event.where_clauses)
            store.meta["include_expression"] = event.include_expression
            store.meta["post_run_methods"] = list(event.post_run_methods)
            store.meta["depends_on_ref"] = event.depends_on_ref
            return store

        case _:
            raise ValueError(f"Unknown Jobs event type: {type(event)}")


# =============================================================================
# Event Registry
# =============================================================================

# Jobs-specific events registry
JOBS_EVENT_REGISTRY: Dict[str, type] = {}


def _build_jobs_registry():
    """Build the Jobs event registry from all Event subclasses in this module."""
    import inspect

    for name, obj in globals().items():
        if (
            inspect.isclass(obj)
            and issubclass(obj, Event)
            and obj is not Event
            and name.endswith("Event")
        ):
            JOBS_EVENT_REGISTRY[obj.__name__] = obj


_build_jobs_registry()


def get_jobs_event_class(event_name: str) -> type:
    """Get a Jobs event class by name.

    Args:
        event_name: Either the class name (e.g., 'SetSurveyRefEvent')
                   or snake_case name (e.g., 'set_survey_ref')

    Returns:
        The event class.

    Raises:
        ValueError: If event name is not found.
    """
    # Try direct class name lookup first
    if event_name in JOBS_EVENT_REGISTRY:
        return JOBS_EVENT_REGISTRY[event_name]

    # Try snake_case to class name conversion
    class_name = "".join(word.capitalize() for word in event_name.split("_")) + "Event"
    if class_name in JOBS_EVENT_REGISTRY:
        return JOBS_EVENT_REGISTRY[class_name]

    raise ValueError(
        f"Unknown Jobs event: {event_name}. "
        f"Available events: {list(JOBS_EVENT_REGISTRY.keys())}"
    )
