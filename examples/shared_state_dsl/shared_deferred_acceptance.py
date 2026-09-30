"""Preference collection plus registered student-proposing deferred acceptance."""

from edsl.sharedstate import Command, Machine, T, algorithm, append, choose, constant, current, field, input_, local, map_items, map_sequence, record, reduce_, state_field

INSTITUTIONS = ("North", "South")
CAPACITIES = {"North": 1, "South": 1}
PRIORITIES = {"North": ["A", "B", "C"], "South": ["B", "A", "C"]}
latest = reduce_("latest_by", field("requests"), field="student")
first_choices = map_sequence(latest.values(), item="request", value_expr=local("request").get("ranking").at(0))
demand = map_items(
    constant("capacities"), key="institution", value="unused", key_expr=local("institution"),
    value_expr=reduce_("count_equal", first_choices, value=local("institution")),
)
SPEC = Machine(
    name="SharedDeferredAcceptance",
    constants={"capacities": CAPACITIES, "student_count": 2, "priorities": PRIORITIES, "institutions": INSTITUTIONS},
    fields={"requests": state_field(T.sequence(T.map()), []), "matches": state_field(T.map(), {}), "institution_matches": state_field(T.map(), {})},
    commands={
        "collect": Command(
            inputs={"student": T.text(), "ranking": T.rank(INSTITUTIONS)},
            effects=(append("requests", record(interview=current("interview_id"), student=input_("student"), ranking=input_("ranking"))),),
        )
    },
    view={
        "preference_count": latest.length(), "first_choice_demand": demand,
        "matches": choose(current("closed"), field("matches"), {}),
        "institution_matches": choose(current("closed"), field("institution_matches"), {}),
    },
    complete_when=latest.length() == constant("student_count"),
    close_effects=(algorithm("deferred_acceptance", requests=field("requests"), capacities=constant("capacities"), priorities=constant("priorities")),),
    algorithms=("deferred_acceptance@1",),
)
