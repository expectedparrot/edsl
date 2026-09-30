"""Binary LMSR built from arithmetic, stable logsumexp, and map updates.

This matches the legacy market's unconstrained purchases (cash can go negative).
It adds an explicit guard against trading after settlement. Financial policy is
an example choice, not a new primitive in the interpreter.
"""

from edsl.sharedstate import (
    Command,
    Machine,
    T,
    choose,
    constant,
    exp,
    expr,
    field,
    input_,
    let,
    local,
    logsumexp,
    map_items,
    record,
    set_,
    state_field,
)


def build_machine(liquidity=50, initial_cash=100):
    if liquidity <= 0:
        raise ValueError("liquidity must be positive")
    book = field("market")
    liquidity_ref = constant("liquidity")

    def cost(quantities):
        # Authoring helper: this returns an expression, never an execution callback.
        return liquidity_ref * logsumexp(
            [
                quantities.get("yes") / liquidity_ref,
                quantities.get("no") / liquidity_ref,
            ]
        )

    side = choose(input_("action") == "buy_yes", "yes", "no")
    quantity = input_("quantity")
    quantities = book.get("quantities")
    new_quantities = quantities.with_item(
        local("side"), quantities.get(local("side")) + quantity
    )
    portfolio = book.get("portfolios").get(
        input_("trader"), record(cash=constant("initial_cash"), yes=0, no=0)
    )
    updated = (
        local("portfolio")
        .with_item("cash", local("portfolio").get("cash") - local("paid"))
        .with_item(local("side"), local("portfolio").get(local("side")) + quantity)
    )
    traded = (
        book.with_item("quantities", local("quantities"))
        .with_item(
            "portfolios", book.get("portfolios").with_item(input_("trader"), updated)
        )
        .with_item(
            "trades",
            book.get("trades").appended(
                record(
                    trader=input_("trader"),
                    action=input_("action"),
                    quantity=quantity,
                    cost=local("paid"),
                )
            ),
        )
    )
    trade = choose(
        input_("action") == "hold",
        book,
        let(
            "side",
            side,
            let(
                "quantities",
                new_quantities,
                let(
                    "paid",
                    cost(local("quantities")) - cost(quantities),
                    let("portfolio", portfolio, traded),
                ),
            ),
        ),
    )
    settled = map_items(
        book.get("portfolios"),
        key="trader",
        value="portfolio",
        key_expr=local("trader"),
        value_expr=local("portfolio").with_item(
            "settled_wealth",
            local("portfolio").get("cash")
            + local("portfolio").get(choose(input_("outcome"), "yes", "no")),
        ),
    )
    # A log-domain logistic form avoids overflow at extreme quantities.
    difference = (quantities.get("no") - quantities.get("yes")) / liquidity_ref
    yes_price = exp(logsumexp([0, difference]) * -1)
    return Machine(
        name="PrimitiveBinaryMarket",
        constants={"liquidity": liquidity, "initial_cash": initial_cash},
        fields={
            "market": state_field(
                T.map(),
                {
                    "quantities": {"yes": 0, "no": 0},
                    "portfolios": {},
                    "trades": [],
                    "outcome": None,
                },
            )
        },
        commands={
            "trade": Command(
                inputs={
                    "trader": T.text(),
                    "action": T.choice(["buy_yes", "buy_no", "hold"]),
                    "quantity": T.number(minimum=0),
                },
                require=book.get("outcome") == None,
                effects=(set_("market", trade),),
            ),
            "settle": Command(
                inputs={"outcome": T.boolean()},
                require=book.get("outcome") == None,
                effects=(
                    set_(
                        "market",
                        book.with_item("outcome", input_("outcome")).with_item(
                            "portfolios", settled
                        ),
                    ),
                ),
            ),
        },
        view={
            "portfolios": book.get("portfolios"),
            "trades": book.get("trades"),
            "prices": record(yes=yes_price, no=expr("subtract", 1, yes_price)),
        },
    )


DEMO = [
    ("trade", {"trader": "A", "action": "buy_yes", "quantity": 10}),
    ("trade", {"trader": "B", "action": "buy_no", "quantity": 5}),
    ("settle", {"outcome": True}),
]
