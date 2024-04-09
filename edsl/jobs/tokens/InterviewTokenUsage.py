from edsl.jobs.tokens.TokenUsage import TokenUsage
from edsl.enums import TokenPricing


class InterviewTokenUsage:
    def __init__(
        self, new_token_usage: TokenUsage = None, cached_token_usage: TokenUsage = None
    ):
        self.new_token_usage = new_token_usage or TokenUsage(from_cache=False)
        self.cached_token_usage = cached_token_usage or TokenUsage(from_cache=True)

    def __add__(self, other):
        if not isinstance(other, InterviewTokenUsage):
            raise ValueError(f"Can't add {type(other)} to InterviewTokenSummary")
        return InterviewTokenUsage(
            new_token_usage=self.new_token_usage + other.new_token_usage,
            cached_token_usage=self.cached_token_usage + other.cached_token_usage,
        )

    def __repr__(self):
        return f"InterviewTokenUsage(new_token_usage={self.new_token_usage}, cached_token_usage={self.cached_token_usage})"

    def cost(self, prices: TokenPricing):
        return self.new_token_usage.cost(prices)

    def saved(self, prices: TokenPricing):
        return self.cached_token_usage.cost(prices)
