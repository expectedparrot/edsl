"""Explicit decisions, durable retries, and failure/visibility boundaries."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
import sqlite3

import pytest

from edsl.sharedstate import (
    Command,
    CommandRejected,
    Machine,
    MachineValidationError,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    UnsupportedCapabilityError,
    assert_,
    current_value,
    expr,
    field,
    input_,
    reject,
    resolve_read,
    resolve_write,
    set_,
    state_field,
    when,
)
from edsl.sharedstate.dsl import Effect
from edsl.sharedstate.dsl_runtime import DSLValidationError, Runtime, default_runtime
from edsl.sharedstate.steps import StepContext
from edsl.sharedstate.exceptions import SharedStateRuntimeError
from examples.machine_primitives.double_auction import build_machine


def spec(effects=None):
    return Machine(
        name="Decision",
        constants={},
        fields={"count": state_field(T.integer(), 0)},
        commands={
            "act": Command(
                {},
                effects
                or (assert_(field("count") > 0, code="not_ready"), set_("count", 9)),
            ),
            "prepare": Command({}, (set_("count", 1),)),
        },
        view={"count": field("count"), "closed": current_value("closed", False)},
    )


def operation(spaces, command="act", execution="first"):
    return resolve_write(
        spaces.by("scope").data.command(command), StepContext({}, execution)
    )


def test_roundtrip_outcomes_distinguish_applied_noop_rejected_and_error():
    machine = Machine.from_json(spec().to_json())
    machine.validate()
    runtime = Runtime()
    state = runtime.initial_state(machine)
    rejection = runtime.execute(machine, state, "act", {})
    assert rejection.state == state
    assert rejection.event["status"] == "rejected"
    assert rejection.advisory["reason_code"] == "not_ready"
    applied = runtime.execute(machine, state, "prepare", {})
    assert applied.event["status"] == "applied"
    noop = runtime.execute(machine, applied.state, "prepare", {})
    assert noop.event["status"] == "noop"
    assert noop.event["reason_code"] is None
    broken = spec((set_("count", expr("divide", 1, 0)),))
    with pytest.raises(ZeroDivisionError):
        runtime.execute(broken, state, "act", {})
    assert state == {"count": 0}


def test_rejection_rolls_back_earlier_effects_and_skips_later_errors():
    machine = spec(
        (
            set_("count", 5),
            assert_(field("count") > 0, code="not_ready"),
            set_("count", expr("divide", 1, 0)),
        )
    )
    original = {"count": 0}
    result = Runtime().execute(machine, original, "act", {})
    assert result.state == original == {"count": 0}
    assert result.event["outcomes"] == [
        {"status": "rejected", "reason_code": "not_ready"}
    ]
    assert result.event["changed"] is False


@pytest.mark.parametrize(
    "effects,require,status",
    [
        ((reject("closed"),), False, "noop"),
        ((when(False, reject("closed")),), None, "noop"),
        ((when(True, reject("closed")),), None, "rejected"),
        ((assert_(True, code="closed"),), None, "noop"),
    ],
)
def test_existing_require_and_conditional_effect_semantics(effects, require, status):
    machine = replace(spec(), commands={"act": Command({}, effects, require=require)})
    machine.validate()
    assert Runtime().execute(machine, {"count": 0}, "act", {}).event["status"] == status


@pytest.mark.parametrize(
    "code", [None, "", "secret balance is 500", "x" * 65, "☃", 3, field("count")]
)
def test_reason_codes_are_bounded_literals_checked_in_dead_code(code):
    with pytest.raises(MachineValidationError, match="literal identifier"):
        spec((when(False, reject(code)),)).validate()


def test_reason_does_not_expand_private_values_or_report_rolled_back_effects():
    machine = spec((set_("count", 918273645), reject("not_allowed")))
    result = Runtime().execute(machine, {"count": 918273644}, "act", {})
    assert "918273" not in json.dumps(result.advisory)
    assert "count" not in json.dumps(result.advisory)


@pytest.mark.parametrize("condition", [None, 1, "yes", []])
def test_non_boolean_assertion_is_failure_not_rejection(condition):
    machine = replace(
        spec(),
        commands={
            "act": Command(
                {"condition": T.any()}, (assert_(input_("condition"), code="no"),)
            )
        },
    )
    machine.validate()
    with pytest.raises(DSLValidationError, match="Boolean"):
        Runtime().execute(machine, {"count": 0}, "act", {"condition": condition})


def test_malformed_assertion_and_missing_capability_fail_before_execution():
    with pytest.raises(MachineValidationError, match="Boolean|boolean"):
        spec((assert_(1, code="no"),)).validate()
    with pytest.raises(MachineValidationError, match="target"):
        spec((Effect("reject", "count", (), {"code": "no"}),)).validate()
    machine = spec()
    runtime = Runtime(
        capabilities=set(Runtime().capability_manifest()["supported"])
        - {"effect:assert@1"}
    )
    with pytest.raises(UnsupportedCapabilityError, match="effect:assert@1"):
        runtime.execute(machine, {"count": 0}, "act", {})
    assert (
        "effect:reject@1" in spec((reject("no"),)).required_capabilities()["requires"]
    )


def test_rejected_idempotency_key_remains_terminal_after_state_changes_and_restart(
    tmp_path,
):
    spaces = SharedStateMap(SharedState(data=spec()))
    path = tmp_path / "state.sqlite"
    backend = SQLiteStateBackend(spaces, path)
    attempt = operation(spaces)
    first = backend.apply(attempt)
    assert (
        first.accepted and first.status == "rejected"
    )  # accepted is a processing acknowledgement.
    assert first.reason_code == "not_ready" and first.changed is False
    assert backend.snapshot("scope").version == 1
    backend.apply(operation(spaces, "prepare", "prepare"))
    reopened = SQLiteStateBackend(SharedStateMap.from_dict(spaces.to_dict()), path)
    retry = reopened.apply(attempt)
    assert (retry.status, retry.reason_code, retry.observed_version) == (
        first.status,
        first.reason_code,
        1,
    )
    assert retry.changed is None
    assert reopened.snapshot("scope").state["data"]["count"] == 1
    assert len(reopened.history()) == 2
    assert (
        reopened.apply(operation(spaces, execution="new-attempt")).status == "applied"
    )
    assert reopened.snapshot("scope").state["data"]["count"] == 9
    with pytest.raises(SharedStateRuntimeError, match="different content"):
        reopened.apply(replace(attempt, inputs={"forged": 1}))


def test_execution_failure_does_not_consume_key_or_create_event(tmp_path):
    machine = spec(
        (set_("count", 10), set_("count", expr("divide", 1, field("count"))))
    )
    spaces = SharedStateMap(SharedState(data=machine))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    attempt = operation(spaces)
    with pytest.raises(ZeroDivisionError):
        backend.apply(attempt)
    assert backend.snapshot("scope").version == 0
    assert backend.history() == []
    backend.apply(operation(spaces, "prepare", "prepare"))
    # A now-valid division still produces a float, so output type validation
    # fails too. Neither failure consumes this attempt's idempotency key.
    with pytest.raises(DSLValidationError):
        backend.apply(attempt)
    assert len(backend.history()) == 1


def test_failed_key_can_be_retried_after_cause_is_fixed(tmp_path):
    machine = spec(
        (set_("count", expr("at", [10], expr("subtract", 1, field("count")))),)
    )
    spaces = SharedStateMap(SharedState(data=machine))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    attempt = operation(spaces)
    with pytest.raises(IndexError):
        backend.apply(attempt)
    assert backend.history() == []
    backend.apply(operation(spaces, "prepare", "prepare"))
    assert backend.apply(attempt).status == "applied"
    assert backend.snapshot("scope").state["data"]["count"] == 10


def test_concurrent_rejection_retries_create_one_decision(tmp_path):
    spaces = SharedStateMap(SharedState(data=spec()))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    attempt = operation(spaces)
    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(lambda _: backend.apply(attempt), range(8)))
    assert all(o.status == "rejected" and o.observed_version == 1 for o in outcomes)
    assert len(backend.history()) == 1
    assert backend.snapshot("scope").state["data"] == {"count": 0}


def test_legacy_events_without_status_remain_replayable(tmp_path):
    spaces = SharedStateMap(SharedState(data=spec()))
    path = tmp_path / "state.sqlite"
    backend = SQLiteStateBackend(spaces, path)
    attempt = operation(spaces, "prepare")
    backend.apply(attempt)
    with sqlite3.connect(path) as connection:
        payload = json.loads(
            connection.execute("SELECT payload FROM state_events").fetchone()[0]
        )
        payload.pop("status")
        payload.pop("reason_code")
        connection.execute(
            "UPDATE state_events SET payload = ?", (json.dumps(payload),)
        )
    retry = SQLiteStateBackend(spaces, path).apply(attempt)
    assert (
        retry.status == "applied"
        and retry.reason_code is None
        and retry.changed is None
    )


@pytest.mark.parametrize("automatic", [False, True])
def test_rejected_close_is_logged_but_does_not_close_or_partially_settle(
    tmp_path, automatic
):
    machine = replace(
        spec(),
        complete_when=True,
        close_effects=(
            set_("count", 99),
            assert_(field("count") > 0, code="settlement_not_ready"),
        ),
    )
    runtime = Runtime()
    result = runtime.close_result(machine, {"count": 0})
    assert result.event["status"] == "rejected" and result.state == {"count": 0}
    with pytest.raises(CommandRejected, match="settlement_not_ready"):
        runtime.close(machine, {"count": 0})
    spaces = SharedStateMap(SharedState(data=machine))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    bound = spaces.by("scope").data
    close = resolve_write(bound.close(), StepContext({}, "close"))
    apply = lambda: (
        backend.finalize(bound.is_complete(), "scope", execution_id="close")
        if automatic
        else backend.apply(close)
    )
    first, retry = apply(), apply()
    assert first.status == retry.status == "rejected"
    assert first.observed_version == retry.observed_version == 1
    assert len(backend.history()) == 1
    observed = backend.read(resolve_read(bound.read(), StepContext({}, "read")))
    assert observed.value == {"count": 0, "closed": False}
    backend.apply(operation(spaces, "prepare", "repair"))
    assert apply().status == "rejected"  # Same key never changes its decision.
    fixed_close = resolve_write(bound.close(), StepContext({}, "fresh-close"))
    fresh = (
        backend.finalize(bound.is_complete(), "scope", execution_id="fresh-close")
        if automatic
        else backend.apply(fixed_close)
    )
    assert fresh.status == "applied"
    assert apply().status == "rejected"  # Historical decision survives a later success.
    assert backend.read(
        resolve_read(bound.read(), StepContext({}, "read-again"))
    ).value == {"count": 99, "closed": True}


@pytest.mark.parametrize(
    "action,price,code",
    [
        ("buy", 0, "invalid_price"),
        ("buy", -1, "invalid_price"),
        ("buy", 101, "insufficient_cash"),
        ("sell", 10, "insufficient_inventory"),
    ],
)
def test_auction_rejection_corresponds_to_registered_algorithm_error(
    action, price, code
):
    machine = Machine.from_json(build_machine().to_json())
    runtime = Runtime()
    state = runtime.initial_state(machine)
    inputs = {"trader": "Buyer", "action": action, "price": price, "round": 1}
    result = runtime.execute(machine, state, "submit", inputs)
    assert result.event["status"] == "rejected" and result.event["reason_code"] == code
    assert result.state == state
    legacy = default_runtime()
    original = deepcopy(state["market"])
    with pytest.raises(DSLValidationError):
        legacy.algorithms[("double_auction_submit", 1)](original, inputs, {})
    assert original == state["market"]


def test_auction_open_order_rejection_and_hold_noop():
    machine, runtime = build_machine(), Runtime()
    state = runtime.initial_state(machine)
    bid = {"trader": "Buyer", "action": "buy", "price": 10, "round": 1}
    placed = runtime.execute(machine, state, "submit", bid)
    assert placed.event["status"] == "applied"
    denied = runtime.execute(machine, placed.state, "submit", bid)
    assert denied.event["reason_code"] == "open_order_exists"
    assert denied.state == placed.state
    held = runtime.execute(machine, placed.state, "submit", bid | {"action": "hold"})
    assert held.event["status"] == "noop"
    assert held.event["reason_code"] is None


def test_runner_surfaces_rejected_automatic_close(tmp_path):
    from types import SimpleNamespace
    from edsl import QuestionFreeText, Survey
    from edsl.runner.service import JobService
    from edsl.runner.survey_cache import SurveyCache

    machine = replace(
        spec(), complete_when=True, close_effects=(reject("settlement_denied"),)
    )
    spaces = SharedStateMap(SharedState(data=machine))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    bound = spaces.by("scope").data
    q = QuestionFreeText(question_name="reply", question_text="Reply")
    survey = Survey([q, bound.prepare()])
    service = SimpleNamespace(
        _survey_cache=SurveyCache(),
        _jobs=SimpleNamespace(
            get_survey=lambda _: survey.to_dict(), get_agent=lambda *_: {"traits": {}}
        ),
        _answers=SimpleNamespace(get_all_for_interview=lambda *_: []),
        _interviews=SimpleNamespace(
            get_definition=lambda *_: SimpleNamespace(agent_id="a", iteration=0)
        ),
        _interview_schedules={
            "job": SimpleNamespace(finalize_when=bound.is_complete())
        },
        _state_binding=lambda *_: backend,
    )
    with pytest.raises(CommandRejected, match="settlement_denied"):
        JobService._execute_shared_state_steps(
            service, "job", "interview", "reply", "ok", True
        )
    events = backend.history()
    assert [event["status"] for event in events] == ["applied", "rejected"]
    assert (
        backend.read(resolve_read(bound.read(), StepContext({}, "check"))).value[
            "closed"
        ]
        is False
    )
