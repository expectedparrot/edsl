"""
EDSL CLI — agent-friendly interface. All output is JSON on stdout.

Entry point: edsl = "edsl.__main__:main" (pyproject.toml)
"""

import sys
import json
from typing import Optional
from pathlib import Path

import click

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
            "commands": ["run", "models", "info", "validate", "schema", "auth", "results", "coop"],
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
            "commands": ["login", "status"],
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
def coop(ctx):
    """Search, fetch, and share objects via Coop."""
    if ctx.invoked_subcommand is None:
        _output({
            "commands": ["search", "pull", "push"],
            "help": "Use 'edsl coop <command> --help' for details.",
        })


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
        "config": CONFIG.to_dict(),
        "api_key_configured": bool(api_key),
    })


# ---------------------------------------------------------------------------
# edsl models
# ---------------------------------------------------------------------------

@app.command()
@click.option("--service", default=None, help="Filter by service name.")
@click.option("--search", default=None, help="Wildcard search pattern.")
def models(service, search):
    """List available models."""
    from edsl.language_models import Model

    try:
        available = Model.available(search_term=search or None, service_name=service or None)
    except Exception:
        # Some services may fail to import; try with local_only
        try:
            available = Model.available(search_term=search or None, service_name=service or None, local_only=True)
        except Exception as e:
            _error("MODEL_LIST_ERROR", str(e))

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

    model_list = []
    for m in available:
        model_name = m.model if hasattr(m, 'model') else str(m)
        service_name = getattr(m, '_inference_service_', '') or getattr(m, 'inference_service', '') or ""
        model_list.append({
            "model_name": model_name,
            "service_name": service_name,
            "configured": service_name in configured_services,
        })

    # Sort alphabetically by service then model
    model_list.sort(key=lambda x: (x["service_name"], x["model_name"]))
    _output({"models": model_list})


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
            "COOP_ERROR", "NOT_FOUND",
        ],
    })


# ---------------------------------------------------------------------------
# edsl validate
# ---------------------------------------------------------------------------

