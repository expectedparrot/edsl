"""Small data contracts shared by the state and workflow languages."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any


def validate_data(value: Any, *, path: str = "value") -> None:
    """Require lossless JSON values, including finite numbers and string keys.

    >>> validate_data({"round": 1, "answers": [True, None]})
    >>> validate_data(float("nan"))
    Traceback (most recent call last):
        ...
    ValueError: value must be finite
    """
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be finite")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} requires string map keys for JSON storage")
            validate_data(item, path=f"{path}.{key}")
        return
    if isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            validate_data(item, path=f"{path}[{index}]")
        return
    raise TypeError(f"{path} is not JSON-serializable: {type(value).__name__}")


def canonical_data(value: Any) -> str:
    """Encode valid data deterministically without silently converting map keys.

    >>> canonical_data({"b": [True, None], "a": 1})
    '{"a":1,"b":[true,null]}'
    >>> canonical_data({1: "lossy"})
    Traceback (most recent call last):
        ...
    ValueError: value requires string map keys for JSON storage
    """
    validate_data(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def definition_fingerprint(value: Any) -> str:
    """Pin behavior-bearing data, excluding the EDSL package build label."""

    def normalize(item):
        if isinstance(item, Mapping):
            return {
                key: normalize(val)
                for key, val in item.items()
                if key != "edsl_version" or "edsl_class_name" not in item
            }
        if isinstance(item, (tuple, list)):
            return [normalize(val) for val in item]
        return item

    return hashlib.sha256(canonical_data(normalize(value)).encode("utf-8")).hexdigest()


def symbolic_bool() -> bool:
    """Reject implicit branching on a syntax node.

    >>> symbolic_bool()
    Traceback (most recent call last):
        ...
    TypeError: symbolic expressions have no Python truth value; use DSL conditions instead of if/and/or
    """
    raise TypeError(
        "symbolic expressions have no Python truth value; use DSL conditions instead of if/and/or"
    )


def check_arity(op: str, args, minimum: int, maximum: int | None = None) -> None:
    if len(args) < minimum or (maximum is not None and len(args) > maximum):
        expected = (
            str(minimum) if maximum == minimum else f"{minimum}..{maximum or 'many'}"
        )
        raise ValueError(f"{op!r} expects {expected} arguments, got {len(args)}")
