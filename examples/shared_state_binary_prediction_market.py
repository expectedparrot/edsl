"""A live binary-contract prediction market driven by private-belief agents."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMultipleChoice,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedBinaryMarket, SharedState
from edsl.sharedstate.steps import StepContext


CONTRACT = "Project Atlas reaches 100,000 weekly active users within six months"


def traders() -> AgentList:
    specs = [
        (
            "Aria",
            0,
            0.80,
            "bullish telemetry analyst",
            "trusts strong early usage data",
        ),
        ("Basil", 1, 0.66, "sales forecaster", "sees meaningful customer commitments"),
        (
            "Emi",
            2,
            0.54,
            "balanced market researcher",
            "weighs mixed qualitative evidence",
        ),
        ("Chen", 3, 0.38, "skeptical reliability engineer", "expects scaling failures"),
        ("Dara", 4, 0.22, "conservative risk analyst", "uses a pessimistic base rate"),
    ]
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "trader_order": trader_order,
                    "private_belief": belief,
                    "trader_type": trader_type,
                    "evidence": evidence,
                },
            )
            for name, trader_order, belief, trader_type, evidence in specs
        ]
    )


def build_survey(state: SharedState) -> Survey:
    action = QuestionMultipleChoice(
        question_name="market_action",
        question_text=(
            "Round {{ run.round }} of 3. You are {{ agent.name }}, a "
            "{{ agent.trader_type }} who {{ agent.evidence }}. Your private probability "
            "for YES is {{ agent.private_belief }}. Do not reveal it.\n\n"
            "Contract: {{ shared_state.market.contract }}\n"
            "Current YES price: {{ shared_state.market.yes_price }}\n"
            "Current NO price: {{ shared_state.market.no_price }}\n"
            "Your portfolio: {{ shared_state.market.your_portfolio }}\n"
            "Recent trades: {{ shared_state.market.recent_trades }}\n\n"
            "Choose buy_yes when YES is underpriced relative to your belief, buy_no "
            "when NO is underpriced, or hold when neither trade has positive value."
        ),
        question_options=["buy_yes", "buy_no", "hold"],
    )
    quantity = QuestionNumerical(
        question_name="trade_quantity",
        question_text=(
            "You chose {{ market_action.answer }}. Choose a quantity from 0 to 15 "
            "shares. Use 0 when holding. Size the trade according to your perceived "
            "edge while preserving cash for later rounds."
        ),
        min_value=0,
        max_value=15,
    )
    return Survey([action, quantity, state.market.trade(action, quantity)])


def run_market(
    log_path: str | Path = "binary-prediction-market.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "atlas-binary-market",
        FileStateStore(log_path),
        market=SharedBinaryMarket(CONTRACT, liquidity=40, initial_cash=100),
    )
    schedule = InterviewSchedule.rounds(
        count=3,
        within_round="serial",
        state_visibility="live",
        order_by="trader_order",
        round_order="rotate",
    )
    (
        build_survey(state)
        .by(traders())
        .by(Model(model_name))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    # Resolve to YES after trading; agents never receive this outcome in their prompts.
    state.market.settle(True).execute(StepContext({}, "market-resolution"))
    state.close()
    return state


if __name__ == "__main__":
    print(run_market().render_markdown())
