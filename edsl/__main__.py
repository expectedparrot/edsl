"""
EDSL CLI — agent-friendly interface. All output is JSON on stdout.

Entry point: edsl = "edsl.__main__:main" (pyproject.toml)
"""

import sys
import json
import gzip
import html
import tempfile
import time
import zipfile
import webbrowser
from typing import Optional
from pathlib import Path

import click

from edsl.cli_commands import humanize as humanize_commands
from edsl.cli_commands import jobs as jobs_commands
from edsl.cli_commands import results as results_commands

# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_FOUND = 3
EXIT_AUTH = 4
EXIT_VALIDATION = 5
EXIT_REMOTE = 6

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _output(data: dict, warnings: Optional[list] = None) -> None:
    """Write a success envelope to stdout."""
    envelope = {"status": "ok", "data": data, "warnings": warnings or []}
    json.dump(envelope, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def _error(code: str, message: str, suggestion: str = "",
           exit_code: int = EXIT_ERROR, details: Optional[list] = None) -> None:
    """Write an error envelope to stdout and exit."""
    err = {"code": code, "message": message}
    if suggestion:
        err["suggestion"] = suggestion
    if details:
        err["details"] = details
    envelope = {"status": "error", "error": err}
    json.dump(envelope, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    raise SystemExit(exit_code)


def _read_json_file(path: str) -> dict:
    """Read and parse a JSON file, or emit an error."""
    p = Path(path)
    if not p.exists():
        _error("FILE_NOT_FOUND", f"File not found: {path}",
               suggestion="Check the file path.", exit_code=EXIT_NOT_FOUND)
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        _error("INVALID_JSON", f"Failed to parse JSON from {path}: {e}",
               suggestion="Ensure the file contains valid JSON.", exit_code=EXIT_USAGE)


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




humanize_commands.register(humanize)
jobs_commands.register(jobs)
results_commands.register(results)


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


def _read_package_manifest(path: Path) -> dict:
    if path.is_dir():
        manifest_path = path / "manifest.json"
        if not manifest_path.exists():
            _error(
                "INVALID_PACKAGE",
                f"No manifest.json found in package: {path}",
                exit_code=EXIT_USAGE,
            )
        return json.loads(manifest_path.read_text(encoding="utf-8"))

    with zipfile.ZipFile(path) as archive:
        with archive.open("manifest.json") as manifest_file:
            return json.loads(manifest_file.read().decode("utf-8"))


def _load_openable_json(path: Path):
    data = _read_serialized_object(path)
    class_name = data.get("edsl_class_name", "")
    if class_name == "Survey":
        from edsl.surveys import Survey

        return Survey.from_dict(data)
    if class_name == "AgentList":
        from edsl.agents import AgentList

        return AgentList.from_dict(data)
    if class_name == "Jobs":
        from edsl.jobs import Jobs

        return Jobs.from_dict(data)
    if class_name == "Results":
        from edsl.results import Results

        return Results.from_dict(data)
    if class_name == "ScenarioList":
        from edsl.scenarios import ScenarioList

        return ScenarioList.from_dict(data)
    if class_name == "ModelList":
        from edsl.language_models import ModelList

        return ModelList.from_dict(data)
    _error(
        "UNSUPPORTED_OBJECT",
        f"Object type does not support HTML rendering: {class_name or 'unknown'}",
        suggestion="Currently supported JSON object types: Survey, AgentList, Jobs, Results, ScenarioList, ModelList.",
        exit_code=EXIT_USAGE,
    )


def _read_serialized_object(path: Path) -> dict:
    if path.name.endswith(".json.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    _error(
        "USAGE_ERROR",
        f"Unsupported file extension for open: {path}",
        suggestion="Use a .json, .json.gz, or .ep file.",
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


@app.command("clone")
@click.argument("identifier")
@click.option("--path", "output_path", default=None, help="Package path to save to.")
def clone_object(identifier, output_path):
    """Clone a shared EDSL object into a git-backed package."""
    try:
        from edsl.config import CONFIG
        from edsl.coop import Coop

        coop_identifier = _coop_content_identifier(identifier, CONFIG.EXPECTED_PARROT_URL)
        coop_client = Coop()
        obj = coop_client.get(coop_identifier)
        coop_info = coop_client.get_metadata(coop_identifier)
        coop_info = _plain_dict(coop_info)

        if not hasattr(obj, "git"):
            _error(
                "UNSUPPORTED_OBJECT",
                f"Fetched object does not support git-backed packages: {type(obj).__name__}",
                suggestion="Use an EDSL object type with .git support.",
                exit_code=EXIT_VALIDATION,
            )

        save_path = output_path or _default_clone_path(identifier, coop_info, obj)
        save_info = obj.git.save(save_path, message=f"Clone {identifier}")
        coop_commit_info = obj.git._write_coop_info_and_commit(
            coop_info,
            message=f"Store Coop info for {identifier}",
        )

        data = {
            "object_type": type(obj).__name__,
            "path": str(obj.git.path),
            "source": identifier,
            "resolved_identifier": coop_identifier,
            "coop_info": coop_info,
            "save": save_info,
            "commit": coop_commit_info.get("commit"),
            "branch": coop_commit_info.get("branch"),
            "message": coop_commit_info.get("message"),
        }
        _output(data)

    except SystemExit:
        raise
    except Exception as e:
        _error(
            "CLONE_ERROR",
            str(e),
            suggestion="Check the owner/alias, your API key, and the destination path.",
            exit_code=EXIT_REMOTE,
        )


def _coop_content_identifier(identifier: str, expected_parrot_url: str) -> str:
    if identifier.startswith(("http://", "https://")):
        return identifier
    is_uuid = len(identifier) == 36 and identifier.count("-") == 4
    if is_uuid:
        return identifier
    if "/" in identifier:
        return f"{expected_parrot_url.rstrip('/')}/content/{identifier.strip('/')}"
    return identifier


def _default_clone_path(identifier: str, coop_info: dict, obj) -> str:
    alias = coop_info.get("alias")
    if not alias and "/" in identifier and not identifier.startswith(("http://", "https://")):
        alias = identifier.strip("/").split("/")[-1]
    if not alias and coop_info.get("alias_url"):
        alias = str(coop_info["alias_url"]).rstrip("/").split("/")[-1]
    if not alias:
        alias = type(obj).__name__.lower()
    return _safe_clone_name(str(alias))


def _safe_clone_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "-" for ch in value)
    safe = safe.strip(".-")
    return safe or "edsl_object"


def _plain_dict(value) -> dict:
    if hasattr(value, "items"):
        return dict(value)
    if hasattr(value, "__dict__"):
        return {key: val for key, val in value.__dict__.items() if not key.startswith("_")}
    return {"value": str(value)}


def _remote_identifier(target: str) -> str:
    """Resolve a UUID/URL/owner-alias or a local .ep package to a remote identifier."""
    path = Path(target)
    if path.exists():
        if not (path.is_dir() or path.suffix == ".ep"):
            _error(
                "USAGE_ERROR",
                f"Expected a remote identifier or .ep package: {target}",
                suggestion="Use a UUID, URL, owner/alias, or a git-backed .ep package.",
                exit_code=EXIT_USAGE,
            )
        obj = _load_git_object(path)
        coop_info = obj.git._read_coop_info()
        if not coop_info:
            _error(
                "NO_COOP_INFO",
                f"No coop_info.json found for package: {target}",
                suggestion="Use 'edsl clone <owner>/<alias>' or 'edsl push <path.ep>' first.",
                exit_code=EXIT_VALIDATION,
            )
        return obj.git._coop_identifier(coop_info)
    from edsl.config import CONFIG

    return _coop_content_identifier(target, CONFIG.EXPECTED_PARROT_URL)


def _jsonable(value):
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if hasattr(value, "items"):
        return {key: _jsonable(val) for key, val in value.items()}
    if hasattr(value, "__dict__"):
        return {
            key: _jsonable(val)
            for key, val in value.__dict__.items()
            if not key.startswith("_")
        }
    return value


@app.command("push")
@click.argument("object_path", type=click.Path(exists=True))
@click.option("--alias", default=None, help="Short Expected Parrot alias.")
@click.option("--description", default=None, help="Object description.")
@click.option("--visibility", default=None, help="private, public, or unlisted.")
@click.option("--force", is_flag=True, default=False, help="Patch an existing alias conflict when creating.")
def push_object(object_path, alias, description, visibility, force):
    """Push or patch an EDSL object on Expected Parrot."""
    source_path = Path(object_path)
    try:
        if not (source_path.is_dir() or source_path.suffix == ".ep"):
            _error(
                "USAGE_ERROR",
                f"Push requires a git-backed .ep package: {object_path}",
                suggestion="Save the object as a .ep package first, then run 'edsl push <path.ep>'.",
                exit_code=EXIT_USAGE,
            )

        obj = _load_git_object(source_path)
        if not hasattr(obj, "git"):
            _error(
                "UNSUPPORTED_OBJECT",
                f"Object does not support git-backed packages: {type(obj).__name__}",
                suggestion="Use an EDSL object type with .git support.",
                exit_code=EXIT_VALIDATION,
            )

        had_coop_info = _object_has_coop_info(obj)
        info = obj.git.coop_push(
            description=description,
            alias=alias,
            visibility=visibility,
            force=force,
            message=f"Push {source_path.name} to Expected Parrot",
        )

        _output(
            {
                "object_type": type(obj).__name__,
                "source": str(source_path),
                "path": str(obj.git.path) if getattr(obj.git, "path", None) else None,
                "operation": "patch" if had_coop_info else "push",
                "coop_info": info.get("coop_info"),
                "commit": info.get("commit"),
                "branch": info.get("branch"),
                "message": info.get("message"),
                "result": info,
            }
        )

    except SystemExit:
        raise
    except Exception as e:
        _error(
            "PUSH_ERROR",
            str(e),
            suggestion="Check the object path, alias, visibility, and Expected Parrot API key.",
            exit_code=EXIT_REMOTE,
        )


@app.command("pull")
@click.argument("object_path", type=click.Path(exists=True))
def pull_object(object_path):
    """Fetch the latest Expected Parrot object into a git-backed package."""
    source_path = Path(object_path)
    try:
        if not (source_path.is_dir() or source_path.suffix == ".ep"):
            _error(
                "USAGE_ERROR",
                f"Pull requires a git-backed .ep package: {object_path}",
                suggestion="Use 'edsl clone <owner>/<alias>' first, or pass a .ep package path.",
                exit_code=EXIT_USAGE,
            )

        obj = _load_git_object(source_path)
        if not _object_has_coop_info(obj):
            _error(
                "NO_COOP_INFO",
                f"No coop_info.json found for package: {object_path}",
                suggestion="Use 'edsl clone <owner>/<alias>' or 'edsl push <object>' first.",
                exit_code=EXIT_VALIDATION,
            )

        info = obj.git._coop_pull_if_remote_updated(
            message=f"Pull {source_path.name} from Expected Parrot"
        )
        coop_info = obj.git._read_coop_info()
        if info is None:
            info = {
                "status": "unchanged",
                "path": str(obj.git.path),
                "commit": getattr(obj.git, "commit", None),
                "branch": getattr(obj.git, "current_branch", None),
                "message": "remote metadata is not newer",
            }
        status = info.get("status")
        _output(
            {
                "object_type": type(obj).__name__,
                "source": str(source_path),
                "path": str(obj.git.path) if getattr(obj.git, "path", None) else str(source_path),
                "operation": "unchanged" if status == "unchanged" else "updated",
                "coop_info": coop_info,
                "commit": info.get("commit"),
                "branch": info.get("branch"),
                "message": info.get("message"),
                "result": info,
            }
        )

    except SystemExit:
        raise
    except Exception as e:
        _error(
            "PULL_ERROR",
            str(e),
            suggestion="Check the package path, stored Coop info, and Expected Parrot API key.",
            exit_code=EXIT_REMOTE,
        )


def _load_git_object(path: Path):
    manifest = _read_package_manifest(path)
    class_name = manifest.get("edsl_class_name") or manifest.get("object_type")
    if class_name == "Survey":
        from edsl.surveys import Survey

        return Survey.git.load(path)
    if class_name == "AgentList":
        from edsl.agents import AgentList

        return AgentList.git.load(path)
    if class_name == "Jobs":
        from edsl.jobs import Jobs

        return Jobs.git.load(path)
    if class_name == "Results":
        from edsl.results import Results

        return Results.git.load(path)
    if class_name == "ScenarioList":
        from edsl.scenarios import ScenarioList

        return ScenarioList.git.load(path)
    if class_name == "ModelList":
        from edsl.language_models import ModelList

        return ModelList.git.load(path)
    _error(
        "UNSUPPORTED_OBJECT",
        f"Object package type does not support push: {class_name or 'unknown'}",
        suggestion="Currently supported package types: Survey, AgentList, Jobs, Results, ScenarioList, ModelList.",
        exit_code=EXIT_USAGE,
    )


def _object_has_coop_info(obj) -> bool:
    try:
        return obj.git._read_coop_info() is not None
    except Exception:
        return False


# ---------------------------------------------------------------------------
# edsl auth
# ---------------------------------------------------------------------------

@auth.command("login")
@click.option("--api_key", default=None, help="Provide API key directly.")
def auth_login(api_key):
    """Store an API key for Expected Parrot / Coop access."""
    from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler

    handler = ExpectedParrotKeyHandler()

    if api_key:
        handler.store_ep_api_key(api_key)
        _output({"message": "API key stored successfully"})
    else:
        # Browser-based flow
        import secrets
        from edsl.config import CONFIG

        edsl_auth_token = secrets.token_urlsafe(16)
        login_url = f"{CONFIG.EXPECTED_PARROT_URL}/login?edsl_auth_token={edsl_auth_token}"
        _output({
            "action": "awaiting_login",
            "login_url": login_url,
        })

        # Poll for key
        try:
            from edsl.coop import Coop
            import webbrowser
            webbrowser.open(login_url)
            coop_client = Coop()
            api_key_result = coop_client._poll_for_api_key(edsl_auth_token)
            if api_key_result:
                handler.store_ep_api_key(api_key_result)
                _output({"message": "API key stored successfully"})
            else:
                _error("AUTH_TIMEOUT", "Timed out waiting for login.",
                       suggestion="Try again or use --api_key to provide a key directly.",
                       exit_code=EXIT_AUTH)
        except Exception as e:
            _error("AUTH_ERROR", str(e),
                   suggestion="Try again or use --api_key to provide a key directly.",
                   exit_code=EXIT_AUTH)


@auth.command("status")
def auth_status():
    """Check authentication status."""
    import os

    env_key = os.environ.get("EXPECTED_PARROT_API_KEY", "")
    has_key = bool(env_key)

    data = {
        "authenticated": has_key,
        "api_key_source": "environment" if has_key else "none",
    }

    # Try to get username if authenticated
    if has_key:
        try:
            from edsl.coop import Coop
            # Suppress any stdout from Coop internals
            import io
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                coop_client = Coop()
                profile = coop_client.get_profile()
            finally:
                sys.stdout = old_stdout
            if hasattr(profile, 'get'):
                data["username"] = profile.get("username", None)
            elif hasattr(profile, 'username'):
                data["username"] = profile.username
        except Exception:
            data["username"] = None

    _output(data)


@auth.command("balance")
def auth_balance():
    """Get the authenticated Expected Parrot credit balance."""
    _output(_get_expected_parrot_balance())


@app.command("balance")
def balance():
    """Get the authenticated Expected Parrot credit balance."""
    _output(_get_expected_parrot_balance())


def _get_expected_parrot_balance() -> dict:
    """Return Expected Parrot balance data using the configured API key."""
    from edsl.coop.ep_key_handling import ExpectedParrotKeyHandler

    api_key = ExpectedParrotKeyHandler().get_ep_api_key()
    if not api_key:
        _error(
            "AUTH_REQUIRED",
            "No Expected Parrot API key is configured.",
            suggestion="Run 'edsl auth login --api_key <key>' or set EXPECTED_PARROT_API_KEY.",
            exit_code=EXIT_AUTH,
        )

    try:
        from edsl.coop import Coop

        import io

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            balance_info = Coop(api_key=api_key).get_balance()
        finally:
            sys.stdout = old_stdout
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "BALANCE_ERROR",
            str(e),
            suggestion="Check your Expected Parrot API key and network connection.",
            exit_code=EXIT_REMOTE,
        )

    if hasattr(balance_info, "items"):
        return dict(balance_info)
    return {"balance": balance_info}


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


@app.command("metadata")
@click.argument("target")
def metadata(target):
    """Get metadata for a remote object or local .ep package."""
    try:
        from edsl.coop import Coop

        identifier = _remote_identifier(target)
        _output(_jsonable(Coop().get_metadata(identifier)))
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "METADATA_ERROR",
            str(e),
            suggestion="Check the object identifier and your Expected Parrot API key.",
            exit_code=EXIT_REMOTE,
        )


