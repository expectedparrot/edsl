"""Object inspection commands for the EDSL CLI."""

from __future__ import annotations

from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_USAGE,
    error,
    jsonable,
    load_any_object,
    markdown_page,
    output,
    raw_output_written,
    save_edsl_object,
)


def register(app: click.Group) -> None:
    @app.command("inspect")
    @click.argument("target")
    @click.option("--ref", "--commit", help="Read a local package revision from ep log.")
    @click.option(
        "--type",
        "object_type",
        default=None,
        help="Expected remote object type when inspecting a UUID or URL.",
    )
    @click.option(
        "--sample",
        default=None,
        type=int,
        help="Number of JSON summary samples (default 3).",
    )
    @click.option(
        "--markdown", is_flag=True, help="Print a page of Markdown to stdout."
    )
    @click.option("--page", type=int, help="One-based Markdown page (default 1).")
    @click.option(
        "--page-size",
        "--page_size",
        type=int,
        help="Entries per Markdown page (default 10).",
    )
    @click.option(
        "--save",
        "save_path",
        default=None,
        help="Save the inspected object to a local .ep package or serialized file.",
    )
    def inspect_object(
        target: str,
        ref: str | None,
        object_type: str | None,
        sample: int | None,
        markdown: bool,
        page: int | None,
        page_size: int | None,
        save_path: str | None,
    ):
        """Inspect a local EDSL object package/file or remote object.

        \b
        Examples:
          ep inspect survey.ep
          ep inspect survey.ep --ref HEAD~1 --markdown
          ep inspect agents.ep --sample 5
          ep inspect results.ep --sample 10
          ep inspect <uuid> --type Survey
          ep inspect <uuid> --type AgentList --save agents.ep
          ep inspect agents.ep --markdown --page 2 --page-size 5
          ep inspect prompt.json
        """
        try:
            if ref is not None and save_path and save_path != "-":
                source, dest = Path(target), Path(save_path)
                same_file = dest.exists() and source.exists() and dest.samefile(source)
                inside_package = source.is_dir() and source.resolve() in dest.resolve().parents
                if same_file or inside_package:
                    error(
                        "USAGE_ERROR", "A revision must be exported outside the source package.",
                        suggestion="Choose a separate --save path.", exit_code=EXIT_USAGE,
                    )
            if markdown:
                if sample is not None or save_path == "-":
                    error(
                        "USAGE_ERROR",
                        "Use --page-size for Markdown and a file path for --save.",
                        exit_code=EXIT_USAGE,
                    )
                obj = load_any_object(
                    target, expected_object_type=object_type, preview=True, ref=ref
                )
                rendered = markdown_page(obj, page, page_size)
                if save_path:
                    save_edsl_object(obj, save_path, sync_coop=ref is None)
                click.echo(rendered)
                return
            if page is not None or page_size is not None:
                error(
                    "USAGE_ERROR",
                    "Pagination requires --markdown.",
                    exit_code=EXIT_USAGE,
                )
            obj = load_any_object(target, expected_object_type=object_type, ref=ref)
            sample_count = 3 if sample is None else max(0, sample)
            data = _summary(obj, sample=sample_count)
            if ref is not None:
                data["commit"] = obj.git.commit
                if data["object_type"] == "Survey":
                    from .surveys import _question_summary

                    data["sample_questions"] = [
                        _question_summary(q) for q in obj.questions[:sample_count]
                    ]
            if ref is None and isinstance(data.get("stored_survey"), dict) and data["object_type"] == "Results" and Path(target).exists():
                from shlex import quote

                data["stored_survey"]["compare_command"] = (
                    f"ep results check-survey {quote(target)} --against JOB_OR_SURVEY"
                )
            from edsl.language_models.output_token_policy import token_limit_warnings

            model_warnings = token_limit_warnings(getattr(obj, "models", []))
            if save_path:
                data["saved"] = save_edsl_object(obj, save_path, sync_coop=ref is None)
                if raw_output_written(data["saved"]):
                    return
            output(
                data,
                warnings=[
                    {"code": "LOW_REASONING_OUTPUT_LIMIT", "message": message}
                    for message in model_warnings
                ],
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "INSPECT_ERROR",
                f"Failed to inspect object: {e}",
                suggestion="Check the revision with ep log." if ref is not None else "Check the path, UUID, URL, or --type value.",
                exit_code=EXIT_ERROR,
            )


