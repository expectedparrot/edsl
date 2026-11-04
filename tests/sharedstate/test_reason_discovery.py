"""Adaptive options, saturation, identity, replay, and sequential survey execution."""

from concurrent.futures import ThreadPoolExecutor
import json
import random
import subprocess
import sys

import pytest

from edsl import AgentList, InterviewSchedule, Model, Results, Survey
from edsl.runner import Runner
from edsl.sharedstate import (
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    resolve_write,
)
from edsl.sharedstate.dsl_runtime import Runtime
from edsl.sharedstate.steps import StepContext
from examples.machine_primitives.reason_discovery import (
    DEFAULT_SEEDS,
    DEMO,
    build_machine,
)
from examples.reason_discovery import (
    ALL_REASONS,
    build_survey,
    demo_agents,
    demo_answer,
    make_agent,
    run_demo,
)


def submit(runtime, machine, state, respondent, reason, command="suggest"):
    return runtime.execute(
        machine, state, command, {"respondent_id": respondent, "reason": reason}
    )


@pytest.mark.parametrize("seeds", [[], [""], ["  "], [1], ["a", " A "], ["Other"], "a"])
def test_invalid_seeds(seeds):
    with pytest.raises(ValueError):
        build_machine(seeds)


@pytest.mark.parametrize("patience", [0, -1, True, 1.5])
def test_invalid_patience(patience):
    with pytest.raises(ValueError):
        build_machine(patience=patience)


def test_initial_catalog_does_not_know_population_ground_truth():
    machine = build_machine()
    machine.validate()
    for reason in ALL_REASONS[2:]:
        assert reason not in machine.to_json()
    assert Runtime().initial_state(machine)["reasons"] == list(DEFAULT_SEEDS)


def test_other_is_not_an_observation_until_valid_text_arrives():
    machine, runtime = build_machine(), Runtime()
    state = runtime.initial_state(machine)
    result = submit(runtime, machine, state, "R1", "Other", "select")
    assert result.state == state and result.event["status"] == "noop"
    result = submit(runtime, machine, state, "R1", "Convenience")
    assert result.state["quiet_streak"] == 0 and len(result.state["responses"]) == 1
    assert result.state["reasons"] == [*DEFAULT_SEEDS, "Convenience"]


def test_new_reason_resets_nine_quiet_observations_and_tenth_stops():
    machine, runtime = build_machine(), Runtime()
    state = runtime.initial_state(machine)
    for i in range(9):
        state = submit(runtime, machine, state, str(i), "Lower price", "select").state
        assert state["quiet_streak"] == i + 1 and not runtime.complete(machine, state)
    state = submit(runtime, machine, state, "new", "Convenience").state
    assert state["quiet_streak"] == 0
    for i in range(10):
        state = submit(
            runtime, machine, state, f"after-{i}", "Convenience", "select"
        ).state
        assert runtime.complete(machine, state) is (i == 9)
    previous = state
    refused = submit(runtime, machine, state, "late", "Habit")
    assert (
        refused.event["reason_code"] == "discovery_closed" and refused.state == previous
    )


def test_duplicate_suggestions_increment_streak_but_identity_retries_do_not():
    machine, runtime = build_machine(patience=2), Runtime()
    state = runtime.initial_state(machine)
    for respondent, reason in [
        ("A", "  Convenience  "),
        ("B", "CONVENIENCE"),
        ("C", " convenience "),
    ]:
        state = submit(runtime, machine, state, respondent, reason).state
    assert state["reasons"] == [*DEFAULT_SEEDS, "Convenience"]
    assert state["quiet_streak"] == 2 and runtime.complete(machine, state)
    duplicate = submit(runtime, machine, state, "A", "convenience")
    assert duplicate.event["status"] == "noop" and duplicate.state == state
    changed = submit(runtime, machine, state, "A", "Habit")
    assert (
        changed.event["reason_code"] == "respondent_reason_changed"
        and changed.state == state
    )


