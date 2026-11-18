"""Standard shared-state resources for common workflow artifacts and collections."""

from __future__ import annotations

from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    StateType,
    append,
    field,
    arg,
    record,
    set_once,
    state_field,
)


def Artifact(state_id: str, *, field_name: str = "value") -> SharedStateMap:
    """Create a write-once text artifact resource."""
    machine = Machine(
        name="Artifact",
        constants={},
        fields={field_name: state_field(StateType.optional(StateType.text()), None)},
        commands={
            "submit": Command(
                inputs={"value": StateType.text()},
                effects=(set_once(field_name, arg("value")),),
            )
        },
        view={field_name: field(field_name)},
    )
    return SharedStateMap(SharedState(artifact=machine), state_id=state_id)


def Collection(state_id: str, *, field_name: str = "items") -> SharedStateMap:
    """Create an append-only collection of actor/value records."""
    machine = Machine(
        name="Collection",
        constants={},
        fields={field_name: state_field(StateType.sequence(), [])},
        commands={
            "add": Command(
                inputs={"actor": StateType.text(), "value": StateType.text()},
                effects=(
                    append(
                        field_name,
                        record(actor=arg("actor"), value=arg("value")),
                    ),
                ),
            )
        },
        view={field_name: field(field_name)},
    )
    return SharedStateMap(SharedState(collection=machine), state_id=state_id)
