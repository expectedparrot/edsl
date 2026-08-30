"""Ultimatum game expressed without a target-specific runtime function."""

from edsl.sharedstate import Command, Machine, T, choose, constant, field, input_, record, set_once, state_field

SPEC = Machine(
    name="SharedUltimatumGame",
    constants={"stake": 100},
    fields={
        "offer": state_field(T.optional(T.number()), None),
        "proposer": state_field(T.optional(T.text()), None),
        "responder": state_field(T.optional(T.text()), None),
        "decision": state_field(T.optional(T.choice(("accept", "reject"))), None),
    },
    commands={
        "offer": Command(
            inputs={"player": T.text(), "amount": T.number(minimum=0, maximum=constant("stake"))},
            effects=(set_once("proposer", input_("player")), set_once("offer", input_("amount"))),
        ),
        "respond": Command(
            inputs={"player": T.text(), "decision": T.choice(("accept", "reject"))},
            require=field("offer") != None,  # noqa: E711
            effects=(set_once("responder", input_("player")), set_once("decision", input_("decision"))),
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
