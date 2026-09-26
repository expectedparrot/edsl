"""Contract tests for the sole, machine-based shared-state implementation."""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    current,
    field,
    input_,
    put,
    reduce_,
    resolve_read,
    resolve_write,
    set_,
    state_field,
)
from edsl.sharedstate.steps import StepContext


ACTIVITIES = ("bike ride", "sailing", "hike", "beach day")


def activity_poll() -> Machine:
    return Machine(
        name="ActivityPoll",
        constants={"activities": ACTIVITIES},
        fields={"votes": state_field(T.map(T.text(), T.choice(ACTIVITIES)), {})},
        commands={
            "vote": Command(
                inputs={"voter": T.text(), "activity": T.choice(ACTIVITIES)},
                effects=(put("votes", input_("voter"), input_("activity")),),
            )
        },
        view={
            "votes": field("votes"),
            "counts": reduce_("count_by", field("votes").values()),
        },
        complete_when=field("votes").length() >= 8,
    )


def state_map() -> SharedStateMap:
    return SharedStateMap(SharedState(poll=activity_poll()), state_id="activity")


def _write_vote(path: str, start: int, count: int) -> None:
    spaces = state_map()
    backend = SQLiteStateBackend(spaces, path)
    poll = spaces.by("family").poll
    for index in range(start, start + count):
        context = StepContext({}, f"worker-{index}")
        step = poll.vote(voter=f"p-{index}", activity=ACTIVITIES[index % 4])
        backend.apply(resolve_write(step, context))


def test_sqlite_backend_serializes_separate_processes(tmp_path):
    path = tmp_path / "state.sqlite3"
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_write_vote, str(path), worker * 10, 10) for worker in range(4)]
        for future in futures:
            future.result(timeout=30)

    spaces = state_map()
    backend = SQLiteStateBackend(spaces, path)
    snapshot = backend.snapshot("family")
    assert snapshot.version == 40
    assert len(snapshot.state["poll"]["votes"]) == 40
    assert len(backend.history()) == 40


def test_scopes_are_isolated_and_reads_are_audited(tmp_path):
    spaces = state_map()
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite3")
    for scope, voter in (("alpha", "Ada"), ("beta", "Ben")):
        poll = spaces.by(scope).poll
        context = StepContext({}, voter)
        backend.apply(
            resolve_write(poll.vote(voter=voter, activity="hike"), context)
        )
        observed = backend.read(resolve_read(poll.read(), context))
        assert observed.scope == scope
        assert observed.version == 1
        assert observed.value["votes"] == {voter: "hike"}

    events = backend.history()
    assert [event["kind"] for event in events] == ["write", "read", "write", "read"]
    assert len({event["read_id"] for event in events if event["kind"] == "read"}) == 2


def test_runtime_receives_interview_agent_and_round_capabilities(tmp_path):
    from edsl.sharedstate import append, current_value, record

    machine = Machine(
        name="ContextAudit",
        constants={},
        fields={"seen": state_field(T.sequence(T.map()), [])},
        commands={
            "record": Command(
                inputs={},
                effects=(
                    append(
                        "seen",
                        record(
                            interview=current_value("interview_id"),
                            name=current_value("name"),
                            role=current_value("role"),
                            round=current_value("round"),
                        ),
                    ),
                ),
            )
        },
        view={"seen": field("seen"), "viewer": current_value("name")},
    )
    spaces = SharedStateMap(SharedState(audit=machine), state_id="context-audit")
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite3")
    audit = spaces.by("scope").audit
    context = StepContext(
        {},
        "interview-7",
        agent_traits={"name": "Amina", "role": "buyer"},
        run_context={"round": 2},
    )

    backend.apply(resolve_write(audit.record(), context))
    observed = backend.read(resolve_read(audit.read(), context))

    assert observed.value == {
        "seen": [
            {
                "interview": "interview-7",
                "name": "Amina",
                "role": "buyer",
                "round": 2,
            }
        ],
        "viewer": "Amina",
    }


def test_retry_is_idempotent_and_outcome_is_advisory(tmp_path):
    spaces = state_map()
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite3")
    poll = spaces.by("family").poll
    context = StepContext({}, "same-interview")
    operation = resolve_write(
        poll.vote(voter="Ada", activity="sailing"), context
    )

    first = backend.apply(operation)
    retry = backend.apply(operation)

    assert first.accepted and retry.accepted
    assert first.observed_version == retry.observed_version == 1
    assert retry.changed is None
    assert len(backend.history()) == 1


def test_history_reconstructs_every_committed_version(tmp_path):
    spaces = state_map()
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite3")
    poll = spaces.by("family").poll
    for index, activity in enumerate(ACTIVITIES, 1):
        backend.apply(
            resolve_write(
                poll.vote(voter=f"p-{index}", activity=activity),
                StepContext({}, f"i-{index}"),
            )
        )

    writes = [event for event in backend.history() if event["kind"] == "write"]
    assert [event["version"] for event in writes] == [1, 2, 3, 4]
    assert writes[-1]["state"] == backend.snapshot("family").state


