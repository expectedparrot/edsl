"""Preference collection plus registered serial-dictatorship settlement."""

from edsl.sharedstate import Command, Machine, T, algorithm, append, choose, constant, current, field, input_, local, map_items, map_sequence, record, reduce_, state_field

ITEMS = ("bike ride", "sailing", "hike", "beach day")
claimant = choose(input_("claimant") != None, input_("claimant"), current("interview_id"))  # noqa: E711
latest = reduce_("latest_by", field("requests"), field="claimant")
first_choices = map_sequence(latest.values(), item="request", value_expr=local("request").get("ranking").at(0))
request_counts = map_items(
    constant("zero_counts"), key="item", value="unused", key_expr=local("item"),
    value_expr=reduce_("count_equal", first_choices, value=local("item")),
)
SPEC = Machine(
    name="SharedMatchPool",
    constants={"items": ITEMS, "claimant_count": 3, "rule": "serial_dictatorship", "capacity": 1, "zero_counts": {item: 0 for item in ITEMS}},
    fields={"requests": state_field(T.sequence(T.map()), []), "assignments": state_field(T.map(), {})},
    commands={
        "collect": Command(
            inputs={"claimant": T.optional(T.text()), "priority": T.optional(T.number()), "ranking": T.rank(ITEMS)},
            effects=(append("requests", record(interview=current("interview_id"), claimant=claimant, priority=input_("priority"), ranking=input_("ranking"))),),
        )
    },
    view={"request_counts": request_counts, "assignments": choose(current("closed"), field("assignments"), {})},
    complete_when=latest.length() == constant("claimant_count"),
    close_effects=(algorithm("serial_dictatorship", requests=field("requests"), items=constant("items"), capacity=constant("capacity")),),
    algorithms=("serial_dictatorship@1",),
)
