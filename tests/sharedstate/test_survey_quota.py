"""Quota invariants, concurrent admissions, durable retries, and actual survey stops."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import random
import subprocess
import sys

import pytest

from edsl import Agent, AgentList, Model, Survey
from edsl.runner import Runner
from edsl.sharedstate import (
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    resolve_read,
    resolve_write,
)
from edsl.sharedstate.dsl_runtime import Runtime
from edsl.sharedstate.steps import StepContext
from examples.machine_primitives.survey_quota import build_machine, DEMO
from examples.survey_quota import build_survey, demo_agents, demo_answer


def screen(runtime, machine, state, respondent, group):
    return runtime.execute(
        machine, state, "screen", {"respondent_id": respondent, "group": group}
    )


@pytest.mark.parametrize("quota", [-1, True, 1.5, "10"])
def test_invalid_quotas_fail_at_authoring(quota):
    with pytest.raises(ValueError, match="nonnegative integers"):
        build_machine(quota_a=quota)


@pytest.mark.parametrize("seed", range(10))
def test_random_arrivals_never_overfill_or_cross_count(seed):
    machine = Machine.from_json(build_machine().to_json())
    machine.validate()
    runtime = Runtime()
    state, expected = runtime.initial_state(machine), {}
    arrivals = [
        (f"{group}{i}", group) for group in ("A", "B", "Other") for i in range(15)
    ]
    random.Random(seed).shuffle(arrivals)
    for respondent, group in arrivals:
        previous = state
        counts = Counter(expected.values())
        result = screen(runtime, machine, state, respondent, group)
        state = result.state
        if group in ("A", "B") and counts[group] < 10:
            expected[respondent] = group
            assert result.event["status"] == "applied"
        else:
            assert result.event["status"] == "rejected" and state == previous
        assert state["admissions"] == expected
        view = runtime.render_view(
            machine, state, current={"respondent_id": respondent}
        )
        assert view["admitted"] == (respondent in expected)
        assert view["counts"] == {
            g: list(expected.values()).count(g) for g in ("A", "B")
        }
        assert all(n <= 10 for n in view["counts"].values())
        assert runtime.complete(machine, state) == (len(expected) == 20)
    assert Counter(expected.values()) == {"A": 10, "B": 10}


def test_type_a_full_does_not_close_type_b_and_last_admission_can_finish():
    machine, runtime = build_machine(1, 1), Runtime()
    state = runtime.initial_state(machine)
    state = screen(runtime, machine, state, "first", "A").state
    result = screen(runtime, machine, state, "overflow", "A")
    assert result.event["reason_code"] == "type_quota_full"
    assert not runtime.complete(machine, result.state)
    state = screen(runtime, machine, state, "last", "B").state
    assert runtime.complete(machine, state)
    result = screen(runtime, machine, state, "late", "B")
    assert result.event["reason_code"] == "quotas_full"
    own = runtime.render_view(machine, state, current={"respondent_id": "last"})
    assert own["admitted"] and own["your_group"] == "B" and not own["accepting"]
    # No other respondent's identity is in the public projection.
    assert "admissions" not in own and "first" not in json.dumps(own)


def test_identity_retries_never_count_twice_even_after_close():
    machine, runtime = build_machine(1, 1), Runtime()
    state = screen(
        runtime, machine, runtime.initial_state(machine), "person", "A"
    ).state
    state = runtime.close(machine, state)
    again = screen(runtime, machine, state, "person", "A")
    assert again.event["status"] == "noop" and again.state == state
    changed = screen(runtime, machine, state, "person", "B")
    assert (
        changed.event["reason_code"] == "respondent_type_changed"
        and changed.state == state
    )
    refused = screen(runtime, machine, state, "new", "B")
    assert refused.event["reason_code"] == "enrollment_closed"
    assert runtime.render_view(machine, state, current={"respondent_id": "person"})[
        "admitted"
    ]


@pytest.mark.parametrize(
    "respondent,group,code",
    [
        ("", "A", "missing_respondent_id"),
        ("  ", "B", "missing_respondent_id"),
        ("other", "Other", "ineligible_type"),
        ("lowercase", "a", "ineligible_type"),
    ],
)
def test_screened_out_paths_preserve_state(respondent, group, code):
    machine, runtime = build_machine(), Runtime()
    state = runtime.initial_state(machine)
    result = screen(runtime, machine, state, respondent, group)
    assert result.state == state and result.event["reason_code"] == code


@pytest.mark.parametrize(
    "quotas,complete", [((0, 0), True), ((0, 1), False), ((1, 0), False)]
)
def test_zero_quota_boundaries(quotas, complete):
    machine, runtime = build_machine(*quotas), Runtime()
    state = runtime.initial_state(machine)
    assert runtime.complete(machine, state) is complete
    zero_group = "A" if quotas[0] == 0 else "B"
    assert (
        screen(runtime, machine, state, "person", zero_group).event["status"]
        == "rejected"
    )


def test_concurrent_admissions_with_stale_prechecks_and_restart(tmp_path):
    spaces = SharedStateMap(SharedState(quota=build_machine()))
    target, path = spaces.by("study").quota, tmp_path / "quotas.sqlite"
    backend = SQLiteStateBackend(spaces, path, runtime=Runtime())
    arrivals = [(f"{group}{i}", group) for group in ("A", "B") for i in range(16)]
    # Every contender observes the same open snapshot before any admission.
    for respondent, _ in arrivals:
        observed = backend.read(
            resolve_read(
                target.read(),
                StepContext({}, respondent, agent_traits={"respondent_id": respondent}),
            )
        )
        assert observed.value["accepting"]

    def admit(arrival):
        respondent, group = arrival
        operation = resolve_write(
            target.screen(respondent_id=respondent, group=group),
            StepContext({}, respondent),
        )
        # Independent backend objects share the transactional database, not a Python lock.
        return operation, SQLiteStateBackend(spaces, path, runtime=Runtime()).apply(
            operation
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(admit, arrivals))
    restarted = SQLiteStateBackend(
        SharedStateMap.from_dict(spaces.to_dict()), path, runtime=Runtime()
    )
    assert Counter(result.status for _, result in outcomes) == {
        "applied": 20,
        "rejected": 12,
    }
    state = restarted.snapshot("study").state["quota"]
    assert Counter(state["admissions"].values()) == {"A": 10, "B": 10}
    before = restarted.snapshot("study")
    for operation, original in outcomes:
        retry = restarted.apply(operation)
        assert retry.changed is None
        assert (retry.status, retry.reason_code) == (
            original.status,
            original.reason_code,
        )
    assert restarted.snapshot("study") == before
    assert len([e for e in restarted.history() if e["kind"] == "write"]) == 32


def test_concurrent_duplicate_identity_reserves_only_one_place(tmp_path):
    spaces = SharedStateMap(SharedState(quota=build_machine()))
    backend = SQLiteStateBackend(spaces, tmp_path / "quotas.sqlite", runtime=Runtime())
    target = spaces.by("study").quota
    operations = [
        resolve_write(
            target.screen(respondent_id="same", group="A"),
            StepContext({}, f"attempt-{i}"),
        )
        for i in range(12)
    ]
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(backend.apply, operations))
    assert Counter(r.status for r in results) == {"applied": 1, "noop": 11}
    assert backend.snapshot("study").state["quota"]["admissions"] == {"same": "A"}


def test_fresh_process_replays_export_without_authoring_code():
    script = """import json, sys
