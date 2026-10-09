"""Version-1 exact arithmetic and stateless SHA-256 random primitives.

The byte protocol and rounding rules are specified in the canonical Machine manual.
These do not replace the separately versioned legacy market algorithms.
"""

import hashlib
import re

from .resources import BoundedCollection, _active_budget


ARITIES = {"seeded_integer": 3, "seeded_order": 1, "decimal_units": 1, "round_ratio": 2}
ROUNDING = {"half_even", "half_up", "toward_zero", "floor", "ceiling"}


def validate_options(op, options):
    required = {
        "seeded_integer": {"scope", "key"},
        "seeded_order": {"seed", "scope", "key"},
        "decimal_units": {"places", "rounding"},
        "round_ratio": {"rounding"},
    }[op]
    if set(options) != required:
        raise ValueError(f"{op} requires exactly options {sorted(required)}")
    if "rounding" in required and (
        not isinstance(options["rounding"], str) or options["rounding"] not in ROUNDING
    ):
        raise ValueError(f"{op} requires a literal rounding mode in {sorted(ROUNDING)}")
    if op == "decimal_units" and (
        type(options["places"]) is not int or not 0 <= options["places"] <= 18
    ):
        raise ValueError("decimal_units places must be a literal integer from 0 to 18")


def _text(value):
    if not isinstance(value, str) or not value:
        raise ValueError("random seed, scope, key and item IDs must be nonempty text")
    # Strict UTF-8 rejects unpaired surrogates. Do not normalize Unicode IDs.
    encoded = value.encode("utf-8")
    if len(encoded) >= 2**32:
        raise ValueError("random text component exceeds the 32-bit length protocol")
    return len(encoded).to_bytes(4, "big") + encoded


def _prefix(op, seed, scope, key):
    return f"edsl.machine.{op}@1\0".encode("ascii") + b"".join(
        _text(part) for part in (seed, scope, key)
    )


def _digest(prefix, suffix):
    # Charge every attempt, including rejected samples, to the shared budget.
    _active_budget.get().charge(1 + (len(prefix) + len(suffix) + 63) // 64)
    return hashlib.sha256(prefix + suffix).digest()


def _round(numerator, denominator, mode):
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise ValueError(
            "round_ratio requires an integer numerator and positive integer denominator"
        )
    quotient, remainder = divmod(abs(numerator), denominator)
    increment = (
        mode == "floor"
        and numerator < 0
        and remainder != 0
        or mode == "ceiling"
        and numerator > 0
        and remainder != 0
        or mode in {"half_up", "half_even"}
        and (
            remainder > denominator - remainder
            or remainder == denominator - remainder
            and (mode == "half_up" or quotient % 2 == 1)
        )
    )
    rounded = quotient + int(increment)
    return -rounded if numerator < 0 else rounded


def evaluate(op, args, options):
    validate_options(op, options)
    if len(args) != ARITIES[op]:
        raise ValueError(f"{op} requires {ARITIES[op]} operands")
    budget = _active_budget.get()
    if op == "seeded_integer":
        seed, low, high = args
        if type(low) is not int or type(high) is not int or high <= low:
            raise ValueError("seeded_integer requires integer low < high (exclusive)")
        width = high - low
        if width > 2**256:
            raise ValueError("seeded_integer range cannot exceed 2**256")
        prefix = _prefix(op, seed, options["scope"], options["key"])
        cutoff = 2**256 - (2**256 % width)
        counter = 0
        while counter < 2**64:
            candidate = int.from_bytes(
                _digest(prefix, counter.to_bytes(8, "big")), "big"
            )
            if candidate < cutoff:
                return low + candidate % width
            counter += 1
        raise ValueError("seeded_integer exhausted its 64-bit attempt counter")
    if op == "seeded_order":
        items = args[0]
        if not isinstance(items, (list, tuple)):
            raise ValueError("seeded_order requires a sequence of unique text IDs")
        prefix = _prefix(op, options["seed"], options["scope"], options["key"])
        ranked, seen = BoundedCollection(), set()
        for item in items:
            encoded = _text(item)
            if item in seen:
                raise ValueError("seeded_order requires unique IDs")
            seen.add(item)
            # Hex preserves digest byte ordering and lets the shared JSON-tree
            # accounting bound temporary priorities before retaining them.
            ranked.append((_digest(prefix, encoded).hex(), item))
        budget.charge(len(items) * max(1, len(items).bit_length()))
        return [
            item
            for _, item in sorted(
                ranked.value, key=lambda pair: (pair[0], pair[1].encode("utf-8"))
            )
        ]
    if op == "round_ratio":
        return _round(*args, options["rounding"])
    value = args[0]
    if not isinstance(value, str):
        raise ValueError("decimal_units requires exact decimal text, not a float")
    budget.charge(len(value))
    if not re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError(
            "decimal_units requires signed decimal digits without exponent or whitespace"
        )
    negative = value.startswith("-")
    whole, _, fraction = value.lstrip("+-").partition(".")
    digits = (whole + fraction).lstrip("0") or "0"
    shift = options["places"] - len(fraction)
    # Conservative preallocation guards for decimal parsing and powers of ten.
    # 3322/1000 is an upper bound on log2(10).
    for count in (len(digits) + max(shift, 0), max(-shift, 0)):
        budget.check("max_integer_bits", (count * 3322 + 999) // 1000)
    # Parse in small chunks, independent of Python's global int-string limit.
    numerator = 0
    for start in range(0, len(digits), 9):
        chunk = digits[start : start + 9]
        numerator = numerator * 10 ** len(chunk) + int(chunk)
    if negative:
        numerator = -numerator
    if shift >= 0:
        return numerator * 10**shift
    return _round(numerator, 10**-shift, options["rounding"])
