"""Verify verbatim respondent wording across an imported instrument."""

from shlex import join

import click

from edsl.cli_shared import EXIT_USAGE, EXIT_VALIDATION, error, load_json_object, output
from .survey_question_model import preview


def _contains_in_order(text, phrases):
    offset = 0
    for phrase in phrases:
        start = text.find(phrase, offset)
        if start < 0:
            return False
        offset = start + len(phrase)
    return True


@click.command("check-wording")
@click.argument("survey_path", type=click.Path(exists=True))
@click.option(
    "--expected",
    help="JSON object or file mapping every question name to its approved wording or ordered list of literal phrases. Defaults to the authored stems.",
)
@click.option(
    "--forbid-text",
    multiple=True,
    help="Staff-only text that must be absent from every rendered prompt. Repeat for each phrase.",
)
@click.option("--scenario", help="Sample scenario values as a JSON object or file.")
@click.option("--traits", help="Sample agent traits as a JSON object or file.")
@click.option(
    "--answers",
    help="Sample answers for piping. Each prompt receives only earlier answers.",
)
def check_wording(survey_path, expected, forbid_text, scenario, traits, answers):
    """Render each question locally and check literal wording, including custom presentations.

    Checks the model prompts for one set of inputs. Use check-paths for routing.
    """
    from .surveys import _load_survey

    try:
        survey = _load_survey(survey_path, preview=True)
        stems = (
            load_json_object(expected)
            if expected is not None
            else {q.question_name: q.question_text for q in survey.questions}
        )
        names = survey.question_names
        phrases = {k: v if isinstance(v, list) else [v] for k, v in stems.items()}
        if set(stems) != set(names) or not all(
            items and all(isinstance(v, str) and v for v in items)
            for items in phrases.values()
        ):
            error(
                "USAGE_ERROR",
                "Each question needs a nonempty string or ordered list of nonempty strings.",
                suggestion=f"Supply --expected with these keys: {names}",
                exit_code=EXIT_USAGE,
            )
        if expected is None and any(
            any(token in v for token in ("{{", "{%", "{#")) for v in stems.values()
        ):
            error(
                "USAGE_ERROR",
                "Templated question text needs an independent expected rendering.",
                suggestion="Provide --expected and the sample --scenario, --traits or --answers used by the templates.",
                exit_code=EXIT_USAGE,
            )
        scenario, traits, answers = [
            load_json_object(v) if v is not None else {}
            for v in (scenario, traits, answers)
        ]
        if unknown := answers.keys() - set(names):
            error(
                "USAGE_ERROR",
                f"Unknown questions in sample answers: {sorted(unknown)}.",
                exit_code=EXIT_USAGE,
            )
        prior = {}
        failures = []
        for name in names:
            prompt = preview(survey, name, prior, traits, scenario)
            texts = [prompt[k] for k in ("user_prompt", "system_prompt")]
            missing = not any(_contains_in_order(text, phrases[name]) for text in texts)
            forbidden = [
                phrase for phrase in forbid_text if any(phrase in t for t in texts)
            ]
            if missing or forbidden:
                failure = {
                    "question": name,
                    "missing_wording": stems[name] if missing else None,
                    "forbidden_text_found": forbidden,
                }
                question = survey.get(name)
                if getattr(question, "_question_presentation", None):
                    failure["custom_question_presentation"] = (
                        question.question_presentation
                    )
                    failure["restore_default_presentation"] = join(
                        [
                            "ep",
                            "surveys",
                            "update-question",
                            survey_path,
                            name,
                            "--patch",
                            '{"question_presentation":null}',
                        ]
                    )
                failures.append(failure)
            if name in answers:
                prior[name] = answers[name]
        if failures:
            error(
                "SURVEY_WORDING_MISMATCH",
                f"{len(failures)} of {len(names)} rendered questions failed the wording checks.",
                suggestion="Use ep surveys preview-prompt SURVEY QUESTION to inspect the actual model input. If a custom presentation contains staff notes, keep those in a separate guide and use the reported restore command to render the normal stem and options. Rerun this check after edits.",
                details=failures,
                exit_code=EXIT_VALIDATION,
            )
        output({"checked_questions": names})
    except Exception as exc:
        error(
            "VALIDATION_ERROR",
            str(exc),
            suggestion="Check the survey and sample inputs.",
            exit_code=EXIT_VALIDATION,
        )
