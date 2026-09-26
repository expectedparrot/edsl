"""Shared interpreter quotas fail atomically, including persisted transitions."""

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

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
    expr,
    field,
    fold,
    input_,
    iterate,
    local,
    map_sequence,
    resolve_write,
    set_,
    state_field,
)
from edsl.sharedstate.dsl_runtime import Runtime
from edsl.sharedstate.steps import StepContext


def machine(expression, *, effects=None, view=None):
    return Machine(
        name="Budget",
        constants={},
        fields={"answer": state_field(T.any(), 0)},
        commands={"run": Command({}, effects or (set_("answer", expression),))},
        view=view or {"answer": field("answer")},
    )


def nested_work():
    inner = fold(list(range(30)), 0, item="i", accumulator="a", body=local("a") + 1)
    return map_sequence(list(range(30)), item="outer", value_expr=inner)


def test_nested_folds_share_budget_and_reset_after_failure():
    runtime = Runtime(limits=ExecutionLimits(max_steps=2000))
    with pytest.raises(ResourceLimitError, match="max_steps"):
        runtime.evaluate(nested_work(), {})
    assert runtime.evaluate(expr("add", 1, 2), {}) == 3


def test_effects_share_one_budget():
    work = fold(list(range(50)), 0, item="i", accumulator="a", body=local("a") + 1)
    single = machine(work)
    combined = machine(work, effects=(set_("answer", work), set_("answer", work)))
    runtime = Runtime(limits=ExecutionLimits(max_steps=2000))
    assert runtime.execute(single, {"answer": 0}, "run", {}).state == {"answer": 50}
    with pytest.raises(ResourceLimitError, match="max_steps"):
        runtime.execute(combined, {"answer": 0}, "run", {})


@pytest.mark.parametrize(
    "operation", ["execute", "close", "render_view", "complete", "initial_state"]
)
def test_all_entry_points_are_bounded(operation):
    spec = machine(nested_work())
    runtime = Runtime(limits=ExecutionLimits(max_steps=2000))
    if operation == "close":
        spec = replace(spec, close_effects=(set_("answer", nested_work()),))
    elif operation == "render_view":
        spec = replace(spec, view={"answer": nested_work()})
    elif operation == "complete":
        spec = replace(spec, complete_when=nested_work())
    elif operation == "initial_state":
        spec = replace(spec, fields={"answer": state_field(T.any(), nested_work())})
    with pytest.raises(ResourceLimitError, match="max_steps"):
        if operation == "execute":
            runtime.execute(spec, {"answer": 0}, "run", {})
        elif operation == "initial_state":
            runtime.initial_state(spec)
        else:
            getattr(runtime, operation)(spec, {"answer": 0})


@pytest.mark.parametrize(
    "expression,limits,resource",
    [
        (
            expr("multiply", [1], 1000000000),
            ExecutionLimits(max_collection_items=100),
            "max_collection_items",
        ),
        (
            expr("multiply", "x", 1000000000),
            ExecutionLimits(max_value_bytes=1000),
            "max_value_bytes",
        ),
        (
            iterate(
                [0],
                state="s",
                until=False,
                step=local("s").appended(local("s")),
                max_steps=20,
            ),
            ExecutionLimits(max_value_nodes=100),
            "max_value_nodes",
        ),
        (
            expr("multiply", 2**100, 2**100),
            ExecutionLimits(max_integer_bits=150),
            "max_integer_bits",
        ),
    ],
)
def test_growth_limits(expression, limits, resource):
    with pytest.raises(ResourceLimitError, match=resource):
        Runtime(limits=limits).evaluate(expression, {})


def test_ast_size_depth_and_cyclic_data_fail_before_recursive_work():
    spec = machine(0)
    with pytest.raises(ResourceLimitError, match="max_ast_nodes"):
        Runtime(limits=ExecutionLimits(max_ast_nodes=10)).execute(
            spec, {"answer": 0}, "run", {}
        )
    deep = expr("add", 1, 2)
    for _ in range(100):
        deep = expr("add", deep, 1)
    with pytest.raises(MachineValidationError, match="max_depth"):
        machine(deep).validate()
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(ResourceLimitError, match="max_depth"):
        Runtime().evaluate(cyclic, {})


def test_input_and_combined_view_sizes_are_bounded():
    runtime = Runtime(
        limits=ExecutionLimits(max_collection_items=10, max_value_bytes=2000)
    )
    spec = replace(machine(0), commands={"run": Command({"v": T.any()}, ())})
    with pytest.raises(ResourceLimitError, match="max_collection_items"):
        runtime.execute(spec, {"answer": 0}, "run", {"v": list(range(11))})
    spec = machine(0, view={"left": field("answer"), "right": field("answer")})
    with pytest.raises(ResourceLimitError, match="max_value_bytes"):
        runtime.render_view(spec, {"answer": "x" * 200})


