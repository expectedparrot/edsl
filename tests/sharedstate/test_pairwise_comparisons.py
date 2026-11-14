"""Adaptive selection, scoring, persistence, and actual rendered survey choices."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import tempfile

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
from examples.machine_primitives.pairwise_comparisons import (
    DEFAULT_ITEMS,
    DEMO,
    build_machine,
)
from examples.pairwise_comparisons import build_survey, demo_agents, run_demo


def assign(runtime, spec, state, rid):
    return runtime.execute(spec, state, "assign", {"respondent_id": rid})


def compare(runtime, spec, state, rid, winner):
    return runtime.execute(
        spec, state, "compare", {"respondent_id": rid, "winner": winner}
    )


@pytest.mark.parametrize(
    "items", [[], ["A"], ["", "B"], ["A", "A"], [1, "B"], "AB", [" ", "B"]]
)
def test_invalid_items(items):
    with pytest.raises(ValueError):
        build_machine(items=items)


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
@pytest.mark.parametrize("parameter", ["budget", "explore_every"])
def test_positive_integer_parameters(parameter, value):
    with pytest.raises(ValueError):
        build_machine(**{parameter: value})


@pytest.mark.parametrize(
    "rate", [0, -0.5, 1.1, float("inf"), float("nan"), True, "0.5"]
)
def test_invalid_learning_rate(rate):
    with pytest.raises(ValueError):
        build_machine(learning_rate=rate)


@pytest.mark.parametrize("seed", ["", None])
def test_invalid_seed(seed):
    with pytest.raises(ValueError):
        build_machine(seed=seed)


@pytest.mark.parametrize("seed", range(3))
def test_reference_policy_and_scores_for_mixed_winners_and_abandonment(seed):
    spec = Machine.from_json(build_machine(budget=25).to_json())
    runtime, rng = Runtime(), random.Random(seed)
    state = runtime.initial_state(spec)
    pairs = spec.constants["pairs"]
    scores = dict.fromkeys(DEFAULT_ITEMS, 0.0)
    counts = dict.fromkeys([p["pair_id"] for p in pairs], 0)
    streak, completed = 0, 0
    modes = []
    for index in range(40):
        if completed == 25:
            break
        rid = f"R{index}"
        explore = 0 in counts.values() or streak >= 4

        def key(p):
            gap = abs(scores[p["left"]] - scores[p["right"]])
            return (
                (counts[p["pair_id"]], gap, p["pair_id"])
                if explore
                else (gap, counts[p["pair_id"]], p["pair_id"])
            )

        selected = min(pairs, key=key)
        state = assign(runtime, spec, state, rid).state
        actual = state["assignments"][rid]
        assert actual["pair_id"] == selected["pair_id"]
        assert set(actual["options"]) == {selected["left"], selected["right"]}
        assert actual["mode"] == ("explore" if explore else "adaptive")
        if index in (2, 7, 12):
            continue  # Assignment alone consumes no budget or pair coverage.
        winner = rng.choice([selected["left"], selected["right"]])
        loser = selected["right"] if winner == selected["left"] else selected["left"]
        probability = 1 / (1 + math.exp(scores[loser] - scores[winner]))
        delta = 0.5 * (1 - probability)
        scores[winner] += delta
        scores[loser] -= delta
        counts[selected["pair_id"]] += 1
        completed += 1
        streak = 0 if explore else streak + 1
        modes.append(actual["mode"])
        state = compare(runtime, spec, state, rid, winner).state
        assert state["ratings"] == pytest.approx(scores, abs=1e-12)
        assert abs(sum(state["ratings"].values())) < 1e-12
        assert state["pair_counts"] == counts
        assert state["comparisons"] == sum(counts.values()) == completed
        assert state["adaptive_streak"] == streak
    assert runtime.complete(spec, state)
    assert modes[:10] == ["explore"] * 10
    assert modes[10:] == (["adaptive"] * 4 + ["explore"]) * 3


def test_assignment_and_display_order_stay_fixed_after_other_answers():
    runtime, spec = Runtime(), build_machine()
    state = assign(runtime, spec, runtime.initial_state(spec), "A").state
    saved = deepcopy(state["assignments"]["A"])
    assert state["comparisons"] == 0
    state = assign(runtime, spec, state, "B").state
    state = compare(runtime, spec, state, "B", "Beacon").state
    retry = assign(runtime, spec, state, "A")
    assert retry.event["status"] == "noop"
    assert retry.state["assignments"]["A"] == saved
    view = runtime.render_view(spec, state, current={"respondent_id": "A"})
    assert view["options"] == saved["options"] and view["accepting"]
    assert not {"ratings", "responses", "assignments"} & set(view)


def test_seeded_option_order_has_both_orientations_and_replays():
    spec, runtime = build_machine(items=["A", "B"]), Runtime()
    state = runtime.initial_state(spec)
    for i in range(20):
        state = assign(runtime, spec, state, str(i)).state
    orders = {tuple(x["options"]) for x in state["assignments"].values()}
    assert orders == {("A", "B"), ("B", "A")}
    other = runtime.initial_state(spec)
    for i in reversed(range(20)):
        other = assign(runtime, spec, other, str(i)).state
    assert other == state  # Without responses, arrival order does not change pairs.


def test_rejections_and_retries_do_not_change_scores_or_consume_budget():
    runtime, spec = Runtime(), build_machine(budget=1)
    state = assign(runtime, spec, runtime.initial_state(spec), "A").state
    for rid, winner, code in [
        ("B", "Atlas", "pair_not_assigned"),
        ("A", "Ember", "winner_not_in_pair"),
    ]:
        result = compare(runtime, spec, state, rid, winner)
        assert result.event["reason_code"] == code and result.state == state
    state = compare(runtime, spec, state, "A", "Atlas").state
    retry = compare(runtime, spec, state, "A", "Atlas")
    assert retry.event["status"] == "noop" and retry.state == state
    changed = compare(runtime, spec, state, "A", "Beacon")
    assert changed.event["reason_code"] == "answer_changed" and changed.state == state
    assert (
        assign(runtime, spec, state, "B").event["reason_code"] == "comparisons_closed"
    )
    assert not runtime.render_view(spec, state, current={"respondent_id": "A"})[
        "accepting"
    ]
    with pytest.raises(DSLValidationError):
        compare(runtime, spec, state, "A", "Unknown")
    assert (
        assign(runtime, spec, state, " ").event["reason_code"]
        == "missing_respondent_id"
    )


def test_manual_close_blocks_unanswered_assignment_without_claiming_completion():
    spec, runtime = build_machine(), Runtime()
    state = assign(runtime, spec, runtime.initial_state(spec), "A").state
    state = runtime.close(spec, state)
    assert not runtime.complete(spec, state)
    assert (
        compare(runtime, spec, state, "A", "Atlas").event["reason_code"]
        == "comparisons_closed"
    )


@pytest.mark.parametrize("winner", ["A", "B"])
def test_extreme_rating_gap_is_finite_and_zero_sum(winner):
    runtime, spec = Runtime(), build_machine(items=["A", "B"], budget=2000)
    state = assign(runtime, spec, runtime.initial_state(spec), "R").state
    state["ratings"] = {"A": 1000.0, "B": -1000.0}
    state = compare(runtime, spec, state, "R", winner).state
    assert all(math.isfinite(x) for x in state["ratings"].values())
    assert sum(state["ratings"].values()) == 0
    assert state["ratings"]["A"] == (1000.0 if winner == "A" else 999.5)


def test_concurrent_answers_respect_budget_and_independent_scopes(tmp_path):
    spaces = SharedStateMap(SharedState(comparisons=build_machine(budget=1)))
    target = spaces.by("study").comparisons
    backend = SQLiteStateBackend(
        spaces, tmp_path / "comparisons.sqlite", runtime=Runtime()
    )
    for i in range(8):
        backend.apply(
            resolve_write(
                target.assign(respondent_id=str(i)), StepContext({}, f"assign-{i}")
            )
        )
    writes = [
        resolve_write(
            target.compare(respondent_id=str(i), winner="Atlas"),
            StepContext({}, f"answer-{i}"),
        )
        for i in range(8)
    ]
    with ThreadPoolExecutor(max_workers=4) as pool:
        decisions = list(pool.map(backend.apply, writes))
    assert Counter(x.status for x in decisions) == {"applied": 1, "rejected": 7}
    assert all(
        x.reason_code == "comparisons_closed"
        for x in decisions
        if x.status == "rejected"
    )
    assert backend.snapshot("study").state["comparisons"]["comparisons"] == 1
    assert backend.snapshot("another-study").state["comparisons"]["comparisons"] == 0


def test_sqlite_restart_preserves_assignment_and_deduplicates_answer(tmp_path):
    spaces = SharedStateMap(SharedState(comparisons=build_machine()))
    path = tmp_path / "comparisons.sqlite"
    target = spaces.by("study").comparisons
    backend = SQLiteStateBackend(spaces, path, runtime=Runtime())
    backend.apply(
        resolve_write(target.assign(respondent_id="R"), StepContext({}, "assign"))
    )
    saved = backend.snapshot("study").state["comparisons"]["assignments"]["R"]
    backend = SQLiteStateBackend(
        SharedStateMap.from_dict(spaces.to_dict()), path, runtime=Runtime()
    )
    assert backend.snapshot("study").state["comparisons"]["assignments"]["R"] == saved
    operation = resolve_write(
        target.compare(respondent_id="R", winner="Atlas"), StepContext({}, "answer")
    )
    assert backend.apply(operation).status == "applied"
    before = backend.snapshot("study")
    assert backend.apply(operation).changed is None
    assert backend.snapshot("study") == before
    again = resolve_write(
        target.compare(respondent_id="R", winner="Atlas"),
        StepContext({}, "different-key"),
    )
    assert backend.apply(again).status == "noop"
    assert backend.snapshot("study").state == before.state


def test_fresh_process_replays_machine_without_authoring_code():
    script = """import json,sys
