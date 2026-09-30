"""Portable random protocol, exact rounding, durable replay, and conservation."""

from dataclasses import replace
from decimal import Decimal, localcontext
import itertools
import json
import os
import subprocess
import sys

import pytest

from edsl.sharedstate import (
    Command,
    ExecutionLimits,
    Machine,
    MachineValidationError,
    ResourceLimitError,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    UnsupportedCapabilityError,
    decimal_units,
    expr,
    field,
    input_,
    resolve_write,
    round_ratio,
    seeded_integer,
    seeded_order,
    set_,
    state_field,
)
from edsl.sharedstate.dsl_runtime import DSLValidationError, Runtime
from edsl.sharedstate.steps import StepContext
from examples.machine_primitives import monetary_settlement, seeded_allocation
from examples.machine_primitives.__main__ import run_example


def evaluate(expression):
    return Runtime().evaluate(expression, {})


def machine(expression):
    return Machine(
        name="PortableProbe",
        constants={},
        fields={"answer": state_field(T.any(), 0)},
        commands={"run": Command({}, (set_("answer", expression),))},
        view={"answer": field("answer")},
    )


def draw(seed="study", scope="cohort-1", key="draw", low=-10, high=11):
    return seeded_integer(seed, low, high, scope=scope, key=key)


@pytest.mark.parametrize(
    "seed,scope,key,expected",
    [
        (
            "study",
            "cohort-1",
            "draw",
            7130233266410831006229336428245676939602130548031383085669217368896524999301,
        ),
        (
            "study",
            "cohort-2",
            "draw",
            69686360587739139367004100174323957756496271593164948273457462349631919960080,
        ),
        (
            "study",
            "cohort-1",
            "other",
            106972767050573581234123771726905432151718248541667775111272025933596170660050,
        ),
        (
            "sëed",
            "实验",
            "🎲",
            35181767980117685721076239565298663848407027519161172786719824337229071396192,
        ),
    ],
)
def test_sha256_known_answers(seed, scope, key, expected):
    # Fixed protocol vectors, also verified by an independent Node implementation.
    assert evaluate(draw(seed, scope, key, 0, 2**256)) == expected
    assert evaluate(draw(seed, scope, key)) == -10 + expected % 21


def test_draws_are_stateless_separated_and_do_not_consume_global_rng():
    import random

    state = random.getstate()
    a = evaluate(draw())
    other = [evaluate(draw(key=f"other-{i}")) for i in range(20)]
    assert len(set(other)) > 5
    assert evaluate(draw()) == a == -3
    assert evaluate(draw(scope="cohort-2")) == 1
    assert evaluate(draw(key="other")) == -6
    assert random.getstate() == state
    # Length prefixes distinguish concatenation-ambiguous components.
    assert evaluate(draw("ab", "c", "d", 0, 2**256)) != evaluate(
        draw("a", "bc", "d", 0, 2**256)
    )
    assert evaluate(draw(low=-2, high=-1)) == -2


def test_rejection_sampling_uses_next_counter(monkeypatch):
    from edsl.sharedstate import portable

    counters = []

    def digest(prefix, suffix):
        counters.append(int.from_bytes(suffix, "big"))
        return ((2**256 - 1) if len(counters) == 1 else 7).to_bytes(32, "big")

    monkeypatch.setattr(portable, "_digest", digest)
    assert evaluate(draw(low=0, high=10)) == 7
    assert counters == [0, 1]


def test_repeated_rejected_samples_exhaust_shared_budget(monkeypatch):
    from edsl.sharedstate import portable

    class MaxDigest:
        def digest(self):
            return b"\xff" * 32

    monkeypatch.setattr(portable.hashlib, "sha256", lambda _: MaxDigest())
    with pytest.raises(ResourceLimitError, match="max_steps"):
        Runtime(limits=ExecutionLimits(max_steps=1000)).evaluate(
            draw(low=0, high=10), {}
        )


