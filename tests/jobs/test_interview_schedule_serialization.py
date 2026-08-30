import json

from edsl import Agent, InterviewSchedule, QuestionMultipleChoice, Survey
from edsl.jobs import Jobs
from edsl.sharedstate import SharedState, SharedStateMap, current
from examples.shared_state_dsl.shared_voting_game import SPEC


def voting_job():
    states = SharedStateMap(SharedState(game=SPEC), state_id="voting-roundtrip")
    game = states.by(current.agent.group).game
    question = QuestionMultipleChoice(
        question_name="vote",
        question_text="Choose a candidate.",
        question_options=["A", "B", "C"],
    )
    survey = Survey(
        [game.read(), question, game.vote(voter=current.agent.name, ranking=["A", "B", "C"])]
    )
    jobs = survey.by([Agent(name="Voter", traits={"group": "election"})])
    jobs.run_config.parameters.interview_schedule = InterviewSchedule.rounds(
        count=1,
        group_by="group",
        within_round="concurrent",
        state_visibility="snapshot",
        finalize_when=game.is_complete(),
    )
    return jobs


def test_interview_schedule_json_round_trip():
    original = voting_job().run_config.parameters.interview_schedule
    payload = json.loads(json.dumps(original.to_dict()))
    restored = InterviewSchedule.from_dict(payload)

    assert restored == original
    assert restored.finalize_when.state_id == "voting-roundtrip"
    assert restored.finalize_when.scope == current.agent.group


def test_jobs_preserves_interview_schedule_through_json():
    original = voting_job()
    payload = json.loads(json.dumps(original.to_dict()))
    restored = Jobs.from_dict(payload)

    assert restored.run_config.parameters.interview_schedule == (
        original.run_config.parameters.interview_schedule
    )
    assert restored.to_dict() == original.to_dict()
