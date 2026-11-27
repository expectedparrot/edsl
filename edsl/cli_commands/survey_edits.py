"""Local, name-based edits to native Survey objects."""

import ast
import sys
from contextlib import redirect_stdout
from pathlib import Path

import click

from edsl.cli_shared import (
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    output,
    load_json_object,
    read_serialized_object,
    raw_output_written,
)


def update_question(survey, name, fields):
    """Rebuild the question in place in the serialized survey, retaining its references."""
    from edsl.questions.question_base import QuestionBase

    if not isinstance(fields, dict) or not fields:
        raise ValueError("Supply at least one question field to update.")
    protected = {"question_name", "question_type", "edsl_version", "edsl_class_name"}
    if protected.intersection(fields):
        raise ValueError(
            "Use rename-question for names; update-question preserves the type."
        )
    old = survey.get(name)
    replacement = QuestionBase.from_dict({**old.to_dict(), **fields})
    return replace_question(survey, name, replacement)


def replace_question(survey, name, replacement):
    # Serialized order includes instructions, so use the name, not a question index.
    data = survey.to_dict()
    for i, item in enumerate(data["questions"]):
        if item.get("question_name") == name:
            data["questions"][i] = replacement.to_dict()
            break
    else:
        raise ValueError(f"Unknown question: {name}")
    memory = data["memory_plan"]
    index = memory["survey_question_names"].index(name)
    memory["survey_question_texts"][index] = replacement.question_text
    return type(survey).from_dict(data)


def set_groups(survey, groups):
    if not isinstance(groups, dict):
        raise ValueError(
            "Groups must be an object mapping group names to [first, last]."
        )
    survey.question_groups = {}
    for name, bounds in groups.items():
        if not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError(f"Expected two question names for group {name!r}.")
        survey.add_question_group(bounds[0], bounds[1], name)
    return survey


def replace_rule(
    survey, question, expression, when, priority, destination, match_expression
):
    """Change one authored rule while preserving its position in the collection."""
    from edsl.surveys.base import EndOfSurvey
    from edsl.surveys.rules.rule import Rule
    from edsl.surveys.rules.rule_collection import RuleCollection

    current = survey._get_question_index(question)
    rules = survey.rule_collection
    matches = [
        rule
        for rule in rules.non_default_rules
        if rule.current_q == current
        and (when is None or rule.before_rule == (when == "before"))
        and (priority is None or rule.priority == priority)
        and (match_expression is None or rule.expression == match_expression)
    ]
    if not matches:
        raise ValueError(
            f"No matching custom rule on {question!r}. Inspect it with ep surveys show."
        )
    if len(matches) > 1:
        choices = ", ".join(
            f"--when {'before' if r.before_rule else 'after'} --priority {r.priority}"
            for r in matches
        )
        raise ValueError(
            f"Multiple rules on {question!r}. Select a phase and priority ({choices}), or use --match-expression."
        )
    old = matches[0]
    next_q = old.next_q
    if destination is not None:
        if old.before_rule:
            raise ValueError(
                "A before-question rule skips its question. Use --next on an after-answer rule."
            )
        next_q = (
            EndOfSurvey
            if destination == "EndOfSurvey"
            else survey._get_question_index(destination)
        )
    expression = expression.strip()
    try:
        ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid rule expression: {exc.msg}") from exc

    # The native rule constructor validates references and rebuilds its parsed expression.
    with redirect_stdout(sys.stderr):
        updated = Rule(
            current,
            expression,
            next_q,
            survey.question_name_to_index,
            old.priority,
            old.before_rule,
        )
    if old.before_rule and current in updated.named_questions_by_index:
        raise ValueError(
            f"The answer to {question!r} is unavailable before the question is asked."
        )
    # Rebuild the collection so warmed rule lookups cannot retain the old rule.
    survey.rule_collection = RuleCollection(
        num_questions=rules.num_questions,
        rules=[updated if rule is old else rule for rule in rules],
        question_name_to_index=survey.question_name_to_index,
    )
    return survey


