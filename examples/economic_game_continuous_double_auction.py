"""A live unit-order double auction with private buyer values and seller costs."""

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
from edsl.sharedstate import FileStateStore, SharedDoubleAuction, SharedState


TRADERS = [
    ("Buyer 1", "buyer", 112),
    ("Buyer 2", "buyer", 98),
    ("Buyer 3", "buyer", 84),
    ("Buyer 4", "buyer", 69),
    ("Seller 1", "seller", 42),
    ("Seller 2", "seller", 58),
    ("Seller 3", "seller", 76),
    ("Seller 4", "seller", 91),
]


def traders() -> AgentList:
    return AgentList(
        [
            Agent(
                name=name,
                traits={
                    "role": role,
                    "private_limit": limit,
                    "objective": (
                        "buy one unit at or below your private value"
                        if role == "buyer"
                        else "sell one unit at or above your private cost"
                    ),
                },
            )
            for name, role, limit in TRADERS
        ]
    )


def survey(state: SharedState) -> Survey:
    action = QuestionMultipleChoice(
        question_name="order_action",
        question_text=(
            "Round {{ run.round }} of 3. You are {{ agent.name }}, a {{ agent.role }}, "
            "and should {{ agent.objective }}. Your private limit is "
            "{{ agent.private_limit }}.\n\nLive order book and your account:\n"
            "{{ shared_state.book }}\n\nChoose buy or sell only for your assigned role. "
            "If you already traded, hold. If you have an open order and want a new "
            "price, cancel it this round; you can replace it next round."
        ),
        question_options=["buy", "sell", "cancel", "hold"],
    )
    price = QuestionNumerical(
        question_name="limit_price",
        question_text=(
            "You selected {{ order_action.answer }}. If buying or selling, submit a "
            "profitable integer limit price from 1 to 150. For cancel or hold, enter 0."
        ),
        min_value=0,
        max_value=150,
    )
    return Survey([action, price, state.book.submit(action, price)])


def realized_surplus(state: SharedState) -> tuple[float, list[dict]]:
    limits = {name: (role, limit) for name, role, limit in TRADERS}
    trades = state.read().state["book"]["trades"]
    details = []
    total = 0.0
    for trade in trades:
        buyer_value = limits[trade["buyer"]][1]
        seller_cost = limits[trade["seller"]][1]
        surplus = buyer_value - seller_cost
        total += surplus
        details.append(dict(trade) | {"surplus": surplus})
    return total, details


def run_double_auction(
    log_path: str | Path = "economic-game-double-auction.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> tuple[SharedState, float, list[dict]]:
    participants = {
        name: {
            "cash": 150 if role == "buyer" else 0,
            "inventory": 0 if role == "buyer" else 1,
        }
        for name, role, _ in TRADERS
    }
    state = SharedState(
        "continuous-double-auction",
        FileStateStore(log_path),
        book=SharedDoubleAuction(participants),
    )
    schedule = InterviewSchedule.rounds(
        count=3,
        within_round="concurrent",
        state_visibility="live",
        round_order="rotate",
    )
    (
        survey(state)
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
    state.close()
    total, trades = realized_surplus(state)
    return state, total, trades


if __name__ == "__main__":
    shared_state, surplus, executed = run_double_auction()
    print(shared_state.render_markdown())
    print(f"\nRealized surplus: {surplus:g}\nTrades: {executed}")
