"""Fixed assignments, exact answer coverage, and generated survey skip rules."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import random
import subprocess
import sys

import pytest

from edsl import AgentList, InterviewSchedule, Model, Survey
from edsl.runner import Runner
from edsl.sharedstate import (
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    resolve_write,
)
from edsl.sharedstate.dsl_runtime import DSLValidationError, Runtime
from edsl.sharedstate.steps import StepContext
from examples.machine_primitives.question_coverage import (
    DEFAULT_QUESTIONS,
    DEMO,
    build_machine,
)
from examples.question_coverage import build_survey, demo_agents, run_demo


def assign(runtime, machine, state, respondent):
    return runtime.execute(machine, state, "assign", {"respondent_id": respondent})


def answer(runtime, machine, state, respondent, question, value=3):
    return runtime.execute(
        machine,
        state,
        "record_answer",
        {"respondent_id": respondent, "question": question, "answer": value},
    )


@pytest.mark.parametrize(
    "questions", [[], [""], ["q", "q"], ["bad name"], ["coverage_slot_1"], [1], "q01"]
)
def test_invalid_question_identifiers(questions):
    with pytest.raises(ValueError):
        build_machine(questions)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
@pytest.mark.parametrize("parameter", ["target", "per_agent"])
def test_positive_integer_parameters(parameter, value):
    with pytest.raises(ValueError):
        build_machine(**{parameter: value})


def test_assignment_is_fixed_and_does_not_count_as_answers():
    machine, runtime = (
        build_machine(["q1", "q2", "q3"], target=2, per_agent=2),
        Runtime(),
    )
    state = runtime.initial_state(machine)
    state = assign(runtime, machine, state, "A").state
    assert state["assignments"]["A"] == ["q1", "q2"]
    assert state["counts"] == {"q1": 0, "q2": 0, "q3": 0}
    state = answer(runtime, machine, state, "A", "q1").state
    retry = assign(runtime, machine, state, "A")
    assert retry.event["status"] == "noop" and retry.state == state
    own = runtime.render_view(machine, state, current={"respondent_id": "A"})
    assert own["assigned"] == ["q1", "q2"] and own["pending"] == ["q2"]
    assert "answers" not in own and "assignments" not in own
    state = assign(runtime, machine, state, "B").state
    assert state["assignments"]["B"] == ["q2", "q3"]


@pytest.mark.parametrize("seed", range(5))
def test_assignment_and_coverage_match_reference_with_abandoned_answers(seed):
    machine = Machine.from_json(
        build_machine(["q1", "q2", "q3", "q4", "q5"], target=3, per_agent=2).to_json()
    )
    machine.validate()
    runtime, rng = Runtime(), random.Random(seed)
    state = runtime.initial_state(machine)
    expected = dict.fromkeys(machine.constants["questions"], 0)
    ledger = {}
    for i in range(50):
        if runtime.complete(machine, state):
            break
        respondent = f"R{i}"
        chosen = sorted(
            (q for q, n in expected.items() if n < 3), key=lambda q: (expected[q], q)
        )[:2]
        state = assign(runtime, machine, state, respondent).state
        assert state["assignments"][respondent] == chosen
        for question in chosen:
            if rng.random() < 0.2:
                continue  # Abandon this assigned question; capacity is not consumed.
            value = rng.randint(1, 5)
            state = answer(runtime, machine, state, respondent, question, value).state
            expected[question] += 1
            ledger.setdefault(respondent, {})[question] = value
            assert state["counts"] == expected and state["answers"] == ledger
            assert all(n <= 3 for n in expected.values())
    assert runtime.complete(machine, state) and sum(expected.values()) == 15


def test_tail_assignment_is_partial_and_completion_requires_answers():
    machine, runtime = (
        build_machine(["q1", "q2", "q3", "q4", "q5"], target=1),
        Runtime(),
    )
    state = assign(runtime, machine, runtime.initial_state(machine), "A").state
    for q in state["assignments"]["A"]:
        state = answer(runtime, machine, state, "A", q).state
    state = assign(runtime, machine, state, "B").state
    assert state["assignments"]["B"] == ["q4", "q5"] and not runtime.complete(
        machine, state
    )
    for q in state["assignments"]["B"]:
        state = answer(runtime, machine, state, "B", q).state
    assert runtime.complete(machine, state)
    state = assign(runtime, machine, state, "C").state
    assert state["assignments"]["C"] == []


def test_answer_retry_is_noop_and_changed_or_unassigned_answer_is_rejected():
    machine, runtime = build_machine(["q1", "q2"], target=1, per_agent=1), Runtime()
    state = assign(runtime, machine, runtime.initial_state(machine), "A").state
    state = answer(runtime, machine, state, "A", "q1").state
    retry = answer(runtime, machine, state, "A", "q1")
    assert retry.event["status"] == "noop" and retry.state == state
    for result, code in [
        (answer(runtime, machine, state, "A", "q1", 4), "answer_changed"),
        (answer(runtime, machine, state, "A", "q2"), "question_not_assigned"),
        (answer(runtime, machine, state, "B", "q1"), "question_not_assigned"),
    ]:
        assert result.event["reason_code"] == code and result.state == state


@pytest.mark.parametrize("value", [0, 6, True, 2.5, "3", None])
def test_invalid_answers_do_not_increment_coverage(value):
    machine, runtime = build_machine(), Runtime()
    state = assign(runtime, machine, runtime.initial_state(machine), "A").state
    with pytest.raises(DSLValidationError):
        answer(runtime, machine, state, "A", "q01", value)
    assert sum(state["counts"].values()) == 0 and not state["answers"]


def test_close_blocks_new_work_but_keeps_completed_retry_idempotent():
    machine, runtime = build_machine(), Runtime()
    state = assign(runtime, machine, runtime.initial_state(machine), "A").state
    state = answer(runtime, machine, state, "A", "q01").state
    state = runtime.close(machine, state)
    assert answer(runtime, machine, state, "A", "q01").event["status"] == "noop"
    assert (
        answer(runtime, machine, state, "A", "q02").event["reason_code"]
        == "coverage_closed"
    )
    assert (
        assign(runtime, machine, state, "new").event["reason_code"] == "coverage_closed"
    )
    assert (
        runtime.render_view(machine, state, current={"respondent_id": "A"})["pending"]
        == []
    )


def test_stale_concurrent_assignments_are_not_reservations_but_counts_cannot_overfill(
    tmp_path,
):
    spaces = SharedStateMap(SharedState(coverage=build_machine(["q1"], target=1)))
    path = tmp_path / "coverage.sqlite"
    backend = SQLiteStateBackend(spaces, path, runtime=Runtime())
    target = spaces.by("study").coverage
    for i in range(8):
        backend.apply(
            resolve_write(
                target.assign(respondent_id=str(i)), StepContext({}, f"assign-{i}")
            )
        )
    operations = [
        resolve_write(
            target.record_answer(respondent_id=str(i), question="q1", answer=3),
            StepContext({}, str(i)),
        )
        for i in range(8)
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        decisions = list(pool.map(backend.apply, operations))
    assert Counter(d.status for d in decisions) == {"applied": 1, "rejected": 7}
    assert all(
        d.reason_code == "question_full" for d in decisions if d.status == "rejected"
    )
    state = backend.snapshot("study").state["coverage"]
    assert state["counts"] == {"q1": 1} and len(state["answers"]) == 1
    # A late resume omits an unanswered question that another agent already filled.
    loser = next(str(i) for i in range(8) if str(i) not in state["answers"])
    assert (
        Runtime().render_view(
            build_machine(["q1"], target=1), state, current={"respondent_id": loser}
        )["pending"]
        == []
    )


def test_sqlite_restart_preserves_assignment_and_each_answer_retry(tmp_path):
    spaces = SharedStateMap(SharedState(coverage=build_machine(["q1", "q2"], target=1)))
    path = tmp_path / "coverage.sqlite"
    target = spaces.by("study").coverage
    backend = SQLiteStateBackend(spaces, path, runtime=Runtime())
    backend.apply(
        resolve_write(target.assign(respondent_id="A"), StepContext({}, "assign"))
    )
    operations = [
        resolve_write(
            target.record_answer(respondent_id="A", question=q, answer=3),
            StepContext({}, q),
        )
        for q in ("q1", "q2")
    ]
    for operation in operations:
        backend = SQLiteStateBackend(
            SharedStateMap.from_dict(spaces.to_dict()), path, runtime=Runtime()
        )
        assert backend.apply(operation).status == "applied"
    before = backend.snapshot("study")
    for operation in operations:
        assert backend.apply(operation).changed is None
    assert backend.snapshot("study") == before and len(backend.history()) == 3
    assert before.state["coverage"]["counts"] == {"q1": 1, "q2": 1}


def test_fresh_process_executes_machine_without_authoring_module():
    script = """import json, sys
