"""Three-round sealed prisoner's dilemma with revealed prior-round history."""

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
from edsl.sharedstate import FileStateStore, SharedRepeatedMatrixGame, SharedState


PAYOFFS = {
    "cooperate|cooperate": [3, 3],
    "cooperate|defect": [0, 5],
    "defect|cooperate": [5, 0],
    "defect|defect": [1, 1],
}


def players():
    specs = [
        ("Tara", "pair-1", 0, "start cooperative, then use tit-for-tat"),
        ("Felix", "pair-1", 1, "start cooperative and forgive one defection"),
        ("Greta", "pair-2", 0, "cooperate until betrayed, then defect forever"),
        ("Dex", "pair-2", 1, "always defect to maximize immediate payoff"),
    ]
    return AgentList(
        [
            Agent(name=n, traits={"pair_id": p, "seat": s, "strategy": x})
            for n, p, s, x in specs
        ]
    )


def run_simulation(
    path: str | Path = "economic-game-repeated-pd.jsonl", model_name="gemini-2.5-flash"
):
    state = SharedState(
        "{{ agent.pair_id }}",
        FileStateStore(path),
        game=SharedRepeatedMatrixGame(["cooperate", "defect"], PAYOFFS, 3),
    )
    action = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            "Round {{ run.round }} of 3 in a repeated prisoner's dilemma. You are "
            "{{ agent.name }} and should {{ agent.strategy }}. Payoffs are C/C=(3,3), "
            "C/D=(0,5), D/C=(5,0), D/D=(1,1). Completed public history: "
            "{{ shared_state.game.history }}. Current-round actions are sealed. Choose."
        ),
        question_options=["cooperate", "defect"],
    )
    survey = Survey([action, state.game.submit(action)])
    schedule = InterviewSchedule.rounds(
        count=3,
        group_by="pair_id",
        within_round="concurrent",
        reveal="after_round",
        finalize_when=GroupStopCondition("game", "complete"),
    )
    survey.by(players()).by(Model(model_name)).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


if __name__ == "__main__":
    result = run_simulation()
    for pair in ("pair-1", "pair-2"):
        print(result.render_markdown(scope=pair), "\n")
