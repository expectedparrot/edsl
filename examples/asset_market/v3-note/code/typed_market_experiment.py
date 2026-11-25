"""Typed, configurable authoring of the 30-round asset-market experiment.

Default prompts and wire specification reproduce the archived experiment.
All economics are supplied by CallMarketRules; treatment settings are separate.
Use --prepare-only or --responses for execution without model calls.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import random

from edsl import Agent, QuestionFreeText, Survey
from pydantic import Field, StrictInt, StrictStr, field_validator
from typing import Literal
from edsl.sharedstate.market_rules import MarketModel, NonnegativeNumber, PositiveInt
from edsl.sharedstate import (
    CallMarketRules,
    CashInterest,
    Endowment,
    Redemption,
    ShareDividend,
    DiscreteDistribution,
    PricingRule,
    DecisionSchema,
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
# This object is the single source for settlement, economic instructions, and
# the report's theoretical price benchmark. with_changes(...) revalidates edits.
RULES = CallMarketRules(
    periods=PERIODS,
    endowment=Endowment(cash_cents=10_000, shares=4),
    pricing=PricingRule.MARGINAL_MIDPOINT,
    income=(
        CashInterest(rate=0.05),
        ShareDividend(
            distribution=DiscreteDistribution(
                values_cents=(40, 100), probabilities=(0.5, 0.5)
            ),
        ),
    ),
    redemption=Redemption(value_cents=1_400),
)


class TraderTreatment(MarketModel):
    composition: tuple[Literal["RA", "MC", "BT", "PC", "NT", "OC"], ...] = tuple(
        COMPOSITION
    )
    assignment_seed: StrictInt | StrictStr = SEED
    model: StrictStr = Field("gpt-5-mini", min_length=1)
    service: StrictStr = Field("openai", min_length=1)
    temperature: NonnegativeNumber = 1
    reasoning_effort: Literal["low", "medium", "high"] = "medium"
    max_tokens: PositiveInt = 8000
    forecast_horizons: tuple[StrictInt, ...] = (0, 2, 5, 10)

    @field_validator("composition")
    @classmethod
    def participants_required(cls, value):
        if not value:
            raise ValueError("composition must contain at least one trader")
        return value

    @field_validator("forecast_horizons")
    @classmethod
    def increasing_horizons(cls, value):
        if not value or value[0] != 0 or any(a >= b for a, b in zip(value, value[1:])):
            raise ValueError(
                "forecast_horizons must start at zero and strictly increase"
            )
        return value

    @property
    def decision_schema(self):
        return DecisionSchema(
            forecast_keys=tuple(f"forecast_{h}" for h in self.forecast_horizons)
        )


TREATMENT = TraderTreatment()


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
        "resale return with the {cash_return} cash return. Buy when the expected excess return "
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


def question_text(period, rules=RULES, treatment=TREATMENT):
    periods = rules.periods
    horizons = treatment.forecast_horizons
    history_labels = ", ".join("now" if h == 0 else f"+{h}" for h in horizons)
    history_values = ", ".join(
        "{{ h.decision.forecast_" + str(h) + " }}" for h in horizons
    )
    future = [str(h) for h in horizons[1:]]
    if not future:
        forecast_instruction = "Forecast the transaction price now, then choose "
    else:
        ahead = (
            future[0]
            if len(future) == 1
            else ", ".join(future[:-1]) + ", and " + future[-1]
        )
        unit = "period" if future == ["1"] else "periods"
        forecast_instruction = (
            f"Forecast transaction prices now and {ahead} {unit} ahead, then choose "
        )
    forecast_names = ", ".join(treatment.decision_schema.forecast_keys)
    return (
        f"Period {period} of {periods}; {periods - period + 1} trading periods remain, including this one.\n\n"
        "MARKET RULES\n"
        + rules.instructions(len(treatment.composition))
        + "YOUR ACCOUNT (all money below is in dollars)\n"
        "Cash: {{ shared_state.market.your_account.cash_cents / 100 }}. "
        "Shares: {{ shared_state.market.your_account.shares }}.\n"
        "Your previous decisions and fills:\n"
        "{% for h in shared_state.market.your_account.history %}"
        "Period {{ h.period }}: {{ h.side }} {{ h.decision.quantity }} at limit "
        "{{ h.limit_cents / 100 }}; admitted {{ h.accepted_quantity }}; signed fill "
        "{{ h.fill }}; market price {{ h.transaction_price }}; interest "
        "{{ h.interest }}; dividend per share {{ h.dividend_per_share }}. "
        f"Your forecasts ({history_labels}): {history_values}. Your rationale: {{{{ h.decision.rationale }}}}\n"
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
        + forecast_instruction
        + "your order using your trading approach. For forecast horizons beyond the "
        "last trading period, use the terminal redemption amount. Return "
        f"{forecast_names}, side ('buy', 'sell', or 'hold'), price, "
        "integer quantity, and a brief rationale. All forecasts and prices are in "
        "dollars. For hold use price=0 and quantity=0. Retain any precommitted "
        "schedule or exit plan in your rationale.\n"
    )


def build_agents(rules=RULES, treatment=TREATMENT):
    """Assign the declared composition reproducibly; render economic persona facts."""
    types = list(treatment.composition)
    random.Random(treatment.assignment_seed).shuffle(types)
    agents = [
        Agent(
            name=f"trader-{seat:02d}",
            traits={"role": "trader", "seat": seat},
            instruction=COMMON
            + PERSONAS[kind].format(cash_return=f"{rules.interest.rate * 100:g}%"),
        )
        for seat, kind in enumerate(types)
    ]
    agents.append(Agent(name="exchange", traits={"role": "exchange"}))
    return agents


def build_market(trader_names, rules=RULES, seed=SEED):
    return call_market(trader_names, rules=rules, seed=seed)


def build_execution_plan(treatment=TREATMENT):
    """EDSL asks traders; the exchange receives a literal scripted answer."""
    return (
        ExecutionPlan()
        .bind(
            role("trader"),
            llm(
                model=treatment.model,
                service=treatment.service,
                parameters={
                    "temperature": treatment.temperature,
                    "reasoning_effort": treatment.reasoning_effort,
                    "max_tokens": treatment.max_tokens,
                },
            ),
        )
        .bind(role("exchange"), scripted(answers={"settlement": "clear"}))
    )


def build(*, rules=RULES, treatment=TREATMENT, seed=SEED, created_at=None):
    """Build a serializable experiment: state, participants, workflow, execution."""
    if rules.forecast_keys != treatment.decision_schema.forecast_keys:
        raise ValueError("market forecast_keys must match treatment forecast_horizons")
    agents = build_agents(rules, treatment)
    machine = build_market(
        [a.name for a in agents if a.traits["role"] == "trader"], rules, seed
    )
    states = SharedStateMap(
        SharedState(market=machine), state_id="portable-asset-market"
    )
    market = states.by("session").market
    workflow = Workflow(
        f"Speculative asset market: full {rules.periods}-round session",
        metadata={
            "economic_horizon": rules.periods,
            "prompt_variant": "speculative-v1",
            "observation_design": f"Full {rules.periods} rounds fixed before execution; no early observation pauses.",
        },
    )
    previous = None
    for period in range(1, rules.periods + 1):
        question = treatment.decision_schema.question(
            question_name="decision",
            question_text=question_text(period, rules, treatment),
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
        build_execution_plan(treatment),
        metadata={
            "seed": seed,
            "prompt_variant": "speculative-v1",
            "economic_horizon": rules.periods,
            "observation_horizon": rules.periods,
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
    parser.add_argument("--rules", type=Path, help="CallMarketRules JSON")
    parser.add_argument("--treatment", type=Path, help="TraderTreatment JSON")
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    rules = (
        CallMarketRules.from_dict(json.loads(args.rules.read_text()))
        if args.rules
        else RULES
    )
    treatment = (
        TraderTreatment.from_dict(json.loads(args.treatment.read_text()))
        if args.treatment
        else TREATMENT
    )
    specification = args.output / "specification.json"
    if (args.resume or specification.exists()) and (
        args.rules or args.treatment or args.seed != SEED
    ):
        raise ValueError(
            "cannot override a saved specification; use a fresh output directory"
        )
    if args.prepare_only:
        if specification.exists():
            raise FileExistsError(specification)
        experiment = build(rules=rules, treatment=treatment, seed=args.seed)
        args.output.mkdir(parents=True, exist_ok=True)
        experiment.save(specification)
        print(json.dumps({"status": "prepared", "path": str(specification)}))
        return
    if args.resume:
        experiment = WorkflowExperiment.load(args.output / "experiment.json")
    elif specification.exists():
        experiment = WorkflowExperiment.load(specification)
    else:
        experiment = build(rules=rules, treatment=treatment, seed=args.seed)
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
    periods = experiment.metadata["economic_horizon"]
    traders = sum(a.traits["role"] == "trader" for a in experiment.agents)
    assert (
        result["status"] == "completed"
        and result["completed_items"] == (traders + 1) * periods
    )
    assert state["finished"] and len(state["tape"]) == periods
    assert len(state["order_log"]) == traders * periods
    assert all(a["shares"] == 0 for a in state["accounts"].values())
    print(json.dumps({"status": "ok", "data": result, "warnings": []}))


if __name__ == "__main__":
    main()
