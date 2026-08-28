"""Live beauty-contest and common-pool group games."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionNumerical, Survey
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import (
    FileStateStore,
    SharedBeautyContest,
    SharedCommonPoolGame,
    SharedState,
)


def sealed_schedule(target):
    return InterviewSchedule.rounds(
        count=1,
        within_round="concurrent",
        reveal="after_round",
        finalize_when=GroupStopCondition(target, "complete"),
    )


def run_beauty(path, model):
    styles = [
        ("Ana", "chooses intuitively near the midpoint"),
        ("Bert", "uses one level of strategic reasoning"),
        ("Cleo", "uses two levels of strategic reasoning"),
        ("Dev", "iterates strategic reasoning toward equilibrium"),
        ("Eve", "expects unsophisticated opponents"),
        ("Finn", "expects highly sophisticated opponents"),
    ]
    agents = AgentList([Agent(name=n, traits={"style": s}) for n, s in styles])
    state = SharedState(
        "beauty-contest", FileStateStore(path), game=SharedBeautyContest(6)
    )
    choice = QuestionNumerical(
        question_name="choice",
        question_text=(
            "Six players simultaneously choose a number from 0 to 100. The winner "
            "is closest to two-thirds of the group mean. You are {{ agent.name }} and "
            "{{ agent.style }}. Choices are sealed. Choose one number."
        ),
        min_value=0,
        max_value=100,
    )
    Survey([choice, state.game.submit(choice)]).by(agents).by(model).run(
        interview_schedule=sealed_schedule("game"),
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


def run_common_pool(path, model):
    norms = [
        ("Gia", "strongly conservation-minded"),
        ("Hugo", "conditionally cooperative"),
        ("Ira", "moderately self-interested"),
        ("Jae", "strictly payoff maximizing"),
        ("Kira", "expects others to over-extract"),
    ]
    agents = AgentList([Agent(name=n, traits={"norm": x}) for n, x in norms])
    state = SharedState(
        "common-pool", FileStateStore(path), game=SharedCommonPoolGame(5, 60, 20)
    )
    amount = QuestionNumerical(
        question_name="extraction",
        question_text=(
            "Five players simultaneously request 0–20 units from a shared stock of "
            "60. You are {{ agent.name }} and are {{ agent.norm }}. If total requests "
            "are at most 60, you receive your request plus one-fifth of the remainder. "
            "If requests exceed 60, the stock is rationed proportionally with no "
            "remainder. Choices are sealed. Choose your request."
        ),
        min_value=0,
        max_value=20,
    )
    Survey([amount, state.game.extract(amount)]).by(agents).by(model).run(
        interview_schedule=sealed_schedule("game"),
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


def run_simulations(root: str | Path = ".", model_name="gemini-2.5-flash"):
    root, model = Path(root), Model(model_name)
    return {
        "beauty_contest": run_beauty(
            root / "economic-game-beauty-contest.jsonl", model
        ),
        "common_pool": run_common_pool(root / "economic-game-common-pool.jsonl", model),
    }


if __name__ == "__main__":
    for game_name, state in run_simulations().items():
        print(f"# {game_name.replace('_', ' ').title()}")
        print(state.render_markdown(), "\n")
