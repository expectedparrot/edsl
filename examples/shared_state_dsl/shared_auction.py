"""Append-only ascending bids resolved deterministically at close."""

from edsl.sharedstate import Command, Machine, T, append, choose, constant, current, field, filter_items, input_, local, map_sequence, record, reduce_, set_, state_field

positive = filter_items(field("bids"), item="bid", predicate=local("bid").get("amount") > 0)
amounts = map_sequence(positive, item="bid", value_expr=local("bid").get("amount"))
winning = reduce_("argmax", positive, field="amount")
SPEC = Machine(
    name="SharedAuction", constants={"item": "Sailboat lesson", "increment": 1, "bidder_count": 3},
    fields={"bids": state_field(T.sequence(T.map()), []), "winner": state_field(T.optional(T.text()), None), "winning_bid": state_field(T.optional(T.number()), None)},
    commands={"bid": Command(inputs={"amount": T.number(minimum=0)}, effects=(append("bids", record(interview=current("interview_id"), amount=input_("amount"))),))},
    view={
        "item": constant("item"), "highest_bid": choose(positive.length() > 0, reduce_("max", amounts), 0),
        "bid_count": positive.length(), "increment": constant("increment"),
        "winner": choose(current("closed"), field("winner"), None), "winning_bid": choose(current("closed"), field("winning_bid"), None),
    },
    complete_when=field("bids").length() == constant("bidder_count"),
    close_effects=(
        set_("winner", choose(positive.length() > 0, winning.get("interview"), None)),
        set_("winning_bid", choose(positive.length() > 0, winning.get("amount"), None)),
    ),
)
