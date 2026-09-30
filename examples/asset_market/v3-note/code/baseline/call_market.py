"""Version-1 sealed call market: explicit monetary and clearing rules.

The serialized Machine carries all economic parameters. Implementations are
standard runtime capabilities; loading never imports experiment source code.
Amounts in state and rule parameters are integer cents, except quoted prices
and elicited forecasts, which are in dollars. Random streams are specified by
seed and purpose; Python's versioned choice/shuffle behavior is part of v1.
"""

from copy import deepcopy
from decimal import Decimal, ROUND_HALF_UP
import math
import random

from .dsl import Command, Machine, T, algorithm, current, field, input_, state_field


def validate_rules(constants):
    """Reject unsupported or ambiguous policies before a backend starts work."""

    def integer(name, minimum):
        value = constants[name]
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            raise ValueError(f"call market {name} must be an integer >= {minimum}")

    for name, minimum in [
        ("periods", 1),
        ("total_shares", 0),
        ("maximum_buy_quantity", 1),
        ("redemption_cents", 0),
    ]:
        integer(name, minimum)
    if isinstance(constants["seed"], bool) or not isinstance(
        constants["seed"], (str, int)
    ):
        raise ValueError("call market seed must be a string or integer")
    fixed = {
        "rounding": "half_up",
        "money_decimals": 2,
        "tie_breaking": "seeded_price_priority_v1",
        "borrowing": False,
        "short_selling": False,
        "unfilled_orders": "expire",
        "redemption_timing": "after_final_income",
    }
    for key, value in fixed.items():
        if constants.get(key) != value:
            raise ValueError(f"unsupported call market {key}: expected {value!r}")
    if constants["pricing_rule"] not in {
        "marginal_midpoint",
        "marginal_bid",
        "marginal_ask",
    }:
        raise ValueError("unsupported call market pricing_rule")
    keys = constants["forecast_keys"]
    if (
        not isinstance(keys, (list, tuple))
        or any(not isinstance(k, str) or not k for k in keys)
        or len(keys) != len(set(keys))
    ):
        raise ValueError("forecast_keys must be distinct nonempty strings")
    schedule = constants["income_schedule"]
    if (
        not isinstance(schedule, (list, tuple))
        or len(schedule) != 2
        or sorted(r["kind"] for r in schedule) != ["cash_interest", "share_dividend"]
    ):
        raise ValueError(
            "income_schedule must order one interest and one dividend payment"
        )
    for rule in schedule:
        if rule["kind"] == "cash_interest":
            rate = rule["rate"]
            if (
                isinstance(rate, bool)
                or not isinstance(rate, (int, float))
                or not math.isfinite(rate)
                or rate < 0
            ):
                raise ValueError("interest rate must be finite and nonnegative")
        else:
            values, probabilities = rule["values_cents"], rule["probabilities"]
            if not values or any(
                isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values
            ):
                raise ValueError("dividends must be nonnegative integer cents")
            if (
                len(values) != len(probabilities)
                or any(
                    isinstance(p, bool)
                    or not isinstance(p, (int, float))
                    or not math.isfinite(p)
                    or p < 0
                    for p in probabilities
                )
                or not math.isclose(sum(probabilities), 1)
            ):
                raise ValueError("dividend probabilities must sum to one")
            if rule["sampling"] == "python_random_choice_v1":
                if any(not math.isclose(p, 1 / len(values)) for p in probabilities):
                    raise ValueError("choice sampling requires equal probabilities")
            elif rule["sampling"] != "python_random_choices_v1":
                raise ValueError("unsupported dividend sampling rule")


