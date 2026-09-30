"""Four single-pass design probes: invariants, transport, races, and real routing."""

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import importlib
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
from examples.machine_primitives import appointment_booking as booking
from examples.machine_primitives import price_elicitation as pricing
from examples.machine_primitives import balanced_assignment as balance
from examples.machine_primitives import team_formation as teams

NAMES = (
    "appointment_booking",
    "price_elicitation",
    "balanced_assignment",
    "team_formation",
)


def restored(module, **kwargs):
    machine = Machine.from_json(module.build_machine(**kwargs).to_json())
    runtime = Runtime()
    return machine, runtime, runtime.initial_state(machine)


def command(runtime, machine, state, name, **inputs):
    return runtime.execute(machine, state, name, inputs)


def hold(r, m, s, rid="A", token="a1", slot="09:00"):
    return command(r, m, s, "hold", respondent_id=rid, reservation_id=token, slot=slot)


def decide(r, m, s, rid="A", token="a1", decision="Confirm"):
    return command(
        r, m, s, "decide", respondent_id=rid, reservation_id=token, decision=decision
    )


def test_booking_release_fences_old_tokens_and_does_not_reacquire():
    m, r, s = restored(booking, slots=["09:00"])
    first = hold(r, m, s)
    s = first.state
    assert hold(r, m, s).event["status"] == "noop"
    assert hold(r, m, s, rid="B", token="b1").event["reason_code"] == "slot_unavailable"
    assert decide(r, m, s, rid="B").event["reason_code"] == "reservation_not_owned"
    assert not r.complete(m, s)  # Full is temporary, not terminal.
    s = decide(r, m, s, decision="Release").state
    s = hold(r, m, s, token="a2").state
    s = decide(r, m, s, token="a2").state
    for operation in [hold(r, m, s), decide(r, m, s, decision="Release")]:
        assert operation.state == s and operation.event["status"] == "noop"
    rejected = decide(r, m, s)
    assert (
        rejected.state == s and rejected.event["reason_code"] == "reservation_released"
    )
    assert s["bookings"]["a2"]["status"] == "confirmed"
    assert hold(r, m, s, token="a3").event["reason_code"] == "already_booked"
    view = r.render_view(m, s, current={"respondent_id": "B", "reservation_id": "a2"})
    assert view["slot"] is None and view["status"] == "missing"


def test_booking_changed_payload_and_close_keep_existing_hold_manageable():
    m, r, s = restored(booking)
    s = hold(r, m, s).state
    assert hold(r, m, s, slot="10:00").event["reason_code"] == "reservation_changed"
    s = r.close(m, s)
    assert (
        hold(r, m, s, rid="B", token="b1", slot="10:00").event["reason_code"]
        == "booking_closed"
    )
    s = decide(r, m, s).state
    assert s["bookings"]["a1"]["status"] == "confirmed"
    s = decide(r, m, s, decision="Release").state
    assert r.render_view(m, s)["options"] == []


@pytest.mark.parametrize("seed", range(4))
def test_booking_random_commands_preserve_capacity_and_one_active_per_person(seed):
    m, r, s = restored(booking)
    rng = random.Random(seed)
    for i in range(50):
        rid = rng.choice(["A", "B", "C"])
        token = f"{rid}-{rng.randrange(5)}"
        if rng.randrange(2):
            result = hold(r, m, s, rid, token, rng.choice(booking.DEFAULT_SLOTS))
        else:
            result = decide(r, m, s, rid, token, rng.choice(["Confirm", "Release"]))
        if result.event["status"] == "rejected":
            assert result.state == s
        s = result.state
        active = [b for b in s["bookings"].values() if b["status"] != "released"]
        assert len({b["slot"] for b in active}) == len(active)
        assert len({b["respondent_id"] for b in active}) == len(active)


