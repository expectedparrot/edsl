"""
EDSL CLI — agent-friendly interface. All output is JSON on stdout.

Entry point: edsl = "edsl.__main__:main" (pyproject.toml)
"""

import sys
import json
from typing import Optional
from pathlib import Path

import click

from edsl.cli_commands import auth as auth_commands
from edsl.cli_commands import humanize as humanize_commands
from edsl.cli_commands import jobs as jobs_commands
from edsl.cli_commands import models as models_commands
from edsl.cli_commands import objects as objects_commands
from edsl.cli_commands import open as open_commands
from edsl.cli_commands import results as results_commands
from edsl.cli_commands import run as run_commands
from edsl.cli_commands import schema as schema_commands
from edsl.cli_shared import (
    EXIT_AUTH,
    EXIT_ERROR,
    EXIT_NOT_FOUND,
    EXIT_REMOTE,
    EXIT_USAGE,
    EXIT_VALIDATION,
    error as _error,
    jsonable as _jsonable,
    output as _output,
    read_json_file as _read_json_file,
)


def _read_stdin() -> Optional[str]:
    """Read stdin if it's not a TTY."""
    if sys.stdin.isatty():
        return None
    return sys.stdin.read()


# ---------------------------------------------------------------------------
# Click app hierarchy
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.pass_context
def app(ctx):
    """EDSL CLI — run LLM surveys. All output is JSON."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": [
                "run",
                "models",
                "info",
                "validate",
                "open",
                "clone",
                "search",
                "push",
                "pull",
                "metadata",
                "update-metadata",
                "share",
                "unshare",
                "shared",
                "delete",
                "balance",
                "profile",
                "settings",
                "humanize",
                "schema",
                "auth",
                "results",
                "jobs",
            ],
            "help": "Use 'edsl <command> --help' for details on each command.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def schema(ctx):
    """Introspect object schemas for construction."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["list", "show", "error"],
            "help": "Use 'edsl schema <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def auth(ctx):
    """Authentication management."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["login", "status", "balance"],
            "help": "Use 'edsl auth <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def results(ctx):
    """Query and extract data from Results files."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["columns", "select"],
            "help": "Use 'edsl results <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def jobs(ctx):
    """Inspect and manage remote jobs."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["list", "status", "results", "errors", "manifest", "page", "cancel", "cost"],
            "help": "Use 'edsl jobs <command> --help' for details.",
        })


@app.group(invoke_without_command=True)
@click.pass_context
def humanize(ctx):
    """Create and manage human surveys."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": [
                "list", "create", "status", "responses", "qr", "preview",
                "respondents", "schedules", "deliveries", "callbacks",
                "agent-list", "schema", "css",
            ],
            "help": "Use 'edsl humanize <command> --help' for details.",
        })




auth_commands.register(app, auth)
humanize_commands.register(humanize)
jobs_commands.register(jobs)
models_commands.register(app)
objects_commands.register(app)
open_commands.register(app)
results_commands.register(results)
run_commands.register(app)
schema_commands.register(schema)


# ---------------------------------------------------------------------------
# edsl info
# ---------------------------------------------------------------------------

@app.command()
def info():
    """Version, config, and diagnostics."""
    from edsl.__version__ import __version__
    from edsl.config import CONFIG
    from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler

    handler = ExpectedParrotKeyHandler()
    api_key = handler.get_ep_api_key()

    _output({
        "version": __version__,
        "config": _redact_config(CONFIG.to_dict()),
        "api_key_configured": bool(api_key),
    })


def _redact_config(config: dict) -> dict:
    redacted = {}
    sensitive_markers = ("API_KEY", "AUTH_TOKEN", "SECRET", "PASSWORD")
    for key, value in config.items():
        if any(marker in key.upper() for marker in sensitive_markers):
            redacted[key] = "***" if value not in (None, "", "None") else value
        else:
            redacted[key] = value
    return redacted






@app.command("profile")
def profile():
    """Get the authenticated Expected Parrot profile."""
    try:
        from edsl.coop import Coop

        _output(_jsonable(Coop().get_profile()))
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "PROFILE_ERROR",
            str(e),
            suggestion="Check your Expected Parrot API key with 'edsl auth status'.",
            exit_code=EXIT_REMOTE,
        )




@app.command("settings")
def settings():
    """Get Expected Parrot EDSL settings and rate-limit configuration."""
    try:
        from edsl.coop import Coop

        coop = Coop()
        _output(
            {
                "edsl_settings": _jsonable(coop.edsl_settings),
                "rate_limit_config": _jsonable(coop.fetch_rate_limit_config_vars()),
            }
        )
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "SETTINGS_ERROR",
            str(e),
            suggestion="Check your Expected Parrot API key and network connection.",
            exit_code=EXIT_REMOTE,
        )






# ---------------------------------------------------------------------------
# edsl validate
# ---------------------------------------------------------------------------

