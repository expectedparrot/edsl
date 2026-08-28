"""Binary prediction market with private signals released just in time."""

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
from edsl.sharedstate import (
    FileStateStore,
    SharedBinaryMarket,
    SharedSignalSchedule,
    SharedState,
)
from edsl.sharedstate.steps import StepContext


CONTRACT = "Project Lyra ships its public release before December 1"

SIGNALS = {
    "Nova": [
        "Your prior probability is 0.62 based on the published roadmap.",
        "A private beta report says all critical workflows now pass.",
        "A trusted engineer says release automation is complete.",
    ],
    "Oren": [
        "Your prior probability is 0.46 because past launches slipped.",
        "An internal incident caused a one-week reliability delay.",
        "The incident review closed with no remaining launch blockers.",
    ],
    "Priya": [
        "Your prior probability is 0.55 based on customer readiness.",
        "Two design partners privately committed to launch-day adoption.",
        "A major integration partner moved certification back two weeks.",
    ],
    "Quinn": [
        "Your prior probability is 0.36 due to regulatory uncertainty.",
        "Counsel privately identified an unresolved compliance question.",
        "The regulator granted the required expedited approval.",
    ],
}


def traders() -> AgentList:
    roles = [
        ("Nova", 0, "product telemetry analyst"),
        ("Oren", 1, "reliability forecaster"),
        ("Priya", 2, "customer research lead"),
        ("Quinn", 3, "regulatory risk analyst"),
    ]
    return AgentList(
        [
            Agent(name=name, traits={"seat": seat, "role": role})
            for name, seat, role in roles
        ]
    )


def build_survey(state: SharedState) -> Survey:
    action = QuestionMultipleChoice(
        question_name="market_action",
        question_text=(
            "Round {{ run.round }} of 3. You are {{ agent.name }}, the "
            "{{ agent.role }}.\n\n"
            "New private signal: {{ shared_state.news.your_signal }}\n"
            "Your revealed signal history: {{ shared_state.news.your_signal_history }}\n"
            "Do not reveal the private signals directly.\n\n"
            "Contract: {{ shared_state.market.contract }}\n"
            "Current YES price: {{ shared_state.market.yes_price }}\n"
            "Current NO price: {{ shared_state.market.no_price }}\n"
            "Your portfolio: {{ shared_state.market.your_portfolio }}\n"
            "Recent trades: {{ shared_state.market.recent_trades }}\n\n"
            "Update your belief using only signals revealed so far, then choose a trade."
        ),
        question_options=["buy_yes", "buy_no", "hold"],
    )
    quantity = QuestionNumerical(
        question_name="trade_quantity",
        question_text=(
            "You chose {{ market_action.answer }}. Choose 0–12 shares, preserving "
            "cash for future news. Use 0 for hold."
        ),
        min_value=0,
        max_value=12,
    )
    return Survey(
        [
            state.news.reveal_before(action),
            action,
            quantity,
            state.market.trade(action, quantity),
        ]
    )


def run_simulation(
    log_path: str | Path = "prediction-market-private-news.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    state = SharedState(
        "lyra-private-news-market",
        FileStateStore(log_path),
        news=SharedSignalSchedule(SIGNALS),
        market=SharedBinaryMarket(CONTRACT, liquidity=35, initial_cash=100),
    )
    schedule = InterviewSchedule.rounds(
        count=3,
        within_round="serial",
        state_visibility="live",
        order_by="seat",
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
    state.market.settle(True).execute(StepContext({}, "market-resolution"))
    state.close()
    return state


if __name__ == "__main__":
    print(run_simulation().render_markdown())
