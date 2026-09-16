"""Serializable market workflow with private observations and atomic settlement.

Only the trader answerer uses an LLM. The exchange is a deterministic, versioned
shared-state transition. See README.md for choices not specified by the slides.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from itertools import combinations
import math
from pathlib import Path
import random

from edsl import Agent, QuestionDict, QuestionFreeText, Survey
from edsl.sharedstate import (
    Command, Machine, SharedState, SharedStateMap, T, algorithm,
    current, field, input_, state_field,
)
from edsl.sharedstate.dsl_runtime import default_runtime
from edsl.workflows import Workflow, role


ROOT = Path(__file__).parent
THEORY = {
    "RA": "You are a rational arbitrageur. Compare the asset's expected dividend and resale return with the 5% cash return. Buy when the expected excess return clears a meaningful threshold, sell overpriced holdings, and avoid trades without an advantage.",
    "MC": "You are a momentum chaser. Rising prices encourage you to buy because you expect the rise to continue. When prices dip, sell. Recent price direction is the main influence on your forecasts and orders.",
    "BT": "You are a bubble timer. You try to ride a rising market and exit before the peak. Monitor the speed of price increases: when the rise decelerates, take profits and reduce your position. You can buy above fundamental value if you expect a higher resale price.",
    "PC": "You are a precommitter. Before trading begins, fix the periods in which you intend to buy and sell. State that plan in your first rationale. Keep following that plan in later periods rather than changing it in response to the tape, subject to your cash and share constraints.",
    "NT": "You are a noise trader. You have a vague prior about the price and update it inconsistently. Your forecasts, buy/sell choices, quotes, and quantities need not fit one coherent strategy.",
    "OC": "You are an overconfident contrarian. Trust your judgment strongly. Buy after prices fall because you expect a recovery. Avoid selling a losing position: wait for it to recover. Track your own purchase prices in deciding whether a holding is a loser.",
}
KEYS = ["forecast_0", "forecast_2", "forecast_5", "forecast_10", "side", "price", "quantity", "rationale"]


def compositions():
    return ["+".join(group) for n in range(1, 7) for group in combinations(THEORY, n)]


def build_agents(treatment: str, seed: int = 1):
    if treatment == "baseline":
        types = ["baseline"] * 12
    elif treatment == "evolved":
        types = ["trend_reader"] * 7 + ["noise"] * 3 + ["reversion_rider"] * 2
    else:
        parts = treatment.split("+")
        if not parts or len(set(parts)) != len(parts) or any(p not in THEORY for p in parts):
            raise ValueError(f"Unknown or repeated archetype in {treatment!r}")
        types = [parts[i % len(parts)] for i in range(12)]
    random.Random(seed).shuffle(types)
    agents = []
    for seat, kind in enumerate(types):
        persona = THEORY.get(kind, "")
        if kind in {"trend_reader", "noise", "reversion_rider"}:
            persona = (ROOT / "personas" / f"{kind}.txt").read_text()
        agents.append(Agent(
            name=f"trader-{seat:02d}", traits={"role": "trader", "seat": seat},
            instruction="You are a participant in an experimental asset market. Maximize your final cash wealth.\n" + persona,
        ))
    agents.append(Agent(name="exchange", traits={"role": "exchange"}))
    return agents, dict(zip([a.name for a in agents[:-1]], types))


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def submit_order(state, inputs, constants):
    """Commit a sealed order without changing balances or the public tape."""
    trader, period, answer = inputs["trader"], inputs["period"], inputs["decision"]
    if period != state["period"] or state["finished"] or trader not in state["accounts"]:
        raise ValueError("Invalid trader, stale period, or finished market")
    if trader in state["orders"]:
        raise ValueError("Trader already submitted this period")
    account = state["accounts"][trader]
    error = None
    for key in KEYS[:4]:
        val = answer.get(key)
        if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
            raise ValueError(f"{key} must be a finite nonnegative number")
    side, qty, price = answer.get("side"), answer.get("quantity"), answer.get("price")
    if side not in {"buy", "sell", "hold"}:
        error = "invalid side"
    elif isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
        error = "quantity must be a nonnegative integer"
    elif isinstance(price, bool) or not isinstance(price, (int, float)) or not math.isfinite(price) or price < 0:
        error = "price must be finite and nonnegative"
    elif side != "hold" and (cents(price) <= 0 or qty == 0):
        error = "active orders require positive price and quantity"
    limit = cents(price) if error is None else 0
    accepted_qty = 0
    if error is None and side == "buy":
        accepted_qty = min(qty, account["cash_cents"] // limit, 48)
    elif error is None and side == "sell":
        accepted_qty = min(qty, account["shares"])
    state["orders"][trader] = {
        "trader": trader, "period": period, "decision": dict(answer),
        "side": side, "limit_cents": limit, "accepted_quantity": accepted_qty,
        "rejection": error,
    }


def settle_market(state, inputs, constants):
    """Maximal crossing volume, a single marginal midpoint price, then income."""
    period = inputs["period"]
    if period != state["period"] or state["finished"]:
        raise ValueError("Settlement must occur exactly once per current period")
    if set(state["orders"]) != set(state["accounts"]):
        raise ValueError("Cannot clear until every trader has submitted")
    # A reproducible per-period lottery breaks equal-price ties independently of
    # completion order. Orders are expanded into at most 48 units per trader.
    names = sorted(state["accounts"])
    random.Random(f"{constants['seed']}:priority:{period}").shuffle(names)
    priority = {name: i for i, name in enumerate(names)}
    bids, asks = [], []
    for name, order in state["orders"].items():
        target = bids if order["side"] == "buy" else asks
        target.extend((order["limit_cents"], priority[name], name) for _ in range(order["accepted_quantity"]))
    bids.sort(key=lambda row: (-row[0], row[1]))
    asks.sort(key=lambda row: (row[0], row[1]))
    volume = 0
    for bid, ask in zip(bids, asks):
        if bid[0] < ask[0]:
            break
        volume += 1
    price = (bids[volume-1][0] + asks[volume-1][0] + 1) // 2 if volume else None
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
    assert sum(a["shares"] for a in state["accounts"].values()) == shares_before == 48
    dividend = random.Random(f"{constants['seed']}:dividend:{period}").choice([40, 100])
    total_interest = 0
    for name, account in state["accounts"].items():
        interest = (account["cash_cents"] * 5 + 50) // 100
        total_interest += interest
        account["cash_cents"] += interest + dividend * account["shares"]
        assert account["cash_cents"] >= 0 and account["shares"] >= 0
        account["history"].append({
            **state["orders"][name], "fill": fills[name],
            "transaction_price": None if price is None else price / 100,
            "interest": interest / 100, "dividend_per_share": dividend / 100,
        })
    if price is not None:
        state["last_price"] = price / 100
    row = {
        "period": period, "price": None if price is None else price / 100,
        "reference_price": state["last_price"], "volume": volume,
        "dividend": dividend / 100, "total_interest": total_interest / 100,
        "total_cash": sum(a["cash_cents"] for a in state["accounts"].values()) / 100,
        "total_shares": shares_before,
    }
    assert cents(row["total_cash"]) == cash_before + total_interest + dividend * shares_before
    state["tape"].append(row)
    state["order_log"].extend(state["orders"][name] for name in sorted(names))
    state["orders"] = {}
    if period == constants["periods"]:
        for account in state["accounts"].values():
            account["redeemed_shares"] = account["shares"]
            account["cash_cents"] += 1400 * account["shares"]
            account["shares"] = 0
        state["finished"] = True
    state["period"] += 1


def market_runtime():
    runtime = default_runtime()
    runtime.register("asset_market_submit", 1, submit_order)
    runtime.register("asset_market_settle", 1, settle_market)
    return runtime


def build_experiment(treatment="baseline", *, periods=30, seed=1, state_id="asset-market"):
    if not 1 <= periods <= 100:
        raise ValueError("periods must be between 1 and 100")
    agents, types = build_agents(treatment, seed)
    accounts = {a.name: {"cash_cents": 10000, "shares": 4, "history": []} for a in agents[:-1]}
    machine = Machine(
        name="AssetCallMarket", constants={"periods": periods, "seed": seed},
        fields={
            "accounts": state_field(T.map(), accounts),
            "orders": state_field(T.map(), {}),
            "order_log": state_field(T.sequence(), []),
            "tape": state_field(T.sequence(), []),
            "period": state_field(T.integer(), 1),
            "last_price": state_field(T.number(), 14.0),
            "finished": state_field(T.boolean(), False),
        },
        commands={
            "submit": Command(
                inputs={"trader": T.text(), "period": T.integer(), "decision": T.map()},
                effects=(algorithm("asset_market_submit", trader=input_("trader"), period=input_("period"), decision=input_("decision")),),
            ),
            "settle": Command(
                inputs={"period": T.integer()},
                effects=(algorithm("asset_market_settle", period=input_("period")),),
            ),
        },
        view={
            "period": field("period"), "tape": field("tape"),
            "last_price": field("last_price"),
            "your_account": field("accounts").get(current("name")),
            "finished": field("finished"),
        },
        algorithms=("asset_market_submit@1", "asset_market_settle@1"),
    )
    states = SharedStateMap(SharedState(market=machine), state_id=state_id)
    market = states.by("session").market
    builder = Workflow(
        "Building Traders: asset call market",
        metadata={"treatment": treatment, "periods": periods, "seed": seed,
                  "persona_assignment": types, "source": "Ngo et al., slides dated 2026-09-18",
                  "replication": "design reconstruction; see README.md"},
    )
    # Fixed horizon; dependencies materialize the 12-way fan-out / fan-in barrier.
    previous = None
    for period in range(1, periods + 1):
        question = QuestionDict(
            question_name="decision",
            question_text=(
                f"Period {period} of {periods}; {periods-period+1} trading periods including this one remain. "
                "You began with $100 cash and 4 shares. Submit one sealed limit order: buy, sell, or hold. "
                "All trades this period occur at one clearing price after everyone submits. "
                "You cannot borrow cash or short shares. Buy quantity is capped by cash divided by your limit price; sell quantity by your shares. "
                "Quotes round to cents; unmatched orders expire after this period. "
                "At period end, post-trade cash earns 5% interest, then each held share pays a common dividend of $0.40 or $1.00, each equally likely. "
                f"After period {periods}'s payments, all remaining shares are redeemed for $14 each and you keep all cash. "
                "The asset's fundamental value is $14 each period. "
                "The initial reference quote is $14; it is not an observed trade. "
                "Current private account (cash_cents is in cents, shares are units, history includes your previous decisions and fills): "
                "{{ shared_state.market.your_account }}. "
                "Public history (price=null means no trade): {{ shared_state.market.tape }}. "
                "Last transaction price, or initial reference if none: {{ shared_state.market.last_price }}. "
                "Forecast the market price now and 2, 5, and 10 periods ahead. For horizons beyond the final period, report the $14 redemption value. "
                "Return forecast_0, forecast_2, forecast_5, forecast_10 in dollars, side ('buy', 'sell', or 'hold'), "
                "price in dollars, integer quantity, and a brief rationale. For hold use price=0 and quantity=0. "
                "If you previously committed to a plan, retain it in your rationale."
            ),
            answer_keys=KEYS,
            value_types=["float"] * 4 + ["str", "float", "int", "str"],
            include_comment=False,
        )
        decisions = builder.step(
            f"orders-{period}", Survey([question]), assigned_to=role("trader"),
            after=previous, visible_to=role("exchange"), reads=(market.read(),),
            writes=(market.submit(trader=current.agent.name, period=period, decision=question.answer),),
            metadata={"period": period, "phase": "sealed orders"},
        )
        previous = builder.step(
            f"settle-{period}",
            Survey([QuestionFreeText(question_name="settlement", question_text="Run deterministic market settlement.")]),
            assigned_to=role("exchange"), after=decisions,
            writes=(market.settle(period=period),),
            metadata={"period": period, "phase": "clearing, income, final redemption"},
        )
    return builder.compile(), states, agents


def metrics(tape):
    trades = [row for row in tape if row["price"] is not None]
    peak = max(trades, key=lambda row: row["price"]) if trades else None
    return {
        "periods": len(tape), "trading_periods": len(trades),
        "no_trade_periods": len(tape) - len(trades),
        "volume": sum(row["volume"] for row in tape),
        "peak_price": peak["price"] if peak else None,
        "peak_period": peak["period"] if peak else None,
        "peak_fraction": peak["period"] / len(tape) if peak else None,
        "RAD_traded_periods": sum(abs(row["price"] - 14) / 14 for row in trades) / len(trades) if trades else None,
        "RD_traded_periods": sum((row["price"] - 14) / 14 for row in trades) / len(trades) if trades else None,
        "above_1_25F": peak["price"] >= 17.5 if peak else False,
        "post_peak_drawdown": (peak["price"] - min(row["price"] for row in trades if row["period"] >= peak["period"])) / peak["price"] if peak else None,
    }
