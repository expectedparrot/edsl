"""Posted-price bilateral trade with privately informed sellers."""

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
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedBilateralTrade, SharedState


def participants():
    specs = [
        (
            "Buyer-1",
            "pair-1",
            0,
            "buyer",
            100,
            0,
            "risk neutral; believes seller cost is uniformly 20–80",
        ),
        (
            "Seller-1",
            "pair-1",
            1,
            "seller",
            0,
            30,
            "will trade whenever price covers private cost",
        ),
        (
            "Buyer-2",
            "pair-2",
            0,
            "buyer",
            100,
            0,
            "cautious; believes high-cost sellers are common",
        ),
        (
            "Seller-2",
            "pair-2",
            1,
            "seller",
            0,
            60,
            "will trade whenever price covers private cost",
        ),
        (
            "Buyer-3",
            "pair-3",
            0,
            "buyer",
            100,
            0,
            "aggressive bargainer; expects sellers to concede",
        ),
        (
            "Seller-3",
            "pair-3",
            1,
            "seller",
            0,
            75,
            "will trade whenever price covers private cost",
        ),
    ]
    return AgentList(
        [
            Agent(
                name=n,
                traits={
                    "pair_id": p,
                    "turn": t,
                    "role": r,
                    "buyer_value": v,
                    "seller_cost": c,
                    "strategy": s,
                },
            )
            for n, p, t, r, v, c, s in specs
        ]
    )


def run_simulation(
    path: str | Path = "economic-game-adverse-selection.jsonl",
    model_name="gemini-2.5-flash",
):
    state = SharedState(
        "{{ agent.pair_id }}", FileStateStore(path), trade=SharedBilateralTrade()
    )
    offer = QuestionNumerical(
        question_name="offer",
        question_text=(
            "You are {{ agent.name }}, a buyer valuing an asset at "
            "{{ agent.buyer_value }}. You are {{ agent.strategy }}. The seller privately "
            "knows their cost; you do not. Post one take-it-or-leave-it price from 0–100."
        ),
        min_value=0,
        max_value=100,
    )
    decision = QuestionMultipleChoice(
        question_name="decision",
        question_text=(
            "You are {{ agent.name }}, a seller with private cost {{ agent.seller_cost }}. "
            "You are {{ agent.strategy }}. The buyer posted {{ shared_state.trade.price }}. "
            "Accept or reject to maximize price minus cost."
        ),
        question_options=["accept", "reject"],
    )
    survey = Survey(
        [offer, state.trade.offer(offer), decision, state.trade.respond(decision)]
    )
    survey.add_skip_rule("offer", "'{{ agent.role }}' != 'buyer'")
    survey.add_skip_rule("decision", "'{{ agent.role }}' != 'seller'")
    terminal = GroupStopCondition("trade", "terminal")
    schedule = InterviewSchedule.grouped_round_robin(
        "pair_id", "turn", finalize_when=terminal
    )
    survey.by(participants()).by(Model(model_name)).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


if __name__ == "__main__":
    result = run_simulation()
    for pair in ("pair-1", "pair-2", "pair-3"):
        print(result.render_markdown(scope=pair), "\n")
