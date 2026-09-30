"""Self-contained market construction for the note's explanatory appendix.

This is a presentation refactor, not the frozen source used for model calls.
It builds the same workflow, initial shared state, agents, and prompts as
speculative_prompts.build_experiment without importing other example modules.
Only EDSL and Python's standard library are required.
"""

from decimal import Decimal, ROUND_HALF_UP
import math
import random

from edsl import Agent, QuestionDict, QuestionFreeText, Survey
from edsl.sharedstate import (
    Command, Machine, SharedState, SharedStateMap, T, algorithm,
    current, field, input_, state_field,
)
from edsl.sharedstate.dsl_runtime import default_runtime
from edsl.workflows import Workflow, role



KEYS = ["forecast_0", "forecast_2", "forecast_5", "forecast_10", "side", "price", "quantity", "rationale"]


VERSION = "speculative-v1"


COMPOSITION = "RA+MC+BT+PC+NT+OC"


COMMON = (
    "You are a participant in an experimental asset market. Maximize your final cash wealth. "
    "Make decisions as the trader described below, including that trader's beliefs, "
    "emotions, and habits. Your forecasts concern prices that other participants may "
    "actually pay, which can differ from your own valuation of the dividends. "
    "Buying for later resale is an available strategy; so is selling to take profits. "
    "Use the actual public history and your private experience.\n\n"
)


PERSONAS = {
    "RA": (
        "You are a rational arbitrageur. Compare the asset's expected dividend and "
        "resale return with the 5% cash return. Buy when the expected excess return "
        "clears a meaningful threshold, sell overpriced holdings, and avoid trades "
        "without an advantage."
    ),
    "MC": (
        "You are a momentum chaser. You feel the opportunity cost of missing a rally "
        "strongly. Before there is a price history, you are optimistic that speculative "
        "interest can build and are willing to take a small early position on that belief. "
        "When transaction prices rise, extrapolate the trend into your near-term "
        "forecasts and consider raising your bid to get filled. A rising market can "
        "make you increase your position. When prices dip, sell rather than patiently "
        "waiting for recovery. Your optimism is your belief, not evidence of orders "
        "you have not seen."
    ),
    "BT": (
        "You are a bubble timer. You believe you can profit from a speculative upswing "
        "and sell before other traders rush for the exit. Early in the session you "
        "are willing to build a position in anticipation of resale demand, even if "
        "the dividend valuation alone does not justify the purchase. Compare your "
        "purchase price with what you believe someone will pay before you exit. "
        "During an accelerating rise, ride the trend; when price growth slows or "
        "your planned exit approaches, offer shares to lock in profits. State and "
        "remember an exit plan. Do not assume that another buyer is guaranteed."
    ),
    "PC": (
        "You are a precommitter. In your first decision, choose a concrete schedule "
        "of buying periods and selling periods that you believe will profit from "
        "changes in market demand. You may sell some initial shares as well as buy "
        "additional shares. Include both buying and selling in your schedule. State "
        "the schedule in your first rationale and repeat it in later rationales. "
        "Follow those periods despite intervening news; choose executable limit "
        "prices and quantities using your current expectations, cash, and inventory."
    ),
    "NT": (
        "You are a noise trader. You trade on hunches and a vague, changeable sense "
        "of what others might pay. At the opening you are excited by the possibility "
        "of speculative demand and form your own optimistic price guess. Your "
        "confidence and mood fluctuate: you sometimes buy on enthusiasm, sometimes "
        "sell to take a quick profit or because you become uneasy. You do not force "
        "each forecast or quote to follow a consistent dividend valuation. Pick "
        "specific forecasts and a concrete order reflecting your current hunch. "
        "You have no private factual information about other traders."
    ),
    "OC": (
        "You are an overconfident contrarian. You trust your own optimistic assessment "
        "of resale opportunities and believe you spot bargains others overlook. "
        "You are willing to buy early if the market has not yet recognized your "
        "expected upside. After a price decline, consider buying more because you "
        "expect recovery. Track your purchase prices. Avoid realizing a loss: prefer "
        "to wait for recovery instead of selling a losing position. You can take "
        "profits on winning holdings. Treat your confidence as a personal belief, "
        "not as knowledge of future market prices."
    ),
}


