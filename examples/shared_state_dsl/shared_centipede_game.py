"""Ordered take-or-pass moves with early terminal settlement."""

from edsl.sharedstate import Command, Machine, StateType, append, constant, expr, field, arg, record, assign, state_field, when

is_take = arg("action") == "take"
is_final_pass = (arg("action") == "pass") & (arg("node") == constant("node_count"))
SPEC = Machine(
    name="SharedCentipedeGame",
    constants={"take_payoffs": [[2, 0], [1, 3], [4, 2]], "final_pass_payoffs": [3, 5], "node_count": 3},
    fields={"history": state_field(StateType.sequence(StateType.map()), []), "outcome": state_field(StateType.optional(StateType.text()), None), "payoffs": state_field(StateType.optional(StateType.sequence(StateType.number())), None)},
    commands={
        "move": Command(
            inputs={"player": StateType.text(), "node": StateType.integer(minimum=1, maximum=constant("node_count")), "action": StateType.choice(("take", "pass"))},
            require=(field("outcome") == None) & (arg("node") == field("history").length() + 1),  # noqa: E711
            effects=(
                append("history", record(node=arg("node"), player=arg("player"), action=arg("action"))),
                when(is_take, assign("outcome", expr("concat", "take_at_", arg("node")))),
                when(is_take, assign("payoffs", constant("take_payoffs").at(arg("node") - 1))),
                when(is_final_pass, assign("outcome", "pass_to_end")),
                when(is_final_pass, assign("payoffs", constant("final_pass_payoffs"))),
            ),
        )
    },
    view={"node_count": constant("node_count"), "history": field("history"), "outcome": field("outcome"), "payoffs": field("payoffs")},
    complete_when=field("outcome") != None,  # noqa: E711
)
