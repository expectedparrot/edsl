"""Buyer offer followed by a privately informed seller response."""

from edsl.sharedstate import Command, Machine, T, choose, current, field, input_, map_of, set_, state_field

payoffs = map_of(
    (field("buyer"), choose(field("accepted"), field("buyer_value") - field("price"), 0)),
    (field("seller"), choose(field("accepted"), field("price") - field("seller_cost"), 0)),
)
SPEC = Machine(
    name="SharedBilateralTrade", constants={},
    fields={name: state_field(T.optional(type_), None) for name, type_ in {
        "buyer": T.text(), "seller": T.text(), "buyer_value": T.number(),
        "seller_cost": T.number(), "price": T.number(), "accepted": T.boolean(),
    }.items()},
    commands={
        "offer": Command(
            inputs={"buyer": T.text(), "buyer_value": T.number(minimum=0), "price": T.number(minimum=0)},
            require=input_("price") <= input_("buyer_value"),
            effects=(set_("buyer", input_("buyer")), set_("buyer_value", input_("buyer_value")), set_("price", input_("price"))),
        ),
        "respond": Command(
            inputs={"seller": T.text(), "seller_cost": T.number(minimum=0), "decision": T.choice(("accept", "reject"))},
            require=field("price") != None,  # noqa: E711
            effects=(set_("seller", input_("seller")), set_("seller_cost", input_("seller_cost")), set_("accepted", input_("decision") == "accept")),
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
