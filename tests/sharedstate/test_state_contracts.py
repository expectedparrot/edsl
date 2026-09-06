"""Persistence and language validation contracts for research state machines."""

from dataclasses import replace

import pytest

from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    field,
    input_,
    resolve_write,
    set_,
    state_field,
)
from edsl.sharedstate.dsl import Effect, Expr, choose, reduce_
from edsl.sharedstate.dsl_runtime import DSLValidationError, Runtime
from edsl.sharedstate.exceptions import (
    SharedStateAuthoringError,
    SharedStateRuntimeError,
)
from edsl.sharedstate.steps import StepContext


def machine(input_type=None):
    return Machine(
        name="Contract",
        constants={"label": "original"},
        fields={"value": state_field(T.any(), None)},
        commands={
            "save": Command(
                {"value": T.number() if input_type is None else input_type},
                (set_("value", input_("value")),),
            )
        },
        view={"value": field("value")},
    )


def state_map(spec=None):
    return SharedStateMap(
        SharedState(data=machine() if spec is None else spec), state_id="contract"
    )


def test_symbolic_boolean_operators_fail_loudly():
    with pytest.raises(TypeError, match="truth value"):
        (input_("x") > 0) and (input_("x") < 10)
    condition = (input_("x") > 0) & (input_("x") < 10)
    assert Runtime().evaluate(condition, {"input": {"x": -1}}) is False


@pytest.mark.parametrize(
    "bad", [Expr("add", (1,)), Expr("type", ("numbr",)), reduce_("summ", [])]
)
def test_invalid_expressions_are_rejected_even_in_dead_branches(bad):
    spec = replace(machine(), view={"test": choose(True, 1, bad)})
    with pytest.raises(ValueError):
        spec.validate()


@pytest.mark.parametrize(
    "effect",
    [
        Effect("apend", "value", (1,)),
        Effect("set", "value", ()),
        Effect("set", "value", (1,), {"whne": False}),
    ],
)
def test_invalid_effects_fail_before_execution(effect):
    spec = replace(machine(), commands={"bad": Command({}, (effect,))})
    with pytest.raises(ValueError):
        spec.validate()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("type_expr", [T.number(), T.any()])
def test_nonfinite_values_cannot_enter_state(value, type_expr):
    spec = machine(type_expr)
    with pytest.raises(DSLValidationError, match="finite"):
        Runtime().execute(spec, {"value": None}, "save", {"value": value})


def test_persisted_maps_require_string_keys(tmp_path):
    with pytest.raises(ValueError, match="string map keys"):
        state_map(machine(T.map(T.integer(), T.text())))
    spaces = state_map(machine(T.any()))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    operation = resolve_write(
        spaces.by("scope").data.save(value={1: "value"}), StepContext({}, "interview")
    )
    with pytest.raises(ValueError, match="string map keys"):
        backend.apply(operation)
    assert backend.history() == []


def test_string_maps_round_trip_without_changing_key_types(tmp_path):
    spaces = state_map(machine(T.any()))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    value = {"1": [2, None, {"three": True}]}
    backend.apply(
        resolve_write(
            spaces.by("scope").data.save(value=value), StepContext({}, "interview")
        )
    )
    reopened = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    assert reopened.snapshot("scope").state["data"]["value"] == value


def test_one_operation_identity_cannot_be_reused_for_different_answers(tmp_path):
    spaces = state_map()
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    step = spaces.by("scope").data.save(value=1)
    first = resolve_write(step, StepContext({}, "interview"))
    changed = resolve_write(
        replace(step, inputs={"value": 2}), StepContext({}, "interview")
    )
    assert first.idempotency_key == changed.idempotency_key
    backend.apply(first)
    with pytest.raises(SharedStateRuntimeError, match="different content"):
        backend.apply(changed)
    with pytest.raises(SharedStateRuntimeError, match="different content"):
        backend.apply(replace(first, execution_id="different-interview"))
    with pytest.raises(SharedStateRuntimeError, match="different runtime context"):
        backend.apply(replace(first, runtime_context={"name": "someone-else"}))
    assert backend.snapshot("scope").version == 1


def test_backend_rejects_changed_definition_and_detaches_input(tmp_path):
    spaces = state_map()
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    spaces.definition.machines["data"].constants["label"] = "changed"
    assert (
        backend.state_map.definition.machines["data"].constants["label"] == "original"
    )
    with pytest.raises(SharedStateRuntimeError, match="definition changed"):
        SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    backend.state_map.definition.machines["data"].constants["label"] = "mutated"
    with pytest.raises(SharedStateRuntimeError, match="mutated"):
        backend.snapshot("scope")


def test_legacy_store_requires_explicit_adoption(tmp_path):
    spaces = state_map()
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    backend.apply(
        resolve_write(
            spaces.by("scope").data.save(value=1), StepContext({}, "interview")
        )
    )
    with backend._connect() as db:
        db.execute("DROP TABLE state_definitions")
    with pytest.raises(SharedStateRuntimeError, match="legacy state store"):
        SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    adopted = SQLiteStateBackend(
        spaces, tmp_path / "state.sqlite", adopt_legacy_definition=True
    )
    assert adopted.snapshot("scope").state["data"]["value"] == 1
    with adopted._connect() as db:
        assert (
            db.execute("SELECT adopted_legacy FROM state_definitions").fetchone()[0]
            == 1
        )


def test_unsupported_serialization_versions_are_rejected():
    with pytest.raises(ValueError, match="version"):
        Machine.from_dict({**machine().to_dict(), "version": 999})
    with pytest.raises(SharedStateAuthoringError):
        SharedStateMap.from_dict({**state_map().to_dict(), "version": 999})


def test_fingerprint_ignores_only_edsl_object_build_labels():
    from edsl._data_contracts import definition_fingerprint

    definition = {
        "survey": {"edsl_class_name": "Survey", "edsl_version": "a"},
        "constants": {"edsl_version": "research treatment"},
    }
    build_change = {
        **definition,
        "survey": {**definition["survey"], "edsl_version": "b"},
    }
    treatment_change = {
        **definition,
        "constants": {"edsl_version": "different treatment"},
    }
    assert definition_fingerprint(definition) == definition_fingerprint(build_change)
    assert definition_fingerprint(definition) != definition_fingerprint(
        treatment_change
    )
