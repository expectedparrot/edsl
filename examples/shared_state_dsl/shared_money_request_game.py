"""Sealed two-player request game expressed with ordinary collection operations."""

from edsl.sharedstate import Command, Machine, T, choose, constant, current, field, input_, local, map_items, put, reduce_, set_, state_field

largest = reduce_("max", field("choices").values())
payoffs = map_items(
    field("choices"), key="player", value="request", key_expr=local("player"),
    value_expr=local("request") + choose(largest - local("request") == 1, constant("bonus"), 0),
)
SPEC = Machine(
    name="SharedMoneyRequestGame",
    constants={"minimum": 11, "maximum": 20, "bonus": 20},
    fields={
        "choices": state_field(T.map(T.text(), T.integer()), {}),
        "payoffs": state_field(T.map(T.text(), T.number()), {}),
    },
    commands={
        "submit": Command(
            inputs={"player": T.text(), "request": T.integer(minimum=constant("minimum"), maximum=constant("maximum"))},
            effects=(put("choices", input_("player"), input_("request")),),
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
    close_effects=(set_("payoffs", payoffs),),
)
