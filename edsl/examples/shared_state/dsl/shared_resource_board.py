"""Capability-constrained assignment using predicates and conditional effects."""

from edsl.sharedstate import Command, Machine, StateType, append, constant, field, arg, put, record, state_field, when

required = constant("incident_requirements").get(arg("incident"))
capability = constant("resource_capabilities").get(arg("resource"))
available = ~field("resource_use").contains(arg("resource"))
unassigned = ~field("assignments").contains(arg("incident"))
accepted = available & unassigned & (required == capability)

SPEC = Machine(
    name="SharedResourceBoard",
    constants={
        "incident_requirements": {"fire": "engine", "injury": "ambulance"},
        "resource_capabilities": {"E1": "engine", "A1": "ambulance"},
    },
    fields={
        "assignments": state_field(StateType.map(), {}),
        "resource_use": state_field(StateType.map(), {}),
        "attempts": state_field(StateType.sequence(), []),
    },
    commands={
        "allocate": Command(
            inputs={"responder": StateType.text(), "round": StateType.number(), "incident": StateType.choice(("fire", "injury")), "resource": StateType.choice(("E1", "A1"))},
            effects=(
                when(accepted, put("assignments", arg("incident"), arg("resource"))),
                when(accepted, put("resource_use", arg("resource"), arg("incident"))),
                append("attempts", record(responder=arg("responder"), incident=arg("incident"), resource=arg("resource"), round=arg("round"), accepted=accepted)),
            ),
        )
    },
    view={"assignments": field("assignments"), "resource_use": field("resource_use"), "attempts": field("attempts")},
)
