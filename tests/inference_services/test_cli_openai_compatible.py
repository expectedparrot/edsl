"""CLI coverage for generic OpenAI-compatible model support."""

import json
from types import SimpleNamespace

from click.testing import CliRunner

import edsl.__main__ as cli_module


def test_models_create_persists_connection_without_secret(tmp_path):
    from edsl.language_models import ModelList

    output_path = tmp_path / "local-models.ep"
    result = CliRunner().invoke(
        cli_module.app,
        [
            "models",
            "create",
            "--service",
            "openai_compatible",
            "--model",
            "local-model",
            "--base-url",
            "http://127.0.0.1:8080/v1",
            "--api-key-env",
            "LOCAL_MODEL_API_KEY",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["data"]["models"][0]["connection"] == {
        "base_url": "http://127.0.0.1:8080/v1",
        "api_key_env": "LOCAL_MODEL_API_KEY",
    }
    loaded = ModelList.git.load(output_path)[0]
    assert loaded.base_url == "http://127.0.0.1:8080/v1"
    assert loaded.api_key_env == "LOCAL_MODEL_API_KEY"
    assert "base_url" not in loaded.parameters


def test_run_builds_one_off_openai_compatible_model(tmp_path, monkeypatch):
    from edsl.config import CONFIG
    from edsl.jobs import Jobs
    from edsl.results import Results

    captured = {}
    original_api_timeout = CONFIG.EDSL_API_TIMEOUT

    def fake_run(self, **kwargs):
        model = self.models[0]
        captured.update(
            service=model._inference_service_,
            base_url=model.base_url,
            kwargs=kwargs,
            api_timeout=CONFIG.EDSL_API_TIMEOUT,
        )
        return Results(survey=self.survey, data=[])

    monkeypatch.setattr(Jobs, "run", fake_run)
    result = CliRunner().invoke(
        cli_module.app,
        [
            "run",
            "--question",
            "hi",
            "--model",
            "local-model",
            "--service",
            "openai_compatible",
            "--base-url",
            "http://127.0.0.1:8080/v1",
            "--local",
            "--max-concurrency",
            "3",
            "--api-timeout",
            "120",
            "--output",
            str(tmp_path / "results.json"),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["service"] == "openai_compatible"
    assert captured["base_url"] == "http://127.0.0.1:8080/v1"
    assert captured["kwargs"]["disable_remote_inference"] is True
    assert captured["kwargs"]["max_concurrency"] == 3
    assert captured["api_timeout"] == "120.0"
    assert CONFIG.EDSL_API_TIMEOUT == original_api_timeout
    assert json.loads(result.output)["data"]["meta"]["run_status"] == "complete"


def test_run_restores_api_timeout_after_failure(tmp_path, monkeypatch):
    from edsl.config import CONFIG
    from edsl.jobs import Jobs

    original_api_timeout = CONFIG.EDSL_API_TIMEOUT

    def fail_run(self, **kwargs):
        assert CONFIG.EDSL_API_TIMEOUT == "45.0"
        raise RuntimeError("expected failure")

    monkeypatch.setattr(Jobs, "run", fail_run)
    result = CliRunner().invoke(
        cli_module.app,
        [
            "run",
            "--question",
            "hi",
            "--api-timeout",
            "45",
            "--output",
            str(tmp_path / "results.json"),
        ],
    )

    assert result.exit_code == 1
    assert CONFIG.EDSL_API_TIMEOUT == original_api_timeout


def test_jobs_configures_active_runner_concurrency(monkeypatch):
    from edsl.jobs import Jobs
    from edsl.runner import runner as runner_module

    captured = {}
    expected_results = object()

    class FakeHandle:
        def results(self, **kwargs):
            return expected_results

    class FakeRunner:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def submit(self, *args, **kwargs):
            return FakeHandle()

    monkeypatch.setattr(runner_module, "Runner", FakeRunner)
    job = Jobs.example()
    job.run_config.parameters.max_concurrency = 7

    assert job._execute_with_runner() is expected_results
    assert captured["max_workers"] == 7


def test_run_reports_partial_results(tmp_path, monkeypatch):
    from edsl.jobs import Jobs
    from edsl.results import Results
    import edsl.cli_commands.run as run_command

    # The command only needs a sized result collection here; avoid invoking an
    # example model run as part of this CLI metadata test.
    fake_results = Results(data=[object()])
    fake_results.task_history = SimpleNamespace(
        unfixed_exceptions=[{"q0": "failed"}]
    )
    monkeypatch.setattr(Jobs, "run", lambda self, **kwargs: fake_results)
    monkeypatch.setattr(
        run_command,
        "save_results",
        lambda results, path: {
            "path": str(path),
            "format": "json",
            "object_type": "Results",
        },
    )

    result = CliRunner().invoke(
        cli_module.app,
        ["run", "--question", "hi", "--output", str(tmp_path / "results.json")],
    )

    assert result.exit_code == 0, result.output
    out = json.loads(result.output)
    assert out["data"]["meta"]["run_status"] == "partial"
    assert out["data"]["meta"]["failed_interview_count"] == 1
    assert out["warnings"][-1]["code"] == "PARTIAL_RESULTS"
