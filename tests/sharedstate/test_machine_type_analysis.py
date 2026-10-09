"""Gradual operand checks and explicit loop invariants survive transport."""

import pytest

from edsl.sharedstate import (
    Command,
    Machine,
    MachineValidationError,
    StateType,
    choose,
    expr,
    field,
    fold,
    arg,
    iterate,
    local,
    record,
    assign,
    state_field,
)
from edsl.sharedstate.dsl_runtime import DSLValidationError, Runtime


def machine(expression, inputs=None):
    return Machine(
        name="Types",
        constants={},
        fields={"answer": state_field(StateType.any(), 0)},
        commands={"run": Command(inputs or {}, (assign("answer", expression),))},
        view={"answer": field("answer")},
    )


@pytest.mark.parametrize(
    "expression",
    [
        expr("subtract", "bad", 1),
        expr("add", "bad", 1),
        expr("multiply", [], 0.5),
        expr("divide", True, 2),
        expr("strip", 1),
        expr("length", 2),
        expr("values", []),
        expr("take", [], "one"),
        expr("logsumexp", ["bad"]),
        expr("less_than", "bad", 2),
        fold(2, 0, item="x", accumulator="a", body=0),
    ],
)
def test_bad_operands_in_unselected_command_branch_are_rejected(expression):
    with pytest.raises(MachineValidationError) as caught:
        machine(choose(True, 0, expression)).validate()
    assert "commands['run'].effects[0]" in caught.value.path


def test_join_preserves_record_members_and_numeric_widening():
    joined = choose(arg("flag"), record(total=1), record(total=2.5))
    machine(joined.get("total") + 2, {"flag": StateType.boolean()}).validate()
    with pytest.raises(MachineValidationError, match="unknown record field"):
        machine(joined.get("typo"), {"flag": StateType.boolean()}).validate()
    with pytest.raises(MachineValidationError, match="strip requires"):
        machine(joined.get("total").stripped(), {"flag": StateType.boolean()}).validate()


def test_unknown_and_nullable_lookups_remain_runtime_checked():
    expression = arg("values").get(arg("key"), None) + 1
    spec = machine(expression, {"values": StateType.map(StateType.text(), StateType.number()), "key": StateType.text()})
    spec.validate()
    runtime = Runtime()
    assert runtime.execute(
        spec, {"answer": 0}, "run", {"values": {"n": 2}, "key": "n"}
    ).state == {"answer": 3}
    with pytest.raises(TypeError):
        runtime.execute(spec, {"answer": 0}, "run", {"values": {}, "key": "n"})


@pytest.mark.parametrize(
    "loop",
    [
        fold(
            [1], 0, item="x", accumulator="a", body="bad", accumulator_type=StateType.number()
        ),
        iterate(
            0, state="s", until=True, step="bad", max_steps=1, state_type=StateType.number()
        ),
        fold([], "bad", item="x", accumulator="a", body=0, accumulator_type=StateType.number()),
        fold(
            [1],
            record(n=0),
            item="x",
            accumulator="a",
            body=record(n="bad"),
            accumulator_type=StateType.record({"n": StateType.integer()}),
        ),
    ],
)
def test_statically_incompatible_invariant_is_rejected(loop):
    with pytest.raises(MachineValidationError, match="invariant"):
        machine(loop).validate()


@pytest.mark.parametrize(
    "loop",
    [
        fold(
            [1],
            0,
            item="x",
            accumulator="a",
            body=arg("value"),
            accumulator_type=StateType.integer(maximum=2),
        ),
        iterate(
            0,
            state="s",
            until=local("s") > 0,
            step=arg("value"),
            max_steps=1,
            state_type=StateType.integer(maximum=2),
        ),
    ],
)
def test_dynamic_invariants_are_checked_after_each_step_and_roundtrip(loop):
    spec = Machine.from_json(machine(loop, {"value": StateType.any()}).to_json())
    spec.validate()
    runtime = Runtime()
    for value in ["bad", 3]:
        original = {"answer": 0}
        with pytest.raises(DSLValidationError):
            runtime.execute(spec, original, "run", {"value": value})
        assert original == {"answer": 0}
    assert runtime.execute(spec, {"answer": 0}, "run", {"value": 1}).state == {
        "answer": 1
    }


def test_empty_fold_and_zero_step_iteration_validate_seed():
    for expression in [
        fold(
            [],
            arg("value"),
            item="x",
            accumulator="a",
            body=0,
            accumulator_type=StateType.integer(),
        ),
        iterate(
            arg("value"),
            state="s",
            until=True,
            step=0,
            max_steps=0,
            state_type=StateType.integer(),
        ),
    ]:
        spec = machine(expression, {"value": StateType.any()})
        spec.validate()
        with pytest.raises(DSLValidationError):
            Runtime().execute(spec, {"answer": 0}, "run", {"value": "bad"})
