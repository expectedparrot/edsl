"""Preview a saved job's text prompts without running model inference."""

from base64 import b64decode
from hashlib import sha256
from itertools import islice
from pathlib import PureWindowsPath
import re

import click

from edsl.cli_shared import (
    EXIT_VALIDATION,
    error,
    load_any_object,
    load_json_object,
    output,
)


def _attachment_summary(file):
    """Inspect embedded bytes without reconstructing the original file on disk."""
    content = b64decode(file.base64_string)
    name = file.get("path")
    return {
        "name": PureWindowsPath(name).name if name else None,
        "mime_type": file.mime_type,
        "size_bytes": len(content),
        "sha256": sha256(content).hexdigest(),
    }


def assigned_interview(jobs_path, interview_index, *, skip_retry=False):
    """Select from the same realized assignment order used by the job runner."""
    from edsl.jobs import Jobs
    from edsl.jobs.async_interview_runner import AsyncInterviewRunner

    job = load_any_object(jobs_path, preview=True)
    if not isinstance(job, Jobs):
        raise ValueError(f"Expected Jobs, found {type(job).__name__}.")
    job.run_config.parameters.skip_retry = skip_retry
    job.replace_missing_objects()
    planned_interviews = len(job) * job.run_config.parameters.n
    if job.treatment_assignment:
        job.run_config.parameters.n = (
            job.treatment_assignment.planned_iterations
        )
        planned_interviews = (
            len(job.agents) * len(job.models) * job.run_config.parameters.n
        )
    interviews = AsyncInterviewRunner(job, job.run_config)._expand_interviews()
    interview = next(
        islice(interviews, interview_index, interview_index + 1), None
    )
    if interview is None:
        raise ValueError(
            f"No assigned interview at index {interview_index}. This job plans {planned_interviews} interviews."
        )
    return interview, planned_interviews


def register(group):

    @group.command("preview-prompt")
    @click.argument("jobs_path", type=click.Path(exists=True))
    @click.argument("question_name")
    @click.option(
        "--interview-index",
        default=0,
        show_default=True,
        type=click.IntRange(min=0),
        help="Zero-based interview in the job's assignment order.",
    )
    @click.option("--answers", help="Sample earlier answers as a JSON object or file.")
    @click.option(
        "--expect-text",
        multiple=True,
        help="Require this literal text in either prompt. Repeatable.",
    )
    @click.option(
        "--forbid-text",
        multiple=True,
        help="Reject this literal text in either prompt. Repeatable.",
    )
    @click.option(
        "--expect-files",
        type=click.IntRange(min=0),
        help="Require this many FileStore attachments in the rendered prompt.",
    )
    @click.option(
        "--expect-file-sha256",
        multiple=True,
        metavar="HEX",
        help="Require exactly these attachment digests, in the given order. Repeat for each file.",
    )
    def preview_prompt(
        jobs_path,
        question_name,
        interview_index,
        answers,
        expect_text,
        forbid_text,
        expect_files,
        expect_file_sha256,
    ):
        """Render one question for an assigned interview in a saved Jobs file.

        Uses the saved agent, scenario and model. This previews the question in
        isolation. Use surveys check-paths to verify that routing reaches it.
        Text checks are case-sensitive.
        """
        from edsl.jobs.fetch_invigilator import FetchInvigilator

        try:
            expected_digests = [s.lower() for s in expect_file_sha256]
            if any(not re.fullmatch(r"[0-9a-f]{64}", s) for s in expected_digests):
                raise ValueError(
                    "--expect-file-sha256 requires a 64-digit hexadecimal SHA-256 digest for each file."
                )
            interview, planned_interviews = assigned_interview(
                jobs_path, interview_index
            )
            survey = interview.survey
            prior = load_json_object(answers) if answers is not None else {}
            question = survey.get(question_name)
            earlier = survey.question_names[
                : survey.question_names.index(question_name)
            ]
            if invalid := prior.keys() - set(earlier):
                raise ValueError(
                    f"--answers must name earlier questions. Invalid names: {sorted(invalid)}."
                )
            prompts = FetchInvigilator(interview, current_answers=prior)(
                question
            ).get_prompts()
            texts = {key: prompts[key].text for key in ("user_prompt", "system_prompt")}
            data = {
                "planned_interviews": planned_interviews,
                "interview_index": interview_index,
                "indices": interview.indices,
                "iteration": interview.iteration,
                "question_name": question_name,
                "attachments": [
                    _attachment_summary(f) for f in prompts.get("files_list", [])
                ],
                **texts,
            }
            if expect_files is not None and len(data["attachments"]) != expect_files:
                error(
                    "PROMPT_ATTACHMENT_MISMATCH",
                    f"Expected {expect_files} attached files, found {len(data['attachments'])}.",
                    suggestion="Reference the FileStore field in every question that needs it, for example {{ scenario.artwork }}. Preview the saved job again.",
                    details=[data],
                    exit_code=EXIT_VALIDATION,
                )
            if expected_digests and expected_digests != [
                a["sha256"] for a in data["attachments"]
            ]:
                error(
                    "PROMPT_ATTACHMENT_MISMATCH",
                    "The attached files differ from the expected SHA-256 digests or order.",
                    suggestion="Compare the listed attachments with the expected files for this interview. Check the scenario and question template.",
                    details=[{**data, "expected_sha256": expected_digests}],
                    exit_code=EXIT_VALIDATION,
                )
            missing = [
                s for s in expect_text if not any(s in text for text in texts.values())
            ]
            forbidden = [
                s for s in forbid_text if any(s in text for text in texts.values())
            ]
            if missing or forbidden:
                error(
                    "PROMPT_TEXT_MISMATCH",
                    "The rendered prompts failed the requested text checks.",
                    suggestion="Inspect the prompts below. Check the assignment, Jinja condition, and which respondent traits the question receives.",
                    details=[
                        {
                            **data,
                            "missing_text": missing,
                            "forbidden_text_found": forbidden,
                        }
                    ],
                    exit_code=EXIT_VALIDATION,
                )
            output(data)
        except Exception as exc:
            error(
                "VALIDATION_ERROR",
                str(exc),
                exit_code=EXIT_VALIDATION,
                suggestion="Check the saved job, interview index, question name, and sample earlier answers.",
            )