def _summary(obj, sample: int) -> dict:
    class_name = type(obj).__name__
    data = {
        "object_type": class_name,
        "length": len(obj) if hasattr(obj, "__len__") else None,
    }

    if class_name == "Survey":
        questions = getattr(obj, "questions", [])
        data.update(
            {
                "question_count": len(questions),
                "question_names": list(getattr(obj, "question_names", [])),
                "question_types": [
                    getattr(q, "question_type", type(q).__name__) for q in questions
                ],
            }
        )
    elif class_name == "AgentList":
        data.update(
            {
                "agent_count": len(obj),
                "trait_keys": _agent_trait_keys(obj),
                "sample": [_agent_summary(agent) for agent in list(obj)[:sample]],
            }
        )
    elif class_name == "ScenarioList":
        data.update(
            {
                "scenario_count": len(obj),
                "keys": _scenario_keys(obj),
                "sample": [jsonable(dict(scenario)) for scenario in list(obj)[:sample]],
            }
        )
    elif class_name == "ModelList":
        data.update(
            {
                "model_count": len(obj),
                "models": [
                    {
                        "model_name": getattr(model, "model", None),
                        "service_name": getattr(model, "_inference_service_", None),
                    }
                    for model in list(obj)[:sample or len(obj)]
                ],
            }
        )
    elif class_name == "Jobs":
        from edsl.language_models.output_token_policy import model_token_policy

        survey = getattr(obj, "survey", None)
        data.update(
            {
                "question_count": len(getattr(survey, "questions", []) or []),
                "question_names": list(getattr(survey, "question_names", []) or []),
                "agent_count": _safe_len(getattr(obj, "agents", None)),
                "scenario_count": _safe_len(getattr(obj, "scenarios", None)),
                "model_count": _safe_len(getattr(obj, "models", None)),
                **obj.assignment_summary(),
                "rehearsal_command": "ep jobs variants JOBS_FILE --help",
                "output_token_policies": [
                    model_token_policy(model) for model in obj.models
                ],
            }
        )
    elif class_name == "Evaluation":
        data.update({
            "question_names": list(obj.survey.question_names),
            "scenario_count": len(obj.scenarios), "agent_count": len(obj.agents),
            "models": [{"service": model.service_name, "model": model.model} for model in obj.models],
            "scenario_fields": sorted({key for scenario in obj.scenarios for key in scenario}),
        })
    elif class_name == "Results":
        columns = sorted(getattr(obj, "columns", []) or [])
        data.update(
            {
                "result_count": len(obj),
                "completion": obj.completion_summary(),
                "columns": columns,
                "answer_columns": [c for c in columns if c.startswith("answer.")],
                "scenario_columns": [c for c in columns if c.startswith("scenario.")],
                "agent_columns": [c for c in columns if c.startswith("agent.")],
                "model_columns": [c for c in columns if c.startswith("model.")],
            }
        )
    elif class_name == "Prompt":
        data.update(_prompt_summary(obj))
    else:
        path = Path(str(obj))
        data["repr"] = str(path) if path.exists() else repr(obj)

    if class_name in {"Jobs", "Results"}:
        survey = getattr(obj, "survey", None)
        if survey is not None:
            data["stored_survey"] = {
                "question_count": len(survey.questions),
                "sample_questions": [
                    {"question_name": q.question_name, "question_type": q.question_type,
                     "question_text": q.question_text} for q in survey.questions[:sample]
                ],
            }
    return data


def _prompt_summary(prompt) -> dict:
    """Describe a prompt's text and template variables without rendering it."""
    from jinja2 import TemplateError

    text = str(prompt)
    try:
        template_variables = sorted(set(prompt.template_variables()))
        template_error = None
    except TemplateError as e:
        template_variables = []
        template_error = str(e)
    return {
        "character_count": len(text),
        "line_count": len(text.splitlines()),
        "template_variables": template_variables,
        "template_error": template_error,
        "text": text,
    }


def _safe_len(value) -> int | None:
    try:
        return len(value) if value is not None else 0
    except TypeError:
        return None


def _agent_trait_keys(agent_list) -> list[str]:
    keys = set()
    for agent in agent_list:
        keys.update((getattr(agent, "traits", None) or {}).keys())
    return sorted(keys)


def _agent_summary(agent) -> dict:
    return {
        "name": getattr(agent, "name", None),
        "traits": jsonable(getattr(agent, "traits", {}) or {}),
    }


def _scenario_keys(scenario_list) -> list[str]:
    keys = set()
    for scenario in scenario_list:
        keys.update(dict(scenario).keys())
    return sorted(keys)
