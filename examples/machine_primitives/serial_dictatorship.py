"""Priority allocation as a fold over requests, not a runtime algorithm call.

Latest request wins. Missing priorities sort last, with submission order breaking
priority ties. Each claimant receives the first ranked item with remaining space.
"""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    append,
    choose,
    constant,
    field,
    filter_items,
    fold,
    arg,
    let,
    local,
    record,
    reduce,
    assign,
    state_field,
)


def build_machine(items=("North", "South"), capacity=1):
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0:
        raise ValueError("capacity must be a nonnegative integer")
    items = list(items)
    latest = reduce("latest_by", field("requests"), field="claimant")
    ordered = reduce(
        "sort_records", latest.values(), fields=["unprioritized", "priority", "index"]
    )
    request, allocation = local("request"), local("allocation")
    available = filter_items(
        request.get("ranking"),
        item="option",
        predicate=allocation.get("remaining").get(local("option"), 0) > 0,
    )
    selected = local("selected")
    assign = let(
        "selected",
        available.first(),
        choose(
            selected == None,
            allocation,
            record(
                assignments=allocation.get("assignments").with_item(
                    request.get("claimant"), selected
                ),
                remaining=allocation.get("remaining").with_item(
                    selected, allocation.get("remaining").get(selected) - 1
                ),
            ),
        ),
    )
    initial = {"assignments": {}, "remaining": {item: capacity for item in items}}
    return Machine(
        name="PrimitiveSerialDictatorship",
        constants={"initial": initial},
        fields={
            "requests": state_field(StateType.sequence(StateType.map()), []),
            "allocation": state_field(StateType.map(), initial),
        },
        commands={
            "collect": Command(
                inputs={
                    "claimant": StateType.text(),
                    "priority": StateType.optional(StateType.number()),
                    "ranking": StateType.sequence(StateType.choice(items)),
                },
                effects=(
                    append(
                        "requests",
                        record(
                            claimant=arg("claimant"),
                            ranking=arg("ranking"),
                            unprioritized=arg("priority") == None,
                            priority=choose(
                                arg("priority") == None,
                                field("requests").length(),
                                arg("priority"),
                            ),
                            index=field("requests").length(),
                        ),
                    ),
                ),
            )
        },
        close_effects=(
            assign(
                "allocation",
                fold(
                    ordered,
                    constant("initial"),
                    item="request",
                    accumulator="allocation",
                    body=assign,
                ),
            ),
        ),
        view={
            "assignments": field("allocation").get("assignments"),
            "remaining": field("allocation").get("remaining"),
        },
    )


DEMO = [
    ("collect", {"claimant": "A", "priority": 2, "ranking": ["North", "South"]}),
    ("collect", {"claimant": "B", "priority": 1, "ranking": ["North", "South"]}),
    ("$close", {}),
]
