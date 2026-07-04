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

    def test_cli_output_not_polluted_by_logging_warning(self):
        result = subprocess.run(
            [sys.executable, "-m", "edsl", "info"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, result.stderr
        assert "Could not set up file logging" not in result.stdout
        assert "Could not set up file logging" not in result.stderr
        out = json.loads(result.stdout)
        assert out["status"] == "ok"

    def test_info_redacts_api_key(self, monkeypatch):
        monkeypatch.setenv("EXPECTED_PARROT_API_KEY", "ep_test_secret")

        result = CliRunner().invoke(cli_module.app, ["info"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["api_key_configured"] is True
        assert out["data"]["config"]["EXPECTED_PARROT_API_KEY"] == "***"
        assert "ep_test_secret" not in result.output


# ---------------------------------------------------------------------------
# CLI smoke flows with fake Coop
# ---------------------------------------------------------------------------

class TestCliSmokeFlows:
    def test_remote_object_and_jobs_flow_with_fake_coop(self, tmp_path, monkeypatch):
        from edsl.results import Results
        import edsl.coop

        error_path = tmp_path / "error.md"
        results_path = tmp_path / "results.ep"

        class FakeSearchResult(list):
            current_page = 1
            total_pages = 1
            page_size = 10
            total_count = 1

        class FakeCoop:
            def fetch_working_models(self):
                return [
                    {
                        "service": "openai",
                        "model": "gpt-4o",
                        "works_with_text": True,
                        "works_with_images": True,
                        "usd_per_1M_input_tokens": 2.5,
                        "usd_per_1M_output_tokens": 10.0,
                    }
                ]

            def list(self, **kwargs):
                return FakeSearchResult(
                    [
                        {
                            "uuid": "survey-uuid",
                            "object_type": "survey",
                            "alias": "alice/survey",
                            "visibility": "public",
                        }
                    ]
                )

            def get_metadata(self, identifier):
                assert identifier.endswith("/content/alice/survey")
                return {"uuid": "survey-uuid", "alias": "survey"}

            def get_object_shared_users(self, identifier):
                assert identifier.endswith("/content/alice/survey")
                return {"shared_with": [], "unregistered_shared_with": []}

            def share_object(self, identifier, username_or_email):
                assert identifier.endswith("/content/alice/survey")
                return {"message": "shared", "email": username_or_email}

            def remote_inference_list(self, **kwargs):
                return [{"uuid": "job-uuid", "status": "completed", "results_uuid": "results-uuid"}]

            def new_remote_inference_get(
                self, job_uuid=None, results_uuid=None, include_json_string=False
            ):
                assert job_uuid == "job-uuid"
                return {
                    "job_uuid": job_uuid,
                    "results_uuid": "results-uuid",
                    "status": "completed",
                }

            def pull(self, identifier, expected_object_type=None):
                assert identifier == "results-uuid"
                assert expected_object_type == "results"
                return Results.example()

            def get_error_report_markdown(self, job_uuid):
                assert job_uuid == "job-uuid"
                return "# Error"

            def remote_inference_results_manifest(self, job_uuid, page_size=100):
                assert job_uuid == "job-uuid"
                return {"job_id": job_uuid, "page_count": 1, "page_size": page_size}

            def remote_inference_results_page(self, job_uuid, page=0, page_size=100):
                assert job_uuid == "job-uuid"
                return {"job_id": job_uuid, "page": page, "interviews": []}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)
        runner = CliRunner()

        commands = [
            ["models", "--vision"],
            ["search", "--query", "survey"],
            ["metadata", "alice/survey"],
            ["shared", "alice/survey"],
            ["share", "alice/survey", "--user", "bob@example.com"],
            ["jobs", "list"],
            ["jobs", "status", "job-uuid"],
            ["jobs", "results", "job-uuid", "--output", str(results_path)],
            ["jobs", "errors", "job-uuid", "--output", str(error_path)],
            ["jobs", "manifest", "job-uuid"],
            ["jobs", "page", "job-uuid"],
        ]

        for command in commands:
            result = runner.invoke(cli_module.app, command)
            assert result.exit_code == 0, f"{command}: {result.output}"
            out = json.loads(result.output)
            assert out["status"] == "ok", command

        assert results_path.exists()
        assert error_path.read_text(encoding="utf-8") == "# Error"


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

    def test_validate_accepts_json_alias(self):
        q = json.dumps({"type": "free_text", "question_name": "q0", "question_text": "Hello?"})
        out = run_cli("validate", "--json", q)
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
    @pytest.fixture
    def fake_model_catalog(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def fetch_working_models(self):
                return [
                    {
                        "service": "openai",
                        "model": "gpt-4o",
                        "works_with_text": True,
                        "works_with_images": True,
                        "usd_per_1M_input_tokens": 2.5,
                        "usd_per_1M_output_tokens": 10.0,
                    },
                    {
                        "service": "openai",
                        "model": "gpt-text-only",
                        "works_with_text": True,
                        "works_with_images": False,
                        "usd_per_1M_input_tokens": 1.0,
                        "usd_per_1M_output_tokens": 2.0,
                    },
                    {
                        "service": "anthropic",
                        "model": "claude-3-5-sonnet",
                        "works_with_text": True,
                        "works_with_images": True,
                        "usd_per_1M_input_tokens": 3.0,
                        "usd_per_1M_output_tokens": 15.0,
                    },
                ]

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

    def test_models_returns_list(self, fake_model_catalog):
        result = CliRunner().invoke(cli_module.app, ["models"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        data = out["data"]
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) == 3
        assert data["source"] == "expected_parrot"
        assert data["count"] == 3
        assert data["filters"] == {
            "service": None,
            "search": None,
            "text": None,
            "vision": None,
        }

    def test_model_entries_have_fields(self, fake_model_catalog):
        result = CliRunner().invoke(cli_module.app, ["models"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        models = out["data"]["models"]
        if models:
            m = models[0]
            assert "model_name" in m
            assert "service_name" in m
            assert "configured" in m
            assert "works_with_text" in m
            assert "works_with_images" in m
            assert "usd_per_1M_input_tokens" in m
            assert "usd_per_1M_output_tokens" in m

    def test_models_sorted(self, fake_model_catalog):
        result = CliRunner().invoke(cli_module.app, ["models"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        models = out["data"]["models"]
        keys = [(m["service_name"], m["model_name"]) for m in models]
        assert keys == sorted(keys)

    def test_models_filters_remote_catalog(self, fake_model_catalog):
        result = CliRunner().invoke(
            cli_module.app,
            ["models", "--service", "openai", "--search", "4o"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["source"] == "expected_parrot"
        assert out["data"]["count"] == 1
        assert out["data"]["filters"] == {
            "service": "openai",
            "search": "4o",
            "text": None,
            "vision": None,
        }
        assert out["data"]["models"] == [
            {
                "model_name": "gpt-4o",
                "service_name": "openai",
                "configured": False,
                "works_with_text": True,
                "works_with_images": True,
                "usd_per_1M_input_tokens": 2.5,
                "usd_per_1M_output_tokens": 10.0,
            }
        ]

    def test_models_filters_by_capability(self, fake_model_catalog):
        result = CliRunner().invoke(
            cli_module.app,
            ["models", "--service", "openai", "--vision"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["filters"]["vision"] is True
        assert [m["model_name"] for m in out["data"]["models"]] == ["gpt-4o"]

        result = CliRunner().invoke(
            cli_module.app,
            ["models", "--service", "openai", "--no-vision"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert [m["model_name"] for m in out["data"]["models"]] == ["gpt-text-only"]


# ---------------------------------------------------------------------------
# edsl search
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_lists_shared_objects(self, monkeypatch):
        import edsl.coop

        class FakeSearchResult(list):
            current_page = 2
            total_pages = 4
            page_size = 5
            total_count = 19

        class FakeCoop:
            def list(self, **kwargs):
                assert kwargs == {
                    "page": 2,
                    "page_size": 5,
                    "community": True,
                    "search_query": "economics",
                    "object_type": "survey",
                    "visibility": "public",
                }
                return FakeSearchResult([
                    {
                        "uuid": "survey-uuid",
                        "object_type": "survey",
                        "alias": "alice/economics",
                        "description": "Economics survey",
                        "visibility": "public",
                    }
                ])

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "search",
                "--query",
                "economics",
                "--type",
                "survey",
                "--visibility",
                "public",
                "--community",
                "--page",
                "2",
                "--page_size",
                "5",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["warnings"] == []
        assert out["data"]["page"] == 2
        assert out["data"]["page_size"] == 5
        assert out["data"]["returned_count"] == 1
        assert out["data"]["current_page"] == 2
        assert out["data"]["total_pages"] == 4
        assert out["data"]["total_count"] == 19
        assert out["data"]["query"] == "economics"
        assert out["data"]["type"] == "survey"
        assert out["data"]["visibility"] == "public"
        assert out["data"]["community"] is True
        assert out["data"]["objects"] == [
            {
                "uuid": "survey-uuid",
                "object_type": "survey",
                "alias": "alice/economics",
                "description": "Economics survey",
                "visibility": "public",
            }
        ]


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


class TestAuthBalance:
    def test_auth_balance_returns_expected_parrot_balance(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def __init__(self, api_key=None):
                self.api_key = api_key

            def get_balance(self):
                assert self.api_key == "ep_test_key"
                return {"credits": 123.45, "usage_history": []}

        monkeypatch.setenv("EXPECTED_PARROT_API_KEY", "ep_test_key")
        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["auth", "balance"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["credits"] == 123.45
        assert out["data"]["usage_history"] == []

    def test_top_level_balance_alias_returns_expected_parrot_balance(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def __init__(self, api_key=None):
                self.api_key = api_key

            def get_balance(self):
                assert self.api_key == "ep_test_key"
                return {"credits": 99}

        monkeypatch.setenv("EXPECTED_PARROT_API_KEY", "ep_test_key")
        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["balance"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["status"] == "ok"
        assert out["data"]["credits"] == 99

    def test_auth_balance_requires_api_key(self, monkeypatch):
        monkeypatch.delenv("EXPECTED_PARROT_API_KEY", raising=False)

        result = CliRunner().invoke(cli_module.app, ["auth", "balance"])

        assert result.exit_code == cli_module.EXIT_AUTH
        out = json.loads(result.output)
        assert out["status"] == "error"
        assert out["error"]["code"] == "AUTH_REQUIRED"


# ---------------------------------------------------------------------------
# edsl remote object/account commands
# ---------------------------------------------------------------------------

class TestRemoteObjectCommands:
    def test_profile_returns_expected_parrot_profile(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def get_profile(self):
                return {"username": "alice", "email": "alice@example.com"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["profile"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["username"] == "alice"

    def test_metadata_resolves_identifier(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def get_metadata(self, identifier):
                assert identifier == "object-uuid"
                return {"uuid": "object-uuid", "visibility": "public"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["metadata", "object-uuid"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["uuid"] == "object-uuid"

    def test_update_metadata_requires_a_field(self):
        result = CliRunner().invoke(cli_module.app, ["update-metadata", "object-uuid"])

        assert result.exit_code == cli_module.EXIT_USAGE
        out = json.loads(result.output)
        assert out["error"]["code"] == "USAGE_ERROR"

    def test_update_metadata_patches_remote_metadata(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def patch_metadata(self, identifier, description=None, alias=None, visibility=None):
                assert identifier == "object-uuid"
                assert description == "New description"
                assert alias == "new-alias"
                assert visibility == "unlisted"
                return {"uuid": identifier, "alias": alias, "visibility": visibility}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "update-metadata",
                "object-uuid",
                "--description",
                "New description",
                "--alias",
                "new-alias",
                "--visibility",
                "unlisted",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["alias"] == "new-alias"

    def test_share_and_unshare(self, monkeypatch):
        import edsl.coop

        calls = []

        class FakeCoop:
            def share_object(self, identifier, username_or_email):
                calls.append(("share", identifier, username_or_email))
                return {"message": "shared"}

            def unshare_object(self, identifier, username_or_email):
                calls.append(("unshare", identifier, username_or_email))
                return {"message": "unshared"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        share_result = CliRunner().invoke(
            cli_module.app,
            ["share", "object-uuid", "--user", "bob@example.com"],
        )
        unshare_result = CliRunner().invoke(
            cli_module.app,
            ["unshare", "object-uuid", "--user", "bob@example.com"],
        )

        assert share_result.exit_code == 0, share_result.output
        assert unshare_result.exit_code == 0, unshare_result.output
        assert calls == [
            ("share", "object-uuid", "bob@example.com"),
            ("unshare", "object-uuid", "bob@example.com"),
        ]

    def test_shared_lists_users(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def get_object_shared_users(self, identifier):
                assert identifier == "object-uuid"
                return {
                    "shared_with": [{"username": "bob", "email": "bob@example.com"}],
                    "unregistered_shared_with": [],
                }

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["shared", "object-uuid"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["shared_with"][0]["username"] == "bob"

    def test_delete_requires_confirmation(self):
        result = CliRunner().invoke(cli_module.app, ["delete", "object-uuid"])

        assert result.exit_code == cli_module.EXIT_USAGE
        out = json.loads(result.output)
        assert out["error"]["code"] == "CONFIRMATION_REQUIRED"

    def test_delete_confirmed(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def delete(self, identifier):
                assert identifier == "object-uuid"
                return {"deleted": True}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["delete", "object-uuid", "--yes"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["deleted"] is True

    def test_settings_returns_remote_diagnostics(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            @property
            def edsl_settings(self):
                return {"remote_inference": True}

            def fetch_rate_limit_config_vars(self):
                return {"OPENAI_TPM": "1000"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["settings"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["edsl_settings"] == {"remote_inference": True}
        assert out["data"]["rate_limit_config"] == {"OPENAI_TPM": "1000"}


# ---------------------------------------------------------------------------
# edsl jobs
# ---------------------------------------------------------------------------

class TestJobsCli:
    def test_jobs_group_lists_commands(self):
        result = CliRunner().invoke(cli_module.app, ["jobs"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["commands"] == [
            "list",
            "status",
            "results",
            "errors",
            "manifest",
            "page",
            "cancel",
            "cost",
        ]

    def test_jobs_list(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def remote_inference_list(
                self, status=None, search_query=None, page=1, page_size=10, sort_ascending=False
            ):
                assert status == ["running"]
                assert search_query == "demo"
                assert page == 2
                assert page_size == 5
                assert sort_ascending is True
                return [{"uuid": "job-uuid", "status": "running"}]

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "jobs",
                "list",
                "--status",
                "running",
                "--query",
                "demo",
                "--page",
                "2",
                "--page_size",
                "5",
                "--sort_ascending",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["jobs"] == [{"uuid": "job-uuid", "status": "running"}]
        assert out["data"]["page"] == 2
        assert out["data"]["page_size"] == 5
        assert out["data"]["returned_count"] == 1
        assert out["data"]["status"] == ["running"]
        assert out["data"]["query"] == "demo"
        assert out["data"]["sort_ascending"] is True

    def test_jobs_list_default_page_metadata(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def remote_inference_list(
                self, status=None, search_query=None, page=1, page_size=10, sort_ascending=False
            ):
                assert page == 1
                assert page_size == 10
                return []

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["jobs", "list"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["page"] == 1
        assert out["data"]["page_size"] == 10
        assert out["data"]["returned_count"] == 0

    def test_jobs_status(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def new_remote_inference_get(
                self, job_uuid=None, results_uuid=None, include_json_string=False
            ):
                assert job_uuid == "job-uuid"
                assert results_uuid is None
                assert include_json_string is True
                return {"job_uuid": job_uuid, "status": "completed"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["jobs", "status", "job-uuid", "--include_json"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["status"] == "completed"

    def test_jobs_cancel_requires_confirmation(self):
        result = CliRunner().invoke(cli_module.app, ["jobs", "cancel", "job-uuid"])

        assert result.exit_code == cli_module.EXIT_USAGE
        out = json.loads(result.output)
        assert out["error"]["code"] == "CONFIRMATION_REQUIRED"

    def test_jobs_cancel_confirmed(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def cancel_remote_inference_job(self, job_uuid):
                assert job_uuid == "job-uuid"
                return {"status": "cancelling"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["jobs", "cancel", "job-uuid", "--yes"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["status"] == "cancelling"

    def test_jobs_results_fetches_and_saves_results(self, tmp_path, monkeypatch):
        from edsl.results import Results
        import edsl.coop

        output_path = tmp_path / "remote-results.ep"

        class FakeCoop:
            def new_remote_inference_get(self, job_uuid=None):
                assert job_uuid == "job-uuid"
                return {
                    "job_uuid": job_uuid,
                    "results_uuid": "results-uuid",
                    "status": "completed",
                }

            def pull(self, identifier, expected_object_type=None):
                assert identifier == "results-uuid"
                assert expected_object_type == "results"
                return Results.example()

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["jobs", "results", "job-uuid", "--output", str(output_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["job_uuid"] == "job-uuid"
        assert out["data"]["results_uuid"] == "results-uuid"
        assert out["data"]["status"] == "completed"
        assert out["data"]["saved"]["format"] == "ep"
        assert output_path.exists()

    def test_jobs_results_requires_available_results_uuid(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def new_remote_inference_get(self, job_uuid=None):
                return {"job_uuid": job_uuid, "results_uuid": None, "status": "running"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(cli_module.app, ["jobs", "results", "job-uuid"])

        assert result.exit_code == cli_module.EXIT_NOT_FOUND
        out = json.loads(result.output)
        assert out["error"]["code"] == "RESULTS_NOT_AVAILABLE"

    def test_jobs_errors_fetches_and_saves_markdown(self, tmp_path, monkeypatch):
        import edsl.coop

        output_path = tmp_path / "error.md"

        class FakeCoop:
            def get_error_report_markdown(self, job_uuid):
                assert job_uuid == "job-uuid"
                return "# Error report\n\nDetails"

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["jobs", "errors", "job-uuid", "--output", str(output_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["job_uuid"] == "job-uuid"
        assert out["data"]["saved_to"] == str(output_path)
        assert output_path.read_text(encoding="utf-8") == "# Error report\n\nDetails"

    def test_jobs_manifest(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def remote_inference_results_manifest(self, job_uuid, page_size=100):
                assert job_uuid == "job-uuid"
                assert page_size == 25
                return {"job_id": job_uuid, "page_size": page_size, "page_count": 3}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["jobs", "manifest", "job-uuid", "--page_size", "25"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["page_count"] == 3

    def test_jobs_page(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def remote_inference_results_page(self, job_uuid, page=0, page_size=100):
                assert job_uuid == "job-uuid"
                assert page == 2
                assert page_size == 10
                return {"job_id": job_uuid, "page": page, "total_on_page": 1}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["jobs", "page", "job-uuid", "--page", "2", "--page_size", "10"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["page"] == 2

    def test_jobs_cost_for_survey(self, tmp_path, monkeypatch):
        from edsl.surveys import Survey
        import edsl.coop

        survey_path = tmp_path / "survey.json"
        survey_path.write_text(json.dumps(Survey.example().to_dict()), encoding="utf-8")

        class FakeCoop:
            def remote_inference_cost(self, obj, iterations=1):
                assert type(obj).__name__ == "Survey"
                assert iterations == 3
                return {"credits_hold": 1.23, "usd": 0.0123}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["jobs", "cost", str(survey_path), "--iterations", "3"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["credits_hold"] == 1.23

    def test_jobs_cost_for_jobs_package(self, tmp_path, monkeypatch):
        from edsl.jobs import Jobs
        import edsl.coop

        jobs_path = tmp_path / "jobs.ep"
        Jobs.example().git.save(jobs_path)

        class FakeCoop:
            def remote_inference_cost(self, obj, iterations=1):
                assert type(obj).__name__ == "Jobs"
                assert iterations == 2
                return {"credits_hold": 2.34, "usd": 0.0234}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["jobs", "cost", str(jobs_path), "--iterations", "2"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["credits_hold"] == 2.34


# ---------------------------------------------------------------------------
# edsl humanize
# ---------------------------------------------------------------------------

class TestHumanizeCli:
    def test_humanize_group_lists_commands(self):
        result = CliRunner().invoke(cli_module.app, ["humanize"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["commands"] == [
            "list",
            "create",
            "status",
            "responses",
            "qr",
            "preview",
            "respondents",
            "schedules",
            "deliveries",
            "callbacks",
            "agent-list",
            "schema",
            "css",
        ]

    def test_humanize_schema_group_lists_commands(self):
        result = CliRunner().invoke(cli_module.app, ["humanize", "schema"])

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["commands"] == ["validate", "patch"]

    def test_humanize_schema_validate(self, tmp_path):
        from edsl.surveys import Survey

        survey_path = tmp_path / "survey.json"
        schema_path = tmp_path / "schema.json"
        survey_path.write_text(json.dumps(Survey.example().to_dict()), encoding="utf-8")
        schema_path.write_text(json.dumps({"questions": {}}), encoding="utf-8")

        result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "schema",
                "validate",
                "--survey",
                str(survey_path),
                "--schema",
                str(schema_path),
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["valid"] is True

    def test_humanize_list(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def list_human_surveys(
                self, page=1, page_size=10, search_query=None, sort_ascending=False
            ):
                assert page == 2
                assert page_size == 5
                assert search_query == "demo"
                assert sort_ascending is True
                return {
                    "human_surveys": [{"uuid": "human-survey-uuid"}],
                    "current_page": page,
                    "page_size": page_size,
                    "total_pages": 3,
                    "total_count": 11,
                }

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "list",
                "--query",
                "demo",
                "--page",
                "2",
                "--page_size",
                "5",
                "--sort_ascending",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["human_surveys"] == [{"uuid": "human-survey-uuid"}]
        assert out["data"]["page"] == 2
        assert out["data"]["page_size"] == 5
        assert out["data"]["returned_count"] == 1
        assert out["data"]["query"] == "demo"
        assert out["data"]["sort_ascending"] is True

    def test_humanize_status(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def get_human_survey(self, human_survey_uuid):
                assert human_survey_uuid == "human-survey-uuid"
                return {"uuid": human_survey_uuid, "status": "active"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["humanize", "status", "human-survey-uuid"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["status"] == "active"

    def test_humanize_status_backfills_agent_list_uuid(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def get_human_survey(self, human_survey_uuid):
                assert human_survey_uuid == "human-survey-uuid"
                return {
                    "uuid": human_survey_uuid,
                    "agent_list_uuid": None,
                    "status": "active",
                }

            def get_human_survey_agent_list(self, human_survey_uuid):
                assert human_survey_uuid == "human-survey-uuid"
                return {
                    "agent_list_config": {
                        "uuid": "agent-list-uuid",
                        "delivery_map": {"email": {"col_name": "email"}},
                    }
                }

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["humanize", "status", "human-survey-uuid"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["agent_list_uuid"] == "agent-list-uuid"
        assert out["data"]["agent_list_config"]["delivery_map"]["email"]["col_name"] == "email"

    def test_humanize_preview(self, tmp_path, monkeypatch):
        from edsl.surveys import Survey
        import edsl.coop

        survey_path = tmp_path / "survey.json"
        schema_path = tmp_path / "schema.json"
        survey_path.write_text(json.dumps(Survey.example().to_dict()), encoding="utf-8")
        schema_path.write_text(json.dumps({"questions": {}}), encoding="utf-8")

        class FakeCoop:
            def get_survey_preview_url(self, survey, humanize_schema=None):
                assert type(survey).__name__ == "Survey"
                assert humanize_schema == {"questions": {}}
                return "https://example.com/preview"

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "preview",
                "--survey",
                str(survey_path),
                "--schema",
                str(schema_path),
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["preview_url"] == "https://example.com/preview"

    def test_humanize_create_from_survey(self, tmp_path, monkeypatch):
        from edsl.surveys import Survey
        import edsl.coop

        survey_path = tmp_path / "survey.json"
        schema_path = tmp_path / "schema.json"
        delivery_map_path = tmp_path / "delivery_map.json"
        survey_path.write_text(json.dumps(Survey.example().to_dict()), encoding="utf-8")
        schema_path.write_text(json.dumps({"questions": {}}), encoding="utf-8")
        delivery_map_path.write_text(json.dumps({"email": "survey"}), encoding="utf-8")

        class FakeCoop:
            def create_human_survey(
                self,
                survey,
                scenario_list=None,
                scenario_list_method=None,
                human_survey_name=None,
                survey_description=None,
                survey_alias=None,
                survey_visibility=None,
                scenario_list_description=None,
                scenario_list_alias=None,
                scenario_list_visibility=None,
                agent_list=None,
                agent_list_description=None,
                agent_list_alias=None,
                agent_list_visibility=None,
                humanize_schema=None,
                delivery_map=None,
            ):
                assert type(survey).__name__ == "Survey"
                assert scenario_list is None
                assert scenario_list_method is None
                assert agent_list is None
                assert human_survey_name == "Demo survey"
                assert survey_alias == "demo-survey"
                assert survey_visibility == "unlisted"
                assert humanize_schema == {"questions": {}}
                assert delivery_map == {"email": "survey"}
                return {"uuid": "human-survey-uuid", "name": human_survey_name}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "create",
                "--survey",
                str(survey_path),
                "--name",
                "Demo survey",
                "--schema",
                str(schema_path),
                "--survey_alias",
                "demo-survey",
                "--survey_visibility",
                "unlisted",
                "--delivery_map",
                str(delivery_map_path),
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["uuid"] == "human-survey-uuid"

    def test_humanize_create_requires_exactly_one_source(self):
        result = CliRunner().invoke(cli_module.app, ["humanize", "create"])

        assert result.exit_code == cli_module.EXIT_USAGE
        out = json.loads(result.output)
        assert out["error"]["code"] == "USAGE_ERROR"

    def test_humanize_create_requires_scenario_pair(self, tmp_path):
        from edsl.surveys import Survey

        survey_path = tmp_path / "survey.json"
        survey_path.write_text(json.dumps(Survey.example().to_dict()), encoding="utf-8")

        result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "create",
                "--survey",
                str(survey_path),
                "--scenario_method",
                "randomize",
            ],
        )

        assert result.exit_code == cli_module.EXIT_USAGE
        out = json.loads(result.output)
        assert out["error"]["code"] == "USAGE_ERROR"

    def test_humanize_responses_fetches_and_saves_results(self, tmp_path, monkeypatch):
        from edsl.results import Results
        import edsl.coop

        output_path = tmp_path / "responses.ep"

        class FakeCoop:
            def get_human_survey_responses(self, human_survey_uuid):
                assert human_survey_uuid == "human-survey-uuid"
                return Results.example()

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "responses",
                "human-survey-uuid",
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["human_survey_uuid"] == "human-survey-uuid"
        assert out["data"]["object_type"] == "Results"
        assert out["data"]["saved"]["format"] == "ep"
        assert output_path.exists()

    def test_humanize_responses_without_output_includes_save_hint(self, monkeypatch):
        from edsl.results import Results
        import edsl.coop

        class FakeCoop:
            def get_human_survey_responses(self, human_survey_uuid):
                assert human_survey_uuid == "human-survey-uuid"
                return Results.example()

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["humanize", "responses", "human-survey-uuid"],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert "--output responses.ep" in out["data"]["next_step"]

    def test_humanize_qr_saves_file(self, tmp_path, monkeypatch):
        import edsl.coop

        output_path = tmp_path / "qr.png"

        class FakeQr:
            def save(self, path):
                Path(path).write_bytes(b"png")

        class FakeCoop:
            def get_human_survey_qr_code(self, human_survey_uuid):
                assert human_survey_uuid == "human-survey-uuid"
                return FakeQr()

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            ["humanize", "qr", "human-survey-uuid", "--output", str(output_path)],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["saved_to"] == str(output_path)
        assert output_path.read_bytes() == b"png"

    def test_humanize_schema_css_and_respondents(self, tmp_path, monkeypatch):
        import edsl.coop

        schema_path = tmp_path / "schema.json"
        css_path = tmp_path / "style.css"
        schema_path.write_text(json.dumps({"questions": {"q0": {"optional": True}}}), encoding="utf-8")
        css_path.write_text(".survey { color: red; }", encoding="utf-8")

        class FakeCoop:
            def patch_human_survey_humanize_schema(self, human_survey_uuid, partial_schema):
                assert human_survey_uuid == "human-survey-uuid"
                assert partial_schema == {"questions": {"q0": {"optional": True}}}
                return {"humanize_schema": partial_schema}

            def patch_human_survey_css(self, human_survey_uuid, css):
                assert human_survey_uuid == "human-survey-uuid"
                assert css == ".survey { color: red; }"
                return {"message": "updated"}

            def get_human_survey_respondents(self, human_survey_uuid, page=1, page_size=50):
                assert human_survey_uuid == "human-survey-uuid"
                assert page == 2
                assert page_size == 5
                return {"respondents": [{"respondent_uuid": "resp-uuid"}], "page": page}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        schema_result = CliRunner().invoke(
            cli_module.app,
            ["humanize", "schema", "patch", "human-survey-uuid", "--schema", str(schema_path)],
        )
        css_result = CliRunner().invoke(
            cli_module.app,
            ["humanize", "css", "patch", "human-survey-uuid", "--file", str(css_path)],
        )
        respondents_result = CliRunner().invoke(
            cli_module.app,
            ["humanize", "respondents", "human-survey-uuid", "--page", "2", "--page_size", "5"],
        )

        assert schema_result.exit_code == 0, schema_result.output
        assert css_result.exit_code == 0, css_result.output
        assert respondents_result.exit_code == 0, respondents_result.output
        assert json.loads(schema_result.output)["data"]["humanize_schema"]["questions"]["q0"]["optional"] is True
        assert json.loads(css_result.output)["data"]["message"] == "updated"
        assert json.loads(respondents_result.output)["data"]["respondents"][0]["respondent_uuid"] == "resp-uuid"

    def test_humanize_agent_list_commands(self, tmp_path, monkeypatch):
        import edsl.coop

        delivery_map_path = tmp_path / "delivery_map.json"
        delivery_map_path.write_text(json.dumps({"email": {"col_name": "email"}}), encoding="utf-8")

        class FakeCoop:
            def get_human_survey_agent_list(self, human_survey_uuid):
                assert human_survey_uuid == "human-survey-uuid"
                return {"agent_list_config": {"uuid": "agent-list-uuid"}}

            def patch_human_survey_agent_list(
                self, human_survey_uuid, delivery_map=None, anonymous=None, allow_resubmit=None
            ):
                assert human_survey_uuid == "human-survey-uuid"
                assert delivery_map == {"email": {"col_name": "email"}}
                assert anonymous is True
                assert allow_resubmit is False
                return {"uuid": "agent-list-uuid", "anonymous": anonymous}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        get_result = CliRunner().invoke(
            cli_module.app,
            ["humanize", "agent-list", "get", "human-survey-uuid"],
        )
        patch_result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "agent-list",
                "patch",
                "human-survey-uuid",
                "--delivery_map",
                str(delivery_map_path),
                "--anonymous",
                "--no_allow_resubmit",
            ],
        )

        assert get_result.exit_code == 0, get_result.output
        assert patch_result.exit_code == 0, patch_result.output
        assert json.loads(get_result.output)["data"]["agent_list_config"]["uuid"] == "agent-list-uuid"
        assert json.loads(patch_result.output)["data"]["anonymous"] is True

    def test_humanize_delivery_commands(self, tmp_path, monkeypatch):
        import edsl.coop

        routes_path = tmp_path / "routes.json"
        routes_path.write_text(
            json.dumps([{"channel": "email", "subtype": "respondent"}]),
            encoding="utf-8",
        )

        class FakeCoop:
            def create_human_survey_delivery(self, human_survey_uuid, name, routes=None):
                assert human_survey_uuid == "human-survey-uuid"
                assert name == "Delivery"
                assert routes == [{"channel": "email", "subtype": "respondent"}]
                return {"delivery_uuid": "delivery-uuid"}

            def list_human_survey_deliveries(self, human_survey_uuid, page=1, page_size=50):
                assert page == 2
                return {"deliveries": [{"delivery_uuid": "delivery-uuid"}], "page": page}

            def get_human_survey_delivery(self, human_survey_uuid, delivery_uuid):
                assert delivery_uuid == "delivery-uuid"
                return {"delivery_uuid": delivery_uuid, "status": "completed"}

            def list_human_survey_delivery_tasks(self, human_survey_uuid, delivery_uuid, page=1, page_size=50):
                assert delivery_uuid == "delivery-uuid"
                return {"tasks": [{"task_uuid": "task-uuid"}]}

            def get_human_survey_delivery_task(self, human_survey_uuid, task_uuid):
                assert task_uuid == "task-uuid"
                return {"task_uuid": task_uuid}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        commands = [
            ["humanize", "deliveries", "create", "human-survey-uuid", "--name", "Delivery", "--routes", str(routes_path)],
            ["humanize", "deliveries", "list", "human-survey-uuid", "--page", "2"],
            ["humanize", "deliveries", "get", "human-survey-uuid", "delivery-uuid"],
            ["humanize", "deliveries", "tasks", "human-survey-uuid", "delivery-uuid"],
            ["humanize", "deliveries", "task", "human-survey-uuid", "task-uuid"],
        ]

        outputs = []
        for command in commands:
            result = CliRunner().invoke(cli_module.app, command)
            assert result.exit_code == 0, result.output
            outputs.append(json.loads(result.output)["data"])

        assert outputs[0]["delivery_uuid"] == "delivery-uuid"
        assert outputs[1]["deliveries"][0]["delivery_uuid"] == "delivery-uuid"
        assert outputs[4]["task_uuid"] == "task-uuid"

    def test_humanize_delivery_create_route_helper(self, monkeypatch):
        import edsl.coop

        class FakeCoop:
            def create_human_survey_delivery(self, human_survey_uuid, name, routes=None):
                assert routes == [
                    {
                        "channel": "email",
                        "subtype": "owner",
                        "delivery_template": {
                            "source": "expected_parrot",
                            "name": "owner_response_received",
                        },
                        "subject": "Owner note",
                    }
                ]
                return {"delivery_uuid": "delivery-uuid", "routes": routes}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "deliveries",
                "create",
                "human-survey-uuid",
                "--name",
                "Delivery",
                "--owner-email-template",
                "owner_response_received",
                "--subject",
                "Owner note",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["routes"][0]["subtype"] == "owner"

    def test_humanize_delivery_wait(self, monkeypatch):
        import edsl.coop
        import edsl.cli_humanize_helpers as helper_module

        class FakeCoop:
            def __init__(self):
                self.calls = 0

            def get_human_survey_delivery(self, human_survey_uuid, delivery_uuid):
                self.calls += 1
                if self.calls == 1:
                    return {"delivery_uuid": delivery_uuid, "status": "running"}
                return {"delivery_uuid": delivery_uuid, "status": "completed"}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)
        monkeypatch.setattr(helper_module.time, "sleep", lambda _: None)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "humanize",
                "deliveries",
                "wait",
                "human-survey-uuid",
                "delivery-uuid",
                "--poll_interval",
                "0.1",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        assert out["data"]["completed"] is True
        assert out["data"]["polls"] == 2

    def test_humanize_schedule_commands(self, tmp_path, monkeypatch):
        import edsl.coop

        route_path = tmp_path / "route.json"
        template_path = tmp_path / "template.html"
        filter_path = tmp_path / "filter.json"
        route_path.write_text(json.dumps({"channel": "email", "subtype": "respondent"}), encoding="utf-8")
        template_path.write_text("<p>Hello</p>", encoding="utf-8")
        filter_path.write_text(json.dumps({"type": "group", "conditions": []}), encoding="utf-8")

        class FakeCoop:
            def create_human_survey_one_time_schedule(self, human_survey_uuid, name, run_at, routes=None):
                assert name == "One"
                assert run_at == "2026-07-05T12:00:00Z"
                return {"schedule_uuid": "schedule-uuid", "schedule_type": "one_time"}

            def create_human_survey_cron_schedule(
                self, human_survey_uuid, name, cron_expression, timezone, max_jobs=None, deadline=None, start_at=None, routes=None
            ):
                assert cron_expression == "0 9 * * MON"
                assert timezone == "America/New_York"
                assert max_jobs == 3
                return {"schedule_uuid": "schedule-uuid", "schedule_type": "cron"}

            def list_human_survey_schedules(self, human_survey_uuid, page=1, page_size=50):
                return {"schedules": [{"schedule_uuid": "schedule-uuid"}], "page": page}

            def get_human_survey_schedule(self, human_survey_uuid, schedule_uuid):
                return {"schedule_uuid": schedule_uuid}

            def update_human_survey_one_time_schedule(self, human_survey_uuid, schedule_uuid, run_at):
                assert run_at == "2026-07-06T12:00:00Z"
                return {"schedule_uuid": schedule_uuid, "run_at": run_at}

            def update_human_survey_cron_schedule(
                self, human_survey_uuid, schedule_uuid, cron_expression=None, timezone=None, max_jobs=None, deadline=None, start_at=None
            ):
                assert timezone == "UTC"
                return {"schedule_uuid": schedule_uuid, "timezone": timezone}

            def set_human_survey_schedule_active(self, human_survey_uuid, schedule_uuid, is_active):
                assert is_active is True
                return {"schedule_uuid": schedule_uuid, "is_active": is_active}

            def delete_human_survey_schedule(self, human_survey_uuid, schedule_uuid):
                return {"deleted": schedule_uuid}

            def add_human_survey_schedule_route(self, human_survey_uuid, schedule_uuid, route_config):
                assert route_config == {"channel": "email", "subtype": "respondent"}
                return {"route_uuid": "route-uuid"}

            def delete_human_survey_schedule_route(self, human_survey_uuid, schedule_uuid, route_uuid):
                return {"deleted": route_uuid}

            def patch_human_survey_schedule_respondent_email_route(
                self, human_survey_uuid, schedule_uuid, route_uuid, delivery_template=None, respondent_filter=None, subject=None
            ):
                assert delivery_template == "<p>Hello</p>"
                assert respondent_filter == {"type": "group", "conditions": []}
                assert subject == "Hi"
                return {"route_uuid": route_uuid, "subject": subject}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        commands = [
            ["humanize", "schedules", "create-one-time", "human-survey-uuid", "--name", "One", "--run_at", "2026-07-05T12:00:00Z"],
            ["humanize", "schedules", "create-cron", "human-survey-uuid", "--name", "Cron", "--cron_expression", "0 9 * * MON", "--timezone", "America/New_York", "--max_jobs", "3"],
            ["humanize", "schedules", "list", "human-survey-uuid"],
            ["humanize", "schedules", "get", "human-survey-uuid", "schedule-uuid"],
            ["humanize", "schedules", "update-one-time", "human-survey-uuid", "schedule-uuid", "--run_at", "2026-07-06T12:00:00Z"],
            ["humanize", "schedules", "update-cron", "human-survey-uuid", "schedule-uuid", "--timezone", "UTC"],
            ["humanize", "schedules", "activate", "human-survey-uuid", "schedule-uuid"],
            ["humanize", "schedules", "delete", "human-survey-uuid", "schedule-uuid"],
            ["humanize", "schedules", "route-add", "human-survey-uuid", "schedule-uuid", "--route", str(route_path)],
            ["humanize", "schedules", "route-delete", "human-survey-uuid", "schedule-uuid", "route-uuid"],
            [
                "humanize", "schedules", "route-patch-respondent-email",
                "human-survey-uuid", "schedule-uuid", "route-uuid",
                "--template_file", str(template_path),
                "--respondent_filter", str(filter_path),
                "--subject", "Hi",
            ],
        ]

        for command in commands:
            result = CliRunner().invoke(cli_module.app, command)
            assert result.exit_code == 0, result.output

    def test_humanize_callback_commands(self, tmp_path, monkeypatch):
        import edsl.coop

        route_path = tmp_path / "route.json"
        route_path.write_text(json.dumps({"channel": "email", "subtype": "respondent"}), encoding="utf-8")

        class FakeCoop:
            def create_human_survey_callback(self, human_survey_uuid, name, callback_type, routes=None, max_fires=None):
                assert callback_type == "human_survey_respondent.completed"
                assert max_fires == 2
                return {"callback_uuid": "callback-uuid", "name": name}

            def list_human_survey_callbacks(self, human_survey_uuid, page=1, page_size=50):
                return {"callbacks": [{"callback_uuid": "callback-uuid"}], "page": page}

            def get_human_survey_callback(self, human_survey_uuid, callback_uuid):
                return {"callback_uuid": callback_uuid}

            def patch_human_survey_callback(self, human_survey_uuid, callback_uuid, name=None):
                assert name == "Renamed"
                return {"callback_uuid": callback_uuid, "name": name}

            def set_human_survey_callback_active(self, human_survey_uuid, callback_uuid, is_active):
                return {"callback_uuid": callback_uuid, "is_active": is_active}

            def delete_human_survey_callback(self, human_survey_uuid, callback_uuid):
                return {"deleted": callback_uuid}

            def add_human_survey_callback_route(self, human_survey_uuid, callback_uuid, route_config):
                assert route_config == {"channel": "email", "subtype": "respondent"}
                return {"route_uuid": "route-uuid"}

            def delete_human_survey_callback_route(self, human_survey_uuid, callback_uuid, route_uuid):
                return {"deleted": route_uuid}

            def patch_human_survey_callback_respondent_email_route(
                self, human_survey_uuid, callback_uuid, route_uuid, delivery_template=None, respondent_filter=None, subject=None
            ):
                assert subject == "Hi"
                return {"route_uuid": route_uuid, "subject": subject}

        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)

        commands = [
            [
                "humanize", "callbacks", "create", "human-survey-uuid",
                "--name", "Callback",
                "--type", "human_survey_respondent.completed",
                "--routes", str(route_path),
                "--max_fires", "2",
            ],
            ["humanize", "callbacks", "list", "human-survey-uuid"],
            ["humanize", "callbacks", "get", "human-survey-uuid", "callback-uuid"],
            ["humanize", "callbacks", "patch", "human-survey-uuid", "callback-uuid", "--name", "Renamed"],
            ["humanize", "callbacks", "activate", "human-survey-uuid", "callback-uuid"],
            ["humanize", "callbacks", "deactivate", "human-survey-uuid", "callback-uuid"],
            ["humanize", "callbacks", "delete", "human-survey-uuid", "callback-uuid"],
            ["humanize", "callbacks", "route-add", "human-survey-uuid", "callback-uuid", "--route", str(route_path)],
            ["humanize", "callbacks", "route-delete", "human-survey-uuid", "callback-uuid", "route-uuid"],
            ["humanize", "callbacks", "route-patch-respondent-email", "human-survey-uuid", "callback-uuid", "route-uuid", "--subject", "Hi"],
        ]

        for command in commands:
            result = CliRunner().invoke(cli_module.app, command)
            assert result.exit_code == 0, result.output


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

    def test_results_commands_accept_package(self, tmp_path, results_file):
        from edsl.results import Results

        data = json.loads(Path(results_file).read_text(encoding="utf-8"))
        results = Results.from_dict(data)
        package_path = tmp_path / "results.ep"
        results.git.save(package_path)

        columns_result = CliRunner().invoke(
            cli_module.app,
            ["results", "columns", "--file", str(package_path)],
        )
        select_result = CliRunner().invoke(
            cli_module.app,
            ["results", "select", "--file", str(package_path), "--column", "answer.q0"],
        )

        assert columns_result.exit_code == 0, columns_result.output
        assert select_result.exit_code == 0, select_result.output
        columns = json.loads(columns_result.output)["data"]["columns"]
        rows = json.loads(select_result.output)["data"]["data"]
        assert "answer.q0" in columns
        assert rows[0]["answer.q0"] == "hello"

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

    def test_run_accepts_json_alias(self):
        out = run_cli("run", "--question", "hi", "--json", '{"type":"free_text","question_text":"hi"}',
                      expect_exit=2)
        assert out["error"]["code"] == "USAGE_ERROR"
        assert "json" in out["error"]["message"]

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

    def test_run_background_returns_remote_job_metadata(self, monkeypatch):
        from types import SimpleNamespace
        from edsl.jobs import Jobs
        from edsl.results import Results

        captured = {}

        def fake_run(self, **kwargs):
            captured.update(kwargs)
            job_info = SimpleNamespace(
                creation_data={"uuid": "job-uuid", "status": "queued"},
                job_uuid="job-uuid",
                new_format=True,
                logger=SimpleNamespace(
                    jobs_info=SimpleNamespace(
                        progress_bar_url="https://example.com/progress/job-uuid",
                        remote_inference_url="https://example.com/remote-inference",
                        remote_cache_url="https://example.com/remote-cache",
                        results_uuid=None,
                        results_url=None,
                        error_report_url=None,
                    )
                ),
            )
            return Results.from_job_info(job_info)

        monkeypatch.setattr(Jobs, "run", fake_run)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "run",
                "--question",
                "What is your name?",
                "--background",
                "--remote_inference_description",
                "Demo job",
                "--remote_inference_results_visibility",
                "public",
                "--results_description",
                "Demo results",
            ],
        )

        assert result.exit_code == 0, result.output
        assert captured["background"] is True
        assert captured["remote_inference_description"] == "Demo job"
        assert captured["remote_inference_results_visibility"] == "public"
        assert captured["results_description"] == "Demo results"
        out = json.loads(result.output)
        assert out["data"]["results"] == []
        remote_job = out["data"]["meta"]["remote_job"]
        assert remote_job["job_uuid"] == "job-uuid"
        assert remote_job["progress_bar_url"] == "https://example.com/progress/job-uuid"
        assert remote_job["commands"]["status"] == "edsl jobs status job-uuid"
        assert remote_job["commands"]["results"] == "edsl jobs results job-uuid --output results.ep"

    def test_run_background_rejects_output(self):
        result = CliRunner().invoke(
            cli_module.app,
            [
                "run",
                "--question",
                "What is your name?",
                "--background",
                "--output",
                "results.ep",
            ],
        )

        assert result.exit_code == cli_module.EXIT_USAGE
        out = json.loads(result.output)
        assert out["error"]["code"] == "USAGE_ERROR"

    def test_run_background_wait_fetches_and_saves_results(self, tmp_path, monkeypatch):
        from types import SimpleNamespace
        from edsl.jobs import Jobs
        from edsl.results import Results
        import edsl.coop

        output_path = tmp_path / "wait-results.ep"
        captured = {}

        def completed_results():
            from edsl import Agent
            from edsl.language_models import Model
            from edsl.questions import QuestionFreeText
            from edsl.results.result import Result
            from edsl.scenarios import Scenario
            from edsl.surveys import Survey

            survey = Survey(
                [QuestionFreeText(question_name="name", question_text="What is your name?")]
            )
            result = Result(
                agent=Agent(traits={}),
                scenario=Scenario(),
                model=Model("test", service_name="test"),
                iteration=0,
                answer={"name": "Ada"},
            )
            return Results(survey=survey, data=[result])

        def fake_run(self, **kwargs):
            captured.update(kwargs)
            job_info = SimpleNamespace(
                creation_data={"uuid": "job-uuid", "status": "queued"},
                job_uuid="job-uuid",
                new_format=True,
                logger=SimpleNamespace(
                    jobs_info=SimpleNamespace(
                        progress_bar_url="https://example.com/progress/job-uuid",
                        remote_inference_url="https://example.com/remote-inference",
                        remote_cache_url="https://example.com/remote-cache",
                        results_uuid=None,
                        results_url=None,
                        error_report_url=None,
                    )
                ),
            )
            return Results.from_job_info(job_info)

        class FakeCoop:
            def __init__(self):
                self.calls = 0

            def new_remote_inference_get(self, job_uuid=None):
                assert job_uuid == "job-uuid"
                self.calls += 1
                if self.calls == 1:
                    return {"job_uuid": job_uuid, "status": "running"}
                return {
                    "job_uuid": job_uuid,
                    "status": "completed",
                    "results_uuid": "results-uuid",
                }

            def pull(self, identifier, expected_object_type=None):
                assert identifier == "results-uuid"
                assert expected_object_type == "results"
                return completed_results()

        monkeypatch.setattr(Jobs, "run", fake_run)
        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)
        monkeypatch.setattr(cli_module.time, "sleep", lambda _: None)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "run",
                "--question",
                "What is your name?",
                "--background",
                "--wait",
                "--poll_interval",
                "0.1",
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0, result.output
        assert captured["background"] is True
        out = json.loads(result.output)
        wait_data = out["data"]["meta"]["remote_job"]["wait"]
        assert wait_data["completed"] is True
        assert wait_data["polls"] == 2
        assert wait_data["results_uuid"] == "results-uuid"
        assert wait_data["saved"]["format"] == "ep"
        assert out["data"]["meta"]["saved"]["path"] == str(output_path)
        assert output_path.exists()

    def test_run_background_wait_timeout(self, monkeypatch):
        from types import SimpleNamespace
        from edsl.jobs import Jobs
        from edsl.results import Results
        import edsl.coop

        def fake_run(self, **kwargs):
            job_info = SimpleNamespace(
                creation_data={"uuid": "job-uuid", "status": "queued"},
                job_uuid="job-uuid",
                new_format=True,
                logger=SimpleNamespace(jobs_info=SimpleNamespace()),
            )
            return Results.from_job_info(job_info)

        class FakeCoop:
            def new_remote_inference_get(self, job_uuid=None):
                return {"job_uuid": job_uuid, "status": "running"}

        clock = {"value": 0.0}

        def fake_monotonic():
            clock["value"] += 0.2
            return clock["value"]

        monkeypatch.setattr(Jobs, "run", fake_run)
        monkeypatch.setattr(edsl.coop, "Coop", FakeCoop)
        monkeypatch.setattr(cli_module.time, "monotonic", fake_monotonic)
        monkeypatch.setattr(cli_module.time, "sleep", lambda _: None)

        result = CliRunner().invoke(
            cli_module.app,
            [
                "run",
                "--question",
                "What is your name?",
                "--background",
                "--wait",
                "--poll_interval",
                "0.1",
                "--timeout",
                "0.1",
            ],
        )

        assert result.exit_code == 0, result.output
        out = json.loads(result.output)
        wait_data = out["data"]["meta"]["remote_job"]["wait"]
        assert wait_data["completed"] is False
        assert wait_data["timed_out"] is True
        assert wait_data["last_status"] == "running"

    def test_run_wait_requires_background(self):
        result = CliRunner().invoke(
            cli_module.app,
            ["run", "--question", "What is your name?", "--wait"],
        )

        assert result.exit_code == cli_module.EXIT_USAGE
        out = json.loads(result.output)
        assert out["error"]["code"] == "USAGE_ERROR"


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
        assert "search" in data["commands"]
        assert "coop" not in data["commands"]
        assert "clone" in data["commands"]
        assert "push" in data["commands"]
        assert "pull" in data["commands"]
        assert "metadata" in data["commands"]
        assert "update-metadata" in data["commands"]
        assert "share" in data["commands"]
        assert "unshare" in data["commands"]
        assert "delete" in data["commands"]
        assert "profile" in data["commands"]
        assert "jobs" in data["commands"]
        assert "humanize" in data["commands"]


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
