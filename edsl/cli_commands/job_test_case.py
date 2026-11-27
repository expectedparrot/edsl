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
    json_values_match,
    load_json_object,
    output,
    read_package_manifest,
    save_edsl_object,
)
from .job_prompt_preview import assigned_interview, assigned_interviews


@click.command("test-case")
@click.argument("jobs_path", type=click.Path(exists=True))
@click.option(
    "--interview-index",
    type=click.IntRange(min=0),
    default=None,
    help="Zero-based interview in the saved job's assignment order (default 0).",
)
@click.option(
    "--all",
    "all_interviews",
    is_flag=True,
    help="Rehearse every assigned interview with the same reply map.",
)
@click.option(
    "--iterations",
    "-n",
    type=click.IntRange(min=1),
    help="Iterations for --all. Defaults to the saved job schedule.",
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
    "--expect-rejection",
    metavar="QUESTION",
    help="Pass only if the named question rejects its scripted reply in answer validation.",
)
@click.option(
    "--output",
    "-o",
    "output_path",
    type=click.Path(path_type=Path),
    help="Save the successful interview as Results (.ep or .json).",
)
def test_case(
    jobs_path,
    interview_index,
    all_interviews,
    iterations,
    responses,
    expect,
    expect_rejection,
    output_path,
):
    """Rehearse a saved job with local test models and EDSL's normal answer validation.

    Supply model replies as JSON values. --expect checks the final answer after
    EDSL translates and validates it. A failed case exits 5.

    \b
    Example:
      ep jobs test-case study.ep --all -n 4 --responses replies.json -o rehearsal.ep
      ep jobs test-case study.ep --interview-index 1 --responses replies.json --expect answers.json -o passed.ep
    """
    from edsl import Results
    from edsl.tasks import TaskHistory

    try:
        replies = load_json_object(responses)
        expected = load_json_object(expect) if expect is not None else {}
        if expect_rejection is not None:
            if (
                expect_rejection not in replies
                or expect_rejection in expected
                or output_path is not None
            ):
                error(
                    "USAGE_ERROR",
                    "--expect-rejection requires a scripted reply for that question, no expected answer for it, and no Results output.",
                    exit_code=EXIT_USAGE,
                )
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
        if all_interviews and interview_index is not None:
            error(
                "USAGE_ERROR",
                "Choose either --all or --interview-index.",
                exit_code=EXIT_USAGE,
            )
        if iterations is not None and not all_interviews:
            error("USAGE_ERROR", "--iterations requires --all.", exit_code=EXIT_USAGE)
        if all_interviews:
            survey, interviews, planned = assigned_interviews(
                jobs_path, iterations=iterations, skip_retry=True
            )
            cases = enumerate(interviews)
        else:
            index = interview_index or 0
            interview, planned = assigned_interview(jobs_path, index, skip_retry=True)
            survey = interview.survey
            cases = [(index, interview)]
        names = survey.question_names
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
        rows = []
        completed = []
        count = 0
        for index, interview in cases:
            row, case = _run_case(
                interview, index, planned, canned, expected, expect_rejection
            )
            count += 1
            if output_path is not None:
                rows.append(row)
                completed.append(interview)
        if not count:
            error(
                "JOB_TEST_CASE_FAILED",
                "The saved job produced no assigned interviews.",
                exit_code=EXIT_VALIDATION,
            )
        data = (
            {"tested_interviews": count, "planned_interviews": planned, "model": "test"}
            if all_interviews
            else case
        )
        if all_interviews and expect_rejection is not None:
            data.update(expected_rejection=expect_rejection, validation_rejected=True)
        if output_path is not None:
            results = Results(
                survey=survey,
                data=rows,
                task_history=TaskHistory(interviews=completed),
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


def _run_case(
    interview, interview_index, planned, canned, expected, expect_rejection=None
):
    from edsl.questions.exceptions import QuestionAnswerValidationError
    from edsl import Model
    from edsl.caching import Cache
    from edsl.results import Result

    model = Model("test", canned_response=canned)
    interview.model = model
    interview.cache = Cache()
    overrides = [
        (q, q._model)
        for q in interview.survey.questions
        if getattr(q, "_model", None) is not None
    ]
    try:
        for question, _ in overrides:
            question._model = Model(
                "test", canned_response=canned.get(question.question_name, "")
            )
        with redirect_stdout(sys.stderr):
            asyncio.run(interview.async_conduct_interview())
            result = Result.from_interview(interview)
    finally:
        for question, original_model in overrides:
            question._model = original_model
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
        if q not in answers or not json_values_match(v, answers[q])
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
        for q in interview.survey.question_names
        if q not in canned and isinstance(raw.get(f"{q}_raw_model_response"), dict)
    ]
    if expect_rejection is not None:
        rejected = bool(failures.get(expect_rejection)) and isinstance(
            failures[expect_rejection][-1].exception, QuestionAnswerValidationError
        )
        data.update(expected_rejection=expect_rejection, validation_rejected=rejected)
        unexpected_failure = set(failed) != {expect_rejection} or not rejected
    else:
        unexpected_failure = bool(failed)
    if unexpected_failure or missing or mismatches:
        message = "The scripted interview failed its checks."
        if expect_rejection is not None and not rejected:
            if expect_rejection in answers and answers[expect_rejection] is not None:
                message = f"{expect_rejection!r} accepted the scripted reply. Expected answer validation to reject it."
            else:
                message = f"No answer-validation rejection was recorded for {expect_rejection!r}. Check routing and interview errors."
        error(
            "JOB_TEST_CASE_FAILED",
            message,
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
    return result, data