from edsl.sharedstate import Machine
from edsl.sharedstate.dsl_runtime import Runtime
p = json.load(sys.stdin)
spec = Machine.from_dict(p["machine"])
r = Runtime()
s = r.initial_state(spec)
for command, inputs in p["commands"]:
    s = r.execute(spec, s, command, inputs).state
print(json.dumps(s))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps({"machine": build_machine().to_dict(), "commands": DEMO}),
        text=True,
        capture_output=True,
        check=True,
    )
    state = json.loads(result.stdout)
    assert sum(state["counts"].values()) == 6 and len(state["answers"]) == 2


def run(survey, schedule, people):
    survey = Survey.from_dict(json.loads(json.dumps(survey.to_dict())))
    schedule = InterviewSchedule.from_dict(json.loads(json.dumps(schedule.to_dict())))
    results = (
        Runner(interview_schedule=schedule)
        .submit(survey.by(people).by(Model("test")), cache=False)
        .results()
    )
    assert not results.has_unfixed_exceptions
    return results


def test_survey_generated_rules_use_exact_ids_and_skip_unassigned_writes():
    survey, _, schedule = build_survey(
        question_ids=["q1", "q10", "q2"], target=1, per_agent=2
    )
    results = run(survey, schedule, AgentList(list(reversed(demo_agents(3)))))
    rows = {r.agent.traits["respondent_id"]: r.answer for r in results}
    assert rows["R0"]["q1"] == rows["R0"]["q10"] == 3 and rows["R0"].get("q2") is None
    assert (
        rows["R1"]["q2"] == 3
        and rows["R1"].get("q1") is None
        and rows["R1"].get("q10") is None
    )
    assert rows["R1"]["coverage_slot_1"] == "q2"
    assert rows["R1"]["coverage_slot_2"] == "coverage_none"
    assert all(rows["R2"].get(q) is None for q in ("q1", "q10", "q2"))
    writes = [
        e for e in results.shared_state["bindings"][0]["events"] if e["kind"] == "write"
    ]
    assert all(e["status"] == "applied" for e in writes)
    assert [e["command"] for e in writes] == [
        "assign",
        "record_answer",
        "record_answer",
        "assign",
        "record_answer",
    ]


