"""Survey creation commands for the EDSL CLI."""

from __future__ import annotations

import json

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
    @click.option("--option-json", "json_options", multiple=True, help="Typed question option as JSON, e.g. 1, 1.5, or '{\"id\":1}'.")
    @click.option("--question-item", "question_items", multiple=True, help="Matrix row/item. Repeat for matrix questions.")
    @click.option("--answer-key", "answer_keys", multiple=True, help="Answer key. Repeat for dict questions.")
    @click.option("--value-type", "value_types", multiple=True, help="Value type for dict answer keys. Repeat in answer-key order.")
    @click.option("--value-description", "value_descriptions", multiple=True, help="Description for dict answer keys. Repeat in answer-key order.")
    @click.option("--answer-template", default=None, help="Answer template JSON string or path for extract questions.")
    @click.option("--option-label", "option_labels", multiple=True, help="Option label as OPTION=LABEL. Repeat for linear scale/matrix.")
    @click.option("--min-value", default=None, type=float, help="Minimum numeric answer value.")
    @click.option("--max-value", default=None, type=float, help="Maximum numeric answer value.")
    @click.option("--num-selections", default=None, type=int, help="Exact number of ranked selections.")
    @click.option("--min-selections", default=None, type=int, help="Minimum checkbox/top-k selections.")
    @click.option("--max-selections", default=None, type=int, help="Maximum checkbox/top-k selections.")
    @click.option("--budget-sum", default=None, type=int, help="Total budget for budget allocation questions.")
    @click.option("--min-list-items", default=None, type=int, help="Minimum number of list answer items.")
    @click.option("--max-list-items", default=None, type=int, help="Maximum number of list answer items.")
    @click.option("--max-options-shown", default=None, type=int, help="Dropdown options shown after search.")
    @click.option("--top-k", default=None, type=int, help="Dropdown top-k search results.")
    @click.option("--permissive/--strict", default=None, help="Relax or enforce answer validation where supported.")
    @click.option("--use-code/--no-use-code", default=None, help="Use option indices instead of option text where supported.")
    @click.option("--include-comment/--no-include-comment", default=None, help="Include or omit answer comments where supported.")
    @click.option("--answering-instructions", default=None, help="Custom answering instructions or path.")
    @click.option("--question-presentation", default=None, help="Custom question presentation template or path.")
    @click.option("--param", "params", multiple=True, help="Escape hatch: extra constructor param as KEY=JSON.")
    @click.option("--question-json", default=None, help="Question spec JSON string or path. Merged after direct flags.")
    @click.option("--output", "-o", "output_path", required=True, help="Output .ep package, serialized file, or '-' for raw JSON stdout.")
    def create_survey(question_type: str, question_name: str, question_text: str, options: tuple[str, ...], json_options: tuple[str, ...], question_items: tuple[str, ...], answer_keys: tuple[str, ...], value_types: tuple[str, ...], value_descriptions: tuple[str, ...], answer_template: str | None, option_labels: tuple[str, ...], min_value: float | None, max_value: float | None, num_selections: int | None, min_selections: int | None, max_selections: int | None, budget_sum: int | None, min_list_items: int | None, max_list_items: int | None, max_options_shown: int | None, top_k: int | None, permissive: bool | None, use_code: bool | None, include_comment: bool | None, answering_instructions: str | None, question_presentation: str | None, params: tuple[str, ...], question_json: str | None, output_path: str):
        """Create a Survey with one question.

        \b
        Examples:
          ep surveys create --question-type free_text --question-name q0 --question-text "What is your name?" --output survey.ep
          ep surveys create --question-type numerical --question-name age --question-text "Age?" --min-value 18 --max-value 99 --output survey.ep
          ep surveys create --question-type matrix --question-name prefs --question-text "Rate these." --question-item price --question-item quality --option-json 1 --option-json 5 --option-label 1=Low --option-label 5=High --output survey.ep
          ep surveys create --question-type extract --question-name details --question-text "Extract details." --answer-template '{"name":"example","age":0}' --output survey.ep
        """
        try:
            from edsl.surveys import Survey

            question = _build_question_from_fields(
                question_type=question_type,
                question_name=question_name,
                question_text=question_text,
                options=options,
                json_options=json_options,
                question_items=question_items,
                answer_keys=answer_keys,
                value_types=value_types,
                value_descriptions=value_descriptions,
                answer_template=answer_template,
                option_labels=option_labels,
                min_value=min_value,
                max_value=max_value,
                num_selections=num_selections,
                min_selections=min_selections,
                max_selections=max_selections,
                budget_sum=budget_sum,
                min_list_items=min_list_items,
                max_list_items=max_list_items,
                max_options_shown=max_options_shown,
                top_k=top_k,
                permissive=permissive,
                use_code=use_code,
                include_comment=include_comment,
                answering_instructions=answering_instructions,
                question_presentation=question_presentation,
                params=params,
                question_json=question_json,
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
    @click.option("--option-json", "json_options", multiple=True, help="Typed question option as JSON, e.g. 1, 1.5, or '{\"id\":1}'.")
    @click.option("--question-item", "question_items", multiple=True, help="Matrix row/item. Repeat for matrix questions.")
    @click.option("--answer-key", "answer_keys", multiple=True, help="Answer key. Repeat for dict questions.")
    @click.option("--value-type", "value_types", multiple=True, help="Value type for dict answer keys. Repeat in answer-key order.")
    @click.option("--value-description", "value_descriptions", multiple=True, help="Description for dict answer keys. Repeat in answer-key order.")
    @click.option("--answer-template", default=None, help="Answer template JSON string or path for extract questions.")
    @click.option("--option-label", "option_labels", multiple=True, help="Option label as OPTION=LABEL. Repeat for linear scale/matrix.")
    @click.option("--min-value", default=None, type=float, help="Minimum numeric answer value.")
    @click.option("--max-value", default=None, type=float, help="Maximum numeric answer value.")
    @click.option("--num-selections", default=None, type=int, help="Exact number of ranked selections.")
    @click.option("--min-selections", default=None, type=int, help="Minimum checkbox/top-k selections.")
    @click.option("--max-selections", default=None, type=int, help="Maximum checkbox/top-k selections.")
    @click.option("--budget-sum", default=None, type=int, help="Total budget for budget allocation questions.")
    @click.option("--min-list-items", default=None, type=int, help="Minimum number of list answer items.")
    @click.option("--max-list-items", default=None, type=int, help="Maximum number of list answer items.")
    @click.option("--max-options-shown", default=None, type=int, help="Dropdown options shown after search.")
    @click.option("--top-k", default=None, type=int, help="Dropdown top-k search results.")
    @click.option("--permissive/--strict", default=None, help="Relax or enforce answer validation where supported.")
    @click.option("--use-code/--no-use-code", default=None, help="Use option indices instead of option text where supported.")
    @click.option("--include-comment/--no-include-comment", default=None, help="Include or omit answer comments where supported.")
    @click.option("--answering-instructions", default=None, help="Custom answering instructions or path.")
    @click.option("--question-presentation", default=None, help="Custom question presentation template or path.")
    @click.option("--param", "params", multiple=True, help="Escape hatch: extra constructor param as KEY=JSON.")
    @click.option("--question-json", default=None, help="Question spec JSON string or path. Merged after direct flags.")
    @click.option("--index", default=None, type=int, help="Insert question at this zero-based index. Defaults to append.")
    @click.option("--replace", is_flag=True, default=False, help="Replace an existing question with the same --question-name.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def add_question(survey_path: str, question_type: str, question_name: str, question_text: str, options: tuple[str, ...], json_options: tuple[str, ...], question_items: tuple[str, ...], answer_keys: tuple[str, ...], value_types: tuple[str, ...], value_descriptions: tuple[str, ...], answer_template: str | None, option_labels: tuple[str, ...], min_value: float | None, max_value: float | None, num_selections: int | None, min_selections: int | None, max_selections: int | None, budget_sum: int | None, min_list_items: int | None, max_list_items: int | None, max_options_shown: int | None, top_k: int | None, permissive: bool | None, use_code: bool | None, include_comment: bool | None, answering_instructions: str | None, question_presentation: str | None, params: tuple[str, ...], question_json: str | None, index: int | None, replace: bool, output_path: str | None):
        """Add one question to an existing Survey.

        \b
        Examples:
          ep surveys add-question survey.ep --question-type multiple_choice --question-name q1 --question-text "Pick one." --option A --option B
          ep surveys add-question survey.ep --question-type top_k --question-name top --question-text "Top two?" --option A --option B --option C --min-selections 2 --max-selections 2
        """
        try:
            survey = _load_survey(survey_path)
            question = _build_question_from_fields(
                question_type=question_type,
                question_name=question_name,
                question_text=question_text,
                options=options,
                json_options=json_options,
                question_items=question_items,
                answer_keys=answer_keys,
                value_types=value_types,
                value_descriptions=value_descriptions,
                answer_template=answer_template,
                option_labels=option_labels,
                min_value=min_value,
                max_value=max_value,
                num_selections=num_selections,
                min_selections=min_selections,
                max_selections=max_selections,
                budget_sum=budget_sum,
                min_list_items=min_list_items,
                max_list_items=max_list_items,
                max_options_shown=max_options_shown,
                top_k=top_k,
                permissive=permissive,
                use_code=use_code,
                include_comment=include_comment,
                answering_instructions=answering_instructions,
                question_presentation=question_presentation,
                params=params,
                question_json=question_json,
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

    @surveys_group.command("add-instruction")
    @click.argument("survey_path")
    @click.option("--name", required=True, help="Instruction name.")
    @click.option("--text", required=True, help="Instruction text or path to a text file.")
    @click.option("--preamble", default="You were given the following instructions:", show_default=True, help="Instruction preamble.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def add_instruction(survey_path: str, name: str, text: str, preamble: str, output_path: str | None):
        """Add an Instruction object to a Survey.

        Example:
          ep surveys add-instruction survey.ep --name intro --text instructions.txt
        """
        try:
            from edsl.instructions import Instruction

            survey = _load_survey(survey_path)
            survey = survey.add_instruction(Instruction(name=name, text=_read_text_or_value(text), preamble=preamble))
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            if raw_output_written(saved):
                return
            output(_survey_summary(survey, saved=saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_ADD_INSTRUCTION_ERROR",
                str(e),
                suggestion="Check the survey path and instruction fields.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("set-memory")
    @click.argument("survey_path")
    @click.option("--full", "full_memory", is_flag=True, default=False, help="Remember all prior questions for each later question.")
    @click.option("--target", "targeted_memory", multiple=True, help="Targeted memory as FOCAL=PRIOR. Repeat for multiple prior questions.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def set_memory(survey_path: str, full_memory: bool, targeted_memory: tuple[str, ...], output_path: str | None):
        """Configure Survey memory.

        \b
        Examples:
          ep surveys set-memory survey.ep --full
          ep surveys set-memory survey.ep --target q2=q0 --target q2=q1
        """
        if not full_memory and not targeted_memory:
            error("USAGE_ERROR", "Provide --full or at least one --target FOCAL=PRIOR.", exit_code=EXIT_USAGE)
        try:
            survey = _load_survey(survey_path)
            if full_memory:
                survey = survey.set_full_memory_mode()
            for focal_question, prior_question in _parse_pairs(targeted_memory).items():
                for prior in prior_question:
                    survey = survey.add_targeted_memory(focal_question, prior)
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            if raw_output_written(saved):
                return
            output(_survey_summary(survey, saved=saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_SET_MEMORY_ERROR",
                str(e),
                suggestion="Check the survey path and question names.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("add-question-group")
    @click.argument("survey_path")
    @click.option("--name", "group_name", required=True, help="Question group name.")
    @click.option("--start", "start_question", required=True, help="First question in the group.")
    @click.option("--end", "end_question", required=True, help="Last question in the group.")
    @click.option("--output", "-o", "output_path", default=None, help="Output .ep package, serialized file, or '-' for raw JSON stdout. Defaults to SURVEY_PATH.")
    def add_question_group(survey_path: str, group_name: str, start_question: str, end_question: str, output_path: str | None):
        """Add a named contiguous question group.

        Example:
          ep surveys add-question-group survey.ep --name demographics --start age --end income
        """
        try:
            survey = _load_survey(survey_path)
            survey = survey.add_question_group(start_question, end_question, group_name)
            saved = save_edsl_object(survey, output_path or survey_path, object_type="Survey")
            if raw_output_written(saved):
                return
            output(_survey_summary(survey, saved=saved))
        except SystemExit:
            raise
        except Exception as e:
            error(
                "SURVEYS_ADD_QUESTION_GROUP_ERROR",
                str(e),
                suggestion="Check the survey path, question names, and group name.",
                exit_code=EXIT_ERROR,
            )

    @surveys_group.command("show")
    @click.argument("survey_path")
    def show_survey(survey_path: str):
        """Summarize a Survey.

        Example:
          ep surveys show survey.ep
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
          ep surveys questions survey.ep
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
          ep surveys add-skip-rule survey.ep --question q1 --expression "{{ q0.answer }} == 'no'"
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
          ep surveys add-stop-rule survey.ep --question q0 --expression "{{ q0.answer }} == 'no'"
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
          ep surveys drop-question survey.ep --question q1
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
          ep surveys move-question survey.ep --question q2 --index 1
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
    json_options: tuple[str, ...] = (),
    question_items: tuple[str, ...] = (),
    answer_keys: tuple[str, ...] = (),
    value_types: tuple[str, ...] = (),
    value_descriptions: tuple[str, ...] = (),
    answer_template: str | None = None,
    option_labels: tuple[str, ...] = (),
    min_value: float | None = None,
    max_value: float | None = None,
    num_selections: int | None = None,
    min_selections: int | None = None,
    max_selections: int | None = None,
    budget_sum: int | None = None,
    min_list_items: int | None = None,
    max_list_items: int | None = None,
    max_options_shown: int | None = None,
    top_k: int | None = None,
    permissive: bool | None = None,
    use_code: bool | None = None,
    include_comment: bool | None = None,
    answering_instructions: str | None = None,
    question_presentation: str | None = None,
    params: tuple[str, ...] = (),
    question_json: str | None = None,
):
    spec = {
        "question_type": question_type,
        "question_name": question_name,
        "question_text": question_text,
    }
    question_options = list(options) + [_parse_json_value(value) for value in json_options]
    if question_options:
        spec["question_options"] = question_options
    _apply_direct_question_flags(
        spec,
        question_items=question_items,
        answer_keys=answer_keys,
        value_types=value_types,
        value_descriptions=value_descriptions,
        answer_template=answer_template,
        option_labels=option_labels,
        min_value=min_value,
        max_value=max_value,
        num_selections=num_selections,
        min_selections=min_selections,
        max_selections=max_selections,
        budget_sum=budget_sum,
        min_list_items=min_list_items,
        max_list_items=max_list_items,
        max_options_shown=max_options_shown,
        top_k=top_k,
        permissive=permissive,
        use_code=use_code,
        include_comment=include_comment,
        answering_instructions=answering_instructions,
        question_presentation=question_presentation,
    )
    spec.update(_parse_json_params(params))
    if question_json:
        spec.update(_load_json_object(question_json))
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
        "question_groups": getattr(survey, "question_groups", {}),
        "memory_plan": _memory_plan_summary(survey),
        "instructions": _instruction_summary(survey),
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
    for attr in ("min_value", "max_value", "question_items", "num_selections", "min_selections", "max_selections"):
        if hasattr(question, attr):
            data[attr] = getattr(question, attr)
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


def _parse_json_params(params: tuple[str, ...]) -> dict:
    parsed = {}
    for item in params:
        if "=" not in item:
            error("USAGE_ERROR", f"Invalid --param {item!r}; expected KEY=JSON.", exit_code=EXIT_USAGE)
        key, raw_value = item.split("=", 1)
        key = key.strip()
        if not key:
            error("USAGE_ERROR", f"Invalid --param {item!r}; key is empty.", exit_code=EXIT_USAGE)
        try:
            parsed[key] = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed[key] = raw_value
    return parsed


def _apply_direct_question_flags(
    spec: dict,
    *,
    question_items: tuple[str, ...],
    answer_keys: tuple[str, ...],
    value_types: tuple[str, ...],
    value_descriptions: tuple[str, ...],
    answer_template: str | None,
    option_labels: tuple[str, ...],
    min_value: float | None,
    max_value: float | None,
    num_selections: int | None,
    min_selections: int | None,
    max_selections: int | None,
    budget_sum: int | None,
    min_list_items: int | None,
    max_list_items: int | None,
    max_options_shown: int | None,
    top_k: int | None,
    permissive: bool | None,
    use_code: bool | None,
    include_comment: bool | None,
    answering_instructions: str | None,
    question_presentation: str | None,
) -> None:
    if question_items:
        spec["question_items"] = list(question_items)
    if answer_keys:
        spec["answer_keys"] = list(answer_keys)
    if value_types:
        spec["value_types"] = list(value_types)
    if value_descriptions:
        spec["value_descriptions"] = list(value_descriptions)
    if answer_template:
        spec["answer_template"] = _load_json_object(answer_template)
    if option_labels:
        spec["option_labels"] = _parse_option_labels(option_labels, spec.get("question_options", []))
    scalar_flags = {
        "min_value": min_value,
        "max_value": max_value,
        "num_selections": num_selections,
        "min_selections": min_selections,
        "max_selections": max_selections,
        "budget_sum": budget_sum,
        "min_list_items": min_list_items,
        "max_list_items": max_list_items,
        "max_options_shown": max_options_shown,
        "top_k": top_k,
        "permissive": permissive,
        "use_code": use_code,
        "include_comment": include_comment,
    }
    for key, value in scalar_flags.items():
        if value is not None:
            spec[key] = value
    if answering_instructions:
        spec["answering_instructions"] = _read_text_or_value(answering_instructions)
    if question_presentation:
        spec["question_presentation"] = _read_text_or_value(question_presentation)


def _parse_option_labels(items: tuple[str, ...], question_options: list | None = None) -> dict:
    labels = {}
    for item in items:
        if "=" not in item:
            error("USAGE_ERROR", f"Invalid --option-label {item!r}; expected OPTION=LABEL.", exit_code=EXIT_USAGE)
        raw_key, label = item.split("=", 1)
        if question_options and raw_key in question_options:
            key = raw_key
        else:
            try:
                key = json.loads(raw_key)
            except json.JSONDecodeError:
                key = raw_key
        labels[key] = label
    return labels


def _parse_json_value(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        error("INVALID_JSON", f"Failed to parse option JSON {value!r}: {e}", exit_code=EXIT_USAGE)


def _load_json_object(value: str) -> dict:
    from pathlib import Path

    path = Path(value)
    raw = path.read_text(encoding="utf-8") if path.exists() and path.is_file() else value
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        error("INVALID_JSON", f"Failed to parse JSON: {e}", exit_code=EXIT_USAGE)
    if not isinstance(data, dict):
        error("USAGE_ERROR", "Question JSON must be an object.", exit_code=EXIT_USAGE)
    return data


def _parse_pairs(items: tuple[str, ...]) -> dict[str, list[str]]:
    pairs: dict[str, list[str]] = {}
    for item in items:
        if "=" not in item:
            error("USAGE_ERROR", f"Invalid value {item!r}; expected FOCAL=PRIOR.", exit_code=EXIT_USAGE)
        key, value = item.split("=", 1)
        pairs.setdefault(key, []).append(value)
    return pairs


def _memory_plan_summary(survey) -> dict:
    memory_plan = getattr(survey, "memory_plan", None)
    if memory_plan is None:
        return {}
    try:
        return {
            key: list(getattr(value, "prior_questions", value))
            for key, value in memory_plan.items()
        }
    except Exception:
        return str(memory_plan)


def _instruction_summary(survey) -> list[dict]:
    instructions = getattr(survey, "_instruction_names_to_instructions", {}) or {}
    return [
        {"name": name, "text": getattr(instruction, "text", str(instruction))}
        for name, instruction in instructions.items()
    ]


def _read_text_or_value(value: str) -> str:
    from pathlib import Path

    path = Path(value)
    if path.exists() and path.is_file():
        return path.read_text(encoding="utf-8")
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
