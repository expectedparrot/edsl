from ..enums import TokenPricing
from .exceptions import TokenUsageError, TokenCostError


class TokenUsage:
    def __init__(
        self, from_cache: bool, prompt_tokens: int = 0, completion_tokens: int = 0
    ):
        self.from_cache = from_cache
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def add_tokens(self, prompt_tokens, completion_tokens):
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    def __add__(self, other):
        if not isinstance(other, TokenUsage):
            raise TokenUsageError(f"Can't add {type(other)} to InterviewTokenUsage")
        if self.from_cache != other.from_cache:
            raise TokenUsageError("Can't add token usages from different sources")
        return TokenUsage(
            from_cache=self.from_cache,
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )

    def __repr__(self):
        return f"TokenUsage(from_cache={self.from_cache}, prompt_tokens={self.prompt_tokens}, completion_tokens={self.completion_tokens})"

    def cost(self, prices: TokenPricing):
        return (
            self.prompt_tokens * prices.prompt_token_price
            + self.completion_tokens * prices.completion_token_price
        )
