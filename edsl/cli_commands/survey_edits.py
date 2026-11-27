"""Local, name-based edits to native Survey objects."""

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


def register(group):
    from .surveys import (
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

    @group.command("update-question")
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

    @group.command("rename-question")
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

    @group.command("set-groups")
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

    @group.command("check-paths")
    @click.argument("survey_path", type=local_file)
    @click.option(
        "--schema",
        type=local_file,
        required=True,
        help="Browser settings JSON for grouped presentation.",
    )
    @click.option(
        "--paths",
        required=True,
        help="JSON object or file of named paths, each a list of {page, answers} steps.",
    )
    def check_paths(survey_path, schema, paths):
        """Check the pages shown to each respondent through the end of the survey."""
        from edsl.coop.coop_humanize_schema import validate_humanize_schema

        try:
            survey = _load_survey(survey_path, preview=True)
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
