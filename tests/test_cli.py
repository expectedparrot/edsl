"""
Tests for the EDSL CLI (edsl/__main__.py).

Uses subprocess to invoke the CLI exactly as an agent would,
then parses stdout as JSON and checks structure.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


def run_cli(*args, stdin_data=None, expect_exit=0):
    """Run the EDSL CLI and return parsed JSON output."""
    cmd = [sys.executable, "-m", "edsl"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=stdin_data,
        timeout=60,
    )
    if expect_exit is not None:
        assert result.returncode == expect_exit, (
            f"Expected exit {expect_exit}, got {result.returncode}.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    if result.stdout.strip():
        return json.loads(result.stdout)
    return None


# ---------------------------------------------------------------------------
# Envelope structure
# ---------------------------------------------------------------------------

class TestEnvelope:
    """All commands should return the standard envelope."""

    def test_success_envelope_shape(self):
        out = run_cli("info")
        assert out["status"] == "ok"
        assert "data" in out
        assert "warnings" in out
        assert isinstance(out["warnings"], list)

    def test_error_envelope_shape(self):
        out = run_cli("validate", expect_exit=2)
        assert out["status"] == "error"
        assert "error" in out
        assert "code" in out["error"]
        assert "message" in out["error"]


# ---------------------------------------------------------------------------
# edsl info
# ---------------------------------------------------------------------------

class TestInfo:
    def test_info_returns_version(self):
        out = run_cli("info")
        data = out["data"]
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_info_returns_config(self):
        out = run_cli("info")
        data = out["data"]
        assert "config" in data
        assert isinstance(data["config"], dict)

    def test_info_returns_api_key_configured(self):
        out = run_cli("info")
        data = out["data"]
        assert "api_key_configured" in data
        assert isinstance(data["api_key_configured"], bool)


# ---------------------------------------------------------------------------
# edsl schema
# ---------------------------------------------------------------------------

class TestSchemaList:
    def test_returns_object_and_question_types(self):
        out = run_cli("schema", "list")
        data = out["data"]
        assert "object_types" in data
        assert "question_types" in data
        assert isinstance(data["object_types"], list)
        assert isinstance(data["question_types"], list)

    def test_core_objects_present(self):
        out = run_cli("schema", "list")
        names = [t["name"] for t in out["data"]["object_types"]]
        for expected in ["Agent", "AgentList", "Scenario", "ScenarioList", "Survey", "Model", "Jobs", "Results"]:
            assert expected in names, f"{expected} missing from schema list"

    def test_question_types_present(self):
        out = run_cli("schema", "list")
        names = [t["name"] for t in out["data"]["question_types"]]
        assert "free_text" in names
        assert "multiple_choice" in names

    def test_each_entry_has_description(self):
        out = run_cli("schema", "list")
        for entry in out["data"]["object_types"] + out["data"]["question_types"]:
            assert "name" in entry
            assert "description" in entry


class TestSchemaShow:
    def test_show_agent(self):
        out = run_cli("schema", "show", "--class", "Agent")
        data = out["data"]
        assert data["type"] == "Agent"
        assert "example" in data
        assert "edsl_class_name" in data["example"]

    def test_show_scenario_list(self):
        out = run_cli("schema", "show", "--class", "ScenarioList")
        data = out["data"]
        assert data["type"] == "ScenarioList"
        assert "scenarios" in data["example"]

    def test_show_question_type(self):
        out = run_cli("schema", "show", "--question_type", "multiple_choice")
        data = out["data"]
        assert "example" in data
        assert "question_options" in data["example"]

    def test_show_free_text(self):
        out = run_cli("schema", "show", "--question_type", "free_text")
        data = out["data"]
        assert data["example"]["question_type"] == "free_text"

    def test_unknown_type_errors(self):
        out = run_cli("schema", "show", "--class", "nonexistent", expect_exit=3)
        assert out["status"] == "error"
        assert out["error"]["code"] == "NOT_FOUND"

    def test_no_args_errors(self):
        out = run_cli("schema", "show", expect_exit=2)
        assert out["status"] == "error"


class TestSchemaError:
    def test_error_schema(self):
        out = run_cli("schema", "error")
        data = out["data"]
        assert "exit_codes" in data
        assert "known_error_codes" in data
        assert "envelope" in data


# ---------------------------------------------------------------------------
# edsl validate
# ---------------------------------------------------------------------------

class TestValidate:
    def test_valid_free_text(self):
        q = json.dumps({"type": "free_text", "question_name": "q0", "question_text": "Hello?"})
        out = run_cli("validate", "--json_data", q)
        assert out["data"]["valid"] is True
        assert out["data"]["object_type"] == "question"

    def test_auto_generated_name_warning(self):
        q = json.dumps({"type": "free_text", "question_text": "Hello?"})
        out = run_cli("validate", "--json_data", q)
        assert out["data"]["valid"] is True
        assert any(w["code"] == "AUTO_GENERATED_NAME" for w in out["warnings"])

    def test_invalid_type_errors(self):
        q = json.dumps({"type": "nonexistent", "question_text": "Hi"})
        out = run_cli("validate", "--json_data", q, expect_exit=5)
        assert out["status"] == "error"

    def test_validate_from_file(self):
        q = {"type": "free_text", "question_name": "q0", "question_text": "Hello?"}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(q, f)
            f.flush()
            out = run_cli("validate", "--file", f.name)
            assert out["data"]["valid"] is True

    def test_validate_from_stdin(self):
        q = json.dumps({"type": "free_text", "question_name": "q0", "question_text": "Hello?"})
        out = run_cli("validate", stdin_data=q)
        assert out["data"]["valid"] is True

    def test_no_input_errors(self):
        out = run_cli("validate", expect_exit=2)
        assert out["status"] == "error"
        assert out["error"]["code"] == "USAGE_ERROR"

    def test_invalid_json_errors(self):
        out = run_cli("validate", "--json_data", "{bad json", expect_exit=2)
        assert out["status"] == "error"
        assert out["error"]["code"] == "INVALID_JSON"

    def test_validate_lightweight_job(self):
        job = json.dumps({
            "questions": [
                {"type": "free_text", "question_name": "q0", "question_text": "Hi"}
            ]
        })
        out = run_cli("validate", "--json_data", job)
        assert out["data"]["valid"] is True
        assert out["data"]["object_type"] == "job_lightweight"

    def test_normalized_output(self):
        q = json.dumps({"type": "free_text", "question_text": "Hello?"})
        out = run_cli("validate", "--json_data", q)
        normalized = out["data"]["normalized"]
        assert normalized["question_name"] == "q0"
        assert normalized["type"] == "free_text"


# ---------------------------------------------------------------------------
# edsl models
# ---------------------------------------------------------------------------

class TestModels:
    def test_models_returns_list(self):
        out = run_cli("models")
        data = out["data"]
        assert "models" in data
        assert isinstance(data["models"], list)

    def test_model_entries_have_fields(self):
        out = run_cli("models")
        models = out["data"]["models"]
        if models:
            m = models[0]
            assert "model_name" in m
            assert "service_name" in m
            assert "configured" in m

    def test_models_sorted(self):
        out = run_cli("models")
        models = out["data"]["models"]
        keys = [(m["service_name"], m["model_name"]) for m in models]
        assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# edsl auth
# ---------------------------------------------------------------------------

class TestAuthStatus:
    def test_auth_status_returns_fields(self):
        out = run_cli("auth", "status")
        data = out["data"]
        assert "authenticated" in data
        assert "api_key_source" in data
        assert data["api_key_source"] in ("environment", "stored", "none")


# ---------------------------------------------------------------------------
# edsl results (using a fabricated Results file)
# ---------------------------------------------------------------------------

class TestResults:
    @pytest.fixture
    def results_file(self, tmp_path):
        """Create a minimal Results file for testing via direct construction."""
        from edsl import QuestionFreeText, Survey, Agent
        from edsl.language_models import Model
        from edsl.scenarios import Scenario
        from edsl.results import Results

        q = QuestionFreeText(question_name="q0", question_text="Say hi")
        survey = Survey(questions=[q])
        a = Agent(traits={"age": 30})

        # Build a Results object without running a survey
        from edsl.results.result import Result

        result = Result(
            agent=a,
            scenario=Scenario(),
            model=Model("test", service_name="test"),
            iteration=0,
            answer={"q0": "hello"},
        )
        results = Results(survey=survey, data=[result])

        path = tmp_path / "results.json"
        path.write_text(json.dumps(results.to_dict(), indent=2, default=str))
        return str(path)

    def test_columns(self, results_file):
        out = run_cli("results", "columns", "--file", results_file)
        cols = out["data"]["columns"]
        assert isinstance(cols, list)
        assert len(cols) > 0
        # Should have answer columns
        assert any(c.startswith("answer.") for c in cols)

    def test_select(self, results_file):
        out = run_cli("results", "select", "--file", results_file, "--column", "answer.q0")
        data = out["data"]["data"]
        assert isinstance(data, list)
        assert len(data) > 0

    def test_select_wildcard(self, results_file):
        out = run_cli("results", "select", "--file", results_file, "--column", "answer.*")
        data = out["data"]["data"]
        assert isinstance(data, list)
        assert len(data) > 0

    def test_select_with_limit(self, results_file):
        out = run_cli("results", "select", "--file", results_file, "--column", "answer.q0", "--limit", "1")
        data = out["data"]["data"]
        assert len(data) <= 1

    def test_file_not_found(self):
        out = run_cli("results", "columns", "--file", "/nonexistent/file.json", expect_exit=3)
        assert out["status"] == "error"
        assert out["error"]["code"] == "FILE_NOT_FOUND"


# ---------------------------------------------------------------------------
# edsl run (unit tests — no network)
# ---------------------------------------------------------------------------

class TestRunValidation:
    """Test run command input validation (no actual execution)."""

    def test_no_input_errors(self):
        out = run_cli("run", expect_exit=2)
        assert out["status"] == "error"
        assert out["error"]["code"] == "USAGE_ERROR"

    def test_conflicting_model_flags(self):
        # Both --model and --model_list
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"models": []}, f)
            f.flush()
            out = run_cli("run", "--question", "hi",
                          "--model", "gpt-4o", "--model_list", f.name,
                          expect_exit=2)
            assert out["error"]["code"] == "USAGE_ERROR"

    def test_multiple_input_sources_error(self):
        out = run_cli("run", "--question", "hi", "--json_data", '{"type":"free_text","question_text":"hi"}',
                      expect_exit=2)
        assert out["error"]["code"] == "USAGE_ERROR"

    def test_invalid_question_type_error(self):
        out = run_cli("run", "--question", "hi", "--type", "nonexistent_type",
                      expect_exit=2)
        assert out["error"]["code"] == "UNKNOWN_QUESTION_TYPE"


# ---------------------------------------------------------------------------
# edsl (no subcommand)
# ---------------------------------------------------------------------------

class TestDefault:
    def test_no_subcommand_lists_commands(self):
        out = run_cli()
        data = out["data"]
        assert "commands" in data
        assert "run" in data["commands"]
        assert "models" in data["commands"]
        assert "info" in data["commands"]
        assert "schema" in data["commands"]
        assert "validate" in data["commands"]
        assert "auth" in data["commands"]
        assert "results" in data["commands"]
        assert "coop" in data["commands"]
