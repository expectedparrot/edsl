"""Inspect a participant's stored render and submission from a local workflow."""

from pathlib import Path
import sqlite3

import click

from edsl.cli_shared import (
    EXIT_NOT_FOUND,
    EXIT_VALIDATION,
    error,
    json_values_match,
    load_json_object,
    output,
)


@click.command("check-item")
@click.argument(
    "run_dir", type=click.Path(exists=True, file_okay=False, path_type=Path)
)
@click.option("--step", required=True, help="Workflow step name.")
@click.option("--participant", required=True, help="Participant ID.")
@click.option("--instance-id", default="experiment", show_default=True)
@click.option(
    "--expect-status",
    help="Require a recorded item status such as completed or skipped.",
)
@click.option("--question", help="Check the text of only this question.")
@click.option(
    "--expect-text",
    multiple=True,
    help="Require this literal text in a saved question stem. Repeatable.",
)
@click.option(
    "--forbid-text",
    multiple=True,
    help="Reject this literal text in a saved question stem. Repeatable.",
)
@click.option(
    "--expect-answers",
    help="Expected submitted answers as a JSON object or file. Only named answers are checked.",
)
def check_item(
    run_dir,
    step,
    participant,
    instance_id,
    question,
    expect_text,
    forbid_text,
    expect_answers,
    expect_status,
):
    """Read what this participant was shown in a saved workflow run, without rerunning it."""
    from edsl.workflows.store import SQLiteWorkflowStore

    path = run_dir / "workflow.sqlite"
    if not path.is_file():
        error(
            "FILE_NOT_FOUND",
            f"No workflow.sqlite in {run_dir}.",
            exit_code=EXIT_NOT_FOUND,
        )
    try:
        item = SQLiteWorkflowStore.read_recorded_item(
            path, instance_id, step, participant
        )
    except (ValueError, sqlite3.Error) as exc:
        error(
            "VALIDATION_ERROR",
            f"Could not read the saved work item: {exc}",
            exit_code=EXIT_VALIDATION,
        )
    if item is None:
        error(
            "WORK_ITEM_NOT_FOUND",
            f"No recorded item for step {step!r}, participant {participant!r} in instance {instance_id!r}.",
            exit_code=EXIT_NOT_FOUND,
        )

    survey = item["survey"]
    questions = {
        q["question_name"]: q["question_text"]
        for q in (survey or {}).get("questions", [])
        if "question_name" in q and "question_text" in q
    }
    if question and survey is not None and question not in questions:
        error(
            "QUESTION_NOT_FOUND",
            f"No recorded question {question!r}.",
            details=[{"questions": list(questions)}],
            exit_code=EXIT_NOT_FOUND,
        )
    if question and question in questions:
        questions = {question: questions[question]}

    data = {
        "instance_id": instance_id,
        "step": step,
        "participant": participant,
        "status": item["status"],
        "rendered": survey is not None,
        "questions": questions,
        "submitted": item["answers"] is not None,
        "answer_keys": sorted(item["answers"] or {}),
    }
    missing = [
        s for s in expect_text if not any(s in text for text in questions.values())
    ]
    forbidden = [
        s for s in forbid_text if any(s in text for text in questions.values())
    ]
    try:
        expected = (
            load_json_object(expect_answers) if expect_answers is not None else {}
        )
    except (OSError, ValueError) as exc:
        error("VALIDATION_ERROR", str(exc), exit_code=EXIT_VALIDATION)

    actual = item["answers"] or {}
    mismatches = [
        k
        for k, v in expected.items()
        if k not in actual or not json_values_match(v, actual[k])
    ]
    if (
        missing
        or forbidden
        or mismatches
        or (expect_status is not None and item["status"] != expect_status)
        or (survey is None and (expect_text or forbid_text or question))
        or (item["answers"] is None and expect_answers is not None)
    ):
        error(
            "WORK_ITEM_MISMATCH",
            "The recorded item failed the requested checks.",
            suggestion="Check the recorded render, participant, workflow answer references and executor bindings.",
            details=[
                {
                    **data,
                    "missing_text": missing,
                    "forbidden_text_found": forbidden,
                    "mismatched_answers": mismatches,
                    "expected_status": expect_status,
                }
            ],
            exit_code=EXIT_VALIDATION,
        )
    output(data)
