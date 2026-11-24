"""CLI contract tests for serialized shared-state machines and Results."""

import json

from click.testing import CliRunner

from edsl import Results, Survey
from edsl.__main__ import app
from edsl.examples.shared_state.machine_primitives.reason_discovery import build_machine


def test_state_validate_inspect_and_simulate_json_files(tmp_path):
    machine_path = tmp_path / "machine.json"
    machine_path.write_text(build_machine(patience=2).to_json())
    transitions_path = tmp_path / "transitions.json"
    transitions_path.write_text(
        json.dumps(
            [
                {
                    "command": "suggest",
                    "inputs": {"respondent_id": "r1", "reason": "Trust"},
                },
                {
                    "command": "suggest",
                    "inputs": {"respondent_id": "r2", "reason": "Price"},
                },
            ]
        )
    )
    runner = CliRunner()

    validated = runner.invoke(app, ["state", "validate", "--file", str(machine_path)])
    assert validated.exit_code == 0, validated.output
    assert json.loads(validated.output)["data"]["valid"] is True
    assert json.loads(validated.output)["data"]["locally_executable"] is True

    inspected = runner.invoke(app, ["state", "inspect", "--file", str(machine_path)])
    assert inspected.exit_code == 0, inspected.output
    inspected_data = json.loads(inspected.output)["data"]
    assert inspected_data["name"] == "ReasonDiscovery"
    assert inspected_data["commands"] == {
        "select": {
            "inputs": ["reason", "respondent_id"],
            "effects": 9,
            "timing": "after_answer",
            "requires_condition": True,
        },
        "suggest": {
            "inputs": ["reason", "respondent_id"],
            "effects": 8,
            "timing": "after_answer",
            "requires_condition": False,
        },
    }

    simulated = runner.invoke(
        app,
        [
            "state",
            "simulate",
            "--file",
            str(machine_path),
            "--transitions",
            str(transitions_path),
        ],
    )
    assert simulated.exit_code == 0, simulated.output
    simulation = json.loads(simulated.output)["data"]
    assert len(simulation["steps"]) == 2
    assert simulation["final_state"]["reasons"][-2:] == ["Trust", "Price"]


def test_results_state_returns_all_or_one_binding(tmp_path):
    results = Results(survey=Survey([]), data=[])
    results.shared_state = {
        "version": 1,
        "bindings": [
            {"state_id": "poll-a", "exit_snapshots": [{"state": {"votes": 2}}]},
            {"state_id": "poll-b", "exit_snapshots": [{"state": {"votes": 3}}]},
        ],
    }
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results.to_dict()))
    runner = CliRunner()

    all_bindings = runner.invoke(app, ["results", "state", "--file", str(results_path)])
    assert all_bindings.exit_code == 0, all_bindings.output
    assert json.loads(all_bindings.output)["data"]["binding_count"] == 2

    one_binding = runner.invoke(
        app,
        ["results", "state", "--file", str(results_path), "--binding", "1"],
    )
    assert one_binding.exit_code == 0, one_binding.output
    data = json.loads(one_binding.output)["data"]
    assert data["binding_index"] == 1
    assert data["binding"]["state_id"] == "poll-b"


def test_state_simulate_rejects_bad_transition_json(tmp_path):
    machine_path = tmp_path / "machine.json"
    machine_path.write_text(build_machine(patience=2).to_json())
    transitions_path = tmp_path / "transitions.json"
    transitions_path.write_text('[{"inputs": {}}]')

    result = CliRunner().invoke(
        app,
        [
            "state",
            "simulate",
            "--file",
            str(machine_path),
            "--transitions",
            str(transitions_path),
        ],
    )
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["code"] == "USAGE_ERROR"