def test_definition_rejects_invalid_nested_initial_values():
    invalid = Machine(
        name="Invalid",
        constants={},
        fields={"values": state_field(T.sequence(T.integer()), [1, "two"])},
        commands={},
        view={"values": field("values")},
    )
    with pytest.raises(ValueError, match=r"values\[1\] must be an integer"):
        SharedState(values=invalid)


def test_definition_rejects_unknown_expression_even_in_unselected_branch():
    from edsl.sharedstate import Expr, choose

    invalid = Machine(
        name="Invalid",
        constants={},
        fields={"value": state_field(T.integer(), 1)},
        commands={},
        view={"value": choose(True, field("value"), Expr("execute_python"))},
    )
    with pytest.raises(ValueError, match="unknown expression"):
        SharedState(values=invalid)


def test_machine_completion_condition_is_typed():
    spaces = state_map()
    condition = spaces.by(current.agent.family_id).poll.is_complete()
    assert condition.state_id == "activity"
    assert condition.target == "poll"
    assert condition.scope == current.agent.family_id


def test_backend_protocol_is_runtime_checkable(tmp_path):
    from edsl.sharedstate import StateBackend

    backend = SQLiteStateBackend(state_map(), Path(tmp_path) / "state.sqlite3")
    assert isinstance(backend, StateBackend)


def test_invalid_transition_rolls_back_without_an_event(tmp_path):
    machine = Machine(
        name="TypedCounter",
        constants={},
        fields={"count": state_field(T.integer(), 0)},
        commands={
            "set": Command(
                inputs={"value": T.any()}, effects=(set_("count", input_("value")),)
            )
        },
        view={"count": field("count")},
    )
    spaces = SharedStateMap(SharedState(counter=machine), state_id="typed")
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite3")
    step = spaces.by("scope").counter.set(value="not an integer")

    with pytest.raises(ValueError, match="count must be an integer"):
        backend.apply(resolve_write(step, StepContext({}, "interview")))

    assert backend.snapshot("scope").version == 0
    assert backend.history() == []


def test_runner_records_visibility_and_state_continues_across_results():
    from uuid import uuid4

    from edsl import Agent, AgentList, InterviewSchedule, Model
    from examples.shared_state_activity_poll import build_survey

    state_id = f"runner-contract-{uuid4()}"

    def agents(prefix, count, starting_version):
        people = []
        for index in range(count):
            agent = Agent(
                name=f"{prefix}-{index}",
                traits={
                    "family_id": "family",
                    "turn": index,
                    "expected_seen": starting_version + index,
                },
            )

            def answer(self, question, scenario):
                assert len(scenario["shared_state"]["poll"]["votes"]) == self.traits[
                    "expected_seen"
                ]
                return "hike"

            agent.add_direct_question_answering_method(answer)
            people.append(agent)
        return AgentList(people)

    schedule = InterviewSchedule.grouped_round_robin("family_id", "turn")

    def execute(prefix, count, starting_version):
        return (
            build_survey(state_id)
            .by(agents(prefix, count, starting_version))
            .by(Model("test"))
            .run(
                interview_schedule=schedule,
                disable_remote_inference=True,
                disable_remote_cache=True,
                cache=False,
                stop_on_exceptions=True,
            )
        )

    first = execute("a", 4, 0)
    first_binding = first.shared_state["bindings"][0]
    first_reads = [e for e in first_binding["events"] if e["kind"] == "read"]
    assert [event["version"] for event in first_reads] == [0, 1, 2, 3]
    assert first_binding["entry_snapshots"][0]["version"] == 0
    assert first_binding["exit_snapshots"][0]["version"] == 4
    assert type(first).from_dict(first.to_dict()).shared_state == first.shared_state

    second = execute("b", 2, 4)
    second_binding = second.shared_state["bindings"][0]
    second_reads = [e for e in second_binding["events"] if e["kind"] == "read"]
    assert [event["version"] for event in second_reads] == [4, 5]
    assert second_binding["entry_snapshots"][0]["version"] == 4
    assert second_binding["exit_snapshots"][0]["version"] == 6
    assert len(second_binding["events"]) == 4


def test_snapshot_round_gives_every_agent_the_same_committed_view():
    from uuid import uuid4

    from edsl import Agent, AgentList, InterviewSchedule, Model
    from examples.shared_state_activity_poll import build_survey

    people = []
    for index in range(4):
        agent = Agent(
            name=f"p-{index}", traits={"family_id": "family", "turn": index}
        )

        def answer(self, question, scenario):
            assert scenario["shared_state"]["poll"]["votes"] == {}
            return "hike"

        agent.add_direct_question_answering_method(answer)
        people.append(agent)

    schedule = InterviewSchedule.rounds(
        count=1,
        group_by="family_id",
        within_round="concurrent",
        state_visibility="snapshot",
    )
    results = (
        build_survey(f"snapshot-{uuid4()}")
        .by(AgentList(people))
        .by(Model("test"))
        .run(
            interview_schedule=schedule,
            disable_remote_inference=True,
            disable_remote_cache=True,
            cache=False,
            stop_on_exceptions=True,
        )
    )
    events = results.shared_state["bindings"][0]["events"]
    reads = [event for event in events if event["kind"] == "read"]
    assert len(reads) == 4
    assert {event["version"] for event in reads} == {0}
