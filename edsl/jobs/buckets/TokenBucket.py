from typing import Union, List, Any
import asyncio
import time
from collections import UserDict
from matplotlib import pyplot as plt


class TokenBucket:
    """This is a token bucket used to respect rate limits to services."""

    def __init__(
        self,
        *,
        bucket_name: str,
        bucket_type: str,
        capacity: Union[int, float],
        refill_rate: Union[int, float],
    ):
        self.bucket_name = bucket_name
        self.bucket_type = bucket_type
        self.capacity = capacity  # Maximum number of tokens
        self.tokens = capacity  # Current number of available tokens
        self.refill_rate = refill_rate  # Rate at which tokens are refilled
        self.last_refill = time.monotonic()  # Last refill time

        self.log: List[Any] = []

    def __add__(self, other) -> "TokenBucket":
        """Combine two token buckets.

        The resulting bucket has the minimum capacity and refill rate of the two buckets.
        This is useful, for example, if we have two calls to the same model on the same service but have different temperatures.
        """
        return TokenBucket(
            bucket_name=self.bucket_name,
            bucket_type=self.bucket_type,
            capacity=min(self.capacity, other.capacity),
            refill_rate=min(self.refill_rate, other.refill_rate),
        )

    def __repr__(self):
        return f"TokenBucket(bucket_name={self.bucket_name}, bucket_type='{self.bucket_type}', capacity={self.capacity}, refill_rate={self.refill_rate})"

    def add_tokens(self, tokens: Union[int, float]) -> None:
        """Add tokens to the bucket, up to the maximum capacity."""
        self.tokens = min(self.capacity, self.tokens + tokens)
        self.log.append((time.monotonic(), self.tokens))

    def refill(self) -> None:
        """Refill the bucket with new tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now

        self.log.append((now, self.tokens))

    def wait_time(self, requested_tokens: Union[float, int]) -> float:
        """Calculate the time to wait for the requested number of tokens."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        available_tokens = min(self.capacity, self.tokens + refill_amount)
        return max(0, requested_tokens - available_tokens) / self.refill_rate

    async def get_tokens(self, amount: Union[int, float] = 1, warn=True) -> None:
        """Wait for the specified number of tokens to become available.
        Note that this method is a coroutine.
        """
        if amount > self.capacity:
            msg = f"Requested amount exceeds bucket capacity. Bucket capacity: {self.capacity}, requested amount: {amount}. As the bucket never overflows, the requested amount will never be available."
            raise ValueError(msg)
        while self.tokens < amount:
            self.refill()
            await asyncio.sleep(0.1)  # Sleep briefly to prevent busy waiting
        self.tokens -= amount

        now = time.monotonic()
        self.log.append((now, self.tokens))

    def get_log(self) -> list[tuple]:
        return self.log

    def visualize(self):
        """Visualize the token bucket over time."""
        times, tokens = zip(*self.get_log())
        start_time = times[0]
        times = [t - start_time for t in times]  # Normalize time to start from 0

        plt.figure(figsize=(10, 6))
        plt.plot(times, tokens, label="Tokens Available")
        plt.xlabel("Time (seconds)", fontsize=12)
        plt.ylabel("Number of Tokens", fontsize=12)
        details = f"{self.bucket_name} ({self.bucket_type}) Bucket Usage Over Time\nCapacity: {self.capacity:.1f}, Refill Rate: {self.refill_rate:.1f}/second"
        plt.title(details, fontsize=14)

        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()
