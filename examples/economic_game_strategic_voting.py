"""Plurality voting with a public poll and incentives to desert a trailing candidate."""

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
            Agent(name=f"Voter-{i}", traits={"true_ranking": r})
            for i, r in enumerate(rankings, 1)
        ]
    )


def run_simulation(
    path: str | Path = "economic-game-strategic-voting.jsonl",
    model_name="gemini-2.5-flash",
):
    state = SharedState(
        "strategic-voting",
        FileStateStore(path),
        election=SharedVotingGame(CANDIDATES, 7),
    )
    ballot = QuestionRank(
        question_name="ballot",
        question_text=(
            "You are {{ agent.name }}. Your true preference is "
            "{{ agent.true_ranking }}. This election uses plurality, so only your "
            "first-ranked candidate receives a vote. A credible poll before your "
            "sealed ballot reports Alpha 3, Beta 2, Gamma 2, and says Gamma is less "
            "likely than Beta to defeat Alpha. Submit the ranking that best advances "
            "your true preferences; strategic voting is allowed."
        ),
        question_options=CANDIDATES,
        num_selections=3,
    )
    schedule = InterviewSchedule.rounds(
        count=1,
        reveal="after_round",
        finalize_when=GroupStopCondition("election", "complete"),
    )
    Survey([ballot, state.election.vote(ballot)]).by(voters()).by(
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
