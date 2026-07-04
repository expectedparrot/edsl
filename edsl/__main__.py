"""
EDSL CLI — agent-friendly interface. All output is JSON on stdout.

Entry point: edsl = "edsl.__main__:main" (pyproject.toml)
"""

import sys
import json
import html
import tempfile
import webbrowser
from typing import Optional
from pathlib import Path

import click

from edsl.cli_commands import auth as auth_commands
from edsl.cli_commands import humanize as humanize_commands
from edsl.cli_commands import jobs as jobs_commands
from edsl.cli_commands import objects as objects_commands
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
    load_openable_json as _load_openable_json,
    output as _output,
    read_json_file as _read_json_file,
    read_package_manifest as _read_package_manifest,
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
objects_commands.register(app)
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


# ---------------------------------------------------------------------------
# edsl open
# ---------------------------------------------------------------------------

@app.command("open")
@click.argument("path", type=click.Path(exists=True))
@click.option("--output", "-o", "output_path", default=None, help="Path to write the generated HTML.")
@click.option("--browser/--no-browser", default=True, help="Open the generated HTML in a browser.")
def open_object(path, output_path, browser):
    """Open an EDSL object as an HTML artifact in a browser."""
    source_path = Path(path)
    html_path = _html_output_path(source_path, output_path)

    try:
        obj = _load_openable_object(source_path)
        _write_object_html(obj, html_path)
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "OPEN_ERROR",
            f"Failed to render {path} as HTML: {e}",
            suggestion="Use a saved Survey, AgentList, or Jobs JSON file, or a supported .ep package.",
            exit_code=EXIT_ERROR,
        )

    url = html_path.resolve().as_uri()
    opened = False
    if browser:
        try:
            opened = bool(webbrowser.open(url))
        except Exception as e:
            _error(
                "BROWSER_ERROR",
                f"Failed to open browser: {e}",
                suggestion=f"Open this file manually: {html_path}",
                exit_code=EXIT_ERROR,
            )

    _output({
        "source": str(source_path),
        "html_path": str(html_path),
        "url": url,
        "opened": opened,
        "object_type": _openable_object_type(obj),
    })


def _html_output_path(source_path: Path, output_path: Optional[str]) -> Path:
    if output_path:
        return Path(output_path)
    safe_stem = source_path.name.replace("/", "_")
    handle = tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        prefix=f"edsl-{safe_stem}-",
        suffix=".html",
    )
    handle.close()
    return Path(handle.name)


def _load_openable_object(path: Path):
    if path.is_dir():
        return _load_openable_package(path)
    if path.suffix == ".ep":
        return _load_openable_package(path)
    return _load_openable_json(path)


def _load_openable_package(path: Path):
    manifest = _read_package_manifest(path)
    class_name = manifest.get("edsl_class_name") or manifest.get("object_type")
    if class_name == "Survey":
        from edsl.surveys import Survey

        return Survey.git.open(path)
    if class_name == "AgentList":
        from edsl.agents import AgentList

        return AgentList.git.open(path)
    if class_name == "Jobs":
        from edsl.jobs import Jobs

        return Jobs.git.open(path)
    if class_name == "Results":
        from edsl.results import Results

        return Results.git.open(path)
    if class_name == "ScenarioList":
        from edsl.scenarios import ScenarioList

        return ScenarioList.git.open(path)
    if class_name == "ModelList":
        from edsl.language_models import ModelList

        return ModelList.git.open(path)
    _error(
        "UNSUPPORTED_OBJECT",
        f"Object package type does not support HTML rendering: {class_name or 'unknown'}",
        suggestion="Currently supported package types: Survey, AgentList, Jobs, Results, ScenarioList, ModelList.",
        exit_code=EXIT_USAGE,
    )


def _write_object_html(obj, html_path: Path) -> None:
    html_path.parent.mkdir(parents=True, exist_ok=True)
    renderer = getattr(obj, "to_html", None) or getattr(obj, "html", None)
    if renderer is not None:
        renderer(filename=str(html_path))
    else:
        repr_html = getattr(obj, "_repr_html_", None)
        if repr_html is not None:
            body = repr_html()
        else:
            to_dataset = getattr(obj, "to_dataset", None)
            dataset = to_dataset() if to_dataset is not None else None
            body = dataset._repr_html_() if hasattr(dataset, "_repr_html_") else None
        if body is None:
            _error(
                "UNSUPPORTED_OBJECT",
                f"Object type does not support HTML rendering: {_openable_object_type(obj)}",
                exit_code=EXIT_USAGE,
            )
        html_path.write_text(
            _standalone_html_document(
                title=f"EDSL {_openable_object_type(obj)}",
                body=body,
            ),
            encoding="utf-8",
        )
    if not html_path.exists():
        _error(
            "OPEN_ERROR",
            f"HTML renderer did not create expected file: {html_path}",
            exit_code=EXIT_ERROR,
        )