@app.command()
@click.option("--file", "file_path", default=None, help="Path to JSON file to validate.")
@click.option("--json", "--json_data", "json_data", default=None, help="Inline JSON string.")
@click.option("--type", "force_type", default=None, help="Force validation as type.")
def validate(file_path, json_data, force_type):
    """Validate a question, survey, or job spec without executing."""
    raw = None
    if file_path:
        raw = _read_json_file(file_path)
    elif json_data:
        try:
            raw = json.loads(json_data)
        except json.JSONDecodeError as e:
            _error("INVALID_JSON", f"Failed to parse JSON: {e}",
                   exit_code=EXIT_USAGE)
    else:
        stdin_data = _read_stdin()
        if stdin_data:
            try:
                raw = json.loads(stdin_data)
            except json.JSONDecodeError as e:
                _error("INVALID_JSON", f"Failed to parse JSON from stdin: {e}",
                       exit_code=EXIT_USAGE)

    if raw is None:
        _error("USAGE_ERROR", "No input provided.",
               suggestion="Use --file, --json_data, or pipe JSON via stdin.",
               exit_code=EXIT_USAGE)

    warnings_list = []

    # Detect object type
    obj_type = force_type
    if not obj_type:
        if "survey" in raw and isinstance(raw.get("survey"), dict):
            obj_type = "job"
        elif "questions" in raw and isinstance(raw.get("questions"), list):
            obj_type = "job_lightweight"
        elif "type" in raw and "question_text" in raw:
            obj_type = "question"
        else:
            obj_type = "unknown"

    try:
        if obj_type == "question":
            normalized = _validate_question(raw, warnings_list)
            _output({"valid": True, "object_type": "question", "normalized": normalized}, warnings=warnings_list)
        elif obj_type == "job":
            from edsl.jobs import Jobs
            Jobs.from_dict(raw)
            _output({"valid": True, "object_type": "job", "normalized": raw}, warnings=warnings_list)
        elif obj_type == "job_lightweight":
            _validate_lightweight_job(raw, warnings_list)
            _output({"valid": True, "object_type": "job_lightweight", "normalized": raw}, warnings=warnings_list)
        elif obj_type == "survey":
            from edsl.surveys import Survey
            Survey.from_dict(raw)
            _output({"valid": True, "object_type": "survey", "normalized": raw}, warnings=warnings_list)
        elif obj_type == "agent_list":
            from edsl.agents import AgentList
            AgentList.from_dict(raw)
            _output({"valid": True, "object_type": "agent_list", "normalized": raw}, warnings=warnings_list)
        elif obj_type == "scenario_list":
            from edsl.scenarios import ScenarioList
            ScenarioList.from_dict(raw)
            _output({"valid": True, "object_type": "scenario_list", "normalized": raw}, warnings=warnings_list)
        else:
            _error("VALIDATION_ERROR", "Could not determine object type from input.",
                   suggestion="Use --type to specify: question, survey, job, agent_list, scenario_list.",
                   exit_code=EXIT_VALIDATION)
    except SystemExit:
        raise
    except Exception as e:
        _error("VALIDATION_ERROR", f"Input failed validation: {e}",
               suggestion="Check the input against 'edsl schema' output.",
               exit_code=EXIT_VALIDATION)


def _validate_question(raw: dict, warnings_list: list) -> dict:
    """Validate and normalize a single question dict."""
    from edsl.questions.register_questions_meta import RegisterQuestionsMeta


    qtype = raw.get("type", raw.get("question_type", "free_text"))
    type_map = RegisterQuestionsMeta.question_types_to_classes()

    if qtype not in type_map:
        _error("VALIDATION_ERROR", f"Unknown question type: '{qtype}'",
               suggestion=f"Available: {', '.join(sorted(type_map.keys()))}",
               exit_code=EXIT_VALIDATION)

    if "question_name" not in raw:
        raw["question_name"] = "q0"
        warnings_list.append({
            "code": "AUTO_GENERATED_NAME",
            "message": "question_name was omitted and set to 'q0'",
        })

    kwargs = {k: v for k, v in raw.items() if k not in ("type", "question_type")}

    cls = type_map[qtype]
    q = cls(**kwargs)
    normalized = {"type": qtype, **{k: v for k, v in raw.items() if k != "type" and k != "question_type"}}
    return normalized


def _validate_lightweight_job(raw: dict, warnings_list: list) -> None:
    """Validate a lightweight job spec."""
    questions = raw.get("questions", [])
    if not questions:
        _error("VALIDATION_ERROR", "Job spec has empty 'questions' array.",
               exit_code=EXIT_VALIDATION)

    for i, q in enumerate(questions):
        if "question_text" not in q:
            _error("VALIDATION_ERROR",
                   f"questions[{i}] missing 'question_text'.",
                   exit_code=EXIT_VALIDATION)
        if "question_name" not in q:
            q["question_name"] = f"q{i}"
            warnings_list.append({
                "code": "AUTO_GENERATED_NAME",
                "message": f"questions[{i}].question_name was omitted and set to 'q{i}'",
            })






# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    try:
        app(standalone_mode=False)
    except click.exceptions.MissingParameter as e:
        # Use the flag name (e.g. --type) not the Python variable name
        flag = e.param.opts[0] if e.param and e.param.opts else f"--{e.param.name}"
        _error("USAGE_ERROR", f"Missing required option: {flag}",
               suggestion=f"Run 'edsl {' '.join(sys.argv[1:])} --help' for usage.",
               exit_code=EXIT_USAGE)
    except click.exceptions.BadParameter as e:
        _error("USAGE_ERROR", str(e), exit_code=EXIT_USAGE)
    except click.exceptions.UsageError as e:
        _error("USAGE_ERROR", str(e), exit_code=EXIT_USAGE)
    except click.exceptions.ClickException as e:
        _error("USAGE_ERROR", e.format_message(), exit_code=EXIT_USAGE)


if __name__ == "__main__":
    main()
