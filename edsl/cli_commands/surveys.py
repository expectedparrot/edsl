"""Survey creation commands for the EDSL CLI."""

from __future__ import annotations

import click

from edsl.cli_shared import (
    EXIT_ERROR,
    EXIT_USAGE,
    error,
    load_any_object,
    output,
    raw_output_written,
    save_edsl_object,
)


def register(surveys_group: click.Group) -> None:
    @surveys_group.command("create")
    @click.option("--question-type", required=True, help="Question type, e.g. free_text or multiple_choice.")
    @click.option("--question-name", required=True, help="Question name.")
    @click.option("--question-text", required=True, help="Question text.")
    @click.option("--option", "options", multiple=True, help="Question option. Repeat for multiple-choice, checkbox, scale, or similar questions.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package, serialized file, or '-' for raw JSON stdout.")
    def create_survey(question_type: str, question_name: str, question_text: str, options: tuple[str, ...], output_path: str):
        """Create a Survey with one question.

        Example:
          edsl surveys create --question-type free_text --question-name q0 --question-text "What is your name?" --output survey.ep
        """
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
            if raw_output_written(saved):
                return
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
    @click.argument("survey_path")
    @click.option("--question-type", required=True, help="Question type, e.g. free_text or multiple_choice.")
    @click.option("--question-name", required=True, help="Question name.")
    @click.option("--question-text", required=True, help="Question text.")
    @click.option("--option", "options", multiple=True, help="Question option. Repeat for multiple-choice, checkbox, scale, or similar questions.")
    @click.option("--index", default=None, type=int, help="Insert question at this zero-based index. Defaults to append.")
    @click.option("--replace", is_flag=True, default=False, help="Replace an existing question with the same --question-name.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def add_question(survey_path: str, question_type: str, question_name: str, question_text: str, options: tuple[str, ...], index: int | None, replace: bool, output_path: str | None):
        """Add one question to an existing Survey.

        Example:
          edsl surveys add-question survey.ep --question-type multiple_choice --question-name q1 --question-text "Pick one." --option A --option B
        """
        try:
            survey = _load_survey(survey_path)
            question = _build_question_from_fields(
                question_type=question_type,
                question_name=question_name,
                question_text=question_text,
                options=options,
            )
            if replace and question_name in survey.question_names:
                existing_index = survey.question_name_to_index[question_name]
                survey = survey.delete_question(question_name)
                index = existing_index if index is None else index
            elif replace:
                error(
                    "QUESTION_NOT_FOUND",
                    f"Cannot replace missing question: {question_name}",
                    suggestion="Use add-question without --replace to add a new question.",
                    exit_code=EXIT_USAGE,
                )
            survey = survey.add_question(question, index=index)
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            if raw_output_written(saved):
                return
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

    @surveys_group.command("show")
    @click.argument("survey_path")
    def show_survey(survey_path: str):
        """Summarize a Survey.

        Example:
          edsl surveys show survey.ep
        """
        try:
            survey = _load_survey(survey_path)
            output(_survey_summary(survey))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_SHOW_ERROR",
                str(e),
                suggestion="Check the survey path.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("questions")
    @click.argument("survey_path")
    def survey_questions(survey_path: str):
        """List Survey questions.

        Example:
          edsl surveys questions survey.ep
        """
        try:
            survey = _load_survey(survey_path)
            output(
                {
                    "object_type": "Survey",
                    "question_count": len(survey.questions),
                    "questions": [_question_summary(q) for q in survey.questions],
                }
            )
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_QUESTIONS_ERROR",
                str(e),
                suggestion="Check the survey path.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("add-skip-rule")
    @click.argument("survey_path")
    @click.option("--question", "question_name", required=True, help="Question name where the rule is evaluated.")
    @click.option("--expression", required=True, help="Expression that triggers the rule.")
    @click.option("--next", "next_question", default=None, help="Destination question name or index. Defaults to the next question.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def add_skip_rule(survey_path: str, question_name: str, expression: str, next_question: str | None, output_path: str | None):
        """Add a pre-question skip rule.

        Example:
          edsl surveys add-skip-rule survey.ep --question q1 --expression "{{ q0.answer }} == 'no'"
        """
        try:
            survey = _load_survey(survey_path)
            if next_question is None:
                survey = survey.add_skip_rule(question_name, expression)
            else:
                survey = survey.add_rule(
                    question_name,
                    expression,
                    _parse_next_question(next_question),
                    before_rule=True,
                )
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            if raw_output_written(saved):
                return
            output(_survey_summary(survey, saved=saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_ADD_SKIP_RULE_ERROR",
                str(e),
                suggestion="Check the survey path, question name, expression, and destination.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("add-stop-rule")
    @click.argument("survey_path")
    @click.option("--question", "question_name", required=True, help="Question name where the rule is evaluated.")
    @click.option("--expression", required=True, help="Expression that ends the survey when true.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def add_stop_rule(survey_path: str, question_name: str, expression: str, output_path: str | None):
        """Add a post-answer stop rule.

        Example:
          edsl surveys add-stop-rule survey.ep --question q0 --expression "{{ q0.answer }} == 'no'"
        """
        try:
            survey = _load_survey(survey_path)
            survey = survey.add_stop_rule(question_name, expression)
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            if raw_output_written(saved):
                return
            output(_survey_summary(survey, saved=saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_ADD_STOP_RULE_ERROR",
                str(e),
                suggestion="Check the survey path, question name, and expression.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("drop-question")
    @click.argument("survey_path")
    @click.option("--question", "question_name", required=True, help="Question name to remove.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def drop_question(survey_path: str, question_name: str, output_path: str | None):
        """Remove one question from a Survey.

        Example:
          edsl surveys drop-question survey.ep --question q1
        """
        try:
            survey = _load_survey(survey_path)
            survey = survey.delete_question(question_name)
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            if raw_output_written(saved):
                return
            output(_survey_summary(survey, saved=saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_DROP_QUESTION_ERROR",
                str(e),
                suggestion="Check the survey path and question name.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("move-question")
    @click.argument("survey_path")
    @click.option("--question", "question_name", required=True, help="Question name to move.")
    @click.option("--index", required=True, type=int, help="New zero-based question index.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def move_question(survey_path: str, question_name: str, index: int, output_path: str | None):
        """Move one question in a Survey.

        Example:
          edsl surveys move-question survey.ep --question q2 --index 1
        """
        try:
            survey = _load_survey(survey_path)
            survey = survey.move_question(question_name, index)
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            if raw_output_written(saved):
                return
            output(_survey_summary(survey, saved=saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_MOVE_QUESTION_ERROR",
                str(e),
                suggestion="Check the survey path, question name, and index.",
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


def _load_survey(path: str):
    from edsl.surveys import Survey

    survey = load_any_object(path)
    if not isinstance(survey, Survey):
        error(
            "UNSUPPORTED_OBJECT",
            f"Expected a Survey object, got {type(survey).__name__}.",
            exit_code=EXIT_USAGE,
        )
    return survey


def _survey_summary(survey, saved: dict | None = None) -> dict:
    rules = _non_default_rules(survey)
    data = {
        "object_type": "Survey",
        "question_count": len(survey.questions),
        "question_names": survey.question_names,
        "questions": [_question_summary(q) for q in survey.questions],
        "rule_count": len(rules),
        "rules": [_rule_summary(rule) for rule in rules],
    }
    if saved is not None:
        data["saved"] = saved
    return data


def _question_summary(question) -> dict:
    data = {
        "question_name": question.question_name,
        "question_type": question.question_type,
        "question_text": question.question_text,
    }
    if hasattr(question, "question_options"):
        data["question_options"] = getattr(question, "question_options")
    return data


def _rule_summary(rule) -> dict:
    return {
        "current_q": rule.current_q,
        "expression": rule.expression,
        "next_q": rule.next_q,
        "priority": rule.priority,
        "before_rule": rule.before_rule,
    }


def _non_default_rules(survey) -> list:
    rules = survey.rule_collection.non_default_rules
    return rules() if callable(rules) else rules


def _parse_next_question(value: str):
    try:
        return int(value)
    except ValueError:
        return value


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
