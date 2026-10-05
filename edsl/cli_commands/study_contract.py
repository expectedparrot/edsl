"""Versioned study expectations, independently checked against saved artifacts.

This is an audit contract, not a security boundary: a writable workspace cannot
authenticate human approval. Hosts must enforce authorization separately.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import click

from edsl.cli_shared import EXIT_VALIDATION, error, output


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name.strip() or Path(name).is_absolute():
        raise ValueError("Contract paths must be nonempty relative paths")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Contract path escapes study root: {name}")
    return path


def validate_spec(spec: dict, root: Path) -> None:
    if not isinstance(spec, dict) or spec.get("schema_version") != 1:
        raise ValueError("Expected study contract schema_version 1")
    jobs = spec.get("jobs")
    deliverables = spec.get("deliverables")
    if (
        not isinstance(jobs, list)
        or not isinstance(deliverables, list)
        or not (jobs or deliverables)
    ):
        raise ValueError(
            "Contract must declare jobs and deliverables lists with at least one expectation"
        )
    names = set()
    for job in jobs:
        if (
            not isinstance(job, dict)
            or not isinstance(job.get("id"), str)
            or not job["id"].strip()
            or job["id"] in names
        ):
            raise ValueError("Every job needs a distinct nonempty id")
        names.add(job["id"])
        for field in ("jobs_path", "results_path"):
            local_path(root, job.get(field))
        count = job.get("expected_rows")
        if type(count) is not int or count < 1:
            raise ValueError("expected_rows must be a positive integer")
        answers = job.get("required_answers")
        if not isinstance(answers, list) or not all(
            isinstance(a, str) and a.strip() for a in answers
        ):
            raise ValueError("required_answers must be a list of question names")
    for name in deliverables:
        local_path(root, name)
    for name in spec.get("protected_sources", []):
        local_path(root, name)
    local_path(root, spec.get("plan_path", "plan.md"))


def revisions(root: Path) -> list[Path]:
    return sorted((root / ".study-contract").glob("[0-9][0-9][0-9][0-9].json"))


def latest(root: Path) -> tuple[dict, Path]:
    files = revisions(root)
    if not files:
        raise ValueError(
            "No frozen study contract; freeze the approved specification before execution"
        )
    previous = None
    for number, path in enumerate(files, 1):
        record = json.loads(path.read_text())
        if (
            path.name != f"{number:04d}.json"
            or record.get("previous_sha256") != previous
        ):
            raise ValueError(
                "Study contract revision chain was changed or is incomplete"
            )
        validate_spec(record["spec"], root)
        previous = digest(path)
    return record, files[-1]


def freeze(
    root: Path, spec_path: Path, evidence: str, reason: str | None = None
) -> dict:
    if not evidence.strip() or (reason is not None and not reason.strip()):
        raise ValueError("Approval evidence and amendment reason must be nonempty")
    spec = json.loads(spec_path.read_text())
    validate_spec(spec, root)
    protected = set(spec.get("protected_sources", [])) | {
        spec.get("plan_path", "plan.md")
    }
    # Bind the code that builds the job and the validator, not just a prose count.
    hashes = {name: digest(local_path(root, name)) for name in sorted(protected)}
    files = revisions(root)
    prior = None
    if files:
        old, prior = latest(root)
        if reason is None:
            if old["spec"] == spec and old["protected_sha256"] == hashes:
                return {"revision": len(files), "reused": True, "sha256": digest(prior)}
            raise ValueError(
                "Frozen expectations changed; use contract amend with a reason and fresh approval evidence"
            )
    elif reason is not None:
        raise ValueError("Cannot amend a contract that has not been frozen")
    record = {
        "schema_version": 1,
        "revision": len(files) + 1,
        "spec": spec,
        "protected_sha256": hashes,
        "approval_evidence": evidence,
        "amendment_reason": reason,
        "previous_sha256": digest(prior) if prior else None,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    directory = root / ".study-contract"
    directory.mkdir(exist_ok=True)
    dest = directory / f"{len(files) + 1:04d}.json"
    with dest.open("x") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    return {
        "revision": record["revision"],
        "sha256": digest(dest),
        "path": str(dest),
        "reused": False,
    }


def verify(root: Path, phase: str = "complete") -> dict:
    record, path = latest(root)
    errors = []
    for name, expected in record["protected_sha256"].items():
        source = local_path(root, name)
        if not source.is_file() or digest(source) != expected:
            errors.append({"code": "PROTECTED_SOURCE_CHANGED", "path": name})
    if phase in {"results", "complete"}:
        from edsl import Results

        for job in record["spec"]["jobs"]:
            for field in ("jobs_path", "results_path"):
                artifact = local_path(root, job[field])
                if not artifact.is_file() or not artifact.stat().st_size:
                    errors.append(
                        {
                            "code": "MISSING_JOB_ARTIFACT",
                            "job": job["id"],
                            "path": job[field],
                        }
                    )
            result_path = local_path(root, job["results_path"])
            if not result_path.is_file():
                continue
            try:
                results = Results.git.load(str(result_path))
                if len(results) != job["expected_rows"]:
                    errors.append(
                        {
                            "code": "ROW_COUNT_MISMATCH",
                            "job": job["id"],
                            "expected": job["expected_rows"],
                            "actual": len(results),
                        }
                    )
                for name in job["required_answers"]:
                    missing = sum(
                        row.answer.get(name) is None or row.answer.get(name) == ""
                        for row in results
                    )
                    if missing:
                        errors.append(
                            {
                                "code": "MISSING_REQUIRED_ANSWERS",
                                "job": job["id"],
                                "question": name,
                                "count": missing,
                            }
                        )
            except Exception as exc:
                errors.append(
                    {
                        "code": "UNREADABLE_RESULTS",
                        "job": job["id"],
                        "error_type": type(exc).__name__,
                    }
                )
    if phase == "complete":
        for name in record["spec"]["deliverables"]:
            artifact = local_path(root, name)
            if not artifact.is_file() or not artifact.stat().st_size:
                errors.append({"code": "MISSING_DELIVERABLE", "path": name})
    return {
        "valid": not errors,
        "phase": phase,
        "revision": record["revision"],
        "contract_sha256": digest(path),
        "errors": errors,
        "next_action": (
            "Continue the approved workflow."
            if not errors
            else "Preserve the failed check. Complete missing work or obtain an explicit protocol amendment; do not weaken the validator."
        ),
    }


@click.group("contract")
def contract():
    """Freeze, amend, or independently verify a study's approved expectations."""