def call_market(
    traders,
    *,
    periods=30,
    seed=1,
    initial_cash_cents=10000,
    initial_shares=4,
    initial_reference_price=14.0,
    redemption_cents=1400,
    pricing_rule="marginal_midpoint",
    maximum_buy_quantity=None,
    income_schedule=None,
    forecast_keys=("forecast_0", "forecast_2", "forecast_5", "forecast_10"),
):
    """Build a portable call-market Machine using standard versioned operations.

    ``income_schedule`` is ordered. Each round trades first, applies this
    schedule, then redeems shares if it is the final economic period.
    Observation pauses do not change ``periods`` or redeem inventory.
    """
    traders = list(traders)
    if (
        not traders
        or any(not isinstance(t, str) or not t for t in traders)
        or len(traders) != len(set(traders))
    ):
        raise ValueError("traders must be distinct nonempty names")
    for value in [initial_cash_cents, initial_shares]:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("initial cash and shares must be nonnegative integers")
    constants = dict(
        periods=periods,
        seed=seed,
        total_shares=initial_shares * len(traders),
        maximum_buy_quantity=(
            max(1, initial_shares * len(traders))
            if maximum_buy_quantity is None
            else maximum_buy_quantity
        ),
        redemption_cents=redemption_cents,
        pricing_rule=pricing_rule,
        rounding="half_up",
        money_decimals=2,
        borrowing=False,
        short_selling=False,
        tie_breaking="seeded_price_priority_v1",
        unfilled_orders="expire",
        redemption_timing="after_final_income",
        forecast_keys=list(forecast_keys),
        income_schedule=deepcopy(
            income_schedule
            if income_schedule is not None
            else [
                {"kind": "cash_interest", "rate": 0.05},
                {
                    "kind": "share_dividend",
                    "values_cents": [40, 100],
                    "probabilities": [0.5, 0.5],
                    "sampling": "python_random_choice_v1",
                },
            ]
        ),
    )
    validate_rules(constants)
    machine = Machine(
        name="CallMarket",
        constants=constants,
        fields={
            "accounts": state_field(
                T.map(),
                {
                    t: {
                        "cash_cents": initial_cash_cents,
                        "shares": initial_shares,
                        "history": [],
                    }
                    for t in traders
                },
            ),
            "orders": state_field(T.map(), {}),
            "order_log": state_field(T.sequence(), []),
            "tape": state_field(T.sequence(), []),
            "period": state_field(T.integer(), 1),
            "last_price": state_field(T.optional(T.number()), initial_reference_price),
            "finished": state_field(T.boolean(), False),
        },
        commands={
            "submit": Command(
                inputs={"trader": T.text(), "period": T.integer(), "decision": T.map()},
                effects=(
                    algorithm(
                        "call_market_submit",
                        trader=input_("trader"),
                        period=input_("period"),
                        decision=input_("decision"),
                    ),
                ),
            ),
            "settle": Command(
                inputs={"period": T.integer()},
                effects=(algorithm("call_market_settle", period=input_("period")),),
            ),
        },
        view={
            "period": field("period"),
            "tape": field("tape"),
            "last_price": field("last_price"),
            "your_account": field("accounts").get(current("name")),
            "finished": field("finished"),
        },
        algorithms=("call_market_submit@1", "call_market_settle@1"),
    )
    machine.validate()
    return machine


