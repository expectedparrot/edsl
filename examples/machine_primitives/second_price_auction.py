"""Single-unit sealed-bid second-price auction. Dedicated integer balances; immutable bids; explicit settlement."""

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
    fold,
    input_,
    let,
    local,
    map_items,
    record,
    reduce_,
    seeded_integer,
    set_,
    state_field,
    take,
    when,
)


def build_machine(balances=None, reserve=40, seed="auction-2026"):
    balances = dict({"A": 200, "B": 200, "C": 200} if balances is None else balances)
    if not balances or any(
        not isinstance(k, str) or not k.strip() or type(v) is not int or v < 0
        for k, v in balances.items()
    ):
        raise ValueError(
            "balances require nonempty bidder IDs and nonnegative integer cash"
        )
    if type(reserve) is not int or reserve < 1 or not isinstance(seed, str) or not seed:
        raise ValueError("reserve must be a positive integer and seed nonempty text")
    units, max_demand = 1, 1
    if (
        type(units) is not int
        or units < 1
        or type(max_demand) is not int
        or not 1 <= max_demand <= units
    ):
        raise ValueError("require positive integer units and 1 <= max_demand <= units")
    book = field("auction")
    bidder, bids = input_("bidder_id"), input_("bids")
    submitted = book.get("bids")
    known = submitted.contains(bidder)
    bid_type = T.sequence(T.integer(minimum=0))
    # Validate weakly decreasing marginal bids without requiring a sorting callback.
    order_check = fold(
        bids,
        record(previous=choose(bids.length() > 0, bids.at(0), 0), valid=True),
        item="price",
        accumulator="check",
        body=record(
            previous=local("price"),
            valid=local("check").get("valid")
            & (local("price") <= local("check").get("previous")),
        ),
    )
    # Flatten each bidder's bounded demand into unit tickets. Every .at access
    # sits in a lazy branch, so missing bids and abstentions create no tickets.
    owner, unit, tickets = local("owner"), local("unit"), local("tickets")
    owner_bids = submitted.get(owner, [])
    expanded = fold(
        constant("bidders"),
        [],
        item="owner",
        accumulator="rows",
        body=fold(
            constant("unit_indices"),
            local("rows"),
            item="unit",
            accumulator="tickets",
            body=choose(
                unit < owner_bids.length(),
                tickets.appended(
                    record(
                        bidder=owner,
                        unit=unit,
                        price=owner_bids.at(unit),
                        priority=seeded_integer(
                            constant("seed"),
                            0,
                            4294967296,
                            scope="auction",
                            key=owner,
                        ),
                    )
                ),
                tickets,
            ),
        ),
    )
    ranked = reduce_(
        "sort_records",
        filter_items(
            expanded,
            item="ticket",
            predicate=local("ticket").get("price") >= constant("reserve"),
        ),
        fields=["price", "priority", "bidder", "unit"],
        descending=[True, False, False, False],
    )
    winning = take(local("ranked"), constant("units"))
    price = choose(
        local("winners").length() > 0,
        choose(
            local("ranked").length() > constant("units"),
            local("ranked").at(constant("units")).get("price"),
            constant("reserve"),
        ),
        None,
    )
    quantity = filter_items(
        local("winners"),
        item="ticket",
        predicate=local("ticket").get("bidder") == local("id"),
    ).length()
    payment = quantity * choose(local("price") == None, 0, local("price"))

    def by_bidder(value):
        return map_items(
            book.get("cash"),
            key="id",
            value="cash",
            key_expr=local("id"),
            value_expr=value,
        )

    settlement = let(
        "ranked",
        ranked,
        let(
            "winners",
            winning,
            let(
                "price",
                price,
                book.with_item("settled", True)
                .with_item("price", local("price"))
                .with_item("allocations", by_bidder(quantity))
                .with_item("payments", by_bidder(payment))
                .with_item("cash", by_bidder(local("cash") - payment))
                .with_item(
                    "seller_cash",
                    local("winners").length()
                    * choose(local("price") == None, 0, local("price")),
                )
                .with_item("remaining", constant("units") - local("winners").length()),
            ),
        ),
    )
    finish = when(~book.get("settled"), set_("auction", settlement))
    you = current_value("bidder_id", "")
    return Machine(
        name="SecondPriceAuction",
        constants={
            "bidders": sorted(balances),
            "units": units,
            "unit_indices": list(range(max_demand)),
            "max_demand": max_demand,
            "max_cash": max(balances.values()),
            "reserve": reserve,
            "seed": seed,
        },
        fields={
            "auction": state_field(
                T.record(
                    {
                        "bids": T.map(T.text(), bid_type),
                        "cash": T.map(T.text(), T.integer(minimum=0)),
                        "allocations": T.map(T.text(), T.integer(minimum=0)),
                        "payments": T.map(T.text(), T.integer(minimum=0)),
                        "seller_cash": T.integer(minimum=0),
                        "remaining": T.integer(minimum=0),
                        "price": T.optional(T.integer(minimum=1)),
                        "settled": T.boolean(),
                    }
                ),
                {
                    "bids": {},
                    "cash": balances,
                    "allocations": dict.fromkeys(balances, 0),
                    "payments": dict.fromkeys(balances, 0),
                    "seller_cash": 0,
                    "remaining": units,
                    "price": None,
                    "settled": False,
                },
            )
        },
        commands={
            "submit": Command(
                inputs={"bidder_id": T.text(), "bids": bid_type},
                effects=(
                    assert_(
                        constant("bidders").contains(bidder), code="unknown_bidder"
                    ),
                    assert_(
                        ~known | (submitted.get(bidder) == bids), code="bid_changed"
                    ),
                    when(~known, assert_(~book.get("settled"), code="auction_settled")),
                    assert_(
                        bids.length() <= constant("max_demand"), code="too_many_units"
                    ),
                    assert_(order_check.get("valid"), code="bids_not_decreasing"),
                    # Existing bids replay after funds have been spent at settlement.
                    when(
                        ~known,
                        assert_(
                            reduce_("sum", bids) <= book.get("cash").get(bidder),
                            code="insufficient_budget",
                        ),
                    ),
                    when(
                        ~known,
                        set_(
                            "auction",
                            book.with_item("bids", submitted.with_item(bidder, bids)),
                        ),
                    ),
                ),
            ),
            "settle_if_ready": Command(
                inputs={},
                require=submitted.length() == constant("bidders").length(),
                effects=(finish,),
            ),
        },
        # Explicit close also settles an incomplete roster, including an empty auction.
        close_effects=(finish,),
        complete_when=book.get("settled"),
        view={
            "submitted": submitted.contains(you),
            "settled": book.get("settled"),
            "received": submitted.length(),
            "your_bids": submitted.get(you, []),
            "cash": book.get("cash").get(you),
            "allocation": book.get("allocations").get(you, 0),
            "payment": book.get("payments").get(you, 0),
            "price": book.get("price"),
            "allocations": choose(book.get("settled"), book.get("allocations"), {}),
            "remaining": book.get("remaining"),
            "seller_cash": book.get("seller_cash"),
        },
    )


DEMO = [
    ("submit", {"bidder_id": "A", "bids": [90]}),
    ("submit", {"bidder_id": "B", "bids": [70]}),
    ("submit", {"bidder_id": "C", "bids": [50]}),
    ("settle_if_ready", {}),
]
