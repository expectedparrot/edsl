from typing import Optional

from .token_usage import TokenUsage
from ..enums import TokenPricing
from .exceptions import TokenUsageError

class InterviewTokenUsage:
    """A class to represent the token usage of an interview."""

    def __init__(
        self, new_token_usage: Optional[TokenUsage] = None, cached_token_usage: Optional[TokenUsage] = None
    ):
        """Initialize the InterviewTokenUsage.

        >>> usage = InterviewTokenUsage()
        """
        self.new_token_usage = new_token_usage or TokenUsage(from_cache=False)
        self.cached_token_usage = cached_token_usage or TokenUsage(from_cache=True)

    def __add__(self, other: "InterviewTokenUsage") -> "InterviewTokenUsage":
        """Add two InterviewTokenUsage objects together.

        >>> usage1 = InterviewTokenUsage()
        >>> usage2 = InterviewTokenUsage()
        >>> usage3 = usage1 + usage2
        """
        if not isinstance(other, InterviewTokenUsage):
            raise TokenUsageError(f"Can't add {type(other)} to InterviewTokenSummary")
        return InterviewTokenUsage(
            new_token_usage=self.new_token_usage + other.new_token_usage,
            cached_token_usage=self.cached_token_usage + other.cached_token_usage,
        )

    def __repr__(self):
        return f"InterviewTokenUsage(new_token_usage={self.new_token_usage}, cached_token_usage={self.cached_token_usage})"

    def cost(self, prices: TokenPricing) -> float:
        """Return the cost of the new and cached token usage.

        >>> usage = InterviewTokenUsage()
        >>> usage.cost(TokenPricing.example())
        0.0
        """
        return self.new_token_usage.cost(prices)

    def saved(self, prices: TokenPricing) -> float:
        """Return the saved cost of the cached token usage.
        """
        return self.cached_token_usage.cost(prices)


if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.ELLIPSIS)
