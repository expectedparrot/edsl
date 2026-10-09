"""Privately informed message followed by a receiver action."""

from edsl.sharedstate import Command, Machine, StateType, choose, field, arg, map_of, set_, state_field

sender_target = choose(field("preference") == "aligned", field("private_state"), "R")
payoffs = map_of(
    (field("sender"), choose(field("action") == sender_target, 1, 0)),
    (field("receiver"), choose(field("action") == field("private_state"), 1, 0)),
)
SPEC = Machine(
    name="SharedCheapTalkGame", constants={},
    fields={name: state_field(StateType.optional(StateType.text()), None) for name in ("sender", "receiver", "private_state", "preference", "message", "action")},
    commands={
        "message": Command(
            inputs={"sender": StateType.text(), "state": StateType.choice(("L", "R")), "preference": StateType.text(), "message": StateType.choice(("L", "R"))},
            effects=(set_("sender", arg("sender")), set_("private_state", arg("state")), set_("preference", arg("preference")), set_("message", arg("message"))),
        ),
        "act": Command(
            inputs={"receiver": StateType.text(), "action": StateType.choice(("L", "R"))},
            require=field("message") != None,  # noqa: E711
            effects=(set_("receiver", arg("receiver")), set_("action", arg("action"))),
        ),
    },
    view={
        "sender": field("sender"), "receiver": field("receiver"), "message": field("message"), "action": field("action"),
        "payoffs": choose(field("action") != None, payoffs, None),  # noqa: E711
        "truthful": choose(field("action") != None, field("message") == field("private_state"), None),  # noqa: E711
        "correct_action": choose(field("action") != None, field("action") == field("private_state"), None),  # noqa: E711
    },
    complete_when=field("action") != None,  # noqa: E711
)