@pytest.mark.parametrize("value", [0, 1, 37, 50, 65, 99, 100])
def test_price_search_contains_truth_at_every_step_and_terminates(value):
    m, r, s = restored(pricing)
    history = []
    while not r.complete(m, s):
        # Independent integer binary-search reference, not the Machine view.
        price = (s["lower"] + s["upper"] + 1) // 2
        answer = "Yes" if value >= price else "No"
        i = len(history)
        history.append({"step": i, "price": price, "answer": answer})
        s = command(r, m, s, "observe", step=i, answer=answer).state
        assert s["history"] == history
        assert s["lower"] <= value <= s["upper"]
    assert s["lower"] == s["upper"] == value and len(history) <= 7
    assert command(r, m, s, "observe", step=0, answer=history[0]["answer"]).state == s
    changed = "No" if history[0]["answer"] == "Yes" else "Yes"
    assert (
        command(r, m, s, "observe", step=0, answer=changed).event["reason_code"]
        == "answer_changed"
    )
    assert (
        command(r, m, s, "observe", step=len(history), answer="Yes").event[
            "reason_code"
        ]
        == "elicitation_finished"
    )


@pytest.mark.parametrize(
    "kwargs,precise",
    [
        ({"max_questions": 2}, False),
        ({"tolerance": 30}, True),
        ({"lower": 10, "upper": 10}, True),
    ],
)
def test_price_budget_precision_and_empty_interval_questions(kwargs, precise):
    m, r, s = restored(pricing, **kwargs)
    while not r.complete(m, s):
        s = command(r, m, s, "observe", step=len(s["history"]), answer="Yes").state
    assert r.render_view(m, s)["precise"] is precise
    if not precise:
        assert s["upper"] - s["lower"] > 0
    if kwargs.get("lower") == 10:
        assert s["history"] == []


def test_price_stale_out_of_order_and_closed_observations_do_not_change_bounds():
    m, r, s = restored(pricing)
    result = command(r, m, s, "observe", step=1, answer="Yes")
    assert result.event["reason_code"] == "unexpected_step" and result.state == s
    s = r.close(m, s)
    assert command(r, m, s, "observe", step=0, answer="Yes").state == s
    assert not r.complete(m, s)  # Closed early is not precise or budget exhaustion.


@pytest.mark.parametrize("seed", range(4))
def test_balance_chooses_minimum_marginal_cost_with_stable_personal_assignments(seed):
    m, r, s = restored(balance, seed=f"seed-{seed}")
    rng = random.Random(seed)
    for i in range(16):
        age, experience = rng.choice(balance.AGES), rng.choice(balance.EXPERIENCE)
        scores = {}
        for arm in balance.ARMS:
            held = [a for a in s["assignments"].values() if a["arm"] == arm]
            scores[arm] = (
                len(held)
                + sum(a["age"] == age for a in held)
                + sum(a["experience"] == experience for a in held)
            )
        args = dict(respondent_id=f"R{i}", age=age, experience=experience)
        before = deepcopy(s)
        result = command(r, m, s, "assign", **args)
        assert command(r, m, before, "assign", **args).state == result.state
        s = result.state
        chosen = s["assignments"][f"R{i}"]["arm"]
        assert scores[chosen] == min(scores.values())
        assert command(r, m, s, "assign", **args).state == s
        changed = dict(args, age=balance.AGES[1 - balance.AGES.index(age)])
        assert (
            command(r, m, s, "assign", **changed).event["reason_code"]
            == "characteristics_changed"
        )
    closed = r.close(m, s)
    assert (
        command(
            r, m, closed, "assign", respondent_id="new", age="Younger", experience="New"
        ).event["reason_code"]
        == "assignment_closed"
    )
    assert command(r, m, closed, "assign", **args).state == closed


