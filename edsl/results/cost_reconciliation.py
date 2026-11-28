"""Compare complete Results with remote accounting without retrying inference."""

import sys
import warnings
import math


class RemoteCostMismatchWarning(UserWarning):
    """Finalized accounting disagrees with complete downloaded Results."""


def reconcile_cost(results, remote_status: dict, *, notify: bool = True) -> dict:
    """Return a bounded diagnostic; incomplete or ambiguous scopes stay unknown.

    Tolerance is max($0.0001, 1% of remote cost). A mismatch does not identify
    which ledger is correct. No network requests or mutations are performed.
    """
    diagnostic = {"status": "not_comparable", "reason": None}
    details = remote_status.get("latest_job_run_details") or {}
    counts = details.get("interview_details") or {}
    if remote_status.get("status") != "completed":
        return {**diagnostic, "reason": "accounting_not_final"}
    total = counts.get("total_interviews")
    if (
        type(total) is not int
        or total != len(results)
        or counts.get("completed_interviews") != total
    ):
        return {**diagnostic, "reason": "incomplete_or_unknown_result_scope"}
    if counts.get("interviews_with_exceptions") not in (0, None):
        return {**diagnostic, "reason": "failed_interviews_may_have_separate_charges"}
    remote_cost = details.get("cost_usd")
    if (
        not isinstance(remote_cost, (int, float))
        or isinstance(remote_cost, bool)
        or not math.isfinite(remote_cost)
        or remote_cost < 0
    ):
        return {**diagnostic, "reason": "missing_remote_cost"}
    total_cost = 0.0
    for row in results:
        raw = row.get("raw_model_response") or {}
        cached = row.get("cache_used_dict") or {}
        answers = row.get("answer") or {}
        if not answers:
            return {**diagnostic, "reason": "missing_response_cost_metadata"}
        for question in answers:
            metadata = raw.get(f"{question}_response_metadata") or {}
            calls = metadata.get("provider_calls_attempted")
            retries = metadata.get("retry_count")
            if (isinstance(calls, int) and calls > 1) or (
                isinstance(retries, int) and retries > 0
            ):
                return {**diagnostic, "reason": "retries_may_have_separate_charges"}
            if type(cached.get(question)) is not bool:
                return {**diagnostic, "reason": "missing_cache_metadata"}
            if cached[question] is True:
                continue
            value = raw.get(f"{question}_cost")
            if (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or not math.isfinite(value)
                or value < 0
            ):
                return {**diagnostic, "reason": "missing_response_cost_metadata"}
            total_cost += value
    tolerance = max(0.0001, remote_cost * 0.01)
    delta = total_cost - remote_cost
    mismatch = abs(delta) > tolerance
    diagnostic = {
        "status": "mismatch" if mismatch else "matched",
        "results_cost_usd": total_cost,
        "remote_cost_usd": remote_cost,
        "difference_usd": delta,
        "tolerance_usd": tolerance,
    }
    if mismatch:
        message = (
            f"REMOTE_COST_MISMATCH: finalized remote cost ${remote_cost:.6f} differs from "
            f"Results cost ${total_cost:.6f}. Preserve these Results and investigate accounting; "
            "do not resubmit inference to repair a billing discrepancy."
        )
        diagnostic.update({"code": "REMOTE_COST_MISMATCH", "message": message})
        if notify:
            # A warning-as-error policy must not discard successfully fetched
            # answers or turn this diagnostic into an automatically retried run.
            try:
                warnings.warn(message, RemoteCostMismatchWarning, stacklevel=2)
            except RemoteCostMismatchWarning:
                print(message, file=sys.stderr)
    return diagnostic
