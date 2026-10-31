"""Repeated actions represented as a nested round/seat map."""

from edsl.sharedstate import Command, Machine, StateType, constant, expr, field, arg, put, state_field

round_key = expr("concat", "", arg("round"))
round_actions = field("rounds").get(round_key, {}).with_item(arg("seat"), arg("action"))

SPEC = Machine(
    name="SharedRepeatedMatrixGame",
    constants={"actions": ("cooperate", "defect"), "round_count": 3, "payoffs": {}},
    fields={
        "rounds": state_field(
            StateType.map(StateType.text(), StateType.map(StateType.text(), StateType.choice(constant("actions")))),
            {},
        ),
        "players": state_field(StateType.map(StateType.text(), StateType.text()), {}),
    },
    commands={
        "submit": Command(
            inputs={
                "player": StateType.text(),
                "seat": StateType.choice(("0", "1")),
                "round": StateType.integer(minimum=1, maximum=constant("round_count")),
                "action": StateType.choice(constant("actions")),
            },
            effects=(put("rounds", round_key, round_actions), put("players", arg("seat"), arg("player"), once=True)),
        )
    },
    view={"rounds": field("rounds"), "players": field("players")},
    complete_when=field("rounds").get("3", {}).length() == 2,
)