def test_order_uses_stable_ids_and_domain_separation():
    expected = ["😀", "D", "B", "C", "é", "A"]
    for items in [expected, list(reversed(expected)), sorted(expected)]:
        assert (
            evaluate(
                seeded_order(items, seed="study", scope="cohort-1", key="priority")
            )
            == expected
        )
    subset = ["A", "C", "D"]
    assert evaluate(
        seeded_order(subset, seed="study", scope="cohort-1", key="priority")
    ) == ["D", "C", "A"]
    assert evaluate(seeded_order([], seed="study", scope="c", key="p")) == []


def test_hash_collision_falls_back_to_utf8_id_order(monkeypatch):
    from edsl.sharedstate import portable

    monkeypatch.setattr(portable, "_digest", lambda *args: b"\0" * 32)
    assert evaluate(seeded_order(["😀", "é", "A"], seed="s", scope="c", key="k")) == [
        "A",
        "é",
        "😀",
    ]


@pytest.mark.parametrize(
    "expression",
    [
        draw(seed=1),
        draw(seed=""),
        draw(scope=""),
        draw(key=""),
        draw(seed="\ud800"),
        draw(low=True),
        draw(high=1.5),
        draw(low=3, high=3),
        draw(high=2**256 + 100),
        seeded_order(["A", "A"], seed="s", scope="c", key="k"),
        seeded_order([""], seed="s", scope="c", key="k"),
        seeded_order([1], seed="s", scope="c", key="k"),
        seeded_order("A", seed="s", scope="c", key="k"),
        decimal_units(1.005, places=2, rounding="half_up"),
        *[
            decimal_units(x, places=2, rounding="half_up")
            for x in ["NaN", "inf", "1e2", " 1", ".5", "1.", "１", ""]
        ],
        round_ratio(True, 2, rounding="half_up"),
        round_ratio(1, 0, rounding="half_up"),
        round_ratio(1, -2, rounding="half_up"),
        round_ratio(1.0, 2, rounding="half_up"),
    ],
)
def test_invalid_runtime_operands_fail_explicitly(expression):
    with pytest.raises(DSLValidationError):
        evaluate(expression)


@pytest.mark.parametrize(
    "mode,positive,negative",
    [
        ("half_up", 3, -3),
        ("half_even", 2, -2),
        ("toward_zero", 2, -2),
        ("floor", 2, -3),
        ("ceiling", 3, -2),
    ],
)
def test_signed_half_boundaries(mode, positive, negative):
    assert evaluate(round_ratio(5, 2, rounding=mode)) == positive
    assert evaluate(round_ratio(-5, 2, rounding=mode)) == negative
    assert evaluate(decimal_units("0.025", places=2, rounding=mode)) == positive
    assert evaluate(decimal_units("-0.025", places=2, rounding=mode)) == negative


@pytest.mark.parametrize(
    "mode", ["half_up", "half_even", "toward_zero", "floor", "ceiling"]
)
def test_rounding_against_independent_decimal_oracle(mode):
    decimal_mode = "ROUND_DOWN" if mode == "toward_zero" else "ROUND_" + mode.upper()
    with localcontext() as context:
        context.prec = 100
        context.rounding = decimal_mode
        for numerator in [-(10**30) - 5, *range(-25, 26), 10**30 + 5]:
            for denominator in [1, 2, 3, 10, 11]:
                expected = int(
                    (Decimal(numerator) / Decimal(denominator)).quantize(Decimal(1))
                )
                assert (
                    evaluate(round_ratio(numerator, denominator, rounding=mode))
                    == expected
                )
        for amount, places in itertools.product(
            [
                "0",
                "-0.00",
                "+0001.005",
                "-1.005",
                "1.015",
                "0.00499",
                "0.00501",
                "123456789012345678901234567890.005",
            ],
            [0, 2, 18],
        ):
            expected = int(
                (Decimal(amount) * Decimal(10) ** places).quantize(Decimal(1))
            )
            assert (
                evaluate(decimal_units(amount, places=places, rounding=mode))
                == expected
            )


