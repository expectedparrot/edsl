"""Normalize result dictionaries for content hashing."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


_PROVENANCE_METADATA_KEYS = {
    "provider_calls_attempted",
    "attempt_count",
    "retry_count",
}


def _normalize_response_metadata(metadata: Any) -> Any:
    if not isinstance(metadata, dict):
        return metadata

    normalized = {
        key: value
        for key, value in metadata.items()
        if key not in _PROVENANCE_METADATA_KEYS
    }
    failure = normalized.get("failure")
    if isinstance(failure, dict):
        normalized["failure"] = {
            key: value
            for key, value in failure.items()
            if key not in _PROVENANCE_METADATA_KEYS
        }
    return normalized


def normalize_for_hash(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy without execution-provenance fields.

    Serialization keeps these fields; this only narrows equality/hash semantics to
    substantive result content.
    """
    normalized = deepcopy(data)
    normalized.pop("total_results", None)

    rows = normalized.get("data")
    if not isinstance(rows, list):
        rows = [normalized]

    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_model_response = row.get("raw_model_response")
        if not isinstance(raw_model_response, dict):
            continue
        for key, value in list(raw_model_response.items()):
            if key.endswith("_response_metadata"):
                raw_model_response[key] = _normalize_response_metadata(value)

    return normalized
