"""Repeated actions represented as a nested round/seat map."""

from edsl.sharedstate import Command, Machine, T, constant, expr, field, input_, put, state_field

round_key = expr("concat", "", input_("round"))
round_actions = field("rounds").get(round_key, {}).with_item(input_("seat"), input_("action"))

SPEC = Machine(
    name="SharedRepeatedMatrixGame",
    constants={"actions": ("cooperate", "defect"), "round_count": 3, "payoffs": {}},
    fields={
        "rounds": state_field(
            T.map(T.text(), T.map(T.text(), T.choice(constant("actions")))),
            {},
        ),
        "players": state_field(T.map(T.text(), T.text()), {}),
    },
    commands={
        "submit": Command(
            inputs={
                "player": T.text(),
                "seat": T.choice(("0", "1")),
                "round": T.integer(minimum=1, maximum=constant("round_count")),
                "action": T.choice(constant("actions")),
            },
            effects=(put("rounds", round_key, round_actions), put("players", input_("seat"), input_("player"), once=True)),
        )
    },
    view={"rounds": field("rounds"), "players": field("players")},
    complete_when=field("rounds").get("3", {}).length() == 2,
)