@app.command()
@click.option("--file", "file_path", default=None, help="Path to JSON file to validate.")
@click.option("--json_data", default=None, help="Inline JSON string.")
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
@click.option("--json_data", default=None, help="Inline JSON.")
@click.option("--question", "-q", default=None, help="Question text.")
@click.option("--agent_list", default=None, help="Path to AgentList JSON.")
@click.option("--scenario_list", default=None, help="Path to ScenarioList JSON.")
@click.option("--model_list", default=None, help="Path to ModelList JSON.")
@click.option("--model", "-m", default=None, help="Model name.")
@click.option("--type", "-t", "qtype", default="free_text", help="Question type.")
@click.option("--options", default=None, help="JSON array for MC/checkbox.")
@click.option("--name", "-n", default=None, help="Question name.")
@click.option("--progress/--no_progress", default=False, help="Show progress bar on stderr.")
@click.option("--fresh", is_flag=True, default=False, help="Ignore cache.")
@click.option("--save", default=None, help="Save Results JSON to file.")
def run(jobs, survey, json_data, question, agent_list, scenario_list,
        model_list, model, qtype, options, name, progress, fresh, save):
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

    # Step 1: Determine base input source
    sources = []
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
               suggestion="Use exactly one of: --jobs, --survey, --json_data, --question, or stdin.",
               exit_code=EXIT_USAGE)

    input_mode = sources[0] if sources else None
    if not input_mode:
        _error("USAGE_ERROR", "No input provided.",
               suggestion="Use --jobs, --survey, --json_data, --question, or pipe JSON via stdin.",
               exit_code=EXIT_USAGE)

    # Step 2: Build the Jobs object
    try:
        job = _build_job(
            input_mode=input_mode,
            jobs_path=jobs, survey_path=survey, json_str=json_data,
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
    try:
        results_obj = job.run(
            progress_bar=progress,
            fresh=fresh,
            verbose=False,
        )
    except Exception as e:
        _error("RUN_ERROR", f"Job execution failed: {e}", exit_code=EXIT_ERROR)

    # Format output
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

    # Save if requested
    if save:
        try:
            save_path = Path(save)
            save_path.write_text(json.dumps(results_obj.to_dict(), indent=2, default=str))
        except Exception:
            pass

    meta = {
        "input_mode": input_mode,
        "model_count": len(job.models) if hasattr(job, 'models') else 0,
        "agent_count": len(job.agents) if hasattr(job, 'agents') else 0,
        "scenario_count": len(job.scenarios) if hasattr(job, 'scenarios') else 0,
        "result_count": len(result_data),
    }

    _output({"results": result_data, "meta": meta})


def _build_job(input_mode, jobs_path, survey_path, json_str, stdin_data,
               question_text, question_type, question_options, question_name):
    """Build a Jobs object from the determined input source."""
    from edsl.jobs import Jobs
    from edsl.surveys import Survey as SurveyClass
    from edsl.questions.register_questions_meta import RegisterQuestionsMeta


    if input_mode == "jobs":
        data = _read_json_file(jobs_path)
        return Jobs.from_dict(data)

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
# edsl results
# ---------------------------------------------------------------------------

@results.command("columns")
@click.option("--file", "file_path", required=True, help="Path to serialized Results JSON.")
def results_columns(file_path):
    """List available columns in a Results file."""
    data = _read_json_file(file_path)
    try:
        from edsl.results import Results
        results_obj = Results.from_dict(data)
        _output({"columns": sorted(results_obj.columns)})
    except Exception as e:
        _error("VALIDATION_ERROR", f"Failed to load Results: {e}", exit_code=EXIT_ERROR)


@results.command("select")
@click.option("--file", "file_path", required=True, help="Path to serialized Results JSON.")
@click.option("--column", multiple=True, help="Column to select. Repeat for multiple: --column answer.q0 --column agent.age")
@click.option("--filter", "-f", "filter_expr", default=None, help="Filter expression.")
@click.option("--order_by", default=None, help="Sort by column.")
@click.option("--csv", "as_csv", is_flag=True, default=False, help="Output as CSV.")
@click.option("--limit", default=None, type=int, help="Max rows.")
def results_select(file_path, column, filter_expr, order_by, as_csv, limit):
    """Extract columns from a Results file with optional filtering."""
    data = _read_json_file(file_path)
    try:
        from edsl.results import Results
        results_obj = Results.from_dict(data)
    except Exception as e:
        _error("VALIDATION_ERROR", f"Failed to load Results: {e}", exit_code=EXIT_ERROR)

    try:
        r = results_obj

        if filter_expr:
            r = r.filter(filter_expr)

        if order_by:
            r = r.order_by(order_by)

        if column:
            dataset = r.select(*column)
        else:
            dataset = r.select()

        rows = dataset.to_dicts(remove_prefix=False)

        if limit and limit > 0:
            rows = rows[:limit]

        if as_csv:
            import io
            import csv as csv_mod
            if rows:
                output = io.StringIO()
                writer = csv_mod.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
                sys.stdout.write(output.getvalue())
            return

        _output({"data": rows})

    except SystemExit:
        raise
    except Exception as e:
        _error("RUN_ERROR", f"Query failed: {e}", exit_code=EXIT_ERROR)


# ---------------------------------------------------------------------------
# edsl coop
# ---------------------------------------------------------------------------

@coop.command("search")
@click.option("--query", "-q", default=None, help="Search by description.")
@click.option("--type", "obj_type", default=None, help="Filter by object type.")
@click.option("--visibility", default=None, help="public, private, unlisted.")
@click.option("--community", is_flag=True, default=False, help="Search community objects.")
@click.option("--page", default=1, type=int, help="Page number.")
@click.option("--page_size", default=10, type=int, help="Results per page (max 100).")
def coop_search(query, obj_type, visibility, community, page, page_size):
    """Search for shared EDSL objects on Coop."""
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

        _output({
            "objects": objects,
            "page": page,
            "page_size": page_size,
        })

    except SystemExit:
        raise
    except Exception as e:
        _error("COOP_ERROR", str(e),
               suggestion="Check your API key with 'edsl auth status'.",
               exit_code=EXIT_REMOTE)


@coop.command("pull")
@click.option("--id", "obj_id", required=True, help="UUID, alias, or URL.")
@click.option("--output", "-o", "output_path", required=True, help="File to write pulled object to.")
def coop_pull(obj_id, output_path):
    """Download an object from Coop and save to a file."""
    try:
        from edsl.coop import Coop
        coop_client = Coop()
        obj = coop_client.pull(obj_id)

        # Serialize
        if hasattr(obj, 'to_dict'):
            serialized = obj.to_dict()
        else:
            serialized = obj

        Path(output_path).write_text(json.dumps(serialized, indent=2, default=str))

        # Build a compact summary for the envelope
        obj_type = type(obj).__name__
        summary = {"saved_to": output_path, "object_type": obj_type}

        # Add useful metadata without dumping the whole object
        if isinstance(serialized, dict):
            summary["top_level_keys"] = list(serialized.keys())
            json_size = len(json.dumps(serialized, default=str))
            summary["json_bytes"] = json_size

        _output(summary)

    except SystemExit:
        raise
    except Exception as e:
        _error("COOP_ERROR", str(e),
               suggestion="Check the ID and your API key.",
               exit_code=EXIT_REMOTE)


@coop.command("push")
@click.option("--file", "file_path", required=True, help="Path to serialized JSON.")
@click.option("--description", default="", help="Object description.")
@click.option("--alias", default=None, help="Short name.")
@click.option("--visibility", default="private", help="public, private, unlisted.")
def coop_push(file_path, description, alias, visibility):
    """Upload a serialized EDSL object to Coop."""
    data = _read_json_file(file_path)

    try:
        from edsl.coop import Coop
        from edsl.base import Base

        # Try to deserialize into an EDSL object
        class_name = data.get("edsl_class_name", "")
        obj = None

        if class_name:
            try:
                obj = Base.from_dict(data)
            except Exception:
                pass

        if obj is None:
            _error("VALIDATION_ERROR",
                   "Could not deserialize file into an EDSL object.",
                   suggestion="Ensure the file was produced by .to_dict() on an EDSL object.",
                   exit_code=EXIT_VALIDATION)

        coop_client = Coop()
        push_kwargs = {"description": description, "visibility": visibility}
        if alias:
            push_kwargs["alias"] = alias

        result = coop_client.push(obj, **push_kwargs)

        # Extract result info
        result_data = {}
        if hasattr(result, 'items'):
            result_data = dict(result)
        elif hasattr(result, '__dict__'):
            result_data = {k: v for k, v in result.__dict__.items() if not k.startswith('_')}
        else:
            result_data = {"result": str(result)}

        _output(result_data)

    except SystemExit:
        raise
    except Exception as e:
        _error("COOP_ERROR", str(e),
               suggestion="Check your API key with 'edsl auth status'.",
               exit_code=EXIT_REMOTE)


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