from edsl.sharedstate import Machine
from edsl.sharedstate.dsl_runtime import Runtime
payload = json.load(sys.stdin)
machine = Machine.from_dict(payload["machine"])
runtime = Runtime()
state = runtime.initial_state(machine)
for name, inputs in payload["commands"]:
    state = runtime.execute(machine, state, name, inputs).state
print(json.dumps(runtime.render_view(machine, state)))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps({"machine": build_machine().to_dict(), "commands": DEMO}),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["counts"] == {"A": 10, "B": 10}


def person(respondent, group):
    agent = Agent(name=respondent, traits={"respondent_id": respondent, "group": group})
    agent.add_direct_question_answering_method(demo_answer)
    return agent


def run(survey, agents):
    return (
        Runner()
        .submit(survey.by(AgentList(agents)).by(Model("test")), cache=False)
        .results()
    )


def test_actual_survey_roundtrip_admits_twenty_and_stops_seven():
    survey, _ = build_survey()
    transported = Survey.from_dict(json.loads(json.dumps(survey.to_dict())))
    results = run(transported, demo_agents())
    assert len(results) == 27 and not results.has_unfixed_exceptions
    admitted = Counter()
    screened = 0
    for row in results:
        if row.answer.get("quota_gate") == "admitted":
            admitted[row.agent.traits["group"]] += 1
            assert row.answer["experience"] == "Shorter waiting times."
        else:
            screened += 1
            assert row.answer.get("experience") is None
    assert admitted == {"A": 10, "B": 10} and screened == 7


