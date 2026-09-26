"""One-unit continuous auction using filtering, sorting, and immutable updates.

Orders match at the resting order's price; price then arrival order determines
priority. Invalid admission conditions return explicit, public rejection codes.
"""

from edsl.sharedstate import (
    Command,
    assert_,
    when,
    Machine,
    T,
    choose,
    expr,
    field,
    filter_items,
    input_,
    let,
    local,
    map_items,
    map_sequence,
    record,
    reduce_,
    set_,
    state_field,
)


def build_machine(accounts=None):
    accounts = (
        {"Buyer": {"cash": 100, "inventory": 0}, "Seller": {"cash": 0, "inventory": 2}}
        if accounts is None
        else accounts
    )
    book = field("market")
    action, trader, price = input_("action"), input_("trader"), input_("price")
    row = local("row")
    open_owned = filter_items(
        book.get("orders"),
        item="row",
        predicate=(row.get("status") == "open") & (row.get("trader") == trader),
    )
    account = book.get("accounts").get(trader)
    trading = (action == "buy") | (action == "sell")
    admission = (
        when(trading, assert_(open_owned.length() == 0, code="open_order_exists")),
        when(trading, assert_(price > 0, code="invalid_price")),
        when(
            action == "buy",
            assert_(account.get("cash") >= price, code="insufficient_cash"),
        ),
        when(
            action == "sell",
            assert_(account.get("inventory") >= 1, code="insufficient_inventory"),
        ),
    )
    order = record(
        id=expr("concat", "O", book.get("orders").length() + 1),
        trader=trader,
        side=action,
        price=price,
        round=input_("round"),
        status="open",
        interview=None,
        time=book.get("orders").length() + 1,
    )
    compatible = filter_items(
        book.get("orders"),
        item="row",
        predicate=(row.get("status") == "open")
        & (row.get("side") == choose(action == "buy", "sell", "buy"))
        & choose(action == "buy", row.get("price") <= price, row.get("price") >= price),
    )
    # Choose a whole sorted expression: direction is authoring metadata, not a
    # runtime Python lambda. Both alternatives serialize with the definition.
    best = choose(
        action == "buy",
        reduce_(
            "sort_records",
            compatible,
            fields=["price", "time"],
            descending=[False, False],
        ),
        reduce_(
            "sort_records",
            compatible,
            fields=["price", "time"],
            descending=[True, False],
        ),
    ).first()
    resting, incoming = local("resting"), local("incoming")
    buyer = choose(action == "buy", trader, resting.get("trader"))
    seller = choose(action == "sell", trader, resting.get("trader"))
    p = resting.get("price")
    old_account, owner = local("account"), local("owner")
    new_accounts = map_items(
        book.get("accounts"),
        key="owner",
        value="account",
        key_expr=owner,
        value_expr=choose(
            owner == buyer,
            old_account.with_item("cash", old_account.get("cash") - p).with_item(
                "inventory", old_account.get("inventory") + 1
            ),
            choose(
                owner == seller,
                old_account.with_item("cash", old_account.get("cash") + p).with_item(
                    "inventory", old_account.get("inventory") - 1
                ),
                old_account,
            ),
        ),
    )
    orders = book.get("orders").appended(incoming)
    matched_orders = map_sequence(
        orders,
        item="row",
        value_expr=choose(
            (row.get("id") == resting.get("id"))
            | (row.get("id") == incoming.get("id")),
            row.with_item("status", "filled"),
            row,
        ),
    )
    traded = record(
        accounts=new_accounts,
        orders=matched_orders,
        trades=book.get("trades").appended(
            record(
                buyer=buyer,
                seller=seller,
                price=p,
                round=input_("round"),
                maker_order=resting.get("id"),
                taker_order=incoming.get("id"),
            )
        ),
    )
    submitted = let(
        "incoming",
        order,
        let(
            "resting",
            best,
            choose(resting == None, book.with_item("orders", orders), traded),
        ),
    )
    cancelled = book.with_item(
        "orders",
        map_sequence(
            book.get("orders"),
            item="row",
            value_expr=choose(
                (row.get("status") == "open") & (row.get("trader") == trader),
                row.with_item("status", "cancelled"),
                row,
            ),
        ),
    )
    closed = book.with_item(
        "orders",
        map_sequence(
            book.get("orders"),
            item="row",
            value_expr=choose(
                row.get("status") == "open", row.with_item("status", "expired"), row
            ),
        ),
    )
    return Machine(
        constants={},
        name="PrimitiveDoubleAuction",
        fields={
            "market": state_field(
                T.map(), {"accounts": accounts, "orders": [], "trades": []}
            )
        },
        commands={
            "submit": Command(
                inputs={
                    "trader": T.choice(list(accounts)),
                    "action": T.choice(["buy", "sell", "cancel", "hold"]),
                    "price": T.number(),
                    "round": T.integer(minimum=1),
                },
                effects=(
                    *admission,
                    set_(
                        "market",
                        choose(
                            action == "hold",
                            book,
                            choose(action == "cancel", cancelled, submitted),
                        ),
                    ),
                ),
            )
        },
        close_effects=(set_("market", closed),),
        view={"market": book},
    )


DEMO = [
    ("submit", {"trader": "Seller", "action": "sell", "price": 40, "round": 1}),
    ("submit", {"trader": "Buyer", "action": "buy", "price": 50, "round": 1}),
    ("submit", {"trader": "Buyer", "action": "buy", "price": 1000, "round": 2}),
    ("submit", {"trader": "Buyer", "action": "hold", "price": 0, "round": 2}),
    ("$close", {}),
]
