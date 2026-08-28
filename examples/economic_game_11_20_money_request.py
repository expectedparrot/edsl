"""Four parallel sealed 11–20 money-request games."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionNumerical, Survey
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedMoneyRequestGame, SharedState


def players():
    specs = [
        ("A1", "pair-1", "chooses the largest guaranteed personal payment"),
        ("B1", "pair-1", "expects the opponent to choose the obvious maximum"),
        ("A2", "pair-2", "uses one step of strategic reasoning"),
        ("B2", "pair-2", "uses two steps of strategic reasoning"),
        ("A3", "pair-3", "believes most people choose 19"),
        ("B3", "pair-3", "believes sophisticated players undercut repeatedly"),
        ("A4", "pair-4", "dislikes appearing greedy but values the bonus"),
        ("B4", "pair-4", "randomizes mentally between plausible strategic choices"),
    ]
    return AgentList(
        [
            Agent(name=name, traits={"pair_id": pair, "reasoning_style": style})
            for name, pair, style in specs
        ]
    )


def survey(state):
    request = QuestionNumerical(
        question_name="request",
        question_text=(
            "You are {{ agent.name }} in a one-shot two-player money-request game. "
            "You {{ agent.reasoning_style }}. Each player simultaneously requests an "
            "integer from 11 through 20 and receives that amount. Additionally, a "
            "player who requests exactly one less than the other receives a $20 bonus. "
            "Choices are sealed until both commit. Choose your request."
        ),
        min_value=11,
        max_value=20,
    )
    return Survey([request, state.game.submit(request)])


def run_simulation(
    log_path: str | Path = "economic-game-11-20.jsonl",
    model_name="gemini-2.5-flash",
):
    state = SharedState(
        "{{ agent.pair_id }}",
        FileStateStore(log_path),
        game=SharedMoneyRequestGame(),
    )
    schedule = InterviewSchedule.rounds(
        count=1,
        group_by="pair_id",
        within_round="concurrent",
        state_visibility="snapshot",
        reveal="after_round",
        finalize_when=GroupStopCondition("game", "complete"),
    )
    (
        survey(state)
        .by(players())
        .by(Model(model_name))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    return state


if __name__ == "__main__":
    result = run_simulation()
    for pair_id in ("pair-1", "pair-2", "pair-3", "pair-4"):
        print(result.render_markdown(scope=pair_id), "\n")