@pytest.mark.parametrize(
    "expression",
    [
        expr("seeded_integer", "s", 0, 3, scope="c", key="k", version=2),
        expr("seeded_order", ["A"], seed="s", key="k"),
        decimal_units("1", places=True, rounding="half_up"),
        decimal_units("1", places=19, rounding="half_up"),
        decimal_units("1", places=2, rounding="nearest"),
        round_ratio(1, 2, rounding=field("answer")),
        expr("round_ratio", 1, rounding="half_even"),
        draw(seed=1),
        seeded_order([1], seed="s", scope="c", key="k"),
        round_ratio("1", 2, rounding="half_even"),
        decimal_units(1.0, places=2, rounding="half_even"),
    ],
)
def test_authoring_validation_reports_new_operator_paths(expression):
    with pytest.raises(MachineValidationError) as error:
        machine(expression).validate()
    assert "commands" in error.value.path


@pytest.mark.parametrize(
    "expression",
    [
        draw(),
        seeded_order(["A"], seed="s", scope="c", key="k"),
        decimal_units("1.005", places=2, rounding="half_up"),
        round_ratio(5, 2, rounding="half_even"),
    ],
)
def test_exact_capabilities_and_transport(expression):
    spec = Machine.from_json(machine(expression).to_json())
    spec.validate()
    capability = f"expression:{expression.op}@1"
    assert capability in spec.required_capabilities()["requires"]
    restricted = Runtime(
        capabilities=set(Runtime().capability_manifest()["supported"]) - {capability}
    )
    with pytest.raises(UnsupportedCapabilityError):
        restricted.initial_state(spec)
    assert Runtime().execute(spec, {"answer": 0}, "run", {}).state[
        "answer"
    ] == evaluate(expression)


@pytest.mark.parametrize(
    "amount,places", [("9" * 1000, 0), ("0." + "0" * 1000 + "1", 2), ("1", 18)]
)
def test_decimal_intermediates_are_bounded_before_integer_allocation(amount, places):
    with pytest.raises(ResourceLimitError, match="max_integer_bits"):
        Runtime(limits=ExecutionLimits(max_integer_bits=32)).evaluate(
            decimal_units(amount, places=places, rounding="half_up"), {}
        )


def test_large_exact_decimal_parsing_does_not_use_global_digit_limit():
    result = Runtime(limits=ExecutionLimits(max_integer_bits=20000)).evaluate(
        decimal_units("1" + "0" * 5000, places=0, rounding="half_even"), {}
    )
    assert result == 10**5000


@pytest.mark.parametrize("module", [seeded_allocation, monetary_settlement])
def test_replay_after_sqlite_restart_and_retry(module, tmp_path):
    spaces = SharedStateMap(SharedState(data=module.build_machine()))
    path = tmp_path / "state.sqlite"
    backend = SQLiteStateBackend(spaces, path)
    for index, (command, inputs) in enumerate(module.DEMO):
        # Reopen from serialized definitions on every step, including close.
        backend = SQLiteStateBackend(
            SharedStateMap.from_dict(json.loads(json.dumps(spaces.to_dict()))), path
        )
        target = spaces.by("scope").data
        operation = resolve_write(
            (
                target.close()
                if command == "$close"
                else target.command(command, **inputs)
            ),
            StepContext({}, str(index)),
        )
        decision = backend.apply(operation)
        before = backend.snapshot("scope")
        retry = SQLiteStateBackend(spaces, path).apply(operation)
        assert retry.changed is None and retry.status == decision.status
        assert backend.snapshot("scope") == before
    expected = run_example(module.__name__.rsplit(".", 1)[1])
    assert backend.snapshot("scope").state["data"] == expected["state"]
    assert len(backend.history()) == len(module.DEMO)


