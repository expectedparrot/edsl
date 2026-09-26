"""General expression semantics, serialization, and transaction failure boundaries."""

import math

import pytest

from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    choose,
    exp,
    field,
    fold,
    iterate,
    let,
    local,
    logsumexp,
    resolve_write,
    set_,
    state_field,
    take,
)
from edsl.sharedstate.dsl import Expr
from edsl.sharedstate.dsl_runtime import DSLValidationError, Runtime
from edsl.sharedstate.steps import StepContext


def evaluate(expression):
    machine = Machine(
        name="Expression",
        constants={},
        fields={"answer": state_field(T.any(), None)},
        commands={},
        view={"answer": expression},
    )
    transported = Machine.from_json(machine.to_json())
    transported.validate()
    return Runtime().render_view(transported, {"answer": None})["answer"]


def test_fold_order_empty_and_lexical_shadowing():
    # Nested folds shadow their bindings without changing the outer accumulator.
    inner = fold(
        local("row"),
        0,
        item="number",
        accumulator="total",
        body=local("total") + local("number"),
    )
    outer = fold(
        [[1, 2], [], [4]],
        10,
        item="row",
        accumulator="total",
        body=local("total") + inner,
    )
    assert evaluate(outer) == 17
    assert evaluate(
        fold([], {"empty": True}, item="x", accumulator="a", body=local("x"))
    ) == {"empty": True}
    assert evaluate(
        fold(
            [3, 1, 2],
            [],
            item="x",
            accumulator="a",
            body=local("a").appended(local("x")),
        )
    ) == [3, 1, 2]
    assert (
        evaluate(let("x", 5, let("x", local("x") + 1, local("x")) + local("x"))) == 11
    )


def test_iteration_zero_steps_exact_boundary_and_lazy_stop():
    assert (
        evaluate(
            iterate(7, state="s", until=True, step=Expr("divide", (1, 0)), max_steps=0)
        )
        == 7
    )
    assert (
        evaluate(
            iterate(
                0, state="s", until=local("s") == 3, step=local("s") + 1, max_steps=3
            )
        )
        == 3
    )
    with pytest.raises((ValueError, DSLValidationError), match="exhausted"):
        evaluate(
            iterate(
                0, state="s", until=local("s") == 3, step=local("s") + 1, max_steps=2
            )
        )


@pytest.mark.parametrize("limit", [-1, True, 1.5, "2", 100001])
def test_invalid_iteration_budget(limit):
    with pytest.raises((ValueError, DSLValidationError), match="max_steps"):
        evaluate(iterate(0, state="s", until=True, step=local("s"), max_steps=limit))


def test_iteration_requires_boolean_condition():
    with pytest.raises((ValueError, DSLValidationError), match="[Bb]oolean"):
        evaluate(iterate(0, state="s", until=1, step=local("s"), max_steps=1))


@pytest.mark.parametrize(
    "bad",
    [
        Expr("fold", ([],)),
        Expr("fold", ([], 0), {"item": "x", "accumulator": "x", "body": 0}),
        Expr("let", (1,), {"name": "a.b", "body": 1}),
        Expr("iterate", (0,), {"state": "s", "step": 1, "max_steps": 2}),
        Expr("let", (1,), {"name": "x", "body": 1, "typo": True}),
        Expr("exp", (1, 2)),
        Expr("take", ([], 1), {"typo": True}),
    ],
)
def test_structural_errors_are_rejected_in_dead_branches(bad):
    with pytest.raises(ValueError):
        evaluate(choose(True, 0, bad))


@pytest.mark.parametrize(
    "expression",
    [
        fold({}, 0, item="x", accumulator="a", body=0),
        take([1], -1),
        take([1], True),
        take({}, 1),
    ],
)
def test_collection_operand_contracts(expression):
    with pytest.raises((ValueError, DSLValidationError)):
        evaluate(expression)


def test_stable_math_and_take():
    assert evaluate(logsumexp([1000, 1000])) == pytest.approx(1000 + math.log(2))
    assert evaluate(logsumexp([-1000, -1000])) == pytest.approx(-1000 + math.log(2))
    assert evaluate(exp(-1000)) == 0
    assert evaluate(take([1, 2], 5)) == [1, 2]
    assert evaluate(take([1, 2], 0)) == []


@pytest.mark.parametrize(
    "expression",
    [exp(10000), exp(10**400), logsumexp([]), logsumexp([True]), exp("bad")],
)
def test_invalid_math_fails_explicitly(expression):
    with pytest.raises((ValueError, DSLValidationError)):
        evaluate(expression)


def test_exhaustion_rolls_back_all_effects_and_does_not_commit_sqlite(tmp_path):
    bad = iterate(0, state="s", until=False, step=local("s") + 1, max_steps=3)
    machine = Machine(
        name="AtomicIteration",
        constants={},
        fields={"marker": state_field(T.integer(), 0)},
        commands={"fail": Command({}, (set_("marker", 99), set_("marker", bad)))},
        view={"marker": field("marker")},
    )
    runtime = Runtime()
    original = runtime.initial_state(machine)
    with pytest.raises(DSLValidationError, match="exhausted"):
        runtime.execute(machine, original, "fail", {})
    assert original == {"marker": 0}
    spaces = SharedStateMap(SharedState(data=machine))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    before = backend.snapshot("scope")
    operation = resolve_write(
        spaces.by("scope").data.fail(), StepContext({}, "interview")
    )
    with pytest.raises(DSLValidationError, match="exhausted"):
        backend.apply(operation)
    after = backend.snapshot("scope")
    assert after.state == before.state
    assert backend.history() == []
