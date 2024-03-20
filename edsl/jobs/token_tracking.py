"""This module holds the classes for tracking token usage and pricing."""

class TokenPricing:
    """Hold the pricing for a model."""

    def __init__(
        self,
        *,
        model_name,
        prompt_token_price_per_k: float,
        completion_token_price_per_k: float,
    ):
        """Initialize the token pricing."""
        self.model_name = model_name
        self.prompt_token_price = prompt_token_price_per_k / 1_000.0
        self.completion_token_price = completion_token_price_per_k / 1_000.0

    def __eq__(self, other):
        """Check if two TokenPricings are equal."""
        if not isinstance(other, TokenPricing):
            return False
        return (
            self.model_name == other.model_name
            and self.prompt_token_price == other.prompt_token_price
            and self.completion_token_price == other.completion_token_price
        )


class TokenUsage:
    """Hold the usage of tokens."""

    def __init__(
        self, from_cache: bool, prompt_tokens: int = 0, completion_tokens: int = 0
    ):
        """Initialize the token usage."""
        self.from_cache = from_cache
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

    def add_tokens(self, prompt_tokens, completion_tokens):
        """Add tokens to the token usage."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens

    def __add__(self, other):
        """Add two TokenUsages together."""
        if not isinstance(other, TokenUsage):
            raise ValueError(f"Can't add {type(other)} to InterviewTokenUsage")
        if self.from_cache != other.from_cache:
            raise ValueError(f"Can't add token usages from different sources")
        return TokenUsage(
            from_cache=self.from_cache,
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
        )

    def __repr__(self):
        """Return the string representation of the token usage."""
        return f"TokenUsage(from_cache={self.from_cache}, prompt_tokens={self.prompt_tokens}, completion_tokens={self.completion_tokens})"

    def cost(self, prices: TokenPricing):
        """Return the cost of the tokens."""
        return (
            self.prompt_tokens * prices.prompt_token_price
            + self.completion_tokens * prices.completion_token_price
        )


class InterviewTokenUsage:
    """Hold the usage of tokens in an interview."""

    def __init__(
        self, new_token_usage: TokenUsage = None, cached_token_usage: TokenUsage = None
    ):
        """Initialize the interview token usage."""
        self.new_token_usage = new_token_usage or TokenUsage(from_cache=False)
        self.cached_token_usage = cached_token_usage or TokenUsage(from_cache=True)

    def __add__(self, other):
        """Add two InterviewTokenUsages together."""
        if not isinstance(other, InterviewTokenUsage):
            raise ValueError(f"Can't add {type(other)} to InterviewTokenSummary")
        return InterviewTokenUsage(
            new_token_usage=self.new_token_usage + other.new_token_usage,
            cached_token_usage=self.cached_token_usage + other.cached_token_usage,
        )

    def __repr__(self):
        """Return the string representation of the interview token usage."""
        return f"InterviewTokenUsage(new_token_usage={self.new_token_usage}, cached_token_usage={self.cached_token_usage})"

    def cost(self, prices: TokenPricing):
        """Return the cost of the tokens."""
        return self.new_token_usage.cost(prices)

    def saved(self, prices: TokenPricing):
        """Return the cost of the tokens saved."""
        return self.cached_token_usage.cost(prices)
