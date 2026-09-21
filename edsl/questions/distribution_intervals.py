"""Exact interval construction for QuestionDistribution (no model calls)."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext, ROUND_CEILING
import math
import re

from .exceptions import QuestionCreationValidationError as CreationError

MAX_BINS = 1000
_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_ENDPOINT = rf"(?:{_NUMBER}|[+-]?[Ii][Nn][Ff](?:[Ii][Nn][Ii][Tt][Yy])?)"
_INTERVAL = re.compile(
    rf"^\s*([\[(])\s*({_ENDPOINT})\s*,\s*({_ENDPOINT})\s*([\])])\s*$"
)


def number(value, name, allow_infinity=False):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise CreationError(f"{name} must be numeric.")
    if isinstance(value, str) and not (
        allow_infinity and re.fullmatch(r"[+-]?inf(?:inity)?", value, re.I)
    ):
        raise CreationError(f"{name} must be numeric (only infinity may be a string).")
    result = Decimal(str(value))
    if result.is_nan() or (not allow_infinity and not result.is_finite()):
        raise CreationError(f"{name} must be finite.")
    return result


def label(value):
    if value.is_infinite():
        return "-Inf" if value < 0 else "Inf"
    if value == 0:
        return "0"
    if not -324 <= value.adjusted() <= 308:
        # Avoid expanding a compact, extreme exponent into millions of zeros.
        coefficient, exponent = format(value, "E").split("E")
        if "." in coefficient:
            coefficient = coefficient.rstrip("0").rstrip(".")
        return f"{coefficient}e{int(exponent)}"
    # Decimal.normalize() depends on the active precision; formatting does not.
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def portable(value):
    if isinstance(value, float) and math.isinf(value):
        return "-Inf" if value < 0 else "Inf"
    if isinstance(value, str):
        return label(Decimal(value))
    return value


@dataclass(frozen=True)
class Interval:
    lower: Decimal
    upper: Decimal
    left_closed: bool
    right_closed: bool

    @property
    def label(self):
        return (
            ("[" if self.left_closed else "(")
            + label(self.lower)
            + ","
            + label(self.upper)
            + ("]" if self.right_closed else ")")
        )


def parse_bins(bins, min_value=None, max_value=None):
    if not isinstance(bins, list) or not 1 <= len(bins) <= MAX_BINS:
        raise CreationError(
            f"bins must be a list containing 1 to {MAX_BINS} intervals."
        )
    intervals = []
    for index, text in enumerate(bins):
        match = _INTERVAL.fullmatch(text) if isinstance(text, str) else None
        if not match:
            raise CreationError(f"Invalid interval at bin {index}: {text!r}.")
        left, low, high, right = match.groups()
        try:
            lower, upper = Decimal(low), Decimal(high)
        except InvalidOperation as exc:
            raise CreationError(
                f"Unsupported numerical endpoint in bin {index}."
            ) from exc
        if lower >= upper:
            raise CreationError(f"Bin {index} must have lower < upper.")
        current = Interval(
            lower,
            upper,
            left == "[" and lower.is_finite(),
            right == "]" and upper.is_finite(),
        )
        if intervals:
            previous = intervals[-1]
            if previous.upper != current.lower:
                raise CreationError(
                    f"Bins {index - 1} and {index} have a gap, overlap, or are out of order."
                )
            if previous.right_closed == current.left_closed:
                raise CreationError(
                    f"Bins {index - 1} and {index}: exactly one interval must include boundary {label(lower)}."
                )
        intervals.append(current)
    first, last = intervals[0], intervals[-1]
    if (first.lower.is_finite() and not first.left_closed) or (
        last.upper.is_finite() and not last.right_closed
    ):
        raise CreationError("Finite outside boundaries must be included.")
    for name, supplied, actual in (
        ("min_value", min_value, first.lower),
        ("max_value", max_value, last.upper),
    ):
        if supplied is not None and number(supplied, name, True) != actual:
            raise CreationError(
                f"{name} must equal outer bin boundary {label(actual)}."
            )
    return tuple(intervals)


def generate_bins(min_value, max_value, bucket_size):
    lower = number(min_value, "min_value")
    upper = number(max_value, "max_value")
    size = number(bucket_size, "bucket_size")
    if lower >= upper or size <= 0:
        raise CreationError("Require min_value < max_value and bucket_size > 0.")
    values = (lower, upper, size)
    # Sufficient precision for exact subtraction and integer-multiple edges,
    # including very small bucket sizes and large integer bounds.
    with localcontext() as ctx:
        ctx.prec = max(
            28,
            max(v.adjusted() for v in values)
            - min(v.as_tuple().exponent for v in values)
            + 20,
        )
        count = int(((upper - lower) / size).to_integral_value(rounding=ROUND_CEILING))
        if count > MAX_BINS:
            raise CreationError(f"Generated {count} bins; limit is {MAX_BINS}.")
        return tuple(
            Interval(
                lower + i * size,
                min(lower + (i + 1) * size, upper),
                True,
                i == count - 1,
            )
            for i in range(count)
        )
