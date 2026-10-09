"""Sealed two-player request game expressed with ordinary collection operations."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, field, arg, local, map_items, put, reduce, , state_field

largest = reduce("max", field("choices").values())
payoffs = map_items(
    field("choices"), key="player", value="request", key_expr=local("player"),
    value_expr=local("request") + choose(largest - local("request") == 1, constant("bonus"), 0),
)
SPEC = Machine(
    name="SharedMoneyRequestGame",
    constants={"minimum": 11, "maximum": 20, "bonus": 20},
    fields={
        "choices": state_field(StateType.map(StateType.text(), StateType.integer()), {}),
        "payoffs": state_field(StateType.map(StateType.text(), StateType.number()), {}),
    },
    commands={
        "submit": Command(
            inputs={"player": StateType.text(), "request": StateType.integer(minimum=constant("minimum"), maximum=constant("maximum"))},
            effects=(put("choices", arg("player"), arg("request")),),
        )
    },
    view={
        "range": (constant("minimum"), constant("maximum")),
        "bonus": constant("bonus"),
        "submission_count": field("choices").length(),
        "your_request": field("choices").get(current("name")),
        "choices": choose(current("closed"), field("choices"), {}),
        "payoffs": choose(current("closed"), field("payoffs"), {}),
    },
    complete_when=field("choices").length() == 2,
    close_effects=(assign("payoffs", payoffs),),
)