@pytest.mark.parametrize(
    "respondent,reason,command,code",
    [
        ("", "Price", "suggest", "missing_respondent_id"),
        ("R", "  ", "suggest", "empty_reason"),
        ("R", " OTHER ", "suggest", "reserved_reason"),
        ("R", "Not in choices", "select", "unknown_choice"),
    ],
)
def test_invalid_observations_do_not_advance_streak(respondent, reason, command, code):
    machine, runtime = build_machine(), Runtime()
    state = runtime.initial_state(machine)
    result = submit(runtime, machine, state, respondent, reason, command)
    assert result.event["reason_code"] == code and result.state == state


def test_manual_close_preserves_replay_and_refuses_new_agents():
    machine, runtime = build_machine(), Runtime()
    state = submit(runtime, machine, runtime.initial_state(machine), "R", "Habit").state
    state = runtime.close(machine, state)
    assert not runtime.render_view(machine, state)["accepting"]
    assert not runtime.complete(machine, state)  # Closed early, not saturated.
    assert submit(runtime, machine, state, "R", "Habit").event["status"] == "noop"
    assert (
        submit(runtime, machine, state, "new", "Habit").event["reason_code"]
        == "discovery_closed"
    )


@pytest.mark.parametrize("seed", range(10))
def test_random_sequences_match_independent_catalog_and_streak(seed):
    rng = random.Random(seed)
    machine = Machine.from_json(build_machine(patience=6).to_json())
    runtime = Runtime()
    state, catalog, streak, seen = (
        runtime.initial_state(machine),
        list(DEFAULT_SEEDS),
        0,
        {},
    )
    for i in range(40):
        reason = rng.choice(ALL_REASONS)
        command = (
            "select" if reason in catalog and rng.choice([True, False]) else "suggest"
        )
        old = state
        result = submit(runtime, machine, state, f"R{i}", reason, command)
        state = result.state
        if streak == 6:
            assert result.event["reason_code"] == "discovery_closed" and state == old
        else:
            if reason not in catalog:
                catalog.append(reason)
                streak = 0
            else:
                streak += 1
            seen[f"R{i}"] = reason.casefold()
        assert state["reasons"] == catalog
        assert state["quiet_streak"] == streak and state["responses"] == seen
        assert Runtime().render_view(machine, state)["options"] == [*catalog, "Other"]


def test_reopen_mid_streak_and_retry_completed_writes(tmp_path):
    spaces = SharedStateMap(SharedState(discovery=build_machine(patience=3)))
    path = tmp_path / "discovery.sqlite"
    target = spaces.by("study").discovery
    originals = []
    for i, reason in enumerate(
        ["Convenience", "Convenience", "Habit", "Habit", "Habit", "Habit"]
    ):
        backend = SQLiteStateBackend(
            SharedStateMap.from_dict(spaces.to_dict()), path, runtime=Runtime()
        )
        operation = resolve_write(
            target.suggest(respondent_id=f"R{i}", reason=reason),
            StepContext({}, str(i)),
        )
        originals.append((operation, backend.apply(operation)))
    before = backend.snapshot("study")
    assert before.state["discovery"]["quiet_streak"] == 3
    for operation, original in originals:
        replay = SQLiteStateBackend(spaces, path, runtime=Runtime()).apply(operation)
        assert replay.changed is None and replay.status == original.status
    assert backend.snapshot("study") == before and len(backend.history()) == 6


