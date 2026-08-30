"""Capability-constrained assignment using predicates and conditional effects."""

from edsl.sharedstate import Command, Machine, T, append, constant, field, input_, put, record, state_field, when

required = constant("incident_requirements").get(input_("incident"))
capability = constant("resource_capabilities").get(input_("resource"))
available = ~field("resource_use").contains(input_("resource"))
unassigned = ~field("assignments").contains(input_("incident"))
accepted = available & unassigned & (required == capability)

SPEC = Machine(
    name="SharedResourceBoard",
    constants={
        "incident_requirements": {"fire": "engine", "injury": "ambulance"},
        "resource_capabilities": {"E1": "engine", "A1": "ambulance"},
    },
    fields={
        "assignments": state_field(T.map(), {}),
        "resource_use": state_field(T.map(), {}),
        "attempts": state_field(T.sequence(), []),
    },
    commands={
        "allocate": Command(
            inputs={"responder": T.text(), "round": T.number(), "incident": T.choice(("fire", "injury")), "resource": T.choice(("E1", "A1"))},
            effects=(
                when(accepted, put("assignments", input_("incident"), input_("resource"))),
                when(accepted, put("resource_use", input_("resource"), input_("incident"))),
                append("attempts", record(responder=input_("responder"), incident=input_("incident"), resource=input_("resource"), round=input_("round"), accepted=accepted)),
            ),
        )
    },
    view={"assignments": field("assignments"), "resource_use": field("resource_use"), "attempts": field("attempts")},
)
