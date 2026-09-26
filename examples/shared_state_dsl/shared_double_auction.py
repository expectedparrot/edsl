"""Atomic unit-order matching delegated to a registered mechanism transition."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    algorithm,
    choose,
    current,
    field,
    filter_items,
    input_,
    local,
    map_sequence,
    record,
    reduce_,
    state_field,
)

PARTICIPANTS = {
    "Buyer": {"cash": 100.0, "inventory": 0},
    "Seller": {"cash": 0.0, "inventory": 1},
}
open_orders = filter_items(
    field("orders"), item="order", predicate=local("order").get("status") == "open"
)
bids = reduce_(
    "sort_records",
    filter_items(
        open_orders, item="order", predicate=local("order").get("side") == "buy"
    ),
    fields=("price", "time"),
    descending=(True, False),
)
asks = reduce_(
    "sort_records",
    filter_items(
        open_orders, item="order", predicate=local("order").get("side") == "sell"
    ),
    fields=("price", "time"),
    descending=(False, False),
)


def book_rows(rows):
    return map_sequence(
        rows,
        item="order",
        value_expr=record(
            trader=local("order").get("trader"),
            price=local("order").get("price"),
        ),
    )


viewer_orders = filter_items(
    open_orders, item="order", predicate=local("order").get("trader") == current("name")
)
public_viewer_orders = map_sequence(
    viewer_orders,
    item="order",
    value_expr=record(
        id=local("order").get("id"),
        trader=local("order").get("trader"),
        side=local("order").get("side"),
        price=local("order").get("price"),
        round=local("order").get("round"),
        status=local("order").get("status"),
        interview=local("order").get("interview"),
    ),
)

SPEC = Machine(
    name="SharedDoubleAuction",
    constants={"participants": PARTICIPANTS},
    fields={
        "accounts": state_field(T.map(), PARTICIPANTS),
        "orders": state_field(T.sequence(T.map()), []),
        "trades": state_field(T.sequence(T.map()), []),
    },
    commands={
        "submit": Command(
            inputs={
                "trader": T.text(),
                "round": T.integer(minimum=1),
                "action": T.choice(("buy", "sell", "cancel", "hold")),
                "price": T.any(),
            },
            effects=(
                algorithm(
                    "double_auction_submit",
                    trader=input_("trader"),
                    round=input_("round"),
                    action=input_("action"),
                    price=input_("price"),
                    interview=current("interview_id"),
                ),
            ),
        )
    },
    view={
        "best_bid": choose(bids.length() > 0, bids.at(0).get("price"), None),
        "best_ask": choose(asks.length() > 0, asks.at(0).get("price"), None),
        "bids": book_rows(bids),
        "asks": book_rows(asks),
        "trades": field("trades"),
        "your_account": field("accounts").get(current("name")),
        "your_open_orders": public_viewer_orders,
        "accounts": choose(
            current("name") == None,  # noqa: E711
            field("accounts"),
            {},
        ),
        "closed": current("closed"),
    },
    close_effects=(algorithm("double_auction_close"),),
    algorithms=("double_auction_submit@1", "double_auction_close@1"),
)
