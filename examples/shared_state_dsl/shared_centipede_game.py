"""Ordered take-or-pass moves with early terminal settlement."""

from edsl.sharedstate import Command, Machine, T, append, constant, expr, field, input_, record, set_, state_field, when

is_take = input_("action") == "take"
is_final_pass = (input_("action") == "pass") & (input_("node") == constant("node_count"))
SPEC = Machine(
    name="SharedCentipedeGame",
    constants={"take_payoffs": [[2, 0], [1, 3], [4, 2]], "final_pass_payoffs": [3, 5], "node_count": 3},
    fields={"history": state_field(T.sequence(T.map()), []), "outcome": state_field(T.optional(T.text()), None), "payoffs": state_field(T.optional(T.sequence(T.number())), None)},
    commands={
        "move": Command(
            inputs={"player": T.text(), "node": T.integer(minimum=1, maximum=constant("node_count")), "action": T.choice(("take", "pass"))},
            require=(field("outcome") == None) & (input_("node") == field("history").length() + 1),  # noqa: E711
            effects=(
                append("history", record(node=input_("node"), player=input_("player"), action=input_("action"))),
                when(is_take, set_("outcome", expr("concat", "take_at_", input_("node")))),
                when(is_take, set_("payoffs", constant("take_payoffs").at(input_("node") - 1))),
                when(is_final_pass, set_("outcome", "pass_to_end")),
                when(is_final_pass, set_("payoffs", constant("final_pass_payoffs"))),
            ),
        )
    },
    view={"node_count": constant("node_count"), "history": field("history"), "outcome": field("outcome"), "payoffs": field("payoffs")},
    complete_when=field("outcome") != None,  # noqa: E711
)
