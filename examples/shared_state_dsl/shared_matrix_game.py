"""A sealed two-player normal-form game with data-defined payoffs."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, expr, field, arg, map_of, put, , state_field

ACTIONS = ["cooperate", "defect"]
PAYOFFS = {"cooperate|cooperate": [3, 3], "cooperate|defect": [0, 5], "defect|cooperate": [5, 0], "defect|defect": [1, 1]}
profile = expr("concat", field("choices").get("0"), "|", field("choices").get("1"))
values = constant("payoff_table").get(profile)
resolved = map_of((field("players").get("0"), values.at(0)), (field("players").get("1"), values.at(1)))
SPEC = Machine(
    name="SharedMatrixGame",
    constants={"actions": ACTIONS, "payoff_table": PAYOFFS},
    fields={"choices": state_field(StateType.map(), {}), "players": state_field(StateType.map(), {}), "payoffs": state_field(StateType.map(), {})},
    commands={
        "submit": Command(
            inputs={"player": StateType.text(), "seat": StateType.choice(("0", "1")), "action": StateType.choice(ACTIONS)},
            effects=(put("choices", arg("seat"), arg("action")), put("players", arg("seat"), arg("player"))),
        )
    },
    view={"actions": constant("actions"), "submission_count": field("choices").length(), "choices": choose(current("closed"), field("choices"), {}), "payoffs": choose(current("closed"), field("payoffs"), {})},
    complete_when=field("choices").length() == 2,
    close_effects=(assign("payoffs", resolved),),
)