from edsl.sharedstate import Machine
from edsl.sharedstate.dsl_runtime import Runtime
p=json.load(sys.stdin)
m=Machine.from_dict(p["machine"])
r=Runtime()
s=r.initial_state(m)
for command,inputs in p["commands"]:
    s=r.execute(m,s,command,inputs).state
assert "examples.machine_primitives.pairwise_comparisons" not in sys.modules
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
    assert state["comparisons"] == sum(command == "compare" for command, _ in DEMO)


def run(survey, schedule, people):
    survey = Survey.from_dict(json.loads(json.dumps(survey.to_dict())))
    schedule = InterviewSchedule.from_dict(json.loads(json.dumps(schedule.to_dict())))
    result = (
        Runner(interview_schedule=schedule)
        .submit(survey.by(people).by(Model("test")), cache=False)
        .results()
    )
    assert not result.has_unfixed_exceptions
    return result


def test_actual_choices_match_fixed_assignments_and_later_people_stop():
    observed = {}
    survey, _, schedule = build_survey(budget=12)
    people = demo_agents(15, observed_options=observed)
    results = run(survey, schedule, AgentList(list(reversed(people))))
    writes = [
        e for e in results.shared_state["bindings"][0]["events"] if e["kind"] == "write"
    ]
    final = writes[-1]["state"]["comparisons"]
    assert len(observed) == len(final["responses"]) == 12
    assert {r: a["options"] for r, a in final["assignments"].items()} == observed
    assert final["assignments"]["R0"]["pair_id"] == "pair_0000"
    assert final["assignments"]["R10"]["mode"] == "adaptive"
    assert set(observed["R0"]) != set(observed["R1"])
    assert all(e["status"] == "applied" for e in writes)
    assert len(writes) == 24
    for row in results:
        assert row.answer.get("preference") == final["responses"].get(
            row.agent.traits["respondent_id"]
        )


