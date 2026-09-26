from __future__ import annotations
from dataclasses import dataclass

EDSL_DEFAULT_CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class TokenAmount:
    """Fixed token count, independent of input length."""
    value: int


@dataclass(frozen=True)
class TokenRatio:
    """Token count as a fraction of input tokens."""
    value: float


def _resolve_token_spec(spec: TokenAmount | TokenRatio, input_tokens: int) -> int:
    if isinstance(spec, TokenRatio):
        return int(input_tokens * spec.value)
    return spec.value
