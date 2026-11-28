import json
from pathlib import Path

from click.testing import CliRunner

import edsl.__main__ as cli_module
import edsl.cli_commands.run_manifest as command


def _manifest(tmp_path: Path, **run):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"runs": [{"job_path": "jobs.ep", "result_path": "results.ep", **run}]}))
    return path


def test_run_manifest_verifies_complete_result(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, prediction_count=200)
    monkeypatch.setattr(command, "_result_count", lambda path: 200)
    result = CliRunner().invoke(cli_module.app, ["run-manifest", str(manifest), "--result-base", str(tmp_path)])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["executed_count"] == 0
    assert payload["data"]["verification"] == "result_row_count"
    assert payload["data"]["runs"][0]["status"] == "complete"


def test_run_manifest_requires_explicit_execute(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, scenario_count=10, model_count=2)
    monkeypatch.setattr(command, "_result_count", lambda path: 3)
    result = CliRunner().invoke(cli_module.app, ["run-manifest", str(manifest), "--result-base", str(tmp_path)])
    assert result.exit_code == 6
    payload = json.loads(result.output)
    assert payload["error"]["code"] == "INCOMPLETE_RUNS"
    assert payload["error"]["details"][0]["expected_count"] == 20


def test_run_manifest_executes_incomplete_runs(tmp_path, monkeypatch):
    manifest = _manifest(tmp_path, prediction_count=20)
    monkeypatch.setattr(command, "_result_count", lambda path: 0)
    monkeypatch.setattr(command, "_execute_run", lambda run, base, timeout: {
        "job_path": "jobs.ep", "result_path": str(base / "results.ep"), "expected_count": 20,
        "actual_count": 20, "status": "complete", "executed": True,
    })
    result = CliRunner().invoke(cli_module.app, ["run-manifest", str(manifest), "--result-base", str(tmp_path), "--execute"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["data"]["executed_count"] == 1


def test_run_manifest_requires_a_results_package_even_when_length_matches(tmp_path):
    from edsl import Scenario, ScenarioList

    manifest = _manifest(tmp_path, prediction_count=1)
    ScenarioList([Scenario({"id": "s1"})]).git.save(tmp_path / "results.ep", sync_coop=False)
    result = CliRunner().invoke(cli_module.app, ["run-manifest", str(manifest), "--result-base", str(tmp_path)])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["code"] == "UNSUPPORTED_OBJECT"
