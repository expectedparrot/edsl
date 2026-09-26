"""Destination checks use derived requirements, including code not executed yet."""

from dataclasses import replace
import json

import pytest

from edsl._data_contracts import definition_fingerprint
from edsl.sharedstate import (
    Command,
    Machine,
    SharedState,
    SharedStateMap,
    SQLiteStateBackend,
    T,
    UnsupportedCapabilityError,
    algorithm,
    choose,
    expr,
    field,
    fold,
    input_,
    iterate,
    local,
    record,
    resolve_write,
    set_,
    state_field,
)
from edsl.sharedstate.dsl_runtime import Runtime
from edsl.sharedstate.steps import StepContext


def machine(expression=1):
    return Machine(
        name="Portable",
        constants={},
        fields={"value": state_field(T.any(), 0)},
        commands={"save": Command({}, (set_("value", expression),))},
        view={"value": field("value")},
    )


def destination_without(*capabilities):
    supported = set(Runtime().capability_manifest()["supported"])
    return Runtime(capabilities=supported - set(capabilities))


def test_requirements_are_derived_sorted_unique_and_roundtrip_stable():
    expression = fold(
        [1],
        record(n=0),
        item="i",
        accumulator="a",
        accumulator_type=T.record({"n": T.integer()}),
        body=record(n=local("a").get("n") + local("i")),
    )
    spec = machine(expression)
    before = spec.to_dict()
    required = spec.required_capabilities()
    assert required["version"] == 1
    assert required["requires"] == sorted(set(required["requires"]))
    assert {
        "language:machine@1",
        "expression:fold@1",
        "effect:set@1",
        "feature:fold.accumulator_type@1",
        "type:record@1",
        "type:integer@1",
    } <= set(required["requires"])
    assert Machine.from_json(spec.to_json()).required_capabilities() == required
    assert spec.to_dict() == before
    assert "requires" not in before


@pytest.mark.parametrize(
    "location",
    ["initial", "input", "require", "effect", "view", "complete", "close", "constant"],
)
def test_all_definition_contexts_are_checked(location):
    spec = machine()
    unsupported = expr("exp", 0)
    if location == "initial":
        spec = replace(spec, fields={"value": state_field(T.number(), unsupported)})
    elif location == "input":
        spec = replace(
            spec,
            commands={"save": Command({"amount": T.number(maximum=unsupported)}, ())},
        )
    elif location == "require":
        spec = replace(
            spec,
            commands={"save": Command({}, (), require=choose(True, True, unsupported))},
        )
    elif location == "effect":
        spec = machine(choose(True, 1, unsupported))
    elif location == "view":
        spec = replace(spec, view={"value": choose(True, 0, unsupported)})
    elif location == "complete":
        spec = replace(spec, complete_when=choose(True, True, unsupported))
    elif location == "close":
        spec = replace(spec, close_effects=(set_("value", unsupported),))
    else:
        spec = replace(spec, constants={"unused": unsupported})
    with pytest.raises(UnsupportedCapabilityError) as caught:
        destination_without("expression:exp@1").validate_capabilities(spec)
    assert caught.value.machine == "Portable"
    assert caught.value.missing == ("expression:exp@1",)
    assert caught.value.paths["expression:exp@1"][0].startswith("$.")
    assert json.loads(json.dumps(caught.value.to_dict()))["missing"] == [
        "expression:exp@1"
    ]


@pytest.mark.parametrize(
    "entry", ["execute", "initial_state", "render_view", "complete", "close"]
)
def test_every_machine_entry_point_preflights_before_callbacks(entry):
    calls = []
    runtime = destination_without("expression:exp@1")
    runtime.register(
        "touch",
        1,
        lambda *args: calls.append("effect"),
        validate_constants=lambda constants: calls.append("validator"),
    )
    spec = replace(
        machine(),
        algorithms=("touch@1",),
        commands={
            "save": Command({}, (algorithm("touch"), set_("value", expr("exp", 0))))
        },
    )
    original = {"value": 0}
    with pytest.raises(UnsupportedCapabilityError):
        if entry == "execute":
            runtime.execute(spec, original, "save", {})
        elif entry == "initial_state":
            runtime.initial_state(spec)
        else:
            getattr(runtime, entry)(spec, original)
    assert original == {"value": 0}
    assert calls == []


@pytest.mark.parametrize(
    "expression,capability",
    [
        (
            fold(
                [], 0, item="i", accumulator="a", body=0, accumulator_type=T.integer()
            ),
            "feature:fold.accumulator_type@1",
        ),
        (
            iterate(
                0, state="s", until=True, step=0, max_steps=0, state_type=T.integer()
            ),
            "feature:iterate.state_type@1",
        ),
        (expr("reduce", "sum", [1, 2]), "reducer:sum@1"),
    ],
)
def test_options_and_reducers_have_independent_capabilities(expression, capability):
    spec = Machine.from_json(machine(expression).to_json())
    spec.validate()
    with pytest.raises(UnsupportedCapabilityError, match=capability):
        destination_without(capability).execute(spec, {"value": 0}, "save", {})


def test_standalone_expression_preflight_checks_unselected_branch():
    with pytest.raises(UnsupportedCapabilityError, match="expression:exp@1"):
        destination_without("expression:exp@1").evaluate(
            choose(True, 0, expr("exp", 0)), {}
        )


