"""Privately informed message followed by a receiver action."""

from edsl.sharedstate import Command, Machine, T, choose, field, input_, map_of, set_, state_field

sender_target = choose(field("preference") == "aligned", field("private_state"), "R")
payoffs = map_of(
    (field("sender"), choose(field("action") == sender_target, 1, 0)),
    (field("receiver"), choose(field("action") == field("private_state"), 1, 0)),
)
SPEC = Machine(
    name="SharedCheapTalkGame", constants={},
    fields={name: state_field(T.optional(T.text()), None) for name in ("sender", "receiver", "private_state", "preference", "message", "action")},
    commands={
        "message": Command(
            inputs={"sender": T.text(), "state": T.choice(("L", "R")), "preference": T.text(), "message": T.choice(("L", "R"))},
            effects=(set_("sender", input_("sender")), set_("private_state", input_("state")), set_("preference", input_("preference")), set_("message", input_("message"))),
        ),
        "act": Command(
            inputs={"receiver": T.text(), "action": T.choice(("L", "R"))},
            require=field("message") != None,  # noqa: E711
            effects=(set_("receiver", input_("receiver")), set_("action", input_("action"))),
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