@pytest.mark.parametrize("already_answered", [1, 2])
def test_interview_resume_asks_only_unanswered_assignment_members(already_answered):
    survey, states, schedule = build_survey(
        question_ids=["q1", "q2", "q3"], target=2, per_agent=2
    )
    # Simulate an interrupted interview through the same durable state service.
    from pathlib import Path
    import tempfile

    backend = SQLiteStateBackend(
        states,
        Path(tempfile.gettempdir())
        / "edsl-shared-state"
        / f"{states.state_id}.sqlite3",
        runtime=Runtime(),
    )
    target = states.by("study").coverage
    backend.apply(
        resolve_write(target.assign(respondent_id="R0"), StepContext({}, "initial"))
    )
    for question in ["q1", "q2"][:already_answered]:
        backend.apply(
            resolve_write(
                target.record_answer(respondent_id="R0", question=question, answer=3),
                StepContext({}, f"initial-{question}"),
            )
        )
    result = run(survey, schedule, demo_agents(1))[0]
    assert result.answer["coverage_slot_1"] == (
        "q2" if already_answered == 1 else "coverage_none"
    )
    assert (
        result.answer.get("q2") == (3 if already_answered == 1 else None)
        and result.answer.get("q1") is None
        and result.answer.get("q3") is None
    )
    assert backend.snapshot("study").state["coverage"]["counts"] == {
        "q1": 1,
        "q2": 1,
        "q3": 0,
    }


def test_full_twenty_question_demo_and_partial_final_agent():
    report = run_demo()
    assert report["counts"] == dict.fromkeys(DEFAULT_QUESTIONS, 10)
    assert report["total_answers"] == 200 and report["agents_answering"] == 67
    assert report["answers_per_agent"] == {2: 1, 3: 66}
    assert report["stop_reason"] == "coverage_complete"


def test_pool_exhaustion_does_not_claim_complete_coverage():
    report = run_demo(count=1)
    assert (
        report["total_answers"] == 3 and report["stop_reason"] == "population_exhausted"
    )
