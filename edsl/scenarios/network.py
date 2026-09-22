"""Shared safeguards for scenario-related network requests."""

from numbers import Real
from math import isfinite


DEFAULT_REQUEST_TIMEOUT = 30.0


def validate_request_timeout(timeout: Real) -> float:
    """Return a positive finite request timeout as a float."""
    value = float(timeout)
    if isinstance(timeout, bool) or value <= 0 or not isfinite(value):
        raise ValueError("timeout must be a positive finite number")
    return value
