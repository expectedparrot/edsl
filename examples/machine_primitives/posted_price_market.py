"""Inventory sales at a versioned posted quote; all money uses integer units."""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    assert_,
    choose,
    constant,
    current_value,
    field,
    filter_items,
    input_,
    local,
    put,
    record,
    set_,
    state_field,
    when,
)


def build_machine(stock=5, base_price=20, increment=5, balances=None):
    balances = dict(
        {"A": 200, "B": 200, "C": 200, "D": 200} if balances is None else balances
    )
    if not balances or any(
        not isinstance(k, str) or not k.strip() or type(v) is not int or v < 0
        for k, v in balances.items()
    ):
        raise ValueError(
            "balances require nonempty buyer IDs and nonnegative integer cash"
        )
    if (
        type(stock) is not int
        or stock < 1
        or type(base_price) is not int
        or base_price < 1
        or type(increment) is not int
        or increment < 0
    ):
        raise ValueError(
            "stock and price must be positive integers; increment nonnegative"
        )
    buyer, token, quantity = input_("buyer_id"), input_("order_id"), input_("quantity")
    orders = field("orders")
    seen, old = orders.contains(token), orders.get(token, {})
    fresh = old.get("status") == "quoted"
    sold = constant("initial_stock") - field("stock")
    price = constant("base_price") + sold * constant("increment")
    charge = quantity * old.get("price", 0)
    you = current_value("buyer_id", "")
    your = orders.get(current_value("order_id", ""), {})
    owned = your.get("buyer_id") == you
    status = choose(owned, your.get("status", "missing"), "missing")
    return Machine(
        name="PostedPriceMarket",
        constants={
            "initial_stock": stock,
            "base_price": base_price,
            "increment": increment,
            "quantities": list(range(stock + 1)),
        },
        fields={
            "stock": state_field(T.integer(minimum=0, maximum=stock), stock),
            "cash": state_field(T.map(T.text(), T.integer(minimum=0)), balances),
            "inventory": state_field(
                T.map(T.text(), T.integer(minimum=0)), dict.fromkeys(balances, 0)
            ),
            "seller_cash": state_field(T.integer(minimum=0), 0),
            "version": state_field(T.integer(minimum=0), 0),
            "closed": state_field(T.boolean(), False),
            "orders": state_field(
                T.map(
                    T.text(),
                    T.record(
                        {
                            "buyer_id": T.text(),
                            "price": T.integer(minimum=1),
                            "version": T.integer(minimum=0),
                            "quantity": T.integer(minimum=0),
                            "status": T.choice(["quoted", "filled", "passed"]),
                        }
                    ),
                ),
                {},
            ),
        },
        commands={
            "quote": Command(
                inputs={"buyer_id": T.text(), "order_id": T.text()},
                timing="before_question",
                effects=(
                    assert_(field("cash").contains(buyer), code="unknown_buyer"),
                    assert_(token.stripped().length() > 0, code="missing_order_id"),
                    assert_(
                        ~seen | (old.get("buyer_id") == buyer), code="order_not_owned"
                    ),
                    when(
                        ~seen,
                        assert_(
                            ~field("closed") & (field("stock") > 0),
                            code="market_closed",
                        ),
                    ),
                    put(
                        "orders",
                        token,
                        record(
                            buyer_id=buyer,
                            price=price,
                            version=field("version"),
                            quantity=0,
                            status="quoted",
                        ),
                        once=True,
                    ),
                ),
            ),
            "buy": Command(
                inputs={
                    "buyer_id": T.text(),
                    "order_id": T.text(),
                    "quantity": T.integer(minimum=0),
                },
                effects=(
                    assert_(
                        seen & (old.get("buyer_id") == buyer), code="order_not_owned"
                    ),
                    assert_(
                        fresh | (old.get("quantity") == quantity), code="order_changed"
                    ),
                    when(
                        fresh & (quantity > 0),
                        assert_(~field("closed"), code="market_closed"),
                    ),
                    when(
                        fresh & (quantity > 0),
                        assert_(
                            old.get("version") == field("version"), code="stale_quote"
                        ),
                    ),
                    when(
                        fresh & (quantity > 0),
                        assert_(quantity <= field("stock"), code="insufficient_stock"),
                    ),
                    when(
                        fresh & (quantity > 0),
                        assert_(
                            charge <= field("cash").get(buyer),
                            code="insufficient_funds",
                        ),
                    ),
                    when(
                        fresh,
                        put(
                            "orders",
                            token,
                            old.with_item("quantity", quantity).with_item(
                                "status", choose(quantity > 0, "filled", "passed")
                            ),
                        ),
                    ),
                    when(
                        fresh & (quantity > 0), set_("stock", field("stock") - quantity)
                    ),
                    when(
                        fresh & (quantity > 0),
                        put("cash", buyer, field("cash").get(buyer) - charge),
                    ),
                    when(
                        fresh & (quantity > 0),
                        put(
                            "inventory", buyer, field("inventory").get(buyer) + quantity
                        ),
                    ),
                    when(
                        fresh & (quantity > 0),
                        set_("seller_cash", field("seller_cash") + charge),
                    ),
                    when(fresh & (quantity > 0), set_("version", field("version") + 1)),
                ),
            ),
        },
        complete_when=field("stock") == 0,
        close_effects=(set_("closed", True),),
        view={
            "status": status,
            "quoted_price": choose(owned, your.get("price"), None),
            "quote_current": owned & (your.get("version") == field("version")),
            "stock": field("stock"),
            "cash": field("cash").get(you),
            "quantity": choose(owned, your.get("quantity", 0), 0),
            "price": price,
            "options": choose(
                owned,
                filter_items(
                    constant("quantities"),
                    item="n",
                    predicate=(local("n") <= field("stock"))
                    & (local("n") * your.get("price", 0) <= field("cash").get(you, 0)),
                ),
                [],
            ),
            "accepting": ~field("closed") & (field("stock") > 0),
        },
    )


DEMO = [
    (
        ("quote", {"buyer_id": buyer, "order_id": buyer + "-1"})
        if command == "quote"
        else ("buy", {"buyer_id": buyer, "order_id": buyer + "-1", "quantity": qty})
    )
    for buyer, qty in [("A", 2), ("B", 1), ("C", 2)]
    for command in ["quote", "buy"]
]