def test_concurrent_same_new_reason_is_added_once(tmp_path):
    spaces = SharedStateMap(SharedState(discovery=build_machine()))
    path = tmp_path / "discovery.sqlite"
    target = spaces.by("study").discovery

    def write(item):
        i, reason = item
        backend = SQLiteStateBackend(spaces, path, runtime=Runtime())
        return backend.apply(
            resolve_write(
                target.suggest(respondent_id=str(i), reason=reason),
                StepContext({}, str(i)),
            )
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        decisions = list(pool.map(write, enumerate(["Habit", " HABIT "])))
    assert all(d.status == "applied" for d in decisions)
    state = (
        SQLiteStateBackend(spaces, path, runtime=Runtime())
        .snapshot("study")
        .state["discovery"]
    )
    assert [r.casefold() for r in state["reasons"]] == [
        *(r.casefold() for r in DEFAULT_SEEDS),
        "habit",
    ]
    assert state["quiet_streak"] == 1 and len(state["responses"]) == 2


def test_concurrent_quiet_responses_cannot_overshoot_threshold(tmp_path):
    spaces = SharedStateMap(SharedState(discovery=build_machine(patience=2)))
    backend = SQLiteStateBackend(
        spaces, tmp_path / "discovery.sqlite", runtime=Runtime()
    )
    target = spaces.by("study").discovery
    operations = [
        resolve_write(
            target.select(respondent_id=str(i), reason="Lower price"),
            StepContext({}, str(i)),
        )
        for i in range(8)
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(backend.apply, operations))
    assert sum(r.status == "applied" for r in results) == 2
    state = backend.snapshot("study").state["discovery"]
    assert state["quiet_streak"] == len(state["responses"]) == 2


def test_fresh_process_executes_export_without_authoring_helpers():
    script = """import json, sys
from edsl.sharedstate import Machine
from edsl.sharedstate.dsl_runtime import Runtime
payload = json.load(sys.stdin)
spec = Machine.from_dict(payload["machine"])
runtime = Runtime()
state = runtime.initial_state(spec)
for command, inputs in payload["commands"]:
    state = runtime.execute(spec, state, command, inputs).state
print(json.dumps(runtime.render_view(spec, state)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps({"machine": build_machine().to_dict(), "commands": DEMO}),
        text=True,
        capture_output=True,
        check=True,
    )
    view = json.loads(result.stdout)
    assert view["quiet_streak"] == 10 and view["saturated"]
    assert len(view["reasons"]) == 5 and view["respondents"] == 14


def run_population(truths, patience=10, spy=None):
    survey, _, schedule = build_survey(patience=patience)
    survey = Survey.from_dict(json.loads(json.dumps(survey.to_dict())))
    schedule = InterviewSchedule.from_dict(json.loads(json.dumps(schedule.to_dict())))
    agents = AgentList([make_agent(i, reason) for i, reason in enumerate(truths)])
    if spy is not None:

        def answer(self, question, scenario):
            if question.question_name == "reason":
                spy[self.traits["respondent_id"]] = list(question.question_options)
            return demo_answer(self, question, scenario)

        for agent in agents:
            agent.remove_direct_question_answering_method()
            agent.add_direct_question_answering_method(answer)
    # Supply the pool backwards; the serialized schedule must establish turn order.
    results = (
        Runner(interview_schedule=schedule)
        .submit(
            survey.by(AgentList(list(reversed(agents)))).by(Model("test")), cache=False
        )
        .results()
    )
    assert not results.has_unfixed_exceptions
    assert (
        survey.question_names_to_questions()["reason"].question_options
        == "{{ shared_state.discovery.options }}"
    )
    return results


def test_actual_options_grow_and_only_other_asks_for_text():
    observed = {}
    truths = [
        "Convenience",
        "Convenience",
        "Habit",
        "Habit",
        "Recommendation",
        "Recommendation",
        "Lower price",
        "Lower price",
        "Habit",
    ]
    results = run_population(truths, patience=3, spy=observed)
    rows = {r.agent.traits["respondent_id"]: r.answer for r in results}
    assert observed["R0"] == [*DEFAULT_SEEDS, "Other"]
    assert observed["R1"] == [*DEFAULT_SEEDS, "Convenience", "Other"]
    assert (
        rows["R0"]["reason"] == "Other" and rows["R0"]["other_reason"] == "Convenience"
    )
    assert (
        rows["R1"]["reason"] == "Convenience" and rows["R1"].get("other_reason") is None
    )
    assert "R8" not in observed and rows["R8"].get("reason") is None
    # Catalog growth later in this job must not rewrite an earlier presentation.
    restored = Results.from_dict(json.loads(json.dumps(results.to_dict())))
    for row in restored:
        rid = row.agent.traits["respondent_id"]
        attrs = row.data["question_to_attributes"]["reason"]
        if rid in observed:
            assert row.get_question_options("reason") == observed[rid]
            assert attrs["presentation"]["source"] == "agent_direct"
        else:
            assert "presentation" not in attrs
    writes = [
        e
        for e in results.shared_state["bindings"][0]["events"]
        if e["kind"] == "write" and e["status"] == "applied"
    ]
    assert [e["state"]["discovery"]["quiet_streak"] for e in writes] == [
        0,
        1,
        0,
        1,
        0,
        1,
        2,
        3,
    ]
    assert [e["inputs"]["respondent_id"] for e in writes] == [f"R{i}" for i in range(8)]


def test_saturation_can_stop_before_an_unseen_reason():
    observed = {}
    results = run_population(
        ["Lower price"] * 10 + ["Habit", "Convenience"], spy=observed
    )
    assert len(observed) == 10 and "R10" not in observed
    writes = [
        e for e in results.shared_state["bindings"][0]["events"] if e["kind"] == "write"
    ]
    final = writes[-1]["state"]["discovery"]
    assert final["reasons"] == list(DEFAULT_SEEDS) and final["quiet_streak"] == 10


def test_seeded_population_and_demo_recover_five_then_stop_after_ten():
    people = demo_agents()
    assert {p.traits["true_reason"] for p in people} == set(ALL_REASONS)
    assert [p.traits for p in people] == [p.traits for p in demo_agents()]
    report = run_demo()
    assert report["interviewed"] == 21 and report["population_size"] == 100
    assert report["stop_reason"] == "saturation" and report["quiet_streak"] == 10
    assert set(report["reasons_discovered"]) == set(ALL_REASONS)
    assert report["undiscovered_ground_truth"] == []
    assert [h["quiet_streak"] for h in report["history"][-10:]] == list(range(1, 11))


def test_finite_pool_exhaustion_is_not_reported_as_saturation():
    report = run_demo(count=3)
    assert report["interviewed"] == 3 and report["quiet_streak"] < 10
    assert (
        report["stop_reason"] == "population_exhausted"
        and report["undiscovered_ground_truth"]
    )


@pytest.mark.parametrize("count", [0, -1, True, 1.5])
def test_population_requires_positive_integer_size(count):
    with pytest.raises(ValueError, match="population count"):
        demo_agents(count=count)


def test_survey_resumes_catalog_and_streak_across_jobs():
    survey, _, schedule = build_survey(patience=2)
    first = (
        Runner(interview_schedule=schedule)
        .submit(
            survey.by(AgentList([make_agent(0, "Habit"), make_agent(1, "Habit")])).by(
                Model("test")
            ),
            cache=False,
        )
        .results()
    )
    assert not first.has_unfixed_exceptions
    restored = Survey.from_dict(json.loads(json.dumps(survey.to_dict())))
    resumed_schedule = InterviewSchedule.from_dict(schedule.to_dict())
    later = (
        Runner(interview_schedule=resumed_schedule)
        .submit(
            restored.by(
                AgentList([make_agent(2, "Habit"), make_agent(3, "Convenience")])
            ).by(Model("test")),
            cache=False,
        )
        .results()
    )
    assert not later.has_unfixed_exceptions
    answers = {r.agent.traits["respondent_id"]: r.answer for r in later}
    assert (
        answers["R2"]["reason"] == "Habit" and answers["R2"].get("other_reason") is None
    )
    assert answers["R3"].get("reason") is None
    writes = [
        e for e in later.shared_state["bindings"][0]["events"] if e["kind"] == "write"
    ]
    assert writes[-1]["state"]["discovery"]["quiet_streak"] == 2
