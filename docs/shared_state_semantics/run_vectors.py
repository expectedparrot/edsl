"""Run normative shared-state test vectors against the reference interpreter."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edsl.sharedstate import Machine  # noqa: E402
from edsl.sharedstate.dsl_runtime import (  # noqa: E402
    Runtime,
    lmsr_runtime,
    mechanism_runtime,
)


def runtime_for(machine: Machine) -> Runtime:
    runtime = Runtime()
    for configured in (lmsr_runtime(), mechanism_runtime()):
        runtime.algorithms.update(configured.algorithms)
    return runtime


def validate_schema(payload: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        return
    schema = json.loads((Path(__file__).parent / "machine.schema.json").read_text())
    jsonschema.Draft202012Validator(schema).validate(payload)


def run_vector(path: Path) -> None:
    vector = json.loads(path.read_text())
    envelope = vector["envelope"]
    validate_schema(envelope)
    machine = Machine.from_dict(envelope["machine"])
    machine.validate()
    runtime = runtime_for(machine)
    state = runtime.initial_state(machine)

    for step in vector["steps"]:
        result = runtime.execute(
            machine,
            state,
            step["command"],
            step["inputs"],
            current=step.get("current"),
        )
        if "expect_changed" in step:
            assert result.event["changed"] is step["expect_changed"]
        state = result.state

    if vector.get("close"):
        state = runtime.close(machine, state)

    assert state == vector["expected_state"], (path.name, state)
    view = runtime.render_view(
        machine,
        state,
        current=vector.get("view_current"),
        closed=bool(vector.get("close")),
    )
    assert view == vector["expected_view"], (path.name, view)


def main() -> None:
    paths = sorted((Path(__file__).parent / "test-vectors").glob("*.json"))
    for path in paths:
        run_vector(path)
        print(f"PASS {path.name}")
    print(f"{len(paths)} vector(s) passed")


if __name__ == "__main__":
    main()
