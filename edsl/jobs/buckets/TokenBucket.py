from typing import Union, List, Any, Optional
import asyncio
import time


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
        self.added_tokens = 0

        self.target_rate = (
            capacity * 60
        )  # set this here because it can change with turbo mode

        self._old_capacity = capacity
        self.tokens = capacity  # Current number of available tokens
        self.refill_rate = refill_rate  # Rate at which tokens are refilled
        self._old_refill_rate = refill_rate
        self.last_refill = time.monotonic()  # Last refill time
        self.log: List[Any] = []
        self.turbo_mode = False

        self.creation_time = time.monotonic()

        self.num_requests = 0
        self.num_released = 0
        self.tokens_returned = 0

    def turbo_mode_on(self):
        """Set the refill rate to infinity."""
        if self.turbo_mode:
            pass
        else:
            # pass
            self.turbo_mode = True
            self.capacity = float("inf")
            self.refill_rate = float("inf")

    def turbo_mode_off(self):
        """Restore the refill rate to its original value."""
        self.turbo_mode = False
        self.capacity = self._old_capacity
        self.refill_rate = self._old_refill_rate

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
        """Add tokens to the bucket, up to the maximum capacity.

        :param tokens: The number of tokens to add to the bucket.

        >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=10, refill_rate=1)
        >>> bucket.tokens
        10
        >>> bucket.add_tokens(5)
        >>> bucket.tokens
        10
        """
        self.tokens_returned += tokens
        self.tokens = min(self.capacity, self.tokens + tokens)
        self.log.append((time.monotonic(), self.tokens))

    def refill(self) -> None:
        """Refill the bucket with new tokens based on elapsed time.



        >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=10, refill_rate=1)
        >>> bucket.tokens = 0
        >>> bucket.refill()
        >>> bucket.tokens > 0
        True
        """
        """Refill the bucket with new tokens based on elapsed time."""
        now = time.monotonic()
        # print(f"Time is now: {now}; Last refill time: {self.last_refill}")
        elapsed = now - self.last_refill
        # print("Elapsed time: ", elapsed)
        refill_amount = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now

        if self.tokens < self.capacity:
            pass
            # print(f"Refilled. Current tokens: {self.tokens:.4f}")
            # print(f"Elapsed time: {elapsed:.4f} seconds")
            # print(f"Refill amount: {refill_amount:.4f}")

        self.log.append((now, self.tokens))

    def wait_time(self, requested_tokens: Union[float, int]) -> float:
        """Calculate the time to wait for the requested number of tokens."""
        # self.refill()  # Update the current token count
        if self.tokens >= requested_tokens:
            return 0
        return (requested_tokens - self.tokens) / self.refill_rate

    async def get_tokens(
        self, amount: Union[int, float] = 1, cheat_bucket_capacity=True
    ) -> None:
        """Wait for the specified number of tokens to become available.


        :param amount: The number of tokens
        :param warn: If True, warn if the requested amount exceeds the bucket capacity.

        >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=10, refill_rate=1)
        >>> asyncio.run(bucket.get_tokens(5))
        >>> bucket.tokens
        5
        >>> asyncio.run(bucket.get_tokens(9))
        >>> bucket.tokens < 1
        True

        >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=10, refill_rate=1)
        >>> asyncio.run(bucket.get_tokens(11, cheat_bucket_capacity=False))
        Traceback (most recent call last):
        ...
        ValueError: Requested amount exceeds bucket capacity. Bucket capacity: 10, requested amount: 11. As the bucket never overflows, the requested amount will never be available.
        >>> asyncio.run(bucket.get_tokens(11, cheat_bucket_capacity=True))
        >>> bucket.capacity
        12.100000000000001
        """
        self.num_requests += amount
        if amount >= self.capacity:
            if not cheat_bucket_capacity:
                msg = f"Requested amount exceeds bucket capacity. Bucket capacity: {self.capacity}, requested amount: {amount}. As the bucket never overflows, the requested amount will never be available."
                raise ValueError(msg)
            else:
                self.capacity = amount * 1.10
                self._old_capacity = self.capacity

        start_time = time.monotonic()
        while True:
            self.refill()  # Refill based on elapsed time
            if self.tokens >= amount:
                self.tokens -= amount
                break

            wait_time = self.wait_time(amount)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.num_released += amount
        now = time.monotonic()
        self.log.append((now, self.tokens))
        return None

    def get_log(self) -> list[tuple]:
        return self.log

    def visualize(self):
        """Visualize the token bucket over time."""
        times, tokens = zip(*self.get_log())
        start_time = times[0]
        times = [t - start_time for t in times]  # Normalize time to start from 0
        from matplotlib import pyplot as plt

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

    def get_throughput(self, time_window: Optional[float] = None) -> float:
        """
        Calculate the empirical bucket throughput in tokens per minute for the specified time window.

        :param time_window: The time window in seconds to calculate the throughput for.
        :return: The throughput in tokens per minute.

        >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=100, refill_rate=10)
        >>> asyncio.run(bucket.get_tokens(50))
        >>> time.sleep(1)  # Wait for 1 second
        >>> asyncio.run(bucket.get_tokens(30))
        >>> throughput = bucket.get_throughput(1)
        >>> 4750 < throughput < 4850
        True
        """
        now = time.monotonic()

        if time_window is None:
            start_time = self.creation_time
        else:
            start_time = now - time_window

        if start_time < self.creation_time:
            start_time = self.creation_time

        elapsed_time = now - start_time

        if elapsed_time == 0:
            return self.num_released / 0.001

        return (self.num_released / elapsed_time) * 60

        # # Filter log entries within the time window
        # relevant_log = [(t, tokens) for t, tokens in self.log if t >= start_time]

        # if len(relevant_log) < 2:
        #     return 0  # Not enough data points to calculate throughput

        # # Calculate total tokens used
        # initial_tokens = relevant_log[0][1]
        # final_tokens = relevant_log[-1][1]
        # tokens_used = self.num_released - (final_tokens - initial_tokens)

        # # Calculate actual time elapsed
        # actual_time_elapsed = relevant_log[-1][0] - relevant_log[0][0]

        # # Calculate throughput in tokens per minute
        # throughput = (tokens_used / actual_time_elapsed) * 60

        # return throughput


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
