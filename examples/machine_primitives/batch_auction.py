"""Deterministic one-unit call auction: a smaller model to expose design limits.

This example isolates market clearing. It deliberately omits the full asset
market's dividends, interest, randomized priority, and multi-unit orders.
"""

from edsl.sharedstate import (
    Command,
    Machine,
    StateType,
    choose,
    field,
    filter_items,
    fold,
    arg,
    let,
    local,
    map_sequence,
    put,
    record,
    reduce,
    assign,
    state_field,
    take,
)


def build_machine():
    orders = field("orders").values()
    bids = reduce(
        "sort_records",
        filter_items(
            orders, item="order", predicate=local("order").get("side") == "buy"
        ),
        fields=["price", "trader"],
        descending=[True, False],
    )
    asks = reduce(
        "sort_records",
        filter_items(
            orders, item="order", predicate=local("order").get("side") == "sell"
        ),
        fields=["price", "trader"],
    )
    tally, bid = local("tally"), local("bid")
    ask = asks.at(tally.get("volume"))
    step = choose(
        tally.get("stopped") | (tally.get("volume") >= asks.length()),
        tally.with_item("stopped", True),
        choose(
            bid.get("price") < ask.get("price"),
            tally.with_item("stopped", True),
            record(
                volume=tally.get("volume") + 1,
                price=(bid.get("price") + ask.get("price")) / 2,
                stopped=False,
            ),
        ),
    )
    cleared = fold(
        bids,
        record(volume=0, price=None, stopped=False),
        item="bid",
        accumulator="tally",
        body=step,
    )

    def names(rows):
        return map_sequence(
            take(rows, local("cleared").get("volume")),
            item="order",
            value_expr=local("order").get("trader"),
        )

    return Machine(
        constants={},
        name="PrimitiveBatchAuction",
        fields={
            "orders": state_field(StateType.map(), {}),
            "clearing": state_field(
                StateType.map(), {"volume": 0, "price": None, "buyers": [], "sellers": []}
            ),
        },
        commands={
            "submit": Command(
                inputs={
                    "trader": StateType.text(),
                    "side": StateType.choice(["buy", "sell"]),
                    "price": StateType.number(minimum=0),
                },
                effects=(
                    put(
                        "orders",
                        arg("trader"),
                        record(
                            trader=arg("trader"),
                            side=arg("side"),
                            price=arg("price"),
                        ),
                    ),
                ),
            )
        },
        close_effects=(
            assign(
                "clearing",
                let(
                    "cleared",
                    cleared,
                    record(
                        volume=local("cleared").get("volume"),
                        price=local("cleared").get("price"),
                        buyers=names(bids),
                        sellers=names(asks),
                    ),
                ),
            ),
        ),
        view={"clearing": field("clearing")},
    )


DEMO = [
    ("submit", {"trader": "Buyer", "side": "buy", "price": 50}),
    ("submit", {"trader": "Seller", "side": "sell", "price": 30}),
    ("$close", {}),
]
