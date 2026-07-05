"""Survey creation commands for the EDSL CLI."""

from __future__ import annotations

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_USAGE,
    error,
    load_any_object,
    output,
    save_edsl_object,
)


def register(surveys_group: click.Group) -> None:
    @surveys_group.command("create")
    @click.option("--question-type", required=True, help="Question type, e.g. free_text or multiple_choice.")
    @click.option("--question-name", required=True, help="Question name.")
    @click.option("--question-text", required=True, help="Question text.")
    @click.option("--option", "options", multiple=True, help="Question option. Repeat for multiple-choice, checkbox, scale, or similar questions.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package or serialized file.")
    def create_survey(question_type: str, question_name: str, question_text: str, options: tuple[str, ...], output_path: str):
        """Create a Survey with one question."""
        try:
            from edsl.surveys import Survey

            question = _build_question_from_fields(
                question_type=question_type,
                question_name=question_name,
                question_text=question_text,
                options=options,
            )
            survey = Survey(questions=[question])
            saved = save_edsl_object(survey, output_path, object_type="Survey")
            output(_survey_output(survey, saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_CREATE_ERROR",
                str(e),
                suggestion="Check the question fields and output path.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("add-question")
    @click.argument("survey_path", type=click.Path(exists=True))
    @click.option("--question-type", required=True, help="Question type, e.g. free_text or multiple_choice.")
    @click.option("--question-name", required=True, help="Question name.")
    @click.option("--question-text", required=True, help="Question text.")
    @click.option("--option", "options", multiple=True, help="Question option. Repeat for multiple-choice, checkbox, scale, or similar questions.")
    @click.option("--index", default=None, type=int, help="Insert question at this zero-based index. Defaults to append.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package or serialized file. Defaults to SURVEY_PATH.")
    def add_question(survey_path: str, question_type: str, question_name: str, question_text: str, options: tuple[str, ...], index: int | None, output_path: str | None):
        """Add one question to an existing Survey."""
        try:
            from edsl.surveys import Survey

            survey = load_any_object(survey_path)
            if not isinstance(survey, Survey):
                error(
                    "UNSUPPORTED_OBJECT",
                    f"Expected a Survey object, got {type(survey).__name__}.",
                    exit_code=EXIT_USAGE,
                )
            question = _build_question_from_fields(
                question_type=question_type,
                question_name=question_name,
                question_text=question_text,
                options=options,
            )
            survey = survey.add_question(question, index=index)
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            output(_survey_output(survey, saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_ADD_QUESTION_ERROR",
                str(e),
                suggestion="Check the survey path, question fields, and output path.",
                exit_code=EXIT_ERROR,
            )


def _build_question_from_fields(
    question_type: str,
    question_name: str,
    question_text: str,
    options: tuple[str, ...],
):
    spec = {
        "question_type": question_type,
        "question_name": question_name,
        "question_text": question_text,
    }
    if options:
        spec["question_options"] = list(options)
    return _build_question(spec)


def _survey_output(survey, saved: dict) -> dict:
    return {
        "object_type": "Survey",
        "question_count": len(survey.questions),
        "questions": [
            {
                "question_name": q.question_name,
                "question_type": q.question_type,
            }
            for q in survey.questions
        ],
        "saved": saved,
    }


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
