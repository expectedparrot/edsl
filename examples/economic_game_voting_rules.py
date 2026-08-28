"""Compare plurality, Borda, and Condorcet outcomes on sealed rankings."""

from pathlib import Path

from edsl import Agent, AgentList, InterviewSchedule, Model, QuestionRank, Survey
from edsl.jobs.interview_schedule import GroupStopCondition
from edsl.sharedstate import FileStateStore, SharedState, SharedVotingGame


CANDIDATES = ["Alpha", "Beta", "Gamma"]


def voters():
    rankings = [
        "Alpha > Beta > Gamma",
        "Alpha > Beta > Gamma",
        "Alpha > Beta > Gamma",
        "Beta > Gamma > Alpha",
        "Beta > Gamma > Alpha",
        "Gamma > Beta > Alpha",
        "Gamma > Beta > Alpha",
    ]
    return AgentList(
        [
            Agent(name=f"Voter-{i}", traits={"true_ranking": ranking})
            for i, ranking in enumerate(rankings, 1)
        ]
    )


def run_simulation(
    path: str | Path = "economic-game-voting-rules.jsonl", model_name="gemini-2.5-flash"
):
    state = SharedState(
        "voting-rules", FileStateStore(path), election=SharedVotingGame(CANDIDATES, 7)
    )
    ranking = QuestionRank(
        question_name="ranking",
        question_text=(
            "You are {{ agent.name }}. Your sincere preference is "
            "{{ agent.true_ranking }}. Submit a complete sincere ranking. Ballots are "
            "sealed and the same profile will be evaluated under plurality, Borda, "
            "and pairwise Condorcet rules."
        ),
        question_options=CANDIDATES,
        num_selections=3,
    )
    schedule = InterviewSchedule.rounds(
        count=1,
        reveal="after_round",
        finalize_when=GroupStopCondition("election", "complete"),
    )
    Survey([ranking, state.election.vote(ranking)]).by(voters()).by(
        Model(model_name)
    ).run(
        interview_schedule=schedule,
        disable_remote_inference=True,
        disable_remote_cache=True,
        cache=False,
        stop_on_exceptions=True,
    )
    return state


if __name__ == "__main__":
    print(run_simulation().render_markdown())