def _standalone_html_document(title: str, body: str) -> str:
    return (
        "<!doctype html>\n"
        "<html>\n"
        "<head>\n"
        '  <meta charset="utf-8">\n'
        f"  <title>{html.escape(title)}</title>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def _openable_object_type(obj) -> str:
    return getattr(obj, "object_type", type(obj).__name__)


# ---------------------------------------------------------------------------
# edsl models
# ---------------------------------------------------------------------------

@app.command()
@click.option("--service", default=None, help="Filter by service name.")
@click.option("--search", default=None, help="Wildcard search pattern.")
@click.option("--text/--no-text", "works_with_text", default=None, help="Filter by text capability.")
@click.option("--vision/--no-vision", "works_with_images", default=None, help="Filter by image/vision capability.")
def models(service, search, works_with_text, works_with_images):
    """List available models."""
    from edsl.language_models import Model

    # Determine which services have configured keys
    try:
        key_info = Model.key_info()
        configured_services = set()
        for entry in key_info:
            if hasattr(entry, 'get'):
                if entry.get('api_key_set'):
                    configured_services.add(entry.get('service_name', ''))
            elif hasattr(entry, 'api_key_set'):
                if entry.api_key_set:
                    configured_services.add(getattr(entry, 'service_name', ''))
    except Exception:
        configured_services = set()

    warnings = []
    source = "expected_parrot"
    try:
        from edsl.coop import Coop

        available = Coop().fetch_working_models()
        model_list = []
        for item in available:
            model_name = item.get("model")
            service_name = item.get("service")
            if service and service_name != service:
                continue
            if search and search.lower() not in str(model_name).lower():
                continue
            if works_with_text is not None and item.get("works_with_text") is not works_with_text:
                continue
            if works_with_images is not None and item.get("works_with_images") is not works_with_images:
                continue
            model_list.append({
                "model_name": model_name,
                "service_name": service_name,
                "configured": service_name in configured_services,
                "works_with_text": item.get("works_with_text"),
                "works_with_images": item.get("works_with_images"),
                "usd_per_1M_input_tokens": item.get("usd_per_1M_input_tokens"),
                "usd_per_1M_output_tokens": item.get("usd_per_1M_output_tokens"),
            })
    except Exception as remote_error:
        if works_with_text is not None or works_with_images is not None:
            _error(
                "MODEL_LIST_ERROR",
                f"Could not fetch model capabilities from Expected Parrot: {remote_error}",
                suggestion="Retry without --text/--no-text/--vision/--no-vision, or check your network/API key.",
                exit_code=EXIT_REMOTE,
            )
        try:
            available = Model.available(
                search_term=search or None,
                service_name=service or None,
                local_only=True,
            )
        except Exception as e:
            _error("MODEL_LIST_ERROR", str(e))

        warnings.append(
            f"Could not fetch models from Expected Parrot; returned local models only: {remote_error}"
        )
        source = "local"
        model_list = []
        for m in available:
            model_name = m.model if hasattr(m, 'model') else str(m)
            service_name = getattr(m, '_inference_service_', '') or getattr(m, 'inference_service', '') or ""
            model_list.append({
                "model_name": model_name,
                "service_name": service_name,
                "configured": service_name in configured_services,
                "works_with_text": None,
                "works_with_images": None,
                "usd_per_1M_input_tokens": None,
                "usd_per_1M_output_tokens": None,
            })

    # Sort alphabetically by service then model
    model_list.sort(key=lambda x: (x["service_name"], x["model_name"]))
    _output(
        {
            "models": model_list,
            "source": source,
            "filters": {
                "service": service,
                "search": search,
                "text": works_with_text,
                "vision": works_with_images,
            },
            "count": len(model_list),
        },
        warnings=warnings,
    )






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
