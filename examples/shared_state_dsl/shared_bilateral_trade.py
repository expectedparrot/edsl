"""Buyer offer followed by a privately informed seller response."""

from edsl.sharedstate import Command, Machine, StateType, choose, current, field, arg, map_of, set_, state_field

payoffs = map_of(
    (field("buyer"), choose(field("accepted"), field("buyer_value") - field("price"), 0)),
    (field("seller"), choose(field("accepted"), field("price") - field("seller_cost"), 0)),
)
SPEC = Machine(
    name="SharedBilateralTrade", constants={},
    fields={name: state_field(StateType.optional(type_), None) for name, type_ in {
        "buyer": StateType.text(), "seller": StateType.text(), "buyer_value": StateType.number(),
        "seller_cost": StateType.number(), "price": StateType.number(), "accepted": StateType.boolean(),
    }.items()},
    commands={
        "offer": Command(
            inputs={"buyer": StateType.text(), "buyer_value": StateType.number(minimum=0), "price": StateType.number(minimum=0)},
            require=arg("price") <= arg("buyer_value"),
            effects=(set_("buyer", arg("buyer")), set_("buyer_value", arg("buyer_value")), set_("price", arg("price"))),
        ),
        "respond": Command(
            inputs={"seller": StateType.text(), "seller_cost": StateType.number(minimum=0), "decision": StateType.choice(("accept", "reject"))},
            require=field("price") != None,  # noqa: E711
            effects=(set_("seller", arg("seller")), set_("seller_cost", arg("seller_cost")), set_("accepted", arg("decision") == "accept")),
        ),
    },
    view={
        "buyer": field("buyer"), "seller": field("seller"), "price": field("price"), "accepted": field("accepted"),
        "your_value": choose(current("role") == "buyer", field("buyer_value"), None),
        "your_cost": choose(current("role") == "seller", field("seller_cost"), None),
        "payoffs": choose(field("accepted") != None, payoffs, None),  # noqa: E711
    },
    complete_when=field("accepted") != None,  # noqa: E711
)
