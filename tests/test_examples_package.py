import json
import subprocess
import sys


def _run_example_module(module: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", module],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_packaged_machine_primitive_command_runs_offline():
    output = _run_example_module("edsl.examples.shared_state.machine_primitives")

    assert len(output) == 19
    assert all(item for item in output.values())


def test_packaged_shared_state_dsl_validator_runs_offline():
    output = _run_example_module("edsl.examples.shared_state.dsl.validate")

    assert output["target_count"] == 38
