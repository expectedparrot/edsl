"""Exercise a selected interview with scripted local model responses."""

import asyncio
from contextlib import redirect_stdout
import json
from pathlib import Path
import sys

import click

from edsl.cli_shared import (
    EXIT_USAGE,
    EXIT_VALIDATION,
    error,
    load_json_object,
    output,
    read_package_manifest,
    save_edsl_object,
)
from .job_prompt_preview import assigned_interview


def _matches(expected, actual):
    if type(expected) in (float, int) and type(actual) in (float, int):
        return expected == actual
    if type(expected) is not type(actual):
        return False
    if isinstance(expected, list):
        return len(expected) == len(actual) and all(
            _matches(x, y) for x, y in zip(expected, actual)
        )
    if isinstance(expected, dict):
        return expected.keys() == actual.keys() and all(
            _matches(v, actual[k]) for k, v in expected.items()
        )
    return expected == actual


@click.command("test-case")
@click.argument("jobs_path", type=click.Path(exists=True))
@click.option(
    "--interview-index",
    type=click.IntRange(min=0),
    default=0,
    show_default=True,
    help="Zero-based interview in the saved job's assignment order.",
)
@click.option(
    "--responses",
    required=True,
    help="JSON object or file of test-model replies keyed by question name.",
)
@click.option(
    "--expect",
    help="JSON object or file of expected final EDSL answers keyed by question name.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    help="Save the successful interview as Results (.ep or .json).",
)
def test_case(jobs_path, interview_index, responses, expect, output_path):
    """Run one local regression case through EDSL's normal interview and validation code.

    Supply model replies as JSON values. --expect checks the final answer after
    EDSL translates and validates it. A failed case exits 5.

    \b
    Example:
      ep jobs test-case study.ep --interview-index 1 --responses replies.json --expect answers.json -o passed.ep
    """
    from edsl import Model, Results
    from edsl.caching import Cache
    from edsl.results import Result
    from edsl.tasks import TaskHistory

    try:
        replies = load_json_object(responses)
        expected = load_json_object(expect) if expect is not None else {}
        if output_path is not None:
            source = Path(jobs_path)
            same_input = output_path.exists() and output_path.samefile(source)
            inside_input = (
                source.is_dir() and source.resolve() in output_path.resolve().parents
            )
            if output_path.suffix not in {".ep", ".json"} or same_input or inside_input:
                error(
                    "USAGE_ERROR",
                    "Choose a separate Results .ep or .json output file.",
                    exit_code=EXIT_USAGE,
                )
            if output_path.exists() and output_path.suffix == ".ep":
                if (
                    read_package_manifest(output_path).get("edsl_class_name")
                    != "Results"
                ):
                    error(
                        "USAGE_ERROR",
                        "The output package already contains another object type.",
                        exit_code=EXIT_USAGE,
                    )
        interview, planned = assigned_interview(
            jobs_path, interview_index, skip_retry=True
        )
        names = interview.survey.question_names
        unknown = (replies.keys() | expected.keys()) - set(names)
        if unknown:
            error(
                "USAGE_ERROR",
                f"Unknown question names: {sorted(unknown)}.",
                suggestion=f"Available questions: {names}",
                exit_code=EXIT_USAGE,
            )

        canned = {
            q: (
                value
                if isinstance(value, str)
                else json.dumps(value, ensure_ascii=False)
            )
            for q, value in replies.items()
        }
        model = Model("test", canned_response=canned)
        interview.model = model
        interview.cache = Cache()
        for question in interview.survey.questions:
            if getattr(question, "_model", None) is not None:
                question._model = Model(
                    "test", canned_response=canned.get(question.question_name, "")
                )
        with redirect_stdout(sys.stderr):
            asyncio.run(interview.async_conduct_interview())
            result = Result.from_interview(interview)
        answers = result.answer
        data = {
            "interview_index": interview_index,
            "planned_interviews": planned,
            "indices": interview.indices,
            "iteration": interview.iteration,
            "model": "test",
            "answers": answers,
        }
        mismatches = {
            q: {"expected": v, "actual": answers.get(q)}
            for q, v in expected.items()
            if q not in answers or not _matches(v, answers[q])
        }
        failures = interview.exceptions.unfixed_exceptions()
        failed = sorted(failures)
        reasons = {
            q: str(entries[-1].exception)[:500]
            for q, entries in failures.items()
            if entries
        }
        raw = result.get("raw_model_response", {})
        missing = [
            q
            for q in names
            if q not in replies and isinstance(raw.get(f"{q}_raw_model_response"), dict)
        ]
        if failed or missing or mismatches:
            error(
                "JOB_TEST_CASE_FAILED",
                "The scripted interview failed its checks.",
                suggestion="Review the model replies, the assigned scenario, and the expected final answer values.",
                details=[
                    {
                        **data,
                        "failed_questions": failed,
                        "failure_reasons": reasons,
                        "missing_responses": missing,
                        "mismatches": mismatches,
                    }
                ],
                exit_code=EXIT_VALIDATION,
            )
        if output_path is not None:
            results = Results(
                survey=interview.survey,
                data=[result],
                task_history=TaskHistory(interviews=[interview]),
            )
            if output_path.suffix == ".ep":
                info = results.git.save(
                    output_path, allow_new_commit=True, sync_coop=False
                )
                data["saved"] = {
                    "path": str(output_path),
                    "format": "ep",
                    "object_type": "Results",
                    "commit": info["commit"],
                }
            else:
                data["saved"] = save_edsl_object(
                    results, str(output_path), sync_coop=False
                )
        output(data)
    except Exception as exc:
        error(
            "JOB_TEST_CASE_ERROR",
            str(exc),
            suggestion="Check the job path, interview index and JSON inputs.",
            exit_code=EXIT_VALIDATION,
        )
