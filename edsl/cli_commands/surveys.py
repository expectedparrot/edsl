"""Survey creation commands for the EDSL CLI."""

from __future__ import annotations

import json
from pathlib import Path

import click

from edsl.cli_shared import EXIT_ERROR, EXIT_USAGE, error, output, save_edsl_object


def register(surveys_group: click.Group) -> None:
    @surveys_group.command("create")
    @click.option("--spec", "spec_path", required=True, type=click.Path(exists=True), help="Survey spec JSON or YAML.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package or serialized file.")
    def create_survey(spec_path: str, output_path: str):
        """Create a Survey from a JSON or YAML spec."""
        try:
            from edsl.surveys import Survey

            spec = _read_spec(spec_path)
            question_specs = spec.get("questions")
            if not isinstance(question_specs, list) or not question_specs:
                error(
                    "USAGE_ERROR",
                    "Survey spec must contain a non-empty 'questions' list.",
                    exit_code=EXIT_USAGE,
                )

            questions = [_build_question(item) for item in question_specs]
            survey = Survey(questions=questions)
            saved = save_edsl_object(survey, output_path, object_type="Survey")
            output(
                {
                    "object_type": "Survey",
                    "question_count": len(questions),
                    "questions": [
                        {
                            "question_name": q.question_name,
                            "question_type": q.question_type,
                        }
                        for q in questions
                    ],
                    "saved": saved,
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_CREATE_ERROR",
                str(e),
                suggestion="Check the survey spec and output path.",
                exit_code=EXIT_ERROR,
            )


def _read_spec(path: str) -> dict:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError:
            error(
                "DEPENDENCY_ERROR",
                "YAML survey specs require PyYAML.",
                suggestion="Use JSON, or install PyYAML.",
                exit_code=EXIT_USAGE,
            )
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            error("INVALID_JSON", f"Failed to parse JSON from {path}: {e}", exit_code=EXIT_USAGE)
    if not isinstance(data, dict):
        error("USAGE_ERROR", "Survey spec must be a JSON/YAML object.", exit_code=EXIT_USAGE)
    return data


def _build_question(spec: dict):
    if not isinstance(spec, dict):
        error("USAGE_ERROR", "Each question spec must be an object.", exit_code=EXIT_USAGE)

    question_type = spec.get("type") or spec.get("question_type")
    question_name = spec.get("name") or spec.get("question_name")
    question_text = spec.get("text") or spec.get("question_text")
    if not question_type or not question_name or not question_text:
        error(
            "USAGE_ERROR",
            "Each question requires type, name, and text fields.",
            exit_code=EXIT_USAGE,
        )

    from edsl.questions.register_questions_meta import RegisterQuestionsMeta
    import edsl.questions  # noqa: F401 - ensures question classes are registered

    type_map = RegisterQuestionsMeta.question_types_to_classes()
    question_cls = type_map.get(question_type)
    if question_cls is None:
        error(
            "UNKNOWN_QUESTION_TYPE",
            f"Unknown question type: {question_type}",
            suggestion=f"Known types include: {', '.join(sorted(type_map)[:20])}",
            exit_code=EXIT_USAGE,
        )

    kwargs = {
        "question_name": question_name,
        "question_text": question_text,
    }
    if "options" in spec:
        kwargs["question_options"] = spec["options"]
    if "question_options" in spec:
        kwargs["question_options"] = spec["question_options"]
    for key, value in spec.items():
        if key in {"type", "question_type", "name", "question_name", "text", "question_text", "options", "question_options"}:
            continue
        kwargs[key] = value
    return question_cls(**kwargs)
