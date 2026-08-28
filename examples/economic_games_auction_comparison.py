"""Compare sealed first-price, second-price, and all-pay auctions."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionNumerical, Survey
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedSealedAuction, SharedState


def bidders():
    specs = [
        ("Arun", 0, 92, "risk neutral and strategically sophisticated"),
        ("Bea", 1, 76, "moderately risk averse"),
        ("Cole", 2, 61, "risk neutral but cautious about overpaying"),
        ("Dina", 3, 47, "aggressive and competitive"),
        ("Ezra", 4, 33, "highly loss averse"),
    ]
    return AgentList(
        [
            Agent(name=n, traits={"seat": s, "private_value": v, "style": x})
            for n, s, v, x in specs
        ]
    )


DESCRIPTIONS = {
    "first_price": "The highest bidder wins and pays their own bid.",
    "second_price": "The highest bidder wins and pays the second-highest bid.",
    "all_pay": "The highest bidder wins, but every bidder pays their own bid.",
}


def run_auction(mechanism, path, model):
    state = SharedState(
        mechanism, FileStateStore(path), auction=SharedSealedAuction(mechanism, 5)
    )
    bid = QuestionNumerical(
        question_name="bid",
        question_text=(
            f"You are bidding in a sealed {mechanism.replace('_', '-')} auction. "
            f"{DESCRIPTIONS[mechanism]} Your private value is "
            "{{ agent.private_value }}. You are {{ agent.style }}. Highest bid wins; "
            "ties use a predetermined seat order. Choose a bid from 0 to 100 to "
            "maximize value minus payment."
        ),
        min_value=0,
        max_value=100,
    )
    schedule = InterviewSchedule.rounds(
        count=1,
        reveal="after_round",
        finalize_when=GroupStopCondition("auction", "complete"),
    )
    Survey([bid, state.auction.bid(bid)]).by(bidders()).by(model).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


def run_simulations(root: str | Path = ".", model_name="gemini-2.5-flash"):
    root, model = Path(root), Model(model_name)
    return {
        mechanism: run_auction(
            mechanism, root / f"economic-game-auction-{mechanism}.jsonl", model
        )
        for mechanism in DESCRIPTIONS
    }


if __name__ == "__main__":
    for mechanism, state in run_simulations().items():
        print(f"# {mechanism.replace('_', ' ').title()}")
        print(state.render_markdown(), "\n")
