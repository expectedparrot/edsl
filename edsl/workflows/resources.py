"""Standard shared-state resources for common workflow artifacts and collections."""

from __future__ import annotations

from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    T,
    append,
    field,
    input_,
    record,
    set_once,
    state_field,
)


def Artifact(state_id: str, *, field_name: str = "value") -> SharedStateMap:
    """Create a write-once text artifact resource."""
    machine = Machine(
        name="Artifact",
        constants={},
        fields={field_name: state_field(T.optional(T.text()), None)},
        commands={
            "submit": Command(
                inputs={"value": T.text()},
                effects=(set_once(field_name, input_("value")),),
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
        fields={field_name: state_field(T.sequence(), [])},
        commands={
            "add": Command(
                inputs={"actor": T.text(), "value": T.text()},
                effects=(
                    append(
                        field_name,
                        record(actor=input_("actor"), value=input_("value")),
                    ),
                ),
            )
        },
        view={field_name: field(field_name)},
    )
    return SharedStateMap(SharedState(collection=machine), state_id=state_id)
