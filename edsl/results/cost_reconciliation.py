"""Compare complete Results with remote accounting without retrying inference."""

import sys
import warnings
import math


class RemoteCostMismatchWarning(UserWarning):
    """Finalized accounting disagrees with complete downloaded Results."""


def _known_usd(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _has_retries(metadata):
    if not isinstance(metadata, dict):
        return False
    calls, retries = metadata.get("provider_calls_attempted"), metadata.get(
        "retry_count"
    )
    return (isinstance(calls, int) and calls > 1) or (
        isinstance(retries, int) and retries > 0
    )


def recorded_costs(results):
    """Account for the prices and cache flags actually present in saved responses."""
    known = {"cached": 0.0, "uncached": 0.0}
    unpriced = {"cached": 0, "uncached": 0}
    unknown_cache = unpriced_unknown_cache = retries = missing_metadata = 0
    unknown_cache_value = 0.0
    for row in results:
        raw = row.get("raw_model_response") or {}
        flags = row.get("cache_used_dict") or {}
        answers = row.get("answer") or {}
        questions = set(answers) | set(flags)
        questions.update(key.removesuffix("_cost") for key in raw if key.endswith("_cost"))
        questions.update(
            key.removesuffix("_raw_model_response")
            for key in raw
            if key.endswith("_raw_model_response")
        )
        for question in questions:
            flag = flags.get(question)
            price = raw.get(f"{question}_cost")
            response = raw.get(f"{question}_raw_model_response")
            if flag == "Not Applicable" or response == "Not Applicable":
                continue
            if _has_retries(raw.get(f"{question}_response_metadata") or {}):
                retries += 1
            if type(flag) is not bool:
                if response is not None or _known_usd(price):
                    unknown_cache += 1
                    if _known_usd(price):
                        unknown_cache_value += price
                    else:
                        unpriced_unknown_cache += 1
                elif answers.get(question) is not None:
                    missing_metadata += 1
                continue
            group = "cached" if flag else "uncached"
            if _known_usd(price):
                known[group] += price
            else:
                unpriced[group] += 1

    complete = not (
        unknown_cache or retries or missing_metadata or unpriced["uncached"]
    )
    return {
        "actual_cost_usd": known["uncached"] if complete else None,
        "known_uncached_cost_usd": known["uncached"],
        "known_cached_value_usd": known["cached"],
        "unpriced_uncached_calls": unpriced["uncached"],
        "unpriced_cached_calls": unpriced["cached"],
        "unknown_cache_status_calls": unknown_cache,
        "known_value_unknown_cache_status_usd": unknown_cache_value,
        "unpriced_unknown_cache_status_calls": unpriced_unknown_cache,
        "responses_without_cost_metadata": missing_metadata,
        "responses_with_retries": retries,
    }


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
    if not _known_usd(remote_cost):
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
            if _has_retries(metadata):
                return {**diagnostic, "reason": "retries_may_have_separate_charges"}
            if type(cached.get(question)) is not bool:
                return {**diagnostic, "reason": "missing_cache_metadata"}
            if cached[question] is True:
                continue
            value = raw.get(f"{question}_cost")
            if not _known_usd(value):
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
