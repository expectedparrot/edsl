"""A complete asset-market experiment using native EDSL workflow tools.

All prompts and authoring code are here; no other experiment module is imported.
Running this file exports the specification and archived answers, without calls:
    python -m examples.asset_market.portable

Replay with the generic driver (see PORTABLE_EXPERIMENT.md), or load the JSON
with WorkflowExperiment and call run() to conduct a new, paid model session.
The observation policy retrospectively encodes the exploratory historical run.
"""

import json
from pathlib import Path
import random

from edsl import Agent, QuestionDict, QuestionFreeText, Survey
from edsl.sharedstate import (
    SharedState,
    SharedStateMap,
    call_market,
    current,
    field,
    filter_items,
    local,
)
from edsl.workflows import (
    Workflow,
    WorkflowExperiment,
    ExecutionPlan,
    llm,
    role,
    scripted,
)

ROOT = Path(__file__).parent
SEED = 140926
PERIODS = 30
COMPOSITION = ["RA", "MC", "BT", "PC", "NT", "OC"] * 2
KEYS = [
    "forecast_0",
    "forecast_2",
    "forecast_5",
    "forecast_10",
    "side",
    "price",
    "quantity",
    "rationale",
]
OVERPRICING_THRESHOLD = 17.50

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


def build_agents():
    """Two traders per archetype, with a reproducible seat assignment."""
    types = list(COMPOSITION)
    random.Random(SEED).shuffle(types)
    agents = [
        Agent(
            name=f"trader-{seat:02d}",
            traits={"role": "trader", "seat": seat},
            instruction=COMMON + PERSONAS[kind],
        )
        for seat, kind in enumerate(types)
    ]
    agents.append(Agent(name="exchange", traits={"role": "exchange"}))
    return agents


def build_market(trader_names):
    """Declare economics; standard EDSL commands admit and settle the orders."""
    return call_market(
        trader_names,
        periods=PERIODS,
        seed=SEED,
        initial_cash_cents=10000,
        initial_shares=4,
        initial_reference_price=14.0,  # Internal only; never shown as a quote.
        redemption_cents=1400,
        pricing_rule="marginal_midpoint",
        maximum_buy_quantity=48,
        income_schedule=[
            {"kind": "cash_interest", "rate": 0.05},
            {
                "kind": "share_dividend",
                "values_cents": [40, 100],
                "probabilities": [0.5, 0.5],
                "sampling": "python_random_choice_v1",
            },
        ],
        forecast_keys=KEYS[:4],
    )


def add_pause_rules(workflow, settlement, market, period):
    """Pause observation while retaining the 30-round economic horizon."""
    if period >= 2:
        last = field("tape").at(-1).get("price")
        prior = field("tape").at(-2).get("price")
        workflow.pause_after(
            settlement,
            name=f"overpricing-{period}",
            read=market.read(),
            condition=(last != None)  # noqa: E711 -- symbolic expression
            & (prior != None)  # noqa: E711 -- symbolic expression
            & (last >= OVERPRICING_THRESHOLD)
            & (prior >= OVERPRICING_THRESHOLD),
        )
    if period in {12, 20}:
        no_trades = (
            filter_items(
                field("tape"),
                item="row",
                predicate=local("row").get("volume") > 0,
            ).length()
            == 0
        )
        workflow.pause_after(
            settlement,
            name=f"observation-cap-{period}",
            read=market.read(),
            resume_when=no_trades if period == 12 else True,
        )


def build_execution_plan():
    """EDSL asks traders; the exchange receives a literal scripted answer."""
    return (
        ExecutionPlan()
        .bind(
            role("trader"),
            llm(
                model="gpt-5-mini",
                service="openai",
                parameters={
                    "temperature": 1,
                    "reasoning_effort": "medium",
                    "max_tokens": 8000,
                },
            ),
        )
        .bind(role("exchange"), scripted(answers={"settlement": "clear"}))
    )


def build():
    """Build a serializable experiment: state, participants, workflow, execution."""
    agents = build_agents()
    machine = build_market([a.name for a in agents if a.traits["role"] == "trader"])
    states = SharedStateMap(
        SharedState(market=machine), state_id="portable-asset-market"
    )
    market = states.by("session").market
    workflow = Workflow(
        "Speculative asset market: portable pilot",
        metadata={
            "economic_horizon": PERIODS,
            "prompt_variant": "speculative-v1",
            "observation_design": "Retrospective encoding of the executed exploratory policy; extension to 20 was declared after round 6.",
        },
    )
    previous = None
    for period in range(1, PERIODS + 1):
        question = QuestionDict(
            question_name="decision",
            question_text=question_text(period, PERIODS),
            answer_keys=KEYS,
            value_types=["float"] * 4 + ["str", "float", "int", "str"],
            include_comment=False,
        )
        orders = workflow.step(
            f"orders-{period}",
            Survey([question]),
            assigned_to=role("trader"),
            after=previous,
            visible_to=role("exchange"),
            reads=(market.read(),),
            writes=(
                market.submit(
                    trader=current.agent.name, period=period, decision=question.answer
                ),
            ),
            metadata={"period": period, "phase": "sealed orders"},
        )
        previous = workflow.step(
            f"settle-{period}",
            Survey(
                [
                    QuestionFreeText(
                        question_name="settlement",
                        question_text="Run deterministic market settlement.",
                    )
                ]
            ),
            assigned_to=role("exchange"),
            after=orders,
            writes=(market.settle(period=period),),
            metadata={"period": period},
        )
        add_pause_rules(workflow, previous, market, period)
    return WorkflowExperiment(
        workflow.compile(),
        [states],
        agents,
        build_execution_plan(),
        metadata={
            "seed": SEED,
            "source_run": "gpt5-short-pilot",
            "checkpoint_extension": {
                "after": "settle-12",
                "extend_to": 20,
                "condition": "no transactions through round 12",
                "requires_explicit_resume": True,
            },
        },
    )


def export():
    output = ROOT / "portable"
    output.mkdir(exist_ok=True)
    experiment = build()
    experiment.save(output / "experiment.json")
    run = ROOT / "runs/gpt5-short-pilot"
    calls = [
        json.loads(line)
        for line in (run / "model-calls.jsonl").read_text().splitlines()
    ]
    responses = [
        {
            "step": c["step"],
            "participant": c["participant"],
            "answers": c["result"]["answer"],
        }
        for c in calls
    ]
    (output / "responses.json").write_text(json.dumps(responses, indent=2) + "\n")
    summary = json.loads((run / "summary.json").read_text())
    (output / "expected.json").write_text(
        json.dumps(
            {
                "accounts": summary["accounts"],
                "tape": summary["tape"],
                "orders": json.loads((run / "orders.json").read_text()),
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "data": {"output": str(output), "responses": len(responses)},
                "warnings": [],
            }
        )
    )


if __name__ == "__main__":
    export()