@pytest.mark.parametrize(
    "expression,limits",
    [
        (nested_work(), ExecutionLimits(max_steps=2000)),
        (expr("multiply", [1], 1000000000), ExecutionLimits(max_collection_items=100)),
    ],
)
@pytest.mark.parametrize("close", [False, True])
def test_failed_command_preserves_sqlite_state_version_and_history(
    tmp_path, expression, limits, close
):
    spec = machine(expression, effects=(set_("answer", 99), set_("answer", expression)))
    if close:
        spec = replace(spec, close_effects=spec.commands["run"].effects)
    spaces = SharedStateMap(SharedState(data=spec))
    backend = SQLiteStateBackend(
        spaces, tmp_path / "state.sqlite", runtime=Runtime(limits=limits)
    )
    before = backend.snapshot("scope")
    operation = resolve_write(
        spaces.by("scope").data.close() if close else spaces.by("scope").data.run(),
        StepContext({}, "interview"),
    )
    with pytest.raises(ResourceLimitError):
        backend.apply(operation)
    after = backend.snapshot("scope")
    assert after.state == before.state
    assert after.version == before.version
    assert backend.history() == []


def test_parallel_operations_do_not_share_budget():
    runtime = Runtime(limits=ExecutionLimits(max_steps=100))
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert (
            list(
                pool.map(lambda _: runtime.evaluate(expr("add", 1, 2), {}), range(100))
            )
            == [3] * 100
        )


@pytest.mark.parametrize("limit", [0, -1, True, 1.5])
def test_limits_require_positive_integers(limit):
    with pytest.raises(ValueError):
        ExecutionLimits(max_steps=limit)


def test_generated_collection_is_bounded_during_construction():
    class CountingRuntime(Runtime):
        generated = 0

        def _evaluate(self, value, context):
            if getattr(value, "op", None) == "multiply":
                self.generated += 1
            return super()._evaluate(value, context)

    runtime = CountingRuntime(limits=ExecutionLimits(max_value_bytes=1500))
    expression = map_sequence(
        list(range(20)), item="i", value_expr=expr("multiply", "x", 100)
    )
    with pytest.raises(ResourceLimitError, match="max_value_bytes"):
        runtime.evaluate(expression, {})
    assert 1 < runtime.generated < 20


def test_native_sort_work_is_charged_to_the_shared_budget():
    expression = expr(
        "reduce", "sort_records", [{"n": i} for i in range(30)], fields=["n"] * 30
    )
    with pytest.raises(ResourceLimitError, match="max_steps"):
        Runtime(limits=ExecutionLimits(max_steps=3000)).evaluate(expression, {})


def test_deserialization_checks_depth_before_decoding_expressions():
    data = machine(0).to_dict()
    nested = []
    for _ in range(100):
        nested = [nested]
    data["constants"] = {"nested": nested}
    with pytest.raises(ResourceLimitError, match="max_depth"):
        Machine.from_dict(data)
    with pytest.raises(ResourceLimitError, match="nesting|max_depth"):
        Machine.from_json("[" * 2000 + "0" + "]" * 2000)


def test_accumulator_invariant_failure_rolls_back_sqlite(tmp_path):
    expression = fold(
        [1],
        0,
        item="i",
        accumulator="a",
        body=input_("value"),
        accumulator_type=T.integer(),
    )
    spec = replace(
        machine(0),
        commands={
            "run": Command(
                {"value": T.any()}, (set_("answer", 99), set_("answer", expression))
            )
        },
    )
    spaces = SharedStateMap(SharedState(data=spec))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    before = backend.snapshot("scope")
    operation = resolve_write(
        spaces.by("scope").data.run(value="bad"), StepContext({}, "interview")
    )
    with pytest.raises(ValueError, match="fold accumulator must be an integer"):
        backend.apply(operation)
    after = backend.snapshot("scope")
    assert (after.state, after.version) == (before.state, before.version)
    assert backend.history() == []


@pytest.mark.parametrize("keyword", [False, True])
def test_container_expression_obeys_ast_quota(keyword):
    runtime = Runtime(limits=ExecutionLimits(max_ast_nodes=10))
    expression = {"answer": [expr("add", 1, 2)] * 3}
    with pytest.raises(ResourceLimitError, match="max_ast_nodes"):
        if keyword:
            runtime.evaluate(value=expression, context={})
        else:
            runtime.evaluate(expression, {})