def question_text(period, periods):
    return (
        f"Period {period} of {periods}; {periods - period + 1} trading periods remain, including this one.\n\n"
        "MARKET RULES\n"
        "There are 12 traders. Each began with $100 cash and 4 shares. Submit one "
        "sealed limit order: buy, sell, or hold. A buy limit is the most you will "
        "pay per share; a sell limit is the least you will accept. The exchange "
        "matches crossing orders and all filled orders receive one clearing price. "
        "Unmatched orders expire. You cannot borrow or short shares. Buy quantities "
        "are capped by cash divided by your limit; sells by your inventory. Quotes "
        "round to cents. After trading, cash earns 5% interest, then each held share "
        "pays the same dividend: $0.40 or $1.00, equally likely. "
        f"After period {periods}'s income, each remaining share is redeemed for $14; you keep all cash.\n\n"
        "YOUR ACCOUNT (all money below is in dollars)\n"
        "Cash: {{ shared_state.market.your_account.cash_cents / 100 }}. "
        "Shares: {{ shared_state.market.your_account.shares }}.\n"
        "Your previous decisions and fills:\n"
        "{% for h in shared_state.market.your_account.history %}"
        "Period {{ h.period }}: {{ h.side }} {{ h.decision.quantity }} at limit "
        "{{ h.limit_cents / 100 }}; admitted {{ h.accepted_quantity }}; signed fill "
        "{{ h.fill }}; market price {{ h.transaction_price }}; interest "
        "{{ h.interest }}; dividend per share {{ h.dividend_per_share }}. "
        "Your forecasts (now, +2, +5, +10): {{ h.decision.forecast_0 }}, "
        "{{ h.decision.forecast_2 }}, {{ h.decision.forecast_5 }}, "
        "{{ h.decision.forecast_10 }}. Your rationale: {{ h.decision.rationale }}\n"
        "{% else %}No previous decisions.\n{% endfor %}\n"
        "PUBLIC HISTORY\n"
        "{% for row in shared_state.market.tape %}"
        "Period {{ row.period }}: transaction price {{ row.price }}, volume "
        "{{ row.volume }}, dividend per share {{ row.dividend }}, total cash "
        "{{ row.total_cash }}, total shares {{ row.total_shares }}, total interest "
        "{{ row.total_interest }}.\n"
        "{% else %}The market has not traded yet. There is no opening reference quote.\n{% endfor %}"
        "A null or None price means there was no transaction that period.\n\n"
        "YOUR DECISION\n"
        "Forecast transaction prices now and 2, 5, and 10 periods ahead, then choose "
        "your order using your trading approach. For forecast horizons beyond the "
        "last trading period, use the terminal redemption amount. Return forecast_0, "
        "forecast_2, forecast_5, forecast_10, side ('buy', 'sell', or 'hold'), price, "
        "integer quantity, and a brief rationale. All forecasts and prices are in "
        "dollars. For hold use price=0 and quantity=0. Retain any precommitted "
        "schedule or exit plan in your rationale.\n"
    )


def build_agents(seed):
    # Two traders per archetype, in the same pre-shuffle order as the run.
    types = COMPOSITION.split("+") * 2
    random.Random(seed).shuffle(types)
    agents = [
        Agent(
            name=f"trader-{seat:02d}",
            traits={"role": "trader", "seat": seat},
            instruction=COMMON + PERSONAS[kind],
        )
        for seat, kind in enumerate(types)
    ]
    assignments = {agent.name: kind for agent, kind in zip(agents, types)}
    agents.append(Agent(name="exchange", traits={"role": "exchange"}))
    return agents, assignments


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


def build_experiment(*, periods=30, seed=140926, state_id="asset-market"):
    if not 1 <= periods <= 100:
        raise ValueError("periods must be between 1 and 100")
    agents, types = build_agents(seed)
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
        "Exploratory speculative prompts: asset call market",
        metadata={"treatment": COMPOSITION, "periods": periods, "seed": seed,
                  "persona_assignment": types, "source": "Ngo et al., slides dated 2026-09-18",
                  "replication": "new exploratory prompt intervention; not paper prompts",
                  "prompt_variant": VERSION},
    )
    # Fixed horizon; dependencies materialize the 12-way fan-out / fan-in barrier.
    previous = None
    for period in range(1, periods + 1):
        question = QuestionDict(
            question_name="decision",
            question_text=question_text(period, periods),
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
