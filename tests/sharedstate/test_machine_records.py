"""Structured Machine values and precise, scope-aware authoring diagnostics."""

from dataclasses import replace

import pytest

from edsl.sharedstate import (
    Command,
    Machine,
    MachineValidationError,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    choose,
    field,
    fold,
    input_,
    iterate,
    let,
    local,
    map_items,
    map_sequence,
    record,
    resolve_write,
    set_,
    state_field,
)
from edsl.sharedstate.dsl import Expr, ref
from edsl.sharedstate.dsl_runtime import DSLValidationError, Runtime
from edsl.sharedstate.steps import StepContext


def spec():
    account = T.record(
        {
            "balance": T.number(),
            "label": T.optional(T.text()),
            "entries": T.sequence(T.record({"amount": T.number()})),
        }
    )
    return Machine(
        name="TypedLedger",
        constants={},
        fields={
            "account": state_field(
                account, {"balance": 0, "label": None, "entries": []}
            )
        },
        commands={
            "save": Command({"account": account}, (set_("account", input_("account")),))
        },
        view={"account": field("account")},
    )


def test_nested_record_round_trip_and_runtime_validation():
    machine = Machine.from_json(spec().to_json())
    machine.validate()
    runtime = Runtime()
    state = runtime.initial_state(machine)
    account = {"balance": 10, "label": "cash", "entries": [{"amount": 10}]}
    assert (
        runtime.execute(machine, state, "save", {"account": account}).state["account"]
        == account
    )
    assert machine.to_dict() == spec().to_dict()


@pytest.mark.parametrize(
    "account, message",
    [
        ({"balance": 0, "entries": []}, "missing=.*label"),
        ({"balance": 0, "label": None, "entries": [], "typo": 1}, "extra=.*typo"),
        (
            {"balance": 0, "label": None, "entries": [{"amount": "bad"}]},
            r"account.entries\[0\].amount must be numerical",
        ),
        ([], "must be a record"),
    ],
)
def test_bad_inputs_fail_before_any_effect(account, message):
    machine = spec()
    runtime = Runtime()
    state = runtime.initial_state(machine)
    with pytest.raises(DSLValidationError, match=message):
        runtime.execute(machine, state, "save", {"account": account})
    assert state == runtime.initial_state(machine)


def test_open_records_accept_extra_json_but_require_declared_fields():
    runtime = Runtime()
    schema = T.record({"count": T.integer()}, allow_extra=True)
    runtime._validate_type("value", {"count": 1, "metadata": ["ok"]}, schema, {})
    with pytest.raises(DSLValidationError, match="missing"):
        runtime._validate_type("value", {"metadata": []}, schema, {})
    with pytest.raises(DSLValidationError, match="finite"):
        runtime._validate_type(
            "value", {"count": 1, "metadata": float("nan")}, schema, {}
        )


@pytest.mark.parametrize(
    "schema",
    [
        T.record({"": T.text()}),
        T.record({"x": "text"}),
        T.record({}, allow_extra="yes"),
        T.record([]),
    ],
)
def test_invalid_record_definitions_have_machine_and_path(schema):
    machine = replace(spec(), fields={"account": state_field(schema, {})})
    with pytest.raises(MachineValidationError) as error:
        machine.validate()
    assert error.value.machine == "TypedLedger"
    assert error.value.path.startswith("$.fields['account'].type")


@pytest.mark.parametrize(
    "expression",
    [
        field("account").get("balnce"),
        field("account.balnce"),
        let("a", field("account"), local("a").get("balnce")),
        map_sequence(
            field("account").get("entries"),
            item="entry",
            value_expr=local("entry").get("ammount"),
        ),
    ],
)
def test_misspelled_record_fields_fail_in_dead_branches(expression):
    machine = replace(spec(), view={"bad": choose(False, expression, "unused")})
    with pytest.raises(MachineValidationError, match="unknown record field") as error:
        machine.validate()
    assert error.value.path.startswith("$.view['bad'].args[1]")
    assert error.value.reason


@pytest.mark.parametrize("where", ["view", "require", "complete", "close", "initial"])
def test_unbound_locals_checked_in_every_context(where):
    bad = choose(False, local("missing"), 0)
    machine = spec()
    if where == "view":
        machine = replace(machine, view={"bad": bad})
    elif where == "require":
        machine = replace(machine, commands={"bad": Command({}, (), require=bad)})
    elif where == "complete":
        machine = replace(machine, complete_when=bad)
    elif where == "close":
        machine = replace(machine, close_effects=(set_("account", bad),))
    else:
        machine = replace(machine, fields={"account": state_field(T.any(), bad)})
    with pytest.raises(
        MachineValidationError, match="unbound local reference"
    ) as error:
        machine.validate()
    assert error.value.path != "$"


