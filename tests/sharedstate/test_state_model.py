import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from edsl import QuestionMultipleChoice, Survey
from edsl.sharedstate import (
    Command,
    SQLiteStateBackend,
    Machine,
    SharedState,
    SharedStateMap,
    T,
    current,
    field,
    input_,
    put,
    reduce_,
    resolve_read,
    resolve_write,
    state_field,
)
from edsl.sharedstate.steps import StepContext


ACTIVITIES = ("bike ride", "sailing", "hike", "beach day")


def activity_poll():
    return Machine(
        name="ActivityPoll",
        constants={"activities": ACTIVITIES},
        fields={
            "votes": state_field(T.map(T.text(), T.choice(ACTIVITIES)), {})
        },
        commands={
            "vote": Command(
                inputs={
                    "voter": T.text(),
                    "activity": T.choice(ACTIVITIES),
                },
                effects=(
                    put("votes", input_("voter"), input_("activity")),
                ),
            )
        },
        view={
            "votes": field("votes"),
            "counts": reduce_("count_by", field("votes").values()),
        },
    )


def test_definition_map_and_steps_are_storage_free_and_serializable():
    definition = SharedState(poll=activity_poll())
    state_map = SharedStateMap(definition, state_id="activity-study")
    family = state_map.by(current.agent.family_id)
    question = QuestionMultipleChoice(
        question_name="activity",
        question_text="What should we do?",
        question_options=list(ACTIVITIES),
    )
    write = family.poll.vote(
        voter=current.agent.name, activity=question.answer
    )
    read = family.poll.read()

    serialized = state_map.to_dict()
    assert "store" not in json.dumps(serialized)
    assert SharedStateMap.from_dict(serialized).state_id == "activity-study"
    assert write.step_id != family.poll.vote(
        voter=current.agent.name, activity=question.answer
    ).step_id
    assert read.target == "poll"


def test_local_binding_resolves_context_logs_reads_and_is_idempotent(tmp_path):
    state_map = SharedStateMap(
        SharedState(poll=activity_poll()), state_id="activity-study"
    )
    family = state_map.by(current.agent.family_id)
    question = QuestionMultipleChoice(
        question_name="activity",
        question_text="What should we do?",
        question_options=list(ACTIVITIES),
    )
    step = family.poll.vote(voter=current.agent.name, activity=question.answer)
    context = StepContext(
        answers={"activity": "hike"},
        interview_id="response-1",
        agent_traits={"name": "Ada", "family_id": 7},
    )
    operation = resolve_write(step, context)
    binding = SQLiteStateBackend(state_map, tmp_path / "state.sqlite3")

    first = binding.apply(operation)
    retry = binding.apply(operation)
    observed = binding.read(resolve_read(family.poll.read(), context))

    assert first.accepted and retry.accepted
    assert observed.scope == 7
    assert observed.version == 1
    assert observed.value == {"votes": {"Ada": "hike"}, "counts": {"hike": 1}}
    assert [event["kind"] for event in binding.history()] == ["write", "read"]
    assert binding.history()[-1]["value"] == observed.value


def test_concurrent_local_writes_serialize_per_file(tmp_path):
    state_map = SharedStateMap(
        SharedState(poll=activity_poll()), state_id="activity-study"
    )
    family = state_map.by("family-1")
    binding = SQLiteStateBackend(state_map, tmp_path / "state.sqlite3")

    def vote(index):
        context = StepContext({}, f"response-{index}")
        step = family.poll.vote(voter=f"person-{index}", activity=ACTIVITIES[index % 4])
        return binding.apply(resolve_write(step, context))

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(vote, range(50)))

    observed = binding.read(
        resolve_read(family.poll.read(), StepContext({}, "observer"))
    )
    assert all(outcome.accepted for outcome in outcomes)
    assert observed.version == 50
    assert len(observed.value["votes"]) == 50
    assert sum(observed.value["counts"].values()) == 50


def test_machine_command_inputs_are_checked_when_step_is_created():
    poll = SharedStateMap(SharedState(poll=activity_poll())).by("family")
    with pytest.raises(Exception, match="input mismatch"):
        poll.poll.vote(activity="hike")


def test_survey_round_trip_preserves_explicit_reads_and_writes():
    state_map = SharedStateMap(
        SharedState(poll=activity_poll()), state_id="activity-study"
    )
    family = state_map.by(current.agent.family_id)
    question = QuestionMultipleChoice(
        question_name="activity",
        question_text=(
            "Current votes: {{ shared_state.poll.votes }}. What should we do?"
        ),
        question_options=list(ACTIVITIES),
    )
    survey = Survey(
        [
            family.poll.read(),
            question,
            family.poll.vote(
                voter=current.agent.name,
                activity=question.answer,
            ),
        ]
    )

    payload = survey.to_dict(add_edsl_version=False)
    assert "state_steps" in payload
    assert "shared_state" not in payload
    restored = Survey.from_dict(payload)
    assert restored.to_dict(add_edsl_version=False) == payload
    assert restored._state_reads["activity"][0].state_id == "activity-study"
    assert restored._state_writes["activity"][0].command == "vote"


def test_results_shared_state_round_trip():
    from edsl import Results

    results = Results(survey=Survey([]), data=[])
    results.shared_state = {
        "version": 1,
        "bindings": [{"state_id": "poll", "events": [{"kind": "read"}]}],
    }
    restored = Results.from_dict(results.to_dict())
    assert restored.shared_state == results.shared_state