@pytest.mark.parametrize("name", ["seeded_allocation", "monetary_settlement"])
def test_fresh_process_executes_only_serialized_definition(name):
    replay = run_example(name)
    script = """import json, sys
from edsl.sharedstate import Machine
from edsl.sharedstate.dsl_runtime import Runtime
replay = json.load(sys.stdin)
spec = Machine.from_dict(replay["definition"])
runtime = Runtime()
state = runtime.initial_state(spec)
for command, inputs in replay["commands"]:
    state = (runtime.close_result(spec, state) if command == "$close" else runtime.execute(spec, state, command, inputs)).state
print(json.dumps(state))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        input=json.dumps(replay),
        text=True,
        capture_output=True,
        check=True,
        env=os.environ | {"PYTHONHASHSEED": "42"},
    )
    assert json.loads(result.stdout) == replay["state"]


def test_lottery_is_independent_of_arrival_order_and_unrelated_draws():
    spec, runtime = seeded_allocation.build_machine(), Runtime()
    winners = []
    for ordering in itertools.permutations("ABCD"):
        state = runtime.initial_state(spec)
        for person in ordering:
            state = runtime.execute(spec, state, "enter", {"participant": person}).state
            evaluate(draw(key=person))
        state = runtime.close(spec, state)
        assert state["bonus_units"] == 181
        winners.append(state["winners"])
    assert all(winner == ["C", "A"] for winner in winners)


def test_settlement_conserves_minor_units_at_every_transition():
    spec, runtime = monetary_settlement.build_machine(), Runtime()
    state = runtime.initial_state(spec)
    for amount in ["1.005", "2.00", "6.00", "-1", "0.004", "9999.99"]:
        previous = state
        result = runtime.execute(spec, state, "pay", {"amount": amount})
        state = result.state
        assert sum(state["accounts"].values()) == 100000
        assert all(type(v) is int and v >= 0 for v in state["accounts"].values())
        if amount in ["-1", "0.004", "9999.99"]:
            assert result.event["status"] == "rejected" and state == previous
    assert state["accounts"] == {"payer": 99099, "payee": 899, "fees": 2}


@pytest.mark.parametrize(
    "expression,limits,error",
    [
        (
            decimal_units(input_("value"), places=2, rounding="half_up"),
            ExecutionLimits(),
            DSLValidationError,
        ),
        (
            decimal_units("9" * 1000, places=2, rounding="half_up"),
            ExecutionLimits(max_integer_bits=64),
            ResourceLimitError,
        ),
    ],
)
def test_failed_money_operation_rolls_back_state_history_and_key(
    expression, limits, error, tmp_path
):
    spec = replace(
        machine(0),
        commands={
            "run": Command(
                {"value": T.text()}, (set_("answer", 9), set_("answer", expression))
            )
        },
    )
    spaces = SharedStateMap(SharedState(data=spec))
    backend = SQLiteStateBackend(
        spaces, tmp_path / "state.sqlite", runtime=Runtime(limits=limits)
    )
    before = backend.snapshot("scope")
    operation = resolve_write(
        spaces.by("scope").data.run(value="NaN"), StepContext({}, "attempt")
    )
    for _ in range(2):
        with pytest.raises(error):
            backend.apply(operation)
        assert backend.snapshot("scope") == before
        assert backend.history() == []


def test_random_priority_intermediates_are_bounded():
    expression = seeded_order([str(i) for i in range(20)], seed="s", scope="c", key="k")
    with pytest.raises(ResourceLimitError, match="max_value_bytes"):
        Runtime(limits=ExecutionLimits(max_value_bytes=3000)).evaluate(expression, {})


@pytest.mark.parametrize(
    "expression",
    [
        round_ratio(5, 2, rounding=expr("first", ["half_even"], "half_up")),
        decimal_units("1.005", places=expr("add", 1, 1), rounding="half_up"),
        expr("round_ratio", 1, rounding="half_even"),
        expr("seeded_integer", "s", 0, 10, scope="c", key="k", version=2),
    ],
)
def test_standalone_runtime_enforces_literal_options_and_arity(expression):
    with pytest.raises(DSLValidationError):
        evaluate(expression)


@pytest.mark.parametrize(
    "numerator,expected",
    [
        (expr("subtract", 0, 5), -2),
        (expr("absolute", -5), 2),
    ],
)
def test_integer_arithmetic_composes_with_exact_rounding(numerator, expected):
    spec = machine(round_ratio(numerator, 2, rounding="half_even"))
    spec.validate()
    assert Runtime().execute(spec, {"answer": 0}, "run", {}).state["answer"] == expected
