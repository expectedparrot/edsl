"""Version-1 sealed call market: explicit monetary and clearing rules.

The serialized Machine carries all economic parameters. Implementations are
standard runtime capabilities; loading never imports experiment source code.
Amounts in state and rule parameters are integer cents, except quoted prices
and elicited forecasts, which are in dollars. Random streams are specified by
seed and purpose; Python's versioned choice/shuffle behavior is part of v1.
"""

from decimal import Decimal, ROUND_HALF_UP
import random

from .dsl import Command, Machine, T, algorithm, current, field, input_, state_field
from .market_rules import (
    CallMarketRules,
    MarketConstants,
    WireInterest,
    WireDividend,
    PricingRule,
    DividendSampling,
)
from .market_records import (
    Account,
    AcceptedOrder,
    DecisionSchema,
    OrderIntent,
    TradeFill,
    RoundOutcome,
    cents,
)


def validate_rules(constants):
    """Validate original wire data using the same constraints as authoring."""
    MarketConstants.from_dict(constants)


def call_market(
    traders,
    *,
    rules: CallMarketRules | None = None,
    seed: str | int = 1,
    **legacy_options,
) -> Machine:
    """Build a portable v1 market from validated :class:`CallMarketRules`.

    The original keyword arguments remain supported. They cannot be mixed with
    ``rules``: an ambiguous override is an authoring error. Income is ordered;
    terminal redemption follows the final income payment.
    """
    traders = list(traders)
    if (
        not traders
        or any(not isinstance(t, str) or not t for t in traders)
        or len(traders) != len(set(traders))
    ):
        raise ValueError("traders must be distinct nonempty names")
    if rules is not None and legacy_options:
        raise ValueError("rules cannot be combined with legacy rule keywords")
    if rules is None:
        rules = CallMarketRules.from_legacy(**legacy_options)
    if not isinstance(rules, CallMarketRules):
        raise TypeError(
            "rules must be CallMarketRules; use CallMarketRules.from_dict for JSON"
        )
    constants = rules.to_constants(len(traders), seed)
    machine = Machine(
        name="CallMarket",
        constants=constants,
        fields={
            "accounts": state_field(
                T.map(),
                {
                    t: Account(
                        cash_cents=rules.endowment.cash_cents,
                        shares=rules.endowment.shares,
                    ).to_dict()
                    for t in traders
                },
            ),
            "orders": state_field(T.map(), {}),
            "order_log": state_field(T.sequence(), []),
            "tape": state_field(T.sequence(), []),
            "period": state_field(T.integer(), 1),
            "last_price": state_field(
                T.optional(T.number()), rules.initial_reference_price
            ),
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
    rules = MarketConstants.from_dict(constants)
    DecisionSchema(forecast_keys=rules.forecast_keys).validate_forecasts(answer)
    side, qty, price = answer.get("side"), answer.get("quantity"), answer.get("price")
    error = OrderIntent.rejection(answer)
    limit = cents(price) if error is None else 0
    accepted_qty = 0
    if error is None and side == "buy":
        accepted_qty = min(
            qty, account["cash_cents"] // limit, rules.maximum_buy_quantity
        )
    elif error is None and side == "sell":
        accepted_qty = min(qty, account["shares"])
    state["orders"][trader] = AcceptedOrder.from_dict(
        {
            "trader": trader,
            "period": period,
            "decision": dict(answer),
            "side": side,
            "limit_cents": limit,
            "accepted_quantity": accepted_qty,
            "rejection": error,
        }
    ).to_dict()


def settle_market(state, inputs, constants):
    """Maximal crossing volume, configured uniform price, then scheduled income."""
    rules = MarketConstants.from_dict(constants)
    period = inputs["period"]
    if period != state["period"] or state["finished"]:
        raise ValueError("Settlement must occur exactly once per current period")
    if set(state["orders"]) != set(state["accounts"]):
        raise ValueError("Cannot clear until every trader has submitted")
    # A reproducible per-period lottery breaks equal-price ties independently of
    # completion order. Admission bounds the quantities expanded into unit orders.
    names = sorted(state["accounts"])
    random.Random(f"{rules.seed}:priority:{period}").shuffle(names)
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
            PricingRule.MARGINAL_MIDPOINT: (bid + ask + 1) // 2,
            PricingRule.MARGINAL_BID: bid,
            PricingRule.MARGINAL_ASK: ask,
        }[rules.pricing_rule]
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
        == rules.total_shares
    )
    dividend_rule = next(
        r for r in rules.income_schedule if isinstance(r, WireDividend)
    )
    rng = random.Random(f"{rules.seed}:dividend:{period}")
    values = dividend_rule.values_cents
    dividend = (
        rng.choice(values)
        if dividend_rule.sampling == DividendSampling.CHOICE
        else rng.choices(values, weights=dividend_rule.probabilities, k=1)[0]
    )
    total_interest = 0
    for name, account in state["accounts"].items():
        interest = 0
        for rule in rules.income_schedule:
            if isinstance(rule, WireInterest):
                interest = int(
                    (Decimal(account["cash_cents"]) * Decimal(str(rule.rate))).quantize(
                        Decimal("1"), rounding=ROUND_HALF_UP
                    )
                )
                account["cash_cents"] += interest
                total_interest += interest
            else:
                account["cash_cents"] += dividend * account["shares"]
        assert account["cash_cents"] >= 0 and account["shares"] >= 0
        account["history"].append(
            TradeFill.from_dict(
                {
                    **state["orders"][name],
                    "fill": fills[name],
                    "transaction_price": None if price is None else price / 100,
                    "interest": interest / 100,
                    "dividend_per_share": dividend / 100,
                }
            ).to_dict()
        )
    if price is not None:
        state["last_price"] = price / 100
    row = RoundOutcome.from_dict(
        {
            "period": period,
            "price": None if price is None else price / 100,
            "reference_price": state["last_price"],
            "volume": volume,
            "dividend": dividend / 100,
            "total_interest": total_interest / 100,
            "total_cash": sum(a["cash_cents"] for a in state["accounts"].values())
            / 100,
            "total_shares": shares_before,
        }
    ).to_dict()
    assert (
        cents(row["total_cash"])
        == cash_before + total_interest + dividend * shares_before
    )
    state["tape"].append(row)
    state["order_log"].extend(state["orders"][name] for name in sorted(names))
    state["orders"] = {}
    if period == rules.periods:
        for account in state["accounts"].values():
            account["redeemed_shares"] = account["shares"]
            account["cash_cents"] += rules.redemption_cents * account["shares"]
            account["shares"] = 0
        state["finished"] = True
    state["period"] += 1