def test_survey_stops_before_screener_when_closed_but_preserves_admitted_access():
    survey, _ = build_survey(quota_a=1, quota_b=1)
    first = run(survey, [person("A1", "A")])[0]
    assert first.answer["quota_gate"] == "admitted"
    overflow = run(survey, [person("A2", "A")])[0]
    assert overflow.answer["respondent_type"] == "A"
    assert overflow.answer["quota_gate"] == "screened_out"
    assert overflow.answer.get("experience") is None
    other = run(survey, [person("O1", "Other")])[0]
    assert (
        other.answer["quota_gate"] == "screened_out"
        and other.answer.get("experience") is None
    )
    last = run(survey, [person("B1", "B")])[0]
    assert last.answer["quota_gate"] == "admitted" and last.answer["experience"]
    late = run(survey, [person("B2", "B")])[0]
    assert late.answer["enrollment_gate"] == "closed"
    assert all(
        late.answer.get(name) is None
        for name in ("respondent_type", "quota_gate", "experience")
    )
    retry = run(survey, [person("A1", "A")])[0]
    assert retry.answer["quota_gate"] == "admitted" and retry.answer["experience"]
    changed = run(survey, [person("A1", "B")])[0]
    assert (
        changed.answer["quota_gate"] == "screened_out"
        and changed.answer.get("experience") is None
    )


def test_same_identity_in_independent_studies_has_independent_quotas(tmp_path):
    spaces = SharedStateMap(SharedState(quota=build_machine(1, 0)))
    backend = SQLiteStateBackend(spaces, tmp_path / "quotas.sqlite", runtime=Runtime())
    for scope in ("study-1", "study-2"):
        operation = resolve_write(
            spaces.by(scope).quota.screen(respondent_id="same", group="A"),
            StepContext({}, scope),
        )
        assert backend.apply(operation).status == "applied"
        assert backend.snapshot(scope).state["quota"]["admissions"] == {"same": "A"}


def test_abandoned_admission_is_not_reclaimed(tmp_path):
    spaces = SharedStateMap(SharedState(quota=build_machine(1, 1)))
    backend = SQLiteStateBackend(spaces, tmp_path / "quotas.sqlite", runtime=Runtime())
    target = spaces.by("study").quota
    first = resolve_write(
        target.screen(respondent_id="abandoned", group="A"), StepContext({}, "first")
    )
    assert backend.apply(first).status == "applied"
    # No completion command is submitted; a fresh backend still sees the reservation.
    restarted = SQLiteStateBackend(
        spaces, tmp_path / "quotas.sqlite", runtime=Runtime()
    )
    second = resolve_write(
        target.screen(respondent_id="next", group="A"), StepContext({}, "second")
    )
    assert restarted.apply(second).reason_code == "type_quota_full"


def test_profiler_measures_replayed_work_without_changing_semantics():
    from examples.machine_primitives.profile_corpus import profile
    from examples.machine_primitives.__main__ import run_example

    report = profile("survey_quota")
    replay = run_example("survey_quota")
    assert report["definition_bytes"] == replay["definition_bytes"]
    assert report["expression_occurrences"] > report["distinct_expression_trees"]
    assert [t["status"] for t in report["transitions"]] == [
        d["status"] for d in replay["decisions"]
    ]
    assert all(t["budget_steps"] > 0 for t in report["transitions"])