def test_team_profiles_membership_and_role_specific_availability():
    m, r, s = restored(teams)
    assert (
        command(r, m, s, "join", respondent_id="A", team="Orion").event["reason_code"]
        == "role_required"
    )
    for rid, role, team in [("A", "Designer", "Orion"), ("B", "Designer", "Lyra")]:
        s = command(r, m, s, "register", respondent_id=rid, role=role).state
        s = command(r, m, s, "join", respondent_id=rid, team=team).state
    s = command(r, m, s, "register", respondent_id="C", role="Designer").state
    assert r.render_view(m, s, current={"respondent_id": "C"})["options"] == []
    assert (
        command(r, m, s, "join", respondent_id="C", team="Orion").event["reason_code"]
        == "role_full"
    )
    assert not r.complete(m, s)  # Four Builder seats remain.
    assert (
        command(r, m, s, "register", respondent_id="A", role="Builder").event[
            "reason_code"
        ]
        == "role_changed"
    )
    assert (
        command(r, m, s, "join", respondent_id="A", team="Lyra").event["reason_code"]
        == "team_changed"
    )
    s = r.close(m, s)
    assert command(r, m, s, "join", respondent_id="A", team="Orion").state == s
    assert (
        command(r, m, s, "join", respondent_id="C", team="Orion").event["reason_code"]
        == "teams_closed"
    )


@pytest.mark.parametrize("name", NAMES)
def test_sqlite_reopen_duplicate_delivery_scope_isolation_and_fresh_process(
    name, tmp_path
):
    module = importlib.import_module("examples.machine_primitives." + name)
    m, r, expected = restored(module)
    spaces = SharedStateMap(SharedState(app=m))
    target = spaces.by("study").app
    path = tmp_path / "application.sqlite"
    operations = []
    for i, (cmd, inputs) in enumerate(module.DEMO):
        backend = SQLiteStateBackend(
            SharedStateMap.from_dict(spaces.to_dict()), path, runtime=Runtime()
        )
        op = resolve_write(getattr(target, cmd)(**inputs), StepContext({}, f"step-{i}"))
        original = backend.apply(op)
        predicted = r.execute(m, expected, cmd, inputs)
        expected = predicted.state
        assert original.status == predicted.event["status"]
        assert backend.snapshot("study").state["app"] == expected
        operations.append((op, original.status))
    before = backend.snapshot("study")
    for op, status in operations:
        assert backend.apply(op).status == status
    assert backend.snapshot("study") == before
    assert len(backend.history()) == len(module.DEMO)
    assert backend.snapshot("another-study").state["app"] == r.initial_state(m)
    # Only the transported definition and primitive runtime are imported here.
    code = """import json, sys
from edsl.sharedstate import Machine
from edsl.sharedstate.dsl_runtime import Runtime
p=json.load(sys.stdin); m=Machine.from_dict(p['machine']); r=Runtime(); s=r.initial_state(m)
for c,i in p['commands']: s=r.execute(m,s,c,i).state
print(json.dumps(s))
"""
    output = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"machine": m.to_dict(), "commands": module.DEMO}),
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(output.stdout) == expected


@pytest.mark.parametrize("name", NAMES)
def test_concurrent_writes_obey_live_constraints(name, tmp_path):
    module = importlib.import_module("examples.machine_primitives." + name)
    machine = module.build_machine()
    spaces = SharedStateMap(SharedState(app=machine))
    backend = SQLiteStateBackend(spaces, tmp_path / "races.sqlite", runtime=Runtime())
    target = spaces.by("study").app
    operations = []
    for i in range(8):
        if name == "appointment_booking":
            step = target.hold(
                respondent_id=f"R{i}", reservation_id=f"hold-{i}", slot="09:00"
            )
        elif name == "price_elicitation":
            step = target.observe(step=0, answer="Yes")
        elif name == "balanced_assignment":
            step = target.assign(respondent_id=f"R{i}", age="Younger", experience="New")
        else:
            backend.apply(
                resolve_write(
                    target.register(respondent_id=f"R{i}", role="Designer"),
                    StepContext({}, f"profile-{i}"),
                )
            )
            step = target.join(respondent_id=f"R{i}", team="Orion")
        operations.append(resolve_write(step, StepContext({}, str(i))))
    with ThreadPoolExecutor(max_workers=4) as pool:
        decisions = list(pool.map(backend.apply, operations))
    state = backend.snapshot("study").state["app"]
    if name == "balanced_assignment":
        assert Counter(a["arm"] for a in state["assignments"].values()) == {
            "Control": 4,
            "Treatment": 4,
        }
    else:
        assert sum(d.status == "applied" for d in decisions) == 1
        assert (
            len(
                state[
                    {
                        "appointment_booking": "bookings",
                        "price_elicitation": "history",
                        "team_formation": "members",
                    }[name]
                ]
            )
            == 1
        )
    if name in ("appointment_booking", "team_formation"):
        assert sum(d.status == "rejected" for d in decisions) == 7


