"""Self-contained authoring version of the completed 30-round market.

This post-run consolidation imports no other experiment module. Its complete
specification is checked against the archived experiment, allowing fresh UUIDs.
Requires the shared-state branch with paired assignments from PR #2622.

Safe replay (no model calls):
    python full_market_experiment.py --output replay --responses responses.json
Prepare only: add --prepare-only. Omit --responses for a new paid model session.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random

from edsl import Agent, QuestionDict, QuestionFreeText, Survey
from edsl.sharedstate import (
    SharedState,
    SharedStateMap,
    call_market,
    current,
)
from edsl.workflows import (
    Workflow,
    WorkflowExperiment,
    ExecutionPlan,
    llm,
    role,
    scripted,
)

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


def build(*, created_at=None):
    """Build a serializable experiment: state, participants, workflow, execution."""
    agents = build_agents()
    machine = build_market([a.name for a in agents if a.traits["role"] == "trader"])
    states = SharedStateMap(
        SharedState(market=machine), state_id="portable-asset-market"
    )
    market = states.by("session").market
    workflow = Workflow(
        "Speculative asset market: full 30-round session",
        metadata={
            "economic_horizon": PERIODS,
            "prompt_variant": "speculative-v1",
            "observation_design": "Full 30 rounds fixed before execution; no early observation pauses.",
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
    return WorkflowExperiment(
        workflow.compile(),
        [states],
        agents,
        build_execution_plan(),
        metadata={
            "seed": SEED,
            "prompt_variant": "speculative-v1",
            "economic_horizon": PERIODS,
            "observation_horizon": PERIODS,
            "fresh_model_calls": True,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--responses", type=Path, help="Saved answers; prevents model calls"
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    specification = args.output / "specification.json"
    if args.prepare_only:
        args.output.mkdir(parents=True, exist_ok=True)
        if specification.exists():
            raise FileExistsError(specification)
        build().save(specification)
        print(json.dumps({"status": "prepared", "path": str(specification)}))
        return
    if args.resume:
        experiment = WorkflowExperiment.load(args.output / "experiment.json")
    elif specification.exists():
        experiment = WorkflowExperiment.load(specification)
    else:
        experiment = build()
    responses = None
    if args.responses:
        responses = json.loads(args.responses.read_text())
    else:
        # Hosted execution uses locally configured provider credentials.
        from dotenv import load_dotenv

        load_dotenv()
    result = experiment.run(args.output, responses=responses, resume=args.resume)
    (args.output / "completion.json").write_text(json.dumps(result, indent=2) + "\n")
    from edsl.sharedstate import SQLiteStateBackend

    state = (
        SQLiteStateBackend(experiment.states[0], args.output / "state-0.sqlite")
        .snapshot("session")
        .state["market"]
    )
    (args.output / "market.json").write_text(json.dumps(state, indent=2) + "\n")
    assert result["status"] == "completed" and result["completed_items"] == 390
    assert state["finished"] and len(state["tape"]) == PERIODS
    assert len(state["order_log"]) == 12 * PERIODS
    assert all(a["shares"] == 0 for a in state["accounts"].values())
    print(json.dumps({"status": "ok", "data": result, "warnings": []}))


if __name__ == "__main__":
    main()
