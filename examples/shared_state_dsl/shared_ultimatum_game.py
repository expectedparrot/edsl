"""Ultimatum game expressed without a target-specific runtime function."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, field, arg, record, set_once, state_field

SPEC = Machine(
    name="SharedUltimatumGame",
    constants={"stake": 100},
    fields={
        "offer": state_field(StateType.optional(StateType.number()), None),
        "proposer": state_field(StateType.optional(StateType.text()), None),
        "responder": state_field(StateType.optional(StateType.text()), None),
        "decision": state_field(StateType.optional(StateType.choice(("accept", "reject"))), None),
    },
    commands={
        "offer": Command(
            inputs={"player": StateType.text(), "amount": StateType.number(minimum=0, maximum=constant("stake"))},
            effects=(set_once("proposer", arg("player")), set_once("offer", arg("amount"))),
        ),
        "respond": Command(
            inputs={"player": StateType.text(), "decision": StateType.choice(("accept", "reject"))},
            require=field("offer") != None,  # noqa: E711
            effects=(set_once("responder", arg("player")), set_once("decision", arg("decision"))),
        ),
    },
    view={
        "offer": field("offer"),
        "decision": field("decision"),
        "payoffs": choose(
            field("decision") == "accept",
            record(proposer=constant("stake") - field("offer"), responder=field("offer")),
            record(proposer=0, responder=0),
        ),
    },
    complete_when=field("decision") != None,  # noqa: E711
)