@app.command("update-metadata")
@click.argument("target")
@click.option("--description", default=None, help="New object description.")
@click.option("--alias", default=None, help="New object alias.")
@click.option("--visibility", default=None, help="private, public, or unlisted.")
def update_metadata(target, description, alias, visibility):
    """Update remote object metadata without changing object contents."""
    if description is None and alias is None and visibility is None:
        _error(
            "USAGE_ERROR",
            "Nothing to update.",
            suggestion="Provide at least one of --description, --alias, or --visibility.",
            exit_code=EXIT_USAGE,
        )
    try:
        from edsl.coop import Coop

        identifier = _remote_identifier(target)
        result = Coop().patch_metadata(
            identifier,
            description=description,
            alias=alias,
            visibility=visibility,
        )
        _output(_jsonable(result))
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "METADATA_ERROR",
            str(e),
            suggestion="Check the object identifier, metadata values, and API key.",
            exit_code=EXIT_REMOTE,
        )


@app.command("share")
@click.argument("target")
@click.option("--user", "username_or_email", required=True, help="Expected Parrot username or email.")
def share(target, username_or_email):
    """Share a remote object or local .ep package with a user."""
    try:
        from edsl.coop import Coop

        identifier = _remote_identifier(target)
        _output(_jsonable(Coop().share_object(identifier, username_or_email)))
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "SHARE_ERROR",
            str(e),
            suggestion="Check the object identifier, recipient, and API key.",
            exit_code=EXIT_REMOTE,
        )


