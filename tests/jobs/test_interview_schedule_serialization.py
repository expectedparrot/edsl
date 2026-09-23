import json
from dataclasses import replace

import pytest

from edsl import Agent, InterviewSchedule, QuestionMultipleChoice, Survey
from edsl.jobs import Jobs
from edsl.sharedstate import SharedState, SharedStateMap, StateCondition, current, field
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
        [
            game.read(),
            question,
            game.vote(voter=current.agent.name, ranking=["A", "B", "C"]),
        ]
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


@pytest.mark.parametrize("condition_field", ["stop_when", "finalize_when"])
def test_schedule_compares_symbolic_conditions_by_definition(condition_field):
    condition = voting_job().run_config.parameters.interview_schedule.finalize_when
    schedule = InterviewSchedule.rounds(count=2, **{condition_field: condition})
    restored = InterviewSchedule.from_dict(json.loads(json.dumps(schedule.to_dict())))

    assert restored == schedule
    assert not (restored != schedule)
    assert restored != replace(schedule, count=3)
    assert condition != object()

    alternatives = [
        replace(condition, state_id="another-election"),
        replace(condition, scope=current.agent.other_group),
        replace(
            condition,
            definition=SharedState(
                game=replace(SPEC, complete_when=field("ballots").length() >= 2)
            ),
        ),
    ]
    for changed in alternatives:
        assert condition != changed
        assert restored != replace(schedule, **{condition_field: changed})

    assert StateCondition.from_dict(condition.to_dict()) == condition