@pytest.mark.parametrize("name", NAMES)
def test_survey_transport_actual_choices_and_results_serialization(name):
    module = importlib.import_module("examples." + name)
    survey, _, schedule = module.build_survey()
    survey = Survey.from_dict(json.loads(json.dumps(survey.to_dict())))
    if not isinstance(schedule, str):
        schedule = InterviewSchedule.from_dict(
            json.loads(json.dumps(schedule.to_dict()))
        )
    agents = module.demo_agents()
    seen = {}

    def spy(self, question, scenario):
        seen[(self.traits["respondent_id"], question.question_name)] = deepcopy(
            getattr(question, "question_options", None)
        )
        return module.demo_answer(self, question, scenario)

    for agent in agents:
        agent.remove_direct_question_answering_method()
        agent.add_direct_question_answering_method(spy)
    results = (
        Runner(interview_schedule=schedule)
        .submit(survey.by(AgentList(reversed(agents))).by(Model("test")), cache=False)
        .results()
    )
    assert not results.has_unfixed_exceptions
    copy = Results.from_dict(json.loads(json.dumps(results.to_dict())))
    for row in copy:
        rid = row.agent.traits["respondent_id"]
        for q in survey.questions:
            key = (rid, q.question_name)
            attrs = row.data["question_to_attributes"][q.question_name]
            if key in seen:
                assert row.get_question_options(q.question_name) == seen[key]
                assert attrs["presentation"]["source"] == "agent_direct"
            else:
                assert "presentation" not in attrs
    if name == "appointment_booking":
        assert (
            len([r for r in copy if r.answer.get("booking_outcome") == "confirmed"])
            == 3
        )
    elif name == "price_elicitation":
        for row in copy:
            assert (
                row.answer["price_interval"]
                == f"{row.agent.traits['value']}..{row.agent.traits['value']}"
            )
    elif name == "balanced_assignment":
        assert Counter(r.answer["assigned_arm"] for r in copy) == {
            "Control": 6,
            "Treatment": 6,
        }
    else:
        # Last member must still receive the post-admission question.
        assert sum(r.answer.get("introduction") is not None for r in copy) == 6
        rows = {r.agent.traits["respondent_id"]: r for r in copy}
        assert rows["R2"].answer.get("team") is None
        assert rows["R6"].answer["introduction"] == "Happy to join."
        assert rows["R7"].answer.get("role") is None


@pytest.mark.parametrize("name", NAMES)
def test_documented_local_demo(name):
    assert importlib.import_module("examples." + name).run_demo()


@pytest.mark.parametrize(
    "module,kwargs",
    [
        (booking, {"slots": []}),
        (booking, {"slots": ["A", "A"]}),
        (booking, {"slots": "A"}),
        (pricing, {"upper": -1}),
        (pricing, {"lower": 10, "upper": 5}),
        (pricing, {"max_questions": True}),
        (pricing, {"max_questions": 33}),
        (pricing, {"tolerance": -1}),
        (balance, {"seed": ""}),
        (balance, {"seed": 42}),
        (teams, {"teams": []}),
        (teams, {"teams": ["A", "A"]}),
        (teams, {"role_seats": {}}),
        (teams, {"role_seats": {"X": True}}),
        (teams, {"role_seats": {"X": 0}}),
    ],
)
def test_authoring_rejects_invalid_configuration(module, kwargs):
    with pytest.raises(ValueError):
        module.build_machine(**kwargs)


def run_survey(survey, schedule, agents, model=None):
    return (
        Runner(interview_schedule=schedule)
        .submit(survey.by(agents).by(model or Model("test")), cache=False)
        .results()
    )


