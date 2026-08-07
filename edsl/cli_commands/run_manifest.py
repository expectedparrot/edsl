"""Execute declarative EDSL run manifests safely and resumably."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import click

from edsl.cli_shared import EXIT_REMOTE, EXIT_USAGE, error, load_any_object, output


def _expected_count(run: dict) -> int:
    value = run.get("prediction_count")
    if value is None:
        value = int(run.get("scenario_count") or 0) * int(run.get("model_count") or 1)
    return int(value or 0)


def _result_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len(load_any_object(str(path), expected_object_type="Results"))


def _execute_run(run: dict, *, base: Path, timeout: float) -> dict:
    job = Path(str(run["job_path"]))
    result = Path(str(run["result_path"]))
    if not result.is_absolute():
        result = base / result
    expected, actual = _expected_count(run), _result_count(result)
    if actual == expected and expected > 0:
        return {"job_path": str(job), "result_path": str(result), "expected_count": expected,
                "actual_count": actual, "status": "complete", "executed": False}
    partial = None
    if result.exists():
        partial = result.with_name(f"{result.stem}_partial_{actual}{result.suffix}")
        if partial.exists():
            raise RuntimeError(f"refusing to overwrite preserved partial result: {partial}")
        shutil.move(str(result), str(partial))
    result.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "edsl", "run", "--jobs", str(job), "--background", "--wait",
               "--timeout", str(timeout), "--output", str(result)]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout.strip() or completed.stderr.strip() or "ep run failed")
    actual = _result_count(result)
    if actual != expected:
        raise RuntimeError(f"result count mismatch for {result}: {actual}/{expected}")
    return {"job_path": str(job), "result_path": str(result), "expected_count": expected,
            "actual_count": actual, "status": "complete", "executed": True,
            "preserved_partial": str(partial) if partial else None}


def register(app: click.Group) -> None:
    @app.command("run-manifest")
    @click.argument("manifest", type=click.Path(exists=True, dir_okay=False))
    @click.option("--result-base", type=click.Path(file_okay=False), default=".", show_default=True)
    @click.option("--parallel", type=click.IntRange(min=1), default=1, show_default=True)
    @click.option("--timeout", type=click.FloatRange(min=1), default=3600.0, show_default=True)
    @click.option("--execute", is_flag=True, help="Run incomplete jobs remotely; otherwise only verify them.")
    def run_manifest(manifest, result_base, parallel, timeout, execute):
        """Verify or execute every job in a zwill/EDSL run manifest.

        \b
        Examples:
          ep run-manifest jobs/run-manifest.json
          ep run-manifest jobs/run-manifest.json --parallel 4 --execute
        """
        try:
            payload = json.loads(Path(manifest).read_text())
        except (OSError, json.JSONDecodeError) as exc:
            error("INVALID_MANIFEST", f"Could not read run manifest: {exc}", exit_code=EXIT_USAGE)
        runs = payload.get("runs") if isinstance(payload, dict) else None
        if not isinstance(runs, list) or not runs:
            error("INVALID_MANIFEST", "Run manifest needs a non-empty 'runs' list.", exit_code=EXIT_USAGE)
        base = Path(result_base).resolve()
        records, incomplete = [], []
        for run in runs:
            result = Path(str(run.get("result_path", "")))
            if not result.is_absolute():
                result = base / result
            expected, actual = _expected_count(run), _result_count(result)
            record = {"job_path": str(run.get("job_path", "")), "result_path": str(result),
                      "expected_count": expected, "actual_count": actual,
                      "status": "complete" if expected > 0 and actual == expected else "incomplete",
                      "executed": False}
            records.append(record)
            if record["status"] == "incomplete":
                incomplete.append(run)
        if incomplete and not execute:
            error("INCOMPLETE_RUNS", f"{len(incomplete)} run(s) are incomplete.",
                  suggestion="Review the manifest and rerun with --execute to permit remote inference.",
                  exit_code=EXIT_REMOTE, details=records)
        if incomplete:
            completed_records, failures = [], []
            with ThreadPoolExecutor(max_workers=parallel) as pool:
                futures = {pool.submit(_execute_run, run, base=base, timeout=timeout): run for run in incomplete}
                for future in as_completed(futures):
                    try:
                        completed_records.append(future.result())
                    except Exception as exc:
                        failures.append({"job_path": str(futures[future].get("job_path", "")), "error": str(exc)})
            if failures:
                error("RUN_MANIFEST_FAILED", f"{len(failures)} manifest run(s) failed.",
                      exit_code=EXIT_REMOTE, details=failures)
            by_result = {row["result_path"]: row for row in completed_records}
            records = [by_result.get(row["result_path"], row) for row in records]
        output({"manifest": str(Path(manifest).resolve()), "run_count": len(records),
                "executed_count": sum(bool(row["executed"]) for row in records), "runs": records})