@pytest.mark.parametrize(
    "expression",
    [
        choose(False, input_("absent"), 0),
        choose(False, field("absent"), 0),
        choose(False, ref("mystery", "x"), 0),
        let("x", local("x"), 1),
        fold([], local("acc"), item="i", accumulator="acc", body=0),
        iterate(0, state="s", until=True, step=0, max_steps=local("s")),
        let("x", 1, local("x")) + local("x"),
    ],
)
def test_wrong_namespace_and_binding_leaks_are_rejected(expression):
    with pytest.raises(MachineValidationError):
        replace(spec(), view={"bad": expression}).validate()


def test_shadowing_outer_value_and_dynamic_open_fields_stay_valid():
    expression = let("x", 5, let("x", local("x") + 1, local("x")) + local("x"))
    machine = replace(
        spec(),
        view={
            "answer": expression,
            "dynamic": field("account").get(ref("current", "key")),
        },
    )
    machine.validate()
    result = Runtime().render_view(
        machine, Runtime().initial_state(machine), current={"key": "balance"}
    )
    assert result == {"answer": 11, "dynamic": 0}
    opened = replace(
        spec(),
        fields={
            "account": state_field(
                T.record({"balance": T.number()}, allow_extra=True), {"balance": 0}
            )
        },
        commands={},
        view={"extra": field("account").get("extension", "fallback")},
    )
    opened.validate()


def test_structural_errors_identify_the_expression_path():
    machine = replace(
        spec(), commands={"bad": Command({}, (set_("account", Expr("add", (1,))),))}
    )
    with pytest.raises(MachineValidationError) as error:
        machine.validate()
    assert error.value.path == "$.commands['bad'].effects[0].args[0]"


def test_record_output_failure_rolls_back_sqlite_and_prior_effects(tmp_path):
    machine = replace(
        spec(),
        commands={
            "bad": Command(
                {},
                (
                    set_("account", {"balance": 5, "label": None, "entries": []}),
                    set_("account", {"balance": "bad", "label": None, "entries": []}),
                ),
            )
        },
    )
    spaces = SharedStateMap(SharedState(ledger=machine))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    before = backend.snapshot("scope")
    with pytest.raises(DSLValidationError, match="account.balance must be numerical"):
        backend.apply(
            resolve_write(spaces.by("scope").ledger.bad(), StepContext({}, "interview"))
        )
    assert backend.snapshot("scope").state == before.state
    assert backend.history() == []


def test_record_initial_and_close_values_are_validated():
    bad_initial = replace(
        spec(),
        fields={
            "account": state_field(
                T.record({"balance": T.number()}), {"balance": "bad"}
            )
        },
    )
    with pytest.raises(MachineValidationError, match="account.balance"):
        bad_initial.validate()
    machine = replace(spec(), close_effects=(set_("account", {"balance": 1}),))
    machine.validate()
    state = Runtime().initial_state(machine)
    with pytest.raises(DSLValidationError, match="missing"):
        Runtime().close(machine, state)
    assert state == Runtime().initial_state(machine)


def test_nested_input_record_reference_is_checked_and_executes():
    machine = replace(
        spec(),
        commands={
            "save": Command(
                spec().commands["save"].inputs,
                (
                    set_(
                        "account",
                        field("account").with_item(
                            "balance", input_("account.balance")
                        ),
                    ),
                ),
            )
        },
    )
    machine.validate()
    account = {"balance": 5, "label": None, "entries": []}
    result = Runtime().execute(
        machine, Runtime().initial_state(machine), "save", {"account": account}
    )
    assert result.state["account"]["balance"] == 5


def test_shape_changing_accumulators_are_not_assumed_to_have_seed_type():
    expression = fold(
        [True, False],
        record(a=1),
        item="first",
        accumulator="acc",
        body=choose(local("first"), record(a=1, b=2), record(a=local("acc").get("b"))),
    )
    machine = replace(spec(), view={"answer": expression})
    machine.validate()
    assert Runtime().render_view(machine, Runtime().initial_state(machine))[
        "answer"
    ] == {"a": 2}