def test_callback_versions_are_exact_and_views_are_not_callback_implementations():
    spec = replace(
        machine(),
        algorithms=("callback@1",),
        commands={"save": Command({}, (algorithm("callback"),))},
    )
    spec.validate()  # Authors need not install a custom command implementation.
    with pytest.raises(UnsupportedCapabilityError):
        Runtime().initial_state(spec)
    runtime = Runtime()
    runtime.register("callback", 2, lambda *args: None)
    with pytest.raises(UnsupportedCapabilityError) as caught:
        runtime.validate_capabilities(spec)
    assert set(caught.value.missing) == {
        "algorithm:callback@1",
        "dependency:callback@1",
    }
    runtime.register("callback", 1, lambda *args: None)
    runtime.validate_capabilities(spec)
    fake = replace(
        spec,
        algorithms=("lmsr_prices@1",),
        commands={"save": Command({}, (algorithm("lmsr_prices"),))},
    )
    with pytest.raises(UnsupportedCapabilityError, match="algorithm:lmsr_prices@1"):
        runtime.validate_capabilities(fake)


def test_definition_fingerprint_and_existing_sqlite_survive_preflight(tmp_path):
    spec = machine()
    legacy = spec.to_dict()
    fingerprint = definition_fingerprint(legacy)
    spaces = SharedStateMap(SharedState(data=Machine.from_dict(legacy)))
    backend = SQLiteStateBackend(spaces, tmp_path / "state.sqlite")
    backend.apply(resolve_write(spaces.by("scope").data.save(), StepContext({}, "i")))
    before = backend.snapshot("scope")
    spec.check_capabilities(Runtime().capability_manifest())
    assert spec.to_dict() == legacy
    assert definition_fingerprint(spec.to_dict()) == fingerprint
    reopened = SQLiteStateBackend(
        SharedStateMap.from_dict(spaces.to_dict()), tmp_path / "state.sqlite"
    )
    after = reopened.snapshot("scope")
    assert (before.version, before.state) == (after.version, after.state)
    assert backend.definition_hash == reopened.definition_hash


def test_backend_rejects_before_database_creation_or_existing_history_changes(tmp_path):
    spec = machine(expr("exp", 0))
    spaces = SharedStateMap(SharedState(data=spec))
    runtime = destination_without("expression:exp@1")
    with pytest.raises(UnsupportedCapabilityError):
        SQLiteStateBackend(spaces, tmp_path / "new" / "state.sqlite", runtime=runtime)
    assert not (tmp_path / "new").exists()
    path = tmp_path / "existing.sqlite"
    backend = SQLiteStateBackend(spaces, path)
    backend.apply(
        resolve_write(spaces.by("scope").data.save(), StepContext({}, "committed"))
    )
    before = backend.snapshot("scope")
    history = backend.history()
    original_bytes = path.read_bytes()
    with pytest.raises(UnsupportedCapabilityError):
        SQLiteStateBackend(spaces, path, runtime=runtime)
    assert path.read_bytes() == original_bytes
    backend.runtime = runtime  # Removing support after construction also fails closed.
    with pytest.raises(UnsupportedCapabilityError):
        backend.apply(
            resolve_write(spaces.by("scope").data.save(), StepContext({}, "i"))
        )
    after = backend.snapshot("scope")
    assert (before.version, before.state) == (after.version, after.state)
    assert backend.history() == history


def test_wire_advertisement_is_advisory_destination_rechecks_actual_definition(
    tmp_path,
):
    # These JSON messages model a service boundary; no live endpoint is assumed.
    source = Runtime()
    spec = machine(expr("exp", 0))
    advertised = json.loads(json.dumps(source.capability_manifest()))
    spec.check_capabilities(advertised)
    payload = json.loads(spec.to_json())
    payload["requires"] = []  # A sender cannot erase requirements with metadata.
    received = Machine.from_dict(payload)
    destination = destination_without("expression:exp@1")
    with pytest.raises(UnsupportedCapabilityError):
        destination.execute(received, {"value": 0}, "save", {})
    assert source.execute(received, {"value": 0}, "save", {}).state == {"value": 1.0}


@pytest.mark.parametrize(
    "manifest",
    [
        {},
        {"version": 2, "supported": []},
        {"version": True, "supported": []},
        {"version": 1.0, "supported": []},
        {"version": 1, "supported": "all"},
        {"version": 1, "supported": [1]},
    ],
)
def test_invalid_advertisements_are_rejected(manifest):
    with pytest.raises(ValueError, match="manifest"):
        machine().check_capabilities(manifest)


def test_future_version_is_not_implicit_support_for_older_semantics():
    manifest = Runtime().capability_manifest()
    manifest["supported"].remove("expression:add@1")
    manifest["supported"].append("expression:add@2")
    with pytest.raises(UnsupportedCapabilityError, match="expression:add@1"):
        machine(expr("add", 1, 2)).check_capabilities(manifest)


def test_runtime_cannot_advertise_unimplemented_features_or_callbacks():
    with pytest.raises(ValueError, match="restrict"):
        Runtime(capabilities={"expression:teleport@1"})
    with pytest.raises(ValueError, match="callable"):
        Runtime().register("fake", 1, None)
