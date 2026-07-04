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
from click.testing import CliRunner

import edsl.__main__ as cli_module


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
# edsl open
# ---------------------------------------------------------------------------

class TestOpen:
    def test_open_survey_json_generates_html_and_opens_browser(self, tmp_path, monkeypatch):
        from edsl.surveys import Survey

        survey_path = tmp_path / "survey.json"
        html_path = tmp_path / "survey.html"
        survey_path.write_text(json.dumps(Survey.example().to_dict()), encoding="utf-8")

        opened_urls = []
        monkeypatch.setattr(
            cli_module.webbrowser,
            "open",
            lambda url: opened_urls.append(url) or True,
        )

        result = CliRunner().invoke(
            cli_module.app,
            ["open", str(survey_path), "--output", str(html_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["object_type"] == "Survey"
        assert out["data"]["html_path"] == str(html_path)
        assert out["data"]["opened"] is True
        assert opened_urls == [html_path.resolve().as_uri()]
        assert "<html>" in html_path.read_text(encoding="utf-8")

    def test_open_survey_package_generates_html(self, tmp_path, monkeypatch):
        from edsl.surveys import Survey

        package_path = tmp_path / "survey.ep"
        html_path = tmp_path / "survey-package.html"
        Survey.example().git.save(package_path)

        opened_urls = []
        monkeypatch.setattr(
            cli_module.webbrowser,
            "open",
            lambda url: opened_urls.append(url) or True,
        )

        result = CliRunner().invoke(
            cli_module.app,
            ["open", str(package_path), "--output", str(html_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["object_type"] == "Survey"
        assert opened_urls == [html_path.resolve().as_uri()]
        html = html_path.read_text(encoding="utf-8")
        assert "<title>EDSL Survey</title>" in html
        assert "Expected Parrot" in html
        assert "survey-question-table" in html

    def test_open_jobs_package_generates_html(self, tmp_path, monkeypatch):
        from edsl import Agent, AgentList, Jobs, Model, ModelList, Scenario, ScenarioList
        from edsl.questions import QuestionFreeText
        from edsl.surveys import Survey

        job = Jobs(
            survey=Survey(
                [
                    QuestionFreeText(
                        question_name="name",
                        question_text="What is your name in {{ period }}?",
                    )
                ]
            ),
            agents=AgentList([Agent(traits={"status": "Joyful"})]),
            models=ModelList([Model("test", canned_response="SPAM!")]),
            scenarios=ScenarioList([Scenario({"period": "morning"})]),
        )
        package_path = tmp_path / "jobs.ep"
        html_path = tmp_path / "jobs.html"
        job.git.save(package_path)
        job.git._write_coop_info_and_commit(
            {
                "uuid": "jobs-uuid",
                "url": "https://www.expectedparrot.com/content/jobs-uuid",
                "alias_url": "https://www.expectedparrot.com/content/alice/shared-jobs",
                "alias": "shared-jobs",
                "description": "A shared jobs object",
                "owner": "alice",
            },
            message="Add Coop info",
        )

        opened_urls = []
        monkeypatch.setattr(
            cli_module.webbrowser,
            "open",
            lambda url: opened_urls.append(url) or True,
        )

        result = CliRunner().invoke(
            cli_module.app,
            ["open", str(package_path), "--output", str(html_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["object_type"] == "Jobs"
        assert opened_urls == [html_path.resolve().as_uri()]
        html = html_path.read_text(encoding="utf-8")
        assert "EDSL Jobs" in html
        assert "Expected Parrot" in html
        assert "Expected Parrot Server" in html
        assert "remote-meta" in html
        assert "copy-mini" in html
        assert "object alias" in html
        assert "owner" in html
        assert "jobs-uuid" in html
        assert "alice/shared-jobs" in html
        assert "alias URL" in html
        assert "https://www.expectedparrot.com/content/alice/shared-jobs" in html
        assert "shared-jobs" in html
        assert "A shared jobs object" in html
        assert "alice" in html
        assert '"href": "https://www.expectedparrot.com/content/jobs-uuid"' in html
        assert 'target="_blank"' in html
        assert "Jobs sections" in html
        assert "data-view-tab=\"survey\"" in html
        assert "data-view-tab=\"agents\"" in html
        assert "data-view-tab=\"scenarios\"" in html
        assert "data-view-tab=\"models\"" in html
        assert "What is your name in {{ period }}?" in html

    def test_open_results_package_generates_html(self, tmp_path, monkeypatch):
        from edsl.results import Results

        package_path = tmp_path / "results.ep"
        html_path = tmp_path / "results.html"
        Results.example().git.save(package_path)

        opened_urls = []
        monkeypatch.setattr(
            cli_module.webbrowser,
            "open",
            lambda url: opened_urls.append(url) or True,
        )

        result = CliRunner().invoke(
            cli_module.app,
            ["open", str(package_path), "--output", str(html_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["object_type"] == "Results"
        assert opened_urls == [html_path.resolve().as_uri()]
        html = html_path.read_text(encoding="utf-8")
        assert "<title>EDSL Results</title>" in html
        assert "Expected Parrot" in html
        assert "collection-table" in html
        assert "<table" in html

    def test_open_scenario_list_package_generates_html(self, tmp_path, monkeypatch):
        from edsl import ScenarioList

        package_path = tmp_path / "scenario_list.ep"
        html_path = tmp_path / "scenario-list.html"
        ScenarioList.example().git.save(package_path)

        opened_urls = []
        monkeypatch.setattr(
            cli_module.webbrowser,
            "open",
            lambda url: opened_urls.append(url) or True,
        )

        result = CliRunner().invoke(
            cli_module.app,
            ["open", str(package_path), "--output", str(html_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["object_type"] == "ScenarioList"
        assert opened_urls == [html_path.resolve().as_uri()]
        html = html_path.read_text(encoding="utf-8")
        assert "<title>EDSL ScenarioList</title>" in html
        assert "Expected Parrot" in html
        assert "scenario-table" in html
        assert "<table" in html

    def test_open_model_list_package_generates_html(self, tmp_path, monkeypatch):
        from edsl import ModelList

        package_path = tmp_path / "models.ep"
        html_path = tmp_path / "models.html"
        ModelList.example().git.save(package_path)

        opened_urls = []
        monkeypatch.setattr(
            cli_module.webbrowser,
            "open",
            lambda url: opened_urls.append(url) or True,
        )

        result = CliRunner().invoke(
            cli_module.app,
            ["open", str(package_path), "--output", str(html_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["object_type"] == "ModelList"
        assert opened_urls == [html_path.resolve().as_uri()]
        html = html_path.read_text(encoding="utf-8")
        assert "<title>EDSL ModelList</title>" in html
        assert "Expected Parrot" in html
        assert "collection-table" in html
        assert "<table" in html


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

    def test_run_jobs_package_saves_results_package(self, tmp_path):
        from edsl import Agent, AgentList, Jobs, Model, ModelList, Scenario, ScenarioList
        from edsl.questions import QuestionFreeText
        from edsl.results import Results
        from edsl.surveys import Survey

        job = Jobs(
            survey=Survey(
                [
                    QuestionFreeText(
                        question_name="name",
                        question_text="What is your name in {{ period }}?",
                    )
                ]
            ),
            agents=AgentList([Agent(traits={"status": "Joyful"})]),
            models=ModelList([Model("test", canned_response="SPAM!")]),
            scenarios=ScenarioList([Scenario({"period": "morning"})]),
        )
        jobs_path = tmp_path / "jobs.ep"
        results_path = tmp_path / "results.ep"
        job.git.save(jobs_path)

        result = CliRunner().invoke(
            cli_module.app,
            ["run", str(jobs_path), "-o", str(results_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["meta"]["input_mode"] == "path"
        assert out["data"]["meta"]["saved"]["format"] == "ep"
        assert out["data"]["meta"]["saved"]["object_type"] == "Results"
        assert results_path.exists()
        loaded = Results.git.load(results_path)
        assert len(loaded) == 1


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
        assert "clone" in data["commands"]
        assert "push" in data["commands"]
        assert "pull" in data["commands"]


# ---------------------------------------------------------------------------
# edsl clone
# ---------------------------------------------------------------------------

class TestClone:
    def test_clone_owner_alias_saves_git_package_with_coop_info(
        self, tmp_path, monkeypatch
    ):
        from edsl.surveys import Survey

        class FakeCoop:
            def get(self, identifier):
                assert identifier.endswith("/content/alice/shared-survey")
                return Survey.example()

            def get_metadata(self, identifier):
                assert identifier.endswith("/content/alice/shared-survey")
                return {
                    "uuid": "survey-uuid",
                    "object_type": "survey",
                    "alias": "shared-survey",
                    "owner_username": "alice",
                    "description": "Shared survey",
                    "visibility": "public",
                    "url": "https://www.expectedparrot.com/content/survey-uuid",
                    "alias_url": "https://www.expectedparrot.com/content/alice/shared-survey",
                }

        import edsl.coop as coop_module

        monkeypatch.setattr(coop_module, "Coop", FakeCoop)
        package_path = tmp_path / "cloned-survey.ep"

        result = CliRunner().invoke(
            cli_module.app,
            ["clone", "alice/shared-survey", "--path", str(package_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["object_type"] == "Survey"
        assert out["data"]["path"] == str(package_path)
        assert out["data"]["coop_info"]["uuid"] == "survey-uuid"
        assert out["data"]["coop_info"]["alias"] == "shared-survey"
        assert out["data"]["coop_info"]["owner_username"] == "alice"
        assert out["data"]["commit"]
        assert package_path.exists()

        html = Survey.git.open(package_path).html()
        assert "Expected Parrot Server" in html
        assert "alice/shared-survey" in html
        assert "survey-uuid" in html

    def test_clone_default_path_uses_alias(self, tmp_path, monkeypatch):
        from edsl.surveys import Survey

        class FakeCoop:
            def get(self, identifier):
                return Survey.example()

            def get_metadata(self, identifier):
                return {
                    "uuid": "survey-uuid",
                    "alias": "default-survey",
                    "owner_username": "alice",
                    "url": "https://www.expectedparrot.com/content/survey-uuid",
                    "alias_url": "https://www.expectedparrot.com/content/alice/default-survey",
                }

        import edsl.coop as coop_module

        monkeypatch.setattr(coop_module, "Coop", FakeCoop)
        monkeypatch.chdir(tmp_path)

        result = CliRunner().invoke(cli_module.app, ["clone", "alice/default-survey"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["path"] == "default-survey.ep"
        assert (tmp_path / "default-survey.ep").exists()


# ---------------------------------------------------------------------------
# edsl push
# ---------------------------------------------------------------------------

class TestPush:
    def test_push_new_package_creates_coop_object(self, tmp_path, monkeypatch):
        from edsl.surveys import Survey

        package_path = tmp_path / "survey.ep"
        Survey.example().git.save(package_path)
        push_calls = []

        def fake_push(
            self,
            description=None,
            alias=None,
            visibility=None,
            expected_parrot_url=None,
            force=False,
        ):
            push_calls.append(
                {
                    "description": description,
                    "alias": alias,
                    "visibility": visibility,
                    "force": force,
                }
            )
            return {
                "uuid": "created-uuid",
                "url": "https://www.expectedparrot.com/content/created-uuid",
                "alias": alias,
                "description": description,
                "visibility": visibility,
            }

        class FakeCoop:
            def __init__(self, url=None):
                pass

            def get_metadata(self, identifier):
                return {
                    "uuid": "created-uuid",
                    "url": "https://www.expectedparrot.com/content/created-uuid",
                    "alias_url": "https://www.expectedparrot.com/content/alice/created-alias",
                    "alias": "created-alias",
                    "owner_username": "alice",
                    "description": "Created description",
                    "visibility": "public",
                }

        monkeypatch.setattr(Survey, "push", fake_push)
        import edsl.coop as coop_module

        monkeypatch.setattr(coop_module, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "push",
                str(package_path),
                "--alias",
                "created-alias",
                "--description",
                "Created description",
                "--visibility",
                "public",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["operation"] == "push"
        assert out["data"]["object_type"] == "Survey"
        assert out["data"]["coop_info"]["uuid"] == "created-uuid"
        assert out["data"]["coop_info"]["alias"] == "created-alias"
        assert push_calls == [
            {
                "description": "Created description",
                "alias": "created-alias",
                "visibility": "public",
                "force": False,
            }
        ]
        html = Survey.git.open(package_path).html()
        assert "Expected Parrot Server" in html
        assert "created-uuid" in html

    def test_push_package_with_coop_info_patches_existing_object(
        self, tmp_path, monkeypatch
    ):
        from edsl.surveys import Survey

        package_path = tmp_path / "survey.ep"
        survey = Survey.example()
        survey.git.save(package_path)
        survey.git._write_coop_info_and_commit(
            {
                "uuid": "existing-uuid",
                "url": "https://www.expectedparrot.com/content/existing-uuid",
                "alias": "old-alias",
            },
            message="Store existing Coop info",
        )
        patch_calls = []

        class FakeCoop:
            def __init__(self, url=None):
                pass

            def patch(self, url_or_uuid, description=None, alias=None, value=None, visibility=None):
                patch_calls.append(
                    {
                        "url_or_uuid": url_or_uuid,
                        "description": description,
                        "alias": alias,
                        "object_type": type(value).__name__,
                        "visibility": visibility,
                    }
                )
                return {
                    "uuid": "existing-uuid",
                    "url": "https://www.expectedparrot.com/content/existing-uuid",
                    "alias": alias,
                    "description": description,
                    "visibility": visibility,
                }

            def get_metadata(self, identifier):
                return {
                    "uuid": "existing-uuid",
                    "url": "https://www.expectedparrot.com/content/existing-uuid",
                    "alias_url": "https://www.expectedparrot.com/content/alice/new-alias",
                    "alias": "new-alias",
                    "owner_username": "alice",
                    "description": "Patched description",
                    "visibility": "unlisted",
                }

        import edsl.coop as coop_module

        monkeypatch.setattr(coop_module, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "push",
                str(package_path),
                "--alias",
                "new-alias",
                "--description",
                "Patched description",
                "--visibility",
                "unlisted",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["operation"] == "patch"
        assert out["data"]["coop_info"]["alias"] == "new-alias"
        assert patch_calls == [
            {
                "url_or_uuid": "existing-uuid",
                "description": "Patched description",
                "alias": "new-alias",
                "object_type": "Survey",
                "visibility": "unlisted",
            }
        ]

    def test_push_rejects_non_package_json(self, tmp_path):
        from edsl.surveys import Survey

        json_path = tmp_path / "survey.json"
        json_path.write_text(json.dumps(Survey.example().to_dict()), encoding="utf-8")

        result = CliRunner().invoke(cli_module.app, ["push", str(json_path)])

        assert result.exit_code == cli_module.EXIT_USAGE
        out = json.loads(result.output)
        assert out["status"] == "error"
        assert out["error"]["code"] == "USAGE_ERROR"


# ---------------------------------------------------------------------------
# edsl pull
# ---------------------------------------------------------------------------

class TestPull:
    def test_pull_package_updates_from_coop(self, tmp_path, monkeypatch):
        from edsl.agents import Agent, AgentList

        package_path = tmp_path / "agents.agent_list.ep"
        local = AgentList([Agent(name="local", traits={"age": 22})])
        local.git.save(package_path)
        local.git._write_coop_info_and_commit(
            {"uuid": "agent-list-uuid"},
            message="Store Coop info",
        )
        remote = AgentList([Agent(name="remote", traits={"age": 30})])

        class FakeCoop:
            def __init__(self, url=None):
                pass

            def get_metadata(self, identifier):
                return {
                    "uuid": "agent-list-uuid",
                    "url": "https://www.expectedparrot.com/content/agent-list-uuid",
                    "alias_url": "https://www.expectedparrot.com/content/alice/remote-agents",
                    "alias": "remote-agents",
                    "owner_username": "alice",
                    "last_updated_ts": "2026-07-04T12:00:00+00:00",
                }

        monkeypatch.setattr(
            AgentList,
            "pull",
            classmethod(lambda cls, url_or_uuid, expected_parrot_url=None: remote),
        )
        import edsl.coop as coop_module

        monkeypatch.setattr(coop_module, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["pull", str(package_path)])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["operation"] in {"updated", "unchanged"}
        assert out["data"]["object_type"] == "AgentList"
        assert out["data"]["coop_info"]["alias"] == "remote-agents"

    def test_pull_skips_fetch_when_remote_metadata_not_newer(self, tmp_path, monkeypatch):
        from edsl.agents import Agent, AgentList

        package_path = tmp_path / "agents.agent_list.ep"
        local = AgentList([Agent(name="local", traits={"age": 22})])
        local.git.save(package_path)
        local.git._write_coop_info_and_commit(
            {
                "uuid": "agent-list-uuid",
                "last_updated_ts": "2026-07-04T12:00:00+00:00",
            },
            message="Store Coop info",
        )

        class FakeCoop:
            def __init__(self, url=None):
                pass

            def get_metadata(self, identifier):
                return {
                    "uuid": "agent-list-uuid",
                    "url": "https://www.expectedparrot.com/content/agent-list-uuid",
                    "last_updated_ts": "2026-07-04T12:00:00+00:00",
                }

        def fail_pull(cls, url_or_uuid, expected_parrot_url=None):
            raise AssertionError("pull should not fetch object when metadata is current")

        monkeypatch.setattr(AgentList, "pull", classmethod(fail_pull))
        import edsl.coop as coop_module

        monkeypatch.setattr(coop_module, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["pull", str(package_path)])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["operation"] == "unchanged"

    def test_pull_package_without_coop_info_errors(self, tmp_path):
        from edsl.surveys import Survey

        package_path = tmp_path / "survey.ep"
        Survey.example().git.save(package_path)

        result = CliRunner().invoke(cli_module.app, ["pull", str(package_path)])

        assert result.exit_code == cli_module.EXIT_VALIDATION
        out = json.loads(result.output)
        assert out["status"] == "error"
        assert out["error"]["code"] == "NO_COOP_INFO"