@app.command("unshare")
@click.argument("target")
@click.option("--user", "username_or_email", required=True, help="Expected Parrot username or email.")
def unshare(target, username_or_email):
    """Remove a user's access to a remote object or local .ep package."""
    try:
        from edsl.coop import Coop

        identifier = _remote_identifier(target)
        _output(_jsonable(Coop().unshare_object(identifier, username_or_email)))
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "SHARE_ERROR",
            str(e),
            suggestion="Check the object identifier, recipient, and API key.",
            exit_code=EXIT_REMOTE,
        )


@app.command("shared")
@click.argument("target")
def shared(target):
    """List users a remote object or local .ep package is shared with."""
    try:
        from edsl.coop import Coop

        identifier = _remote_identifier(target)
        _output(_jsonable(Coop().get_object_shared_users(identifier)))
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "SHARE_ERROR",
            str(e),
            suggestion="Check the object identifier and API key.",
            exit_code=EXIT_REMOTE,
        )


@app.command("delete")
@click.argument("target")
@click.option("--yes", is_flag=True, default=False, help="Confirm deletion.")
def delete(target, yes):
    """Delete a remote object."""
    if not yes:
        _error(
            "CONFIRMATION_REQUIRED",
            "Deleting a remote object requires --yes.",
            suggestion="Re-run with --yes if you intend to permanently delete this object.",
            exit_code=EXIT_USAGE,
        )
    try:
        from edsl.coop import Coop

        identifier = _remote_identifier(target)
        _output(_jsonable(Coop().delete(identifier)))
    except SystemExit:
        raise
    except Exception as e:
        _error(
            "DELETE_ERROR",
            str(e),
            suggestion="Check the object identifier and API key.",
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
# edsl schema
# ---------------------------------------------------------------------------

def _get_schema_classes():
    """Return a map of schema names to (class, description) for all introspectable types."""
    from edsl.agents import Agent, AgentList
    from edsl.scenarios import Scenario, ScenarioList
    from edsl.surveys import Survey
    from edsl.language_models import Model
    from edsl.language_models.model_list import ModelList
    from edsl.jobs import Jobs
    from edsl.results import Results
    from edsl.questions.register_questions_meta import RegisterQuestionsMeta

    # Force import of question types

    classes = {
        "Agent": (Agent, "A respondent with traits and optional instructions."),
        "AgentList": (AgentList, "A list of Agent objects. Pass to 'edsl run --agent_list'."),
        "Scenario": (Scenario, "Template parameters for questions using Jinja2 {{variable}} syntax."),
        "ScenarioList": (ScenarioList, "A list of Scenario objects. Pass to 'edsl run --scenario_list'."),
        "Survey": (Survey, "A collection of questions with optional flow logic."),
        "Model": (Model, "An LLM configuration. Pass to 'edsl run --model'."),
        "ModelList": (ModelList, "A list of Model objects. Pass to 'edsl run --model_list'."),
        "Jobs": (Jobs, "A complete job spec (survey + agents + models + scenarios). Pass to 'edsl run --jobs'."),
        "Results": (Results, "Output from a job run. Pass to 'edsl results select --file'."),
    }

    # Add question types
    type_map = RegisterQuestionsMeta.question_types_to_classes()
    for qtype, cls in sorted(type_map.items()):
        classes[qtype] = (cls, f"Question type '{qtype}'.")

    return classes


@schema.command("list")
def schema_list():
    """List all types available for schema introspection."""
    classes = _get_schema_classes()

    object_types = []
    question_types = []
    for name, (cls, desc) in classes.items():
        entry = {"name": name, "description": desc}
        if name[0].isupper():
            object_types.append(entry)
        else:
            question_types.append(entry)

    _output({"object_types": object_types, "question_types": question_types})


@schema.command("show")
@click.option("--class", "class_name", default=None, help="EDSL class to inspect (e.g. Agent, ScenarioList, Survey, Jobs).")
@click.option("--question_type", default=None, help="Question type to inspect (e.g. free_text, multiple_choice).")
def schema_show(class_name, question_type):
    """Show the serialized schema of an EDSL type via its .example().to_dict()."""
    if class_name and question_type:
        _error("USAGE_ERROR", "--class and --question_type are mutually exclusive.",
               exit_code=EXIT_USAGE)
    if not class_name and not question_type:
        _error("USAGE_ERROR", "Provide one of --class or --question_type.",
               suggestion="Use 'edsl schema list' to see available types.",
               exit_code=EXIT_USAGE)

    classes = _get_schema_classes()
    schema_type = class_name or question_type

    if schema_type not in classes:
        # Suggest from the right category
        if class_name:
            available = sorted(n for n in classes if n[0].isupper())
        else:
            available = sorted(n for n in classes if n[0].islower())
        _error("NOT_FOUND", f"Unknown type: '{schema_type}'",
               suggestion=f"Available: {', '.join(available)}",
               exit_code=EXIT_NOT_FOUND)

    cls, desc = classes[schema_type]

    try:
        example = cls.example()
        serialized = example.to_dict()
    except Exception as e:
        _error("RUN_ERROR", f"Failed to generate example for '{schema_type}': {e}",
               exit_code=EXIT_ERROR)

    _output({
        "type": schema_type,
        "description": desc,
        "example": serialized,
    })


@schema.command("error")
def schema_error():
    """Documents the error envelope and all known error codes."""
    _output({
        "envelope": {
            "status": "error",
            "error": {
                "code": "string — error code",
                "message": "string — human-readable description",
                "suggestion": "string — what to do next (optional)",
                "details": "array — detailed sub-errors for validation (optional)",
            },
        },
        "exit_codes": {
            "0": "Success",
            "1": "General error",
            "2": "Usage error (bad arguments, conflicting flags)",
            "3": "Resource not found",
            "4": "Authentication error",
            "5": "Validation error",
            "6": "Remote service error",
        },
        "known_error_codes": [
            "FILE_NOT_FOUND", "INVALID_JSON", "USAGE_ERROR",
            "UNKNOWN_QUESTION_TYPE", "INVALID_MODEL", "MODEL_LIST_ERROR",
            "AUTH_TIMEOUT", "AUTH_ERROR",
            "VALIDATION_ERROR", "RUN_ERROR",
            "COOP_ERROR", "BALANCE_ERROR", "AUTH_REQUIRED", "NOT_FOUND",
            "CONFIRMATION_REQUIRED", "DELETE_ERROR", "DEPENDENCY_ERROR",
            "HUMANIZE_ERROR", "JOBS_ERROR", "METADATA_ERROR", "PROFILE_ERROR",
            "RESULTS_NOT_AVAILABLE", "SEARCH_ERROR", "SETTINGS_ERROR",
            "SHARE_ERROR", "UNSUPPORTED_OBJECT",
        ],
    })


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
# edsl run
# ---------------------------------------------------------------------------

@app.command()
@click.option("--jobs", default=None, help="Path to serialized Jobs JSON.")
@click.option("--survey", default=None, help="Path to serialized Survey JSON.")
@click.option("--json", "--json_data", "json_data", default=None, help="Inline JSON.")
@click.option("--question", "-q", default=None, help="Question text.")
@click.option("--agent_list", default=None, help="Path to AgentList JSON.")
@click.option("--scenario_list", default=None, help="Path to ScenarioList JSON.")
@click.option("--model_list", default=None, help="Path to ModelList JSON.")
@click.option("--model", "-m", default=None, help="Model name.")
@click.option("--type", "-t", "qtype", default="free_text", help="Question type.")
@click.option("--options", default=None, help="JSON array for MC/checkbox.")
@click.option("--name", "-n", default=None, help="Question name.")
@click.option("--progress/--no_progress", default=False, help="Show progress bar on stderr.")
@click.option("--background", is_flag=True, default=False, help="Submit remote job and return immediately.")
@click.option("--wait", is_flag=True, default=False, help="With --background, poll until the remote job reaches a terminal status.")
@click.option("--poll_interval", default=10.0, type=float, help="Seconds between status checks with --wait.")
@click.option("--timeout", default=None, type=float, help="Maximum seconds to wait with --wait.")
@click.option("--remote_inference_description", default=None, help="Description for the remote job.")
@click.option("--remote_inference_results_visibility", default="private", type=click.Choice(["private", "public", "unlisted"]), help="Visibility for remote results.")
@click.option("--results_description", default=None, help="Description for the remote results object.")
@click.option("--fresh", is_flag=True, default=False, help="Ignore cache.")
@click.option("--save", default=None, help="Save Results JSON to file.")
@click.option("--output", "-o", "output_path", default=None, help="Save Results to a file or .ep package.")
@click.argument("input_path", required=False, type=click.Path(exists=True))
def run(jobs, survey, json_data, question, agent_list, scenario_list,
        model_list, model, qtype, options, name, progress, background,
        wait, poll_interval, timeout, remote_inference_description,
        remote_inference_results_visibility, results_description, fresh,
        save, output_path, input_path):
    """Run question(s) and get results."""
    from edsl.jobs import Jobs
    from edsl.agents import AgentList as AgentListClass
    from edsl.scenarios import ScenarioList as ScenarioListClass
    from edsl.language_models import Model as ModelClass
    from edsl.language_models.model_list import ModelList as ModelListClass

    # Check mutually exclusive model flags
    if model and model_list:
        _error("USAGE_ERROR", "--model and --model_list are mutually exclusive.",
               exit_code=EXIT_USAGE)
    if wait and not background:
        _error("USAGE_ERROR", "--wait requires --background.",
               exit_code=EXIT_USAGE)
    if poll_interval <= 0:
        _error("USAGE_ERROR", "--poll_interval must be greater than 0.",
               exit_code=EXIT_USAGE)
    if timeout is not None and timeout <= 0:
        _error("USAGE_ERROR", "--timeout must be greater than 0.",
               exit_code=EXIT_USAGE)

    # Step 1: Determine base input source
    sources = []
    if input_path:
        sources.append("path")
    if jobs:
        sources.append("jobs")
    if survey:
        sources.append("survey")
    if json_data:
        sources.append("json")
    if question:
        sources.append("question")

    stdin_data = _read_stdin() if not sources else None
    if stdin_data:
        sources.append("stdin")

    if len(sources) > 1:
        _error("USAGE_ERROR",
               f"Multiple input sources provided: {', '.join(sources)}. Only one allowed.",
               suggestion="Use exactly one of: INPUT_PATH, --jobs, --survey, --json_data, --question, or stdin.",
               exit_code=EXIT_USAGE)

    input_mode = sources[0] if sources else None
    if not input_mode:
        _error("USAGE_ERROR", "No input provided.",
               suggestion="Use INPUT_PATH, --jobs, --survey, --json_data, --question, or pipe JSON via stdin.",
               exit_code=EXIT_USAGE)

    # Step 2: Build the Jobs object
    try:
        job = _build_job(
            input_mode=input_mode,
            input_path=input_path, jobs_path=jobs, survey_path=survey, json_str=json_data,
            stdin_data=stdin_data, question_text=question,
            question_type=qtype, question_options=options, question_name=name,
        )
    except SystemExit:
        raise
    except Exception as e:
        _error("RUN_ERROR", f"Failed to build job: {e}",
               suggestion="Use 'edsl validate' to check your input.",
               exit_code=EXIT_ERROR)

    # Step 3: Apply component overrides
    try:
        if agent_list:
            data = _read_json_file(agent_list)
            job = Jobs(
                survey=job.survey,
                agents=AgentListClass.from_dict(data),
                models=job.models,
                scenarios=job.scenarios,
            )
        if scenario_list:
            data = _read_json_file(scenario_list)
            job = Jobs(
                survey=job.survey,
                agents=job.agents,
                models=job.models,
                scenarios=ScenarioListClass.from_dict(data),
            )
        if model_list:
            data = _read_json_file(model_list)
            job = Jobs(
                survey=job.survey,
                agents=job.agents,
                models=ModelListClass.from_dict(data),
                scenarios=job.scenarios,
            )
        if model:
            job = Jobs(
                survey=job.survey,
                agents=job.agents,
                models=[ModelClass(model)],
                scenarios=job.scenarios,
            )
    except SystemExit:
        raise
    except Exception as e:
        _error("RUN_ERROR", f"Failed to apply overrides: {e}", exit_code=EXIT_ERROR)

    # Step 4: Execute
    if background and not wait and (save or output_path):
        _error("USAGE_ERROR", "Background jobs cannot be saved before completion.",
               suggestion="Use 'edsl jobs results <job_uuid> --output results.ep' after the job completes.",
               exit_code=EXIT_USAGE)

    try:
        results_obj = job.run(
            progress_bar=progress,
            background=background,
            remote_inference_description=remote_inference_description,
            remote_inference_results_visibility=remote_inference_results_visibility,
            results_description=results_description,
            fresh=fresh,
            verbose=False,
        )
    except Exception as e:
        _error("RUN_ERROR", f"Job execution failed: {e}", exit_code=EXIT_ERROR)

    # Format output
    if background:
        result_data = []
    else:
        try:
            result_data = []
            for r in results_obj:
                entry = {}
                # Answer
                entry["answer"] = dict(r.get("answer", {})) if hasattr(r, 'get') else {}

                # Agent, scenario, model
                if hasattr(r, 'agent'):
                    entry["agent"] = {"traits": dict(r.agent.traits) if hasattr(r.agent, 'traits') else {}}
                if hasattr(r, 'scenario'):
                    entry["scenario"] = dict(r.scenario) if r.scenario else {}
                if hasattr(r, 'model'):
                    entry["model"] = {
                        "model": r.model.model if hasattr(r.model, 'model') else str(r.model),
                        "service": r.model.inference_service if hasattr(r.model, 'inference_service') else "",
                    }
                result_data.append(entry)
        except Exception:
            # Fallback: use select().to_dicts()
            try:
                result_data = results_obj.select("answer.*").to_dicts(remove_prefix=True)
            except Exception:
                result_data = []

    saved = None
    if save and output_path:
        _error("USAGE_ERROR", "--save and --output are mutually exclusive.",
               exit_code=EXIT_USAGE)

    # Save if requested
    if (save or output_path) and not background:
        try:
            saved = _save_results(results_obj, output_path or save)
        except SystemExit:
            raise
        except Exception as e:
            _error("RUN_ERROR", f"Failed to save results: {e}", exit_code=EXIT_ERROR)

    meta = {
        "input_mode": input_mode,
        "model_count": len(job.models) if hasattr(job, 'models') else 0,
        "agent_count": len(job.agents) if hasattr(job, 'agents') else 0,
        "scenario_count": len(job.scenarios) if hasattr(job, 'scenarios') else 0,
        "result_count": len(result_data),
    }
    if background:
        meta["remote_job"] = _remote_job_meta_from_results(results_obj)
        if wait:
            wait_data = _wait_for_remote_job(
                meta["remote_job"].get("job_uuid"),
                poll_interval=poll_interval,
                timeout=timeout,
                output_path=output_path or save,
            )
            meta["remote_job"]["wait"] = wait_data
            if wait_data.get("saved") is not None:
                meta["saved"] = wait_data["saved"]
    if saved is not None:
        meta["saved"] = saved

    _output({"results": result_data, "meta": meta})


def _wait_for_remote_job(
    job_uuid: str,
    poll_interval: float,
    timeout: Optional[float],
    output_path: Optional[str],
) -> dict:
    if not job_uuid:
        _error(
            "RUN_ERROR",
            "Background job did not return a job UUID.",
            exit_code=EXIT_ERROR,
        )

    from edsl.coop import Coop

    coop = Coop()
    terminal_statuses = {
        "completed",
        "failed",
        "partial_failed",
        "partially_failed",
        "cancelled",
        "canceled",
    }
    started_at = time.monotonic()
    polls = 0

    while True:
        status_data = coop.new_remote_inference_get(job_uuid=job_uuid)
        polls += 1
        last_status = status_data.get("status")
        normalized_status = str(last_status or "").lower()
        if normalized_status in terminal_statuses:
            break
        if timeout is not None and time.monotonic() - started_at >= timeout:
            return {
                "completed": False,
                "timed_out": True,
                "polls": polls,
                "elapsed_seconds": round(time.monotonic() - started_at, 3),
                "last_status": last_status,
                "status": _jsonable(status_data),
            }
        time.sleep(poll_interval)

    data = {
        "completed": normalized_status == "completed",
        "timed_out": False,
        "polls": polls,
        "elapsed_seconds": round(time.monotonic() - started_at, 3),
        "last_status": last_status,
        "status": _jsonable(status_data),
    }

    results_uuid = status_data.get("results_uuid") if status_data else None
    if normalized_status == "completed" and results_uuid:
        results_obj = coop.pull(results_uuid, expected_object_type="results")
        data["results_uuid"] = results_uuid
        data["result_count"] = len(results_obj) if hasattr(results_obj, "__len__") else None
        if output_path:
            data["saved"] = _save_results(results_obj, output_path)
    elif normalized_status in {"failed", "partial_failed", "partially_failed"}:
        data["commands"] = {
            "errors": f"edsl jobs errors {job_uuid} --output error.md",
        }

    return data




def _remote_job_meta_from_results(results_obj) -> dict:
    job_info = getattr(results_obj, "job_info", None)
    if job_info is None:
        return {"background": True}

    creation_data = getattr(job_info, "creation_data", None)
    logger = getattr(job_info, "logger", None)
    jobs_info = getattr(logger, "jobs_info", None)
    meta = {
        "background": True,
        "job_uuid": getattr(job_info, "job_uuid", None),
        "creation_data": _jsonable(creation_data) if creation_data is not None else None,
        "new_format": getattr(job_info, "new_format", None),
    }
    for field in (
        "progress_bar_url",
        "remote_inference_url",
        "remote_cache_url",
        "results_uuid",
        "results_url",
        "error_report_url",
    ):
        value = getattr(jobs_info, field, None) if jobs_info is not None else None
        if value is not None:
            meta[field] = value
    meta["commands"] = {
        "status": f"edsl jobs status {meta['job_uuid']}" if meta.get("job_uuid") else None,
        "results": f"edsl jobs results {meta['job_uuid']} --output results.ep" if meta.get("job_uuid") else None,
        "errors": f"edsl jobs errors {meta['job_uuid']} --output error.md" if meta.get("job_uuid") else None,
    }
    return meta


def _build_job(input_mode, input_path, jobs_path, survey_path, json_str, stdin_data,
               question_text, question_type, question_options, question_name):
    """Build a Jobs object from the determined input source."""
    from edsl.jobs import Jobs
    from edsl.surveys import Survey as SurveyClass
    from edsl.questions.register_questions_meta import RegisterQuestionsMeta


    if input_mode == "path":
        return _load_jobs_from_path(input_path)

    if input_mode == "jobs":
        return _load_jobs_from_path(jobs_path)

    if input_mode == "survey":
        data = _read_json_file(survey_path)
        sv = SurveyClass.from_dict(data)
        return Jobs(survey=sv)

    if input_mode in ("json", "stdin"):
        raw_str = json_str if input_mode == "json" else stdin_data
        try:
            data = json.loads(raw_str)
        except json.JSONDecodeError as e:
            _error("INVALID_JSON", f"Failed to parse JSON: {e}", exit_code=EXIT_USAGE)
        return _build_job_from_json(data)

    if input_mode == "question":
        qname = question_name or "q0"
        type_map = RegisterQuestionsMeta.question_types_to_classes()
        if question_type not in type_map:
            _error("UNKNOWN_QUESTION_TYPE", f"Unknown type: '{question_type}'",
                   suggestion=f"Available: {', '.join(sorted(type_map.keys()))}",
                   exit_code=EXIT_USAGE)
        kwargs = {"question_name": qname, "question_text": question_text}
        if question_options:
            try:
                kwargs["question_options"] = json.loads(question_options)
            except json.JSONDecodeError:
                _error("INVALID_JSON", "Failed to parse --options as JSON array.",
                       exit_code=EXIT_USAGE)
        cls = type_map[question_type]
        q = cls(**kwargs)
        sv = SurveyClass(questions=[q])
        return Jobs(survey=sv)

    _error("USAGE_ERROR", f"Unknown input mode: {input_mode}", exit_code=EXIT_USAGE)


def _load_jobs_from_path(path: str):
    path_obj = Path(path)
    if path_obj.suffix == ".ep":
        from edsl.jobs import Jobs

        return Jobs.git.load(path_obj)
    data = _read_json_file(path)
    from edsl.jobs import Jobs

    return Jobs.from_dict(data)


def _save_results(results_obj, output_path: str) -> dict:
    path = Path(output_path)
    if path.suffix == ".ep":
        info = results_obj.git.save(path)
        return {
            "path": info.get("path", str(path)),
            "format": "ep",
            "object_type": "Results",
            "commit": info.get("commit"),
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(results_obj.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    return {"path": str(path), "format": "json", "object_type": "Results"}


def _build_job_from_json(data: dict):
    """Build a Jobs from parsed JSON, auto-detecting shape."""
    from edsl.jobs import Jobs
    from edsl.surveys import Survey as SurveyClass
    from edsl.agents import Agent
    from edsl.scenarios import Scenario
    from edsl.language_models import Model as ModelClass
    from edsl.questions.register_questions_meta import RegisterQuestionsMeta

    # Shape 1: serialized Jobs (has "survey" key)
    if "survey" in data and isinstance(data["survey"], dict):
        return Jobs.from_dict(data)

    # Shape 2: lightweight job spec (has "questions" array)
    if "questions" in data and isinstance(data["questions"], list):
        type_map = RegisterQuestionsMeta.question_types_to_classes()
        questions = []
        for i, qd in enumerate(data["questions"]):
            qtype = qd.pop("type", qd.pop("question_type", "free_text"))
            if "question_name" not in qd:
                qd["question_name"] = f"q{i}"
            if qtype not in type_map:
                _error("UNKNOWN_QUESTION_TYPE", f"Unknown type in questions[{i}]: '{qtype}'",
                       exit_code=EXIT_VALIDATION)
            questions.append(type_map[qtype](**qd))

        sv = SurveyClass(questions=questions)
        agents = [Agent(traits=a.get("traits", a)) for a in data.get("agents", [])]
        scenarios = [Scenario(s) for s in data.get("scenarios", [])]
        models_list = [ModelClass(m) if isinstance(m, str) else ModelClass(**m) for m in data.get("models", [])]

        return Jobs(
            survey=sv,
            agents=agents or None,
            models=models_list or None,
            scenarios=scenarios or None,
        )

    # Shape 3: single question shorthand
    if "type" in data and "question_text" in data:
        type_map = RegisterQuestionsMeta.question_types_to_classes()
        qtype = data.pop("type", data.pop("question_type", "free_text"))
        if "question_name" not in data:
            data["question_name"] = "q0"
        if qtype not in type_map:
            _error("UNKNOWN_QUESTION_TYPE", f"Unknown type: '{qtype}'",
                   exit_code=EXIT_VALIDATION)
        q = type_map[qtype](**{k: v for k, v in data.items() if k != "question_type"})
        sv = SurveyClass(questions=[q])
        return Jobs(survey=sv)

    _error("VALIDATION_ERROR",
           "Could not determine JSON shape. Expected serialized Jobs, lightweight job spec, or single question.",
           suggestion="Use 'edsl schema survey' to see accepted shapes.",
           exit_code=EXIT_VALIDATION)


# ---------------------------------------------------------------------------
# edsl search
# ---------------------------------------------------------------------------

def _search_objects(query, obj_type, visibility, community, page, page_size):
    try:
        from edsl.coop import Coop
        coop_client = Coop()

        kwargs = {
            "page": page,
            "page_size": page_size,
            "community": community,
        }
        if query:
            kwargs["search_query"] = query
        if obj_type:
            kwargs["object_type"] = obj_type
        if visibility:
            kwargs["visibility"] = visibility

        result = coop_client.list(**kwargs)

        objects = []
        for item in result:
            obj = {}
            if hasattr(item, 'items'):
                obj = dict(item)
            elif hasattr(item, '__dict__'):
                obj = {k: v for k, v in item.__dict__.items() if not k.startswith('_')}
            else:
                obj = dict(item) if hasattr(item, '__iter__') else {"value": str(item)}
            objects.append(obj)

        data = {
            "objects": objects,
            "page": page,
            "page_size": page_size,
            "returned_count": len(objects),
            "query": query,
            "type": obj_type,
            "visibility": visibility,
            "community": community,
        }
        for attr in ("current_page", "total_pages", "total_count"):
            if hasattr(result, attr):
                data[attr] = getattr(result, attr)
        if hasattr(result, "page_size"):
            data["page_size"] = getattr(result, "page_size")
        _output(data)

    except SystemExit:
        raise
    except Exception as e:
        _error("SEARCH_ERROR", str(e),
               suggestion="Check your API key with 'edsl auth status'.",
               exit_code=EXIT_REMOTE)


@app.command("search")
@click.option("--query", "-q", default=None, help="Search by description.")
@click.option("--type", "obj_type", default=None, help="Filter by object type.")
@click.option("--visibility", default=None, help="public, private, unlisted.")
@click.option("--community", is_flag=True, default=False, help="Search community objects.")
@click.option("--page", default=1, type=int, help="Page number.")
@click.option("--page_size", default=10, type=int, help="Results per page (max 100).")
def search(query, obj_type, visibility, community, page, page_size):
    """Search for shared EDSL objects."""
    _search_objects(query, obj_type, visibility, community, page, page_size)




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