@pytest.mark.parametrize("answered", [False, True])
def test_survey_resume_preserves_options_and_does_not_reask_recorded_answer(answered):
    survey, spaces, schedule = build_survey()
    target = spaces.by("study").comparisons
    backend = SQLiteStateBackend(
        spaces,
        Path(tempfile.gettempdir())
        / "edsl-shared-state"
        / f"{spaces.state_id}.sqlite3",
    )
    backend.apply(
        resolve_write(target.assign(respondent_id="R0"), StepContext({}, "initial"))
    )
    saved = backend.snapshot("study").state["comparisons"]["assignments"]["R0"]
    if answered:
        backend.apply(
            resolve_write(
                target.compare(respondent_id="R0", winner="Atlas"),
                StepContext({}, "first-answer"),
            )
        )
    observed = {}
    result = run(survey, schedule, demo_agents(1, observed_options=observed))[0]
    assert result.answer.get("preference") == (None if answered else "Atlas")
    assert observed == ({} if answered else {"R0": saved["options"]})
    assert backend.snapshot("study").state["comparisons"]["comparisons"] == 1


def test_default_demo_and_population_exhaustion():
    report = run_demo()
    assert report["comparisons"] == sum(report["pair_counts"].values()) == 40
    assert report["stop_reason"] == "budget_reached"
    assert report["exploration_comparisons"] == 16
    assert min(report["pair_counts"].values()) >= 1
    assert report["matches_simulated_order"]
    short = run_demo(count=1)
    assert short["comparisons"] == 1 and short["stop_reason"] == "population_exhausted"
