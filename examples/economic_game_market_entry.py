"""Sealed market-entry game with congestion-dependent profits."""

from pathlib import Path

from edsl import (
    Agent,
    AgentList,
    InterviewSchedule,
    Model,
    QuestionMultipleChoice,
    Survey,
)
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedMarketEntryGame, SharedState


def run_simulation(
    path: str | Path = "economic-game-market-entry.jsonl", model_name="gemini-2.5-flash"
):
    beliefs = [
        ("Lena", "optimistic and willing to enter crowded markets"),
        ("Milo", "cautious and expects several competitors"),
        ("Nia", "risk neutral and calculates expected payoff"),
        ("Omar", "overconfident about being early"),
        ("Pia", "risk averse and prefers a safe outside option"),
        ("Raj", "strategic and expects others to avoid congestion"),
    ]
    agents = AgentList([Agent(name=n, traits={"belief": b}) for n, b in beliefs])
    state = SharedState(
        "market-entry", FileStateStore(path), game=SharedMarketEntryGame(6, 2, 10, 3)
    )
    action = QuestionMultipleChoice(
        question_name="entry",
        question_text=(
            "Six firms simultaneously choose enter or stay_out. You are {{ agent.name }}, "
            "{{ agent.belief }}. Staying out pays 2. If k firms enter, every entrant "
            "earns 10 - 3k. Choices are sealed. Choose your action."
        ),
        question_options=["enter", "stay_out"],
    )
    schedule = InterviewSchedule.rounds(
        count=1,
        reveal="after_round",
        finalize_when=GroupStopCondition("game", "complete"),
    )
    Survey([action, state.game.submit(action)]).by(agents).by(Model(model_name)).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


if __name__ == "__main__":
    print(run_simulation().render_markdown())
