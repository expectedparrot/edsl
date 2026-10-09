"""First-price, second-price, or all-pay settlement as pure expressions."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, current, field, arg, local, map_items, put, record, reduce_, set_, state_field

ranked = reduce_("sort_records", field("bids").values(), fields=("amount", "seat"), descending=(True, False))
winning = ranked.first()
winner = winning.get("bidder")
second_bid = choose(ranked.length() > 1, ranked.at(1).get("amount"), 0)
price = choose(
    constant("mechanism") == "first_price", winning.get("amount"),
    choose(constant("mechanism") == "second_price", second_bid, winning.get("amount")),
)
payments = map_items(
    field("bids"), key="bidder", value="bid", key_expr=local("bidder"),
    value_expr=choose(
        constant("mechanism") == "all_pay", local("bid").get("amount"),
        choose(local("bidder") == winner, price, 0),
    ),
)
utilities = map_items(
    field("bids"), key="bidder", value="bid", key_expr=local("bidder"),
    value_expr=choose(local("bidder") == winner, local("bid").get("value"), 0) - payments.get(local("bidder")),
)
SPEC = Machine(
    name="SharedSealedAuction",
    constants={"mechanism": "second_price", "bidder_count": 3},
    fields={
        "bids": state_field(StateType.map(), {}), "winner": state_field(StateType.optional(StateType.text()), None),
        "winning_bid": state_field(StateType.optional(StateType.number()), None), "price": state_field(StateType.optional(StateType.number()), None),
        "revenue": state_field(StateType.optional(StateType.number()), None), "utilities": state_field(StateType.map(), {}),
    },
    commands={
        "bid": Command(
            inputs={"bidder": StateType.text(), "seat": StateType.integer(minimum=0), "private_value": StateType.number(minimum=0), "amount": StateType.number(minimum=0)},
            effects=(put("bids", arg("bidder"), record(bidder=arg("bidder"), amount=arg("amount"), value=arg("private_value"), seat=arg("seat"))),),
        )
    },
    view={
        "mechanism": constant("mechanism"), "bidder_count": constant("bidder_count"), "bid_count": field("bids").length(),
        "bids": choose(current("closed"), map_items(field("bids"), key="bidder", value="bid", key_expr=local("bidder"), value_expr=local("bid").get("amount")), {}),
        "winner": choose(current("closed"), field("winner"), None), "winning_bid": choose(current("closed"), field("winning_bid"), None),
        "price": choose(current("closed"), field("price"), None), "revenue": choose(current("closed"), field("revenue"), None),
        "utilities": choose(current("closed"), field("utilities"), {}),
    },
    complete_when=field("bids").length() == constant("bidder_count"),
    close_effects=(
        set_("winner", winner), set_("winning_bid", winning.get("amount")), set_("price", price),
        set_("revenue", reduce_("sum", payments.values())), set_("utilities", utilities),
    ),
)