def cents(value):
    return int(
        (Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    )


def submit_order(state, inputs, constants):
    """Commit a sealed order without changing balances or the public tape."""
    trader, period, answer = inputs["trader"], inputs["period"], inputs["decision"]
    if (
        period != state["period"]
        or state["finished"]
        or trader not in state["accounts"]
    ):
        raise ValueError("Invalid trader, stale period, or finished market")
    if trader in state["orders"]:
        raise ValueError("Trader already submitted this period")
    account = state["accounts"][trader]
    error = None
    for key in constants["forecast_keys"]:
        val = answer.get(key)
        if (
            isinstance(val, bool)
            or not isinstance(val, (int, float))
            or not math.isfinite(val)
            or val < 0
        ):
            raise ValueError(f"{key} must be a finite nonnegative number")
    side, qty, price = answer.get("side"), answer.get("quantity"), answer.get("price")
    if side not in {"buy", "sell", "hold"}:
        error = "invalid side"
    elif isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
        error = "quantity must be a nonnegative integer"
    elif (
        isinstance(price, bool)
        or not isinstance(price, (int, float))
        or not math.isfinite(price)
        or price < 0
    ):
        error = "price must be finite and nonnegative"
    elif side != "hold" and (cents(price) <= 0 or qty == 0):
        error = "active orders require positive price and quantity"
    limit = cents(price) if error is None else 0
    accepted_qty = 0
    if error is None and side == "buy":
        accepted_qty = min(
            qty, account["cash_cents"] // limit, constants["maximum_buy_quantity"]
        )
    elif error is None and side == "sell":
        accepted_qty = min(qty, account["shares"])
    state["orders"][trader] = {
        "trader": trader,
        "period": period,
        "decision": dict(answer),
        "side": side,
        "limit_cents": limit,
        "accepted_quantity": accepted_qty,
        "rejection": error,
    }


def settle_market(state, inputs, constants):
    """Maximal crossing volume, configured uniform price, then scheduled income."""
    period = inputs["period"]
    if period != state["period"] or state["finished"]:
        raise ValueError("Settlement must occur exactly once per current period")
    if set(state["orders"]) != set(state["accounts"]):
        raise ValueError("Cannot clear until every trader has submitted")
    # A reproducible per-period lottery breaks equal-price ties independently of
    # completion order. Admission bounds the quantities expanded into unit orders.
    names = sorted(state["accounts"])
    random.Random(f"{constants['seed']}:priority:{period}").shuffle(names)
    priority = {name: i for i, name in enumerate(names)}
    bids, asks = [], []
    for name, order in state["orders"].items():
        target = bids if order["side"] == "buy" else asks
        target.extend(
            (order["limit_cents"], priority[name], name)
            for _ in range(order["accepted_quantity"])
        )
    bids.sort(key=lambda row: (-row[0], row[1]))
    asks.sort(key=lambda row: (row[0], row[1]))
    volume = 0
    for bid, ask in zip(bids, asks):
        if bid[0] < ask[0]:
            break
        volume += 1
    price = None
    if volume:
        bid, ask = bids[volume - 1][0], asks[volume - 1][0]
        price = {
            "marginal_midpoint": (bid + ask + 1) // 2,
            "marginal_bid": bid,
            "marginal_ask": ask,
        }[constants["pricing_rule"]]
    cash_before = sum(a["cash_cents"] for a in state["accounts"].values())
    shares_before = sum(a["shares"] for a in state["accounts"].values())
    fills = {name: 0 for name in names}
    for bid, ask in zip(bids[:volume], asks[:volume]):
        buyer, seller = state["accounts"][bid[2]], state["accounts"][ask[2]]
        buyer["cash_cents"] -= price
        seller["cash_cents"] += price
        buyer["shares"] += 1
        seller["shares"] -= 1
        fills[bid[2]] += 1
        fills[ask[2]] -= 1
    assert sum(a["cash_cents"] for a in state["accounts"].values()) == cash_before
    assert (
        sum(a["shares"] for a in state["accounts"].values())
        == shares_before
        == constants["total_shares"]
    )
    dividend_rule = next(
        r for r in constants["income_schedule"] if r["kind"] == "share_dividend"
    )
    rng = random.Random(f"{constants['seed']}:dividend:{period}")
    values = dividend_rule["values_cents"]
    dividend = (
        rng.choice(values)
        if dividend_rule["sampling"] == "python_random_choice_v1"
        else rng.choices(values, weights=dividend_rule["probabilities"], k=1)[0]
    )
    total_interest = 0
    for name, account in state["accounts"].items():
        interest = 0
        for rule in constants["income_schedule"]:
            if rule["kind"] == "cash_interest":
                interest = int(
                    (
                        Decimal(account["cash_cents"]) * Decimal(str(rule["rate"]))
                    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                )
                account["cash_cents"] += interest
                total_interest += interest
            else:
                account["cash_cents"] += dividend * account["shares"]
        assert account["cash_cents"] >= 0 and account["shares"] >= 0
        account["history"].append(
            {
                **state["orders"][name],
                "fill": fills[name],
                "transaction_price": None if price is None else price / 100,
                "interest": interest / 100,
                "dividend_per_share": dividend / 100,
            }
        )
    if price is not None:
        state["last_price"] = price / 100
    row = {
        "period": period,
        "price": None if price is None else price / 100,
        "reference_price": state["last_price"],
        "volume": volume,
        "dividend": dividend / 100,
        "total_interest": total_interest / 100,
        "total_cash": sum(a["cash_cents"] for a in state["accounts"].values()) / 100,
        "total_shares": shares_before,
    }
    assert (
        cents(row["total_cash"])
        == cash_before + total_interest + dividend * shares_before
    )
    state["tape"].append(row)
    state["order_log"].extend(state["orders"][name] for name in sorted(names))
    state["orders"] = {}
    if period == constants["periods"]:
        for account in state["accounts"].values():
            account["redeemed_shares"] = account["shares"]
            account["cash_cents"] += constants["redemption_cents"] * account["shares"]
            account["shares"] = 0
        state["finished"] = True
    state["period"] += 1