def test_booking_resumes_a_held_reservation_then_completed_retry_stays_terminal():
    from examples.appointment_booking import build_survey, demo_agents

    full, _, schedule = build_survey()
    agent = demo_agents()[1]  # Confirms, after the interruption below.
    partial = Survey.from_dict(full.to_dict())
    partial.add_stop_rule("hold_status", "{{ hold_status.answer }} == 'held'")
    first = run_survey(partial, schedule, AgentList([agent]))
    assert first[0].answer["hold_status"] == "held"
    assert first[0].answer["confirmation"] is None
    resumed = run_survey(Survey.from_dict(full.to_dict()), schedule, AgentList([agent]))
    assert not resumed.has_unfixed_exceptions
    assert resumed[0].answer["booking_outcome"] == "confirmed"
    assert resumed[0].get_question_options("slot") == [first[0].answer["slot"]]
    again = run_survey(full, schedule, AgentList([agent]))
    assert again[0].answer.get("slot") is None
    assert not again.has_unfixed_exceptions


def test_price_partial_resume_skips_old_slots_and_keeps_the_original_history():
    from examples.price_elicitation import build_survey, demo_agents

    full, _, schedule = build_survey()
    agents = demo_agents([37])
    partial = Survey.from_dict(full.to_dict())
    partial.add_stop_rule("buy_1", "{{ buy_1.answer }} in ['Yes', 'No']")
    first = run_survey(partial, schedule, agents)
    assert first[0].answer["buy_1"] is not None and first[0].answer["buy_2"] is None
    resumed = run_survey(Survey.from_dict(full.to_dict()), schedule, agents)
    assert not resumed.has_unfixed_exceptions
    assert resumed[0].answer["buy_0"] is None and resumed[0].answer["buy_1"] is None
    assert resumed[0].answer["price_interval"] == "37..37"
    writes = [
        e for e in resumed.shared_state["bindings"][0]["events"] if e["kind"] == "write"
    ]
    history = writes[-1]["state"]["pricing"]["history"]
    assert history[:2] == [
        dict(
            step=i,
            price=int(first[0].answer[f"price_{i}"]),
            answer=first[0].answer[f"buy_{i}"],
        )
        for i in range(2)
    ]
    assert all(e["status"] == "applied" for e in writes)
    finished = run_survey(full, schedule, agents)
    assert finished[0].answer["price_interval"] == "37..37"
    assert all(finished[0].answer[f"buy_{i}"] is None for i in range(7))


@pytest.mark.parametrize(
    "name,trait,replacement,downstream",
    [
        ("balanced_assignment", "age_group", "Older", "response"),
        ("team_formation", "role", "Builder", "team"),
    ],
)
def test_changed_self_report_cannot_use_a_prior_profile_silently(
    name, trait, replacement, downstream
):
    module = importlib.import_module("examples." + name)
    survey, _, schedule = module.build_survey()
    agents = AgentList([module.demo_agents()[0]])
    first = run_survey(survey, schedule, agents)
    assert first[0].answer[downstream] is not None
    agents[0].traits[trait] = replacement
    changed = run_survey(Survey.from_dict(survey.to_dict()), schedule, agents)
    assert not changed.has_unfixed_exceptions
    assert changed[0].answer[downstream] is None
    assert any(
        e.get("status") == "rejected"
        for e in changed.shared_state["bindings"][0]["events"]
    )


def test_price_model_prompts_use_each_adaptive_quote():
    from examples.price_elicitation import build_survey, demo_agents

    survey, _, schedule = build_survey()
    agents = demo_agents([100])
    agents[0].remove_direct_question_answering_method()
    prompts = []

    def answer(user_prompt, system_prompt, files_list):
        prompts.append(user_prompt)
        return "Yes"

    result = run_survey(survey, schedule, agents, Model("test", func=answer))
    assert not result.has_unfixed_exceptions
    assert result[0].answer["price_interval"] == "100..100"
    assert len(prompts) == 7
    for i, prompt in enumerate(prompts):
        price = result[0].answer[f"price_{i}"]
        assert f"for {price} price units" in prompt
        attributes = result[0].data["question_to_attributes"][f"buy_{i}"]
        assert attributes["presentation"]["source"] == "prompt"
        assert f"for {price} price units" in attributes["question_text"]
