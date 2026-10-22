"""Interrupt local coopr services during small live shared-state examples.

Requires --live and explicit --restart selections. Only targets localhost and the
named services in the local coopr Compose project. Provider calls may repeat when
a worker dies before persisting its answer; committed state must remain unique.
"""

from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlparse

import requests

from edsl import Model
from edsl.runner.serialization import serialize_job, deserialize_results
from examples.shared_state_advanced_acceptance import (
    binding,
    build_case,
    check_case,
    save_transcript,
)

CASES = {
    "runner-api": "message_board",
    "runner-dispatcher": "repeated_matrix",
    "runner-worker": "pairwise_comparisons",
}


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def run_case(service, args, directory):
    headers = (
        {"X-API-Key": os.environ["COOPR_RUNNER_TEST_KEY"]}
        if os.environ.get("COOPR_RUNNER_TEST_KEY")
        else {}
    )
    base = args.runner_url.rstrip("/")
    name = CASES[service]
    job = build_case(name, Model(args.model, service_name="openai", max_tokens=256))
    job.save(str(directory / "live.jobs.ep"))
    response = requests.post(
        base + "/jobs",
        json={"job": serialize_job(job), "mock_llm": False, "fresh": True},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    submission = response.json()
    save(directory / "submission.json", submission)
    jid = submission["job_id"]
    print(
        json.dumps(
            {"service": service, "case": name, "job_id": jid, "phase": "submitted"}
        ),
        file=sys.stderr,
        flush=True,
    )
    start = time.monotonic()
    deadline = start + args.timeout
    restarted = False
    history = []
    last_progress = None
    while time.monotonic() < deadline:
        try:
            response = requests.get(
                f"{base}/jobs/{jid}/progress", headers=headers, timeout=5
            )
            response.raise_for_status()
            progress = response.json()
        except requests.RequestException as exc:
            if not restarted:
                raise
            entry = {
                "elapsed_seconds": round(time.monotonic() - start, 3),
                "unavailable": type(exc).__name__,
            }
            history.append(entry)
            save(directory / "progress-history.json", history)
            time.sleep(0.25)
            continue
        if progress != last_progress:
            history.append(
                {"elapsed_seconds": round(time.monotonic() - start, 3), **progress}
            )
            save(directory / "progress-history.json", history)
            last_progress = progress
        terminal = progress["status"] in (
            "completed",
            "completed_with_failures",
            "failed",
            "cancelled",
        )
        if terminal:
            save(directory / "status.json", progress)
            if progress["status"] != "completed":
                errors = requests.get(
                    f"{base}/jobs/{jid}/errors", headers=headers, timeout=10
                )
                errors.raise_for_status()
                save(directory / "errors.json", errors.json())
                raise RuntimeError(f"Job {jid} ended as {progress['status']}")
            assert (
                restarted
            ), "Job finished before the restart trigger; no recovery demonstrated"
            break
        if (
            not restarted
            and 0 < progress["completed_tasks"] < progress["total_tasks"]
            and progress["running_tasks"] > 0
        ):
            evidence = {
                "service": service,
                "case": name,
                "job_id": jid,
                "progress_before_restart": progress,
                "restart_elapsed_seconds": round(time.monotonic() - start, 3),
            }
            save(directory / "restart.json", evidence)
            print(
                json.dumps(
                    {
                        "service": service,
                        "phase": "restarting",
                        "completed_tasks": progress["completed_tasks"],
                        "running_tasks": progress["running_tasks"],
                    }
                ),
                file=sys.stderr,
                flush=True,
            )
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    "docker-compose.yml",
                    "-f",
                    "docker-compose.shared-state.yml",
                    "restart",
                    "-t",
                    "0",
                    service,
                ],
                cwd=args.coopr_dir,
                capture_output=True,
                text=True,
                timeout=45,
            )
            # Preserve diagnostics without copying any environment or credentials.
            (directory / "restart.log").write_text(result.stdout + result.stderr)
            evidence.update(
                exit_code=result.returncode,
                restart_returned_seconds=round(time.monotonic() - start, 3),
            )
            save(directory / "restart.json", evidence)
            result.check_returncode()
            restarted = True
        time.sleep(0.1)
    else:
        raise TimeoutError(
            f"Job {jid} is still active; inspect saved submission before retrying"
        )
    assert progress["failed_tasks"] == progress["blocked_tasks"] == 0
    assert (
        progress["completed_tasks"] + progress["skipped_tasks"]
        == progress["total_tasks"]
    )
    response = requests.get(f"{base}/jobs/{jid}/results", headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()
    save(directory / "runner-response.json", payload)
    results = deserialize_results(payload["results"])
    results.save(str(directory / "coopr.results.ep"))
    save_transcript(results, directory)
    actual = check_case(name, results)
    writes = [e for e in binding(results)["events"] if e["kind"] == "write"]
    command = {
        "message_board": "add",
        "repeated_matrix": "submit",
        "pairwise_comparisons": "compare",
    }[name]
    decisions = [e for e in writes if e["command"] == command]
    assert len(decisions) == 6, "Missing or duplicate committed decisions"
    assert len({e["event_id"] for e in decisions}) == 6
    assert len({(e["scope_canonical"], e["version"]) for e in decisions}) == 6
    return {
        "service": service,
        "case": name,
        "status": "passed",
        "job_id": jid,
        "rows": len(results),
        "decisions": len(decisions),
        "actual": actual,
        "elapsed_seconds": round(time.monotonic() - start, 2),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--restart", action="append", choices=CASES, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-4o-mini")
    parser.add_argument("--runner-url", default="http://localhost:8001")
    parser.add_argument(
        "--coopr-dir", type=Path, default=Path(__file__).resolve().parents[2] / "coopr"
    )
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    if not args.live:
        parser.error(
            "--live is required: this test makes provider calls and restarts local services"
        )
    if urlparse(args.runner_url).hostname not in ("localhost", "127.0.0.1"):
        parser.error("Restart acceptance is restricted to the local runner")
    if len(set(args.restart)) != len(args.restart):
        parser.error("Select each restart service only once")
    args.output.mkdir(parents=True, exist_ok=False)
    records = []
    for service in args.restart:
        directory = args.output / service
        directory.mkdir()
        try:
            with redirect_stdout(sys.stderr):
                record = run_case(service, args, directory)
        except Exception as exc:
            record = {
                "service": service,
                "case": CASES[service],
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
            }
        records.append(record)
        print(json.dumps(record), file=sys.stderr, flush=True)
        save(args.output / "summary.json", records)
        # A failed restart can leave a service unavailable; stop the batch for diagnosis.
        if record["status"] != "passed":
            break
    lines = [
        "# Live shared-state restart acceptance",
        "",
        f"Local coopr, {args.model}, fresh inference. Restart triggered after completed work while another task was running.",
        "",
        "| Restarted service | Case | Status | Outcome | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in records:
        service = r["service"]
        lines.append(
            f"| {service} | {r['case']} | {r['status']} | {json.dumps(r.get('actual',r.get('error')))} | [Restart]({service}/restart.json) · [Progress]({service}/progress-history.json) · [Transcript]({service}/transcript.md) |"
        )
    lines += [
        "",
        "This verifies recovered decisions and state, not exactly-once provider calls or billing. Redis/PostgreSQL persistence and local infrastructure remain intact during these service restarts.",
        "",
    ]
    report = args.output / "report.md"
    report.write_text("\n".join(lines))
    passed = sum(r["status"] == "passed" for r in records)
    success = passed == len(args.restart)
    print(
        json.dumps(
            {
                "status": "ok" if success else "error",
                "passed": passed,
                "requested": len(args.restart),
                "report": str(report),
            }
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