def _record(root, spec, approval_evidence, reason=None):
    try:
        output(freeze(root.resolve(), spec, approval_evidence, reason))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        error("STUDY_CONTRACT_ERROR", str(exc), exit_code=EXIT_VALIDATION)


@contract.command("freeze")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd)
@click.option("--spec", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--approval-evidence", required=True)
def freeze_command(root, spec, approval_evidence):
    """Snapshot the approved spec and protected files before execution."""
    _record(root, spec, approval_evidence)


@contract.command("amend")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd)
@click.option("--spec", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--approval-evidence", required=True)
@click.option("--reason", required=True)
def amend_command(root, spec, approval_evidence, reason):
    """Append an approved amendment; preserve all prior expectations."""
    _record(root, spec, approval_evidence, reason)


@contract.command("verify")
@click.option("--root", type=click.Path(path_type=Path), default=Path.cwd)
@click.option(
    "--phase", type=click.Choice(["sources", "results", "complete"]), default="complete"
)
def verify_command(root, phase):
    """Check saved work independently of editable study validation scripts."""
    try:
        result = verify(root.resolve(), phase)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        error("STUDY_CONTRACT_ERROR", str(exc), exit_code=EXIT_VALIDATION)
        return
    if not result["valid"]:
        error(
            "STUDY_CONTRACT_FAILED",
            "Saved work does not satisfy the approved study contract",
            suggestion=result["next_action"],
            details=result["errors"],
            exit_code=EXIT_VALIDATION,
        )
    output(result)
