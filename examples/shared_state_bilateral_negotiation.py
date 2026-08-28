"""Five rounds of parallel bilateral negotiations, serial within each pair."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionFreeText,
    QuestionMultipleChoice,
    QuestionNumerical,
    Survey,
)
from edsl.sharedstate import FileStateStore, SharedNegotiation, SharedState


def negotiation_agents() -> AgentList:
    """Three independent pairs; reservation values remain private traits."""
    pairs = [
        ("p1", 115, 72),
        ("p2", 95, 60),
        ("p3", 80, 88),  # Deliberately has no mutually beneficial price.
    ]
    agents = []
    for pair_id, buyer_value, seller_value in pairs:
        agents.extend(
            [
                Agent(
                    name=f"Buyer {pair_id}",
                    traits={
                        "pair_id": pair_id,
                        "turn_order": 0,
                        "role": "buyer",
                        "private_value": buyer_value,
                        "objective": (
                            "Buy only at or below your private maximum value. "
                            "Seek the lowest credible price."
                        ),
                    },
                ),
                Agent(
                    name=f"Seller {pair_id}",
                    traits={
                        "pair_id": pair_id,
                        "turn_order": 1,
                        "role": "seller",
                        "private_value": seller_value,
                        "objective": (
                            "Sell only at or above your private minimum value. "
                            "Seek the highest credible price."
                        ),
                    },
                ),
            ]
        )
    return AgentList(agents)


def build_negotiation(log_path: str | Path) -> tuple[Survey, SharedState]:
    state = SharedState(
        scope="{{ agent.pair_id }}",
        store=FileStateStore(log_path),
        negotiation=SharedNegotiation("used sailboat"),
    )
    context = (
        "You are the {{ agent.role }} negotiating a used sailboat. "
        "Your private reservation value is ${{ agent.private_value }}. "
        "{{ agent.objective }} Never reveal your reservation value.\n\n"
        "Your pair's transcript so far:\n{{ shared_state.negotiation.turns }}"
    )
    action = QuestionMultipleChoice(
        question_name="action",
        question_text=context + "\n\nChoose your next action.",
        question_options=["offer", "accept", "reject", "walk away"],
    )
    amount = QuestionNumerical(
        question_name="amount",
        question_text=(
            context
            + "\n\nYou chose {{ action.answer }}. Give the price you offer or accept; "
            "use 0 for reject or walk away."
        ),
        min_value=0,
        max_value=1000,
    )
    message = QuestionFreeText(
        question_name="message",
        question_text=(
            context
            + "\n\nYou chose {{ action.answer }} at ${{ amount.answer }}. Write one "
            "concise message to the other party."
        ),
    )
    return (
        Survey(
            [
                action,
                amount,
                message,
                state.negotiation.record(action, amount, message),
            ]
        ),
        state,
    )


def run_negotiations(
    log_path: str | Path = "bilateral-negotiations.jsonl",
    model_name: str = "gemini-2.5-flash",
) -> SharedState:
    survey, state = build_negotiation(log_path)
    schedule = InterviewSchedule.grouped_round_robin(
        group_by="pair_id",
        order_by="turn_order",
        stop_when=state.negotiation.is_terminal,
    )
    (
        survey.by(negotiation_agents())
        .by(Model(model_name))
        .run(
            n=5,
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    return state


if __name__ == "__main__":
    result = run_negotiations()
    for pair_id in ("p1", "p2", "p3"):
        print(result.render_markdown(scope=pair_id))
        print()
