"""Six-node centipede game with early stopping after take."""

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
from edsl.sharedstate import FileStateStore, SharedCentipedeGame, SharedState


TAKE_PAYOFFS = [[2, 0], [1, 3], [4, 2], [3, 5], [6, 4], [5, 7]]


def decision_nodes():
    agents = []
    for node in range(1, 7):
        player = "Alice" if node % 2 else "Bob"
        disposition = (
            "values reciprocity but reasons strategically"
            if player == "Alice"
            else "is cautiously cooperative but fears exploitation"
        )
        agents.append(
            Agent(
                name=f"{player}-node-{node}",
                traits={
                    "game_id": "centipede-1",
                    "node": node,
                    "player": player,
                    "disposition": disposition,
                },
            )
        )
    return AgentList(agents)


def run_simulation(
    path: str | Path = "economic-game-centipede.jsonl",
    model_name="gemini-2.5-flash",
):
    state = SharedState(
        "centipede-1",
        FileStateStore(path),
        game=SharedCentipedeGame(TAKE_PAYOFFS, [6, 6]),
    )
    action = QuestionMultipleChoice(
        question_name="action",
        question_text=(
            "You are {{ agent.player }} acting at node {{ agent.node }} of a six-node "
            "centipede game and {{ agent.disposition }}. Alice's payoff is listed first. "
            "Taking at nodes 1–6 yields respectively (2,0), (1,3), (4,2), (3,5), "
            "(6,4), and (5,7). Passing at node 6 yields (6,6). Earlier passes move to "
            "the next node. Public history: {{ shared_state.game.history }}. Choose."
        ),
        question_options=["take", "pass"],
    )
    survey = Survey([action, state.game.move(action)])
    terminal = GroupStopCondition("game", "terminal")
    schedule = InterviewSchedule.grouped_round_robin(
        "game_id", "node", stop_when=terminal, finalize_when=terminal
    )
    survey.by(decision_nodes()).by(Model(model_name)).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


if __name__ == "__main__":
    print(run_simulation().render_markdown())