def register(group):
    from .surveys import (
        SurveyEditCommand,
        _load_survey,
        _save_survey_edit,
        _survey_output,
    )

    local_file = click.Path(exists=True, dir_okay=False)

    def edit(path, destination, operation):
        try:
            survey = operation(_load_survey(path, preview=True))
            saved = _save_survey_edit(survey, destination or path)
            if not raw_output_written(saved):
                output(_survey_output(survey, saved))
        except Exception as exc:
            error("VALIDATION_ERROR", str(exc), exit_code=EXIT_VALIDATION)

    from .survey_question_model import register as register_question_model

    register_question_model(group, edit)

    @group.command("update-question", cls=SurveyEditCommand)
    @click.argument("survey_path", type=local_file)
    @click.argument("name")
    @click.option("--patch", help="JSON object or file of question fields to change.")
    @click.option("--question-text", help="Set the question wording.")
    @click.option(
        "--option",
        "options",
        multiple=True,
        help="Set the ordered string options. Repeat per option.",
    )
    @click.option(
        "--output",
        "-o",
        type=click.Path(dir_okay=False),
        help="Write a separate revision. Defaults to the input.",
    )
    def update(survey_path, name, patch, question_text, options, output):
        """Change selected fields while keeping the rest of the question and survey."""
        fields = load_json_object(patch) if patch is not None else {}
        for key, value in (
            ("question_text", question_text),
            ("question_options", list(options) if options else None),
        ):
            if value is not None:
                if key in fields:
                    error(
                        "USAGE_ERROR",
                        f"{key} was specified twice.",
                        exit_code=EXIT_USAGE,
                    )
                fields[key] = value
        edit(survey_path, output, lambda s: update_question(s, name, fields))

    @group.command("rename-question", cls=SurveyEditCommand)
    @click.argument("survey_path", type=local_file)
    @click.argument("old_name")
    @click.argument("new_name")
    @click.option(
        "--output",
        "-o",
        type=click.Path(dir_okay=False),
        help="Write a separate revision. Defaults to the input.",
    )
    def rename(survey_path, old_name, new_name, output):
        """Rename a question using the Survey renamer, including rule and piping references."""
        edit(survey_path, output, lambda s: s.with_renamed_question(old_name, new_name))

    @group.command("set-groups", cls=SurveyEditCommand)
    @click.argument("survey_path", type=local_file)
    @click.option(
        "--groups",
        required=True,
        help='JSON object or file, e.g. {"intro":["q1","q2"]}. Use {} to clear.',
    )
    @click.option(
        "--output",
        "-o",
        type=click.Path(dir_okay=False),
        help="Write a separate revision. Defaults to the input.",
    )
    def groups_cmd(survey_path, groups, output):
        """Replace all question group boundaries in one local edit."""
        edit(survey_path, output, lambda s: set_groups(s, load_json_object(groups)))

    @group.command("replace-rule", cls=SurveyEditCommand)
    @click.argument("survey_path", type=local_file)
    @click.option(
        "--question",
        required=True,
        help="Question where the existing rule is evaluated.",
    )
    @click.option("--expression", required=True, help="New condition for this rule.")
    @click.option(
        "--when",
        type=click.Choice(["before", "after"]),
        help="Select by evaluation phase.",
    )
    @click.option(
        "--priority",
        type=click.IntRange(min=0),
        help="Select by existing rule priority.",
    )
    @click.option(
        "--match-expression", help="Select a rule by its exact existing expression."
    )
    @click.option(
        "--next",
        "destination",
        help="New destination for an after-answer rule: a question name or EndOfSurvey.",
    )
    @click.option(
        "--output",
        "-o",
        type=click.Path(dir_okay=False),
        help="Output path. Defaults to the input.",
    )
    def replace_rule_cmd(
        survey_path,
        question,
        expression,
        when,
        priority,
        destination,
        match_expression,
        output,
    ):
        """Replace one custom routing rule in place, preserving its precedence.

        Inspect rules with ep surveys show. If a question has multiple rules,
        select the intended one by phase and priority. Omit --next to keep the
        destination. Recheck the saved file with ep surveys check-paths.
        """
        edit(
            survey_path,
            output,
            lambda s: replace_rule(
                s, question, expression, when, priority, destination, match_expression
            ),
        )

    @group.command("check-paths")
    @click.argument("survey_path", type=local_file)
    @click.option(
        "--schema",
        type=local_file,
        help="Browser settings JSON for grouped presentation.",
    )
    @click.option(
        "--paths",
        help="JSON object or file of named paths, each a list of {page, answers} steps.",
    )
    @click.option(
        "--cases",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        help="JSON file of named question-level cases with answers and expected_path.",
    )
    def check_paths(survey_path, schema, paths, cases):
        """Check respondent routes through the end of a saved survey.

        Use --cases to check individual questions. Write the expectations from
        the research brief before constructing the survey. Supply answers for
        questions used in rules. Optional scenario and agent dictionaries supply
        rule context. Use --schema and --paths together to check grouped pages.

        \b
        ep surveys check-paths survey.ep --cases paths.json
        {"cases":[{"name":"declines","answers":{"consent":"No"},"expected_path":["consent"]}]}
        """
        if cases is not None and (paths is not None or schema is not None):
            error(
                "USAGE_ERROR",
                "Use either --cases or --schema with --paths.",
                exit_code=EXIT_USAGE,
            )
        if cases is None and (paths is None or schema is None):
            error(
                "USAGE_ERROR",
                "Provide --cases, or both --schema and --paths.",
                exit_code=EXIT_USAGE,
            )

        try:
            survey = _load_survey(survey_path, preview=True)
            if cases is not None:
                from .survey_paths import check_question_paths

                return check_question_paths(survey, cases)

            from edsl.coop.coop_humanize_schema import validate_humanize_schema

            settings = read_serialized_object(Path(schema))
            validate_humanize_schema(survey, settings)
            if settings.get("survey", {}).get("presentation") != "group":
                raise ValueError(
                    "The browser settings must enable grouped presentation."
                )
            paths = load_json_object(paths)
            if not paths:
                raise ValueError("Provide at least one named respondent path.")
            for name, steps in paths.items():
                if not isinstance(steps, list) or not steps:
                    raise ValueError(f"Path {name!r} needs at least one page.")
                current = survey.next_group()
                answers = {}
                for i, step in enumerate(steps, 1):
                    expected = step["page"]
                    if current["is_end"] or current["question_names"] != expected:
                        raise ValueError(
                            f"{name}, page {i}: expected {expected}, got {current['question_names']}"
                        )
                    submitted = step.get("answers", {})
                    if not isinstance(submitted, dict) or not set(submitted).issubset(
                        expected
                    ):
                        raise ValueError(
                            f"{name}, page {i}: answer keys must be questions on this page."
                        )
                    answers.update({f"{k}.answer": v for k, v in submitted.items()})
                    current = survey.next_group(current["group_name"], answers)
                if not current["is_end"]:
                    raise ValueError(
                        f"{name}: expected end, got {current['question_names']}"
                    )
            output({"passed_paths": list(paths)})
        except Exception as exc:
            error("VALIDATION_ERROR", str(exc), exit_code=EXIT_VALIDATION)
