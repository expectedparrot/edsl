from typing import Union, List, Any, Optional
import asyncio
import time
from threading import RLock

from ..jobs.decorators import synchronized_class
from .exceptions import TokenLimitError


@synchronized_class
class TokenBucket:
    """Token bucket algorithm implementation for rate limiting.
    
    The token bucket is a rate limiting algorithm that allows for controlled access to 
    resources by maintaining a bucket of tokens that are consumed when requests are made
    and replenished at a constant rate over time.
    
    Features:
    - Supports both local and remote operation via factory method
    - Thread-safe implementation
    - Configurable capacity and refill rates
    - Ability to track usage patterns
    - Visualization of token usage over time
    - Turbo mode for temporarily bypassing rate limits
    
    Typical use cases:
    - Respecting API rate limits (e.g., OpenAI, AWS, etc.)
    - Controlling resource utilization
    - Managing concurrent access to limited resources
    - Testing systems under various rate limiting conditions
    
    Example:
        >>> bucket = TokenBucket(
        ...     bucket_name="openai-gpt4",
        ...     bucket_type="api", 
        ...     capacity=3500,  # 3500 tokens per minute capacity
        ...     refill_rate=58.33  # 3500/60 tokens per second
        ... )
        >>> bucket.capacity
        3500
        >>> bucket.refill_rate
        58.33
    """

    def __new__(
        cls,
        *,
        bucket_name: str,
        bucket_type: str,
        capacity: Union[int, float],
        refill_rate: Union[int, float],
        remote_url: Optional[str] = None,
    ):
        """Factory method to create either a local or remote token bucket.

        This method determines whether to create a local TokenBucket instance or
        a remote TokenBucketClient instance based on the provided parameters.

        Args:
            bucket_name: Name of the bucket for identification
            bucket_type: Type of the bucket (e.g., 'api', 'database', etc.)
            capacity: Maximum number of tokens the bucket can hold
            refill_rate: Rate at which tokens are refilled (tokens per second)
            remote_url: If provided, creates a remote token bucket client

        Returns:
            Either a TokenBucket instance (local) or a TokenBucketClient instance (remote)
        
        Example:
            >>> # Local bucket
            >>> local_bucket = TokenBucket(
            ...     bucket_name="local-rate-limit",
            ...     bucket_type="api",
            ...     capacity=100,
            ...     refill_rate=10
            ... )
            >>> isinstance(local_bucket, TokenBucket)
            True
            >>> local_bucket.bucket_name
            'local-rate-limit'
        """
        if remote_url is not None:
            # Import here to avoid circular imports
            from ..buckets import TokenBucketClient

            return TokenBucketClient(
                bucket_name=bucket_name,
                bucket_type=bucket_type,
                capacity=capacity,
                refill_rate=refill_rate,
                api_base_url=remote_url,
            )

        # Create a local token bucket
        instance = super(TokenBucket, cls).__new__(cls)
        return instance

    def __init__(
        self,
        *,
        bucket_name: str,
        bucket_type: str,
        capacity: Union[int, float],
        refill_rate: Union[int, float],
        remote_url: Optional[str] = None,
    ):
        """Initialize a new token bucket instance.
        
        Sets up the initial state of the token bucket with the specified parameters.
        
        Args:
            bucket_name: Name of the bucket for identification
            bucket_type: Type of the bucket (e.g., 'api', 'database', etc.)
            capacity: Maximum number of tokens the bucket can hold
            refill_rate: Rate at which tokens are refilled (tokens per second)
            remote_url: If provided, initialization is skipped (handled by __new__)
            
        Note:
            - The bucket starts full (tokens = capacity)
            - The target_rate is calculated in tokens per minute
            - A log of token levels over time is maintained for visualization
            
        Example:
            >>> bucket = TokenBucket(bucket_name="test-init", bucket_type="api", capacity=50, refill_rate=5)
            >>> bucket.tokens == bucket.capacity
            True
            >>> bucket.target_rate == bucket.capacity * 60  # Target rate in tokens per minute
            True
        """
        # Skip initialization if this is a remote bucket
        if remote_url is not None:
            return

        self.bucket_name = bucket_name
        self.bucket_type = bucket_type
        self.capacity = capacity
        self.added_tokens = 0
        self._lock = RLock()

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

    def turbo_mode_on(self) -> None:
        """Enable turbo mode to bypass rate limiting.
        
        Sets the capacity and refill rate to infinity, effectively disabling rate 
        limiting. This can be useful for testing or emergency situations where 
        rate limits need to be temporarily ignored.
        
        Note:
            The original capacity and refill rate values are preserved and can be
            restored by calling turbo_mode_off()
        
        Example:
            >>> bucket = TokenBucket(bucket_name="api", bucket_type="test", capacity=10, refill_rate=1)
            >>> bucket.turbo_mode_on()
            >>> bucket.capacity
            inf
            >>> bucket.refill_rate
            inf
        """
        if self.turbo_mode:
            pass
        else:
            self.turbo_mode = True
            self.capacity = float("inf")
            self.refill_rate = float("inf")

    def turbo_mode_off(self) -> None:
        """Disable turbo mode and restore normal rate limiting.
        
        Restores the original capacity and refill rate values that were in effect
        before turbo_mode_on() was called.
        
        Example:
            >>> bucket = TokenBucket(bucket_name="api", bucket_type="test", capacity=10, refill_rate=1)
            >>> original_capacity = bucket.capacity
            >>> bucket.turbo_mode_on()
            >>> bucket.capacity
            inf
            >>> bucket.turbo_mode_off()
            >>> bucket.capacity == original_capacity
            True
        """
        self.turbo_mode = False
        self.capacity = self._old_capacity
        self.refill_rate = self._old_refill_rate

    def __add__(self, other) -> "TokenBucket":
        """Combine two token buckets to create a more restrictive bucket.

        The resulting bucket has the minimum capacity and refill rate of the two input buckets.
        This operation is useful when multiple rate limits need to be respected simultaneously.
        
        Args:
            other: Another TokenBucket instance to combine with this one
            
        Returns:
            A new TokenBucket instance with the more restrictive parameters
            
        Example:
            >>> model_bucket = TokenBucket(bucket_name="gpt4", bucket_type="model", capacity=10000, refill_rate=100)
            >>> global_bucket = TokenBucket(bucket_name="openai", bucket_type="global", capacity=5000, refill_rate=50)
            >>> combined_bucket = model_bucket + global_bucket
            >>> combined_bucket.capacity
            5000
            >>> combined_bucket.refill_rate
            50
        """
        return TokenBucket(
            bucket_name=self.bucket_name,
            bucket_type=self.bucket_type,
            capacity=min(self.capacity, other.capacity),
            refill_rate=min(self.refill_rate, other.refill_rate),
        )

    def __repr__(self):
        """Return a string representation of the TokenBucket instance.
        
        Returns:
            A string containing the essential parameters of the bucket
            
        Example:
            >>> bucket = TokenBucket(bucket_name="repr-test", bucket_type="api", capacity=100, refill_rate=10)
            >>> repr(bucket)
            "TokenBucket(bucket_name=repr-test, bucket_type='api', capacity=100, refill_rate=10)"
        """
        return f"TokenBucket(bucket_name={self.bucket_name}, bucket_type='{self.bucket_type}', capacity={self.capacity}, refill_rate={self.refill_rate})"

    def add_tokens(self, tokens: Union[int, float]) -> None:
        """Add tokens to the bucket, up to the maximum capacity.
        
        This method is typically used when tokens are returned after a request
        used fewer tokens than initially requested.
        
        Args:
            tokens: The number of tokens to add to the bucket
            
        Note:
            - The tokens will be capped at the bucket's capacity
            - This operation is logged for visualization purposes
            - The tokens_returned counter is incremented
            
        Example:
            >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=10, refill_rate=1)
            >>> bucket.tokens = 5  # Set current tokens to 5
            >>> bucket.add_tokens(3)
            >>> bucket.tokens
            8
            >>> bucket.add_tokens(10)  # Should be capped at capacity
            >>> bucket.tokens
            10
        """
        self.tokens_returned += tokens
        self.tokens = min(self.capacity, self.tokens + tokens)
        self.log.append((time.monotonic(), self.tokens))

    def refill(self) -> None:
        """Refill the bucket with new tokens based on elapsed time.
        
        Calculates the number of tokens to add based on the time elapsed since the
        last refill and the current refill rate. Updates the token count and records
        the new level for logging purposes.
        
        Note:
            - This method is called internally by get_tokens() before checking token availability
            - The refill amount is proportional to the time elapsed: amount = elapsed_time * refill_rate
            - Tokens are capped at the bucket's capacity
            
        Example:
            >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=10, refill_rate=2)
            >>> bucket.tokens = 5
            >>> bucket.last_refill = time.monotonic() - 1  # Simulate 1 second passing
            >>> bucket.refill()
            >>> 6.9 < bucket.tokens < 7.1  # Should be around 7 (5 + 2*1)
            True
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now

        if self.tokens < self.capacity:
            pass

        self.log.append((now, self.tokens))

    def wait_time(self, requested_tokens: Union[float, int]) -> float:
        """Calculate the time to wait for the requested number of tokens to become available.
        
        Args:
            requested_tokens: The number of tokens needed
            
        Returns:
            The time in seconds to wait before the requested tokens will be available
            
        Note:
            Returns 0 if the requested tokens are already available
            
        Example:
            >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=10, refill_rate=2)
            >>> bucket.tokens = 3
            >>> wait_time = bucket.wait_time(5)
            >>> 0.9 < wait_time < 1.1  # Should be around 1.0 (need 2 more tokens at 2 tokens/sec)
            True
            >>> bucket.tokens = 10
            >>> bucket.wait_time(5)  # No wait needed when we have enough tokens
            0
        """
        if self.tokens >= requested_tokens:
            return 0
        return (requested_tokens - self.tokens) / self.refill_rate

    async def get_tokens(
        self, amount: Union[int, float] = 1, cheat_bucket_capacity=True
    ) -> None:
        """Wait for the specified number of tokens to become available.
        
        This is the primary method for consuming tokens from the bucket. It will block
        asynchronously until the requested tokens are available, then deduct them
        from the bucket.
        
        Args:
            amount: The number of tokens to consume
            cheat_bucket_capacity: If True and the requested amount exceeds capacity,
                                  automatically increase the bucket capacity to accommodate
                                  the request. If False, raise a ValueError.
                                  
        Raises:
            ValueError: If amount exceeds capacity and cheat_bucket_capacity is False
            
        Note:
            - This method blocks asynchronously using asyncio.sleep() if tokens are not available
            - The bucket is refilled based on elapsed time before checking token availability
            - Usage statistics and token levels are logged for tracking purposes
            
        Example:
            >>> from edsl.buckets.token_bucket import TokenBucket
            >>> bucket = TokenBucket(bucket_name="api", bucket_type="test", capacity=100, refill_rate=10)
            >>> bucket.tokens = 100
            >>> import asyncio
            >>> asyncio.run(bucket.get_tokens(30))
            >>> bucket.tokens
            70
            
            >>> # Example with capacity cheating
            >>> from edsl.buckets.token_bucket import TokenBucket
            >>> bucket = TokenBucket(bucket_name="api", bucket_type="test", capacity=10, refill_rate=1)
            >>> asyncio.run(bucket.get_tokens(15, cheat_bucket_capacity=True))
            >>> bucket.capacity > 15  # Capacity should have been increased
            True
            
            >>> # Example raising TokenLimitError
            >>> from edsl.buckets.token_bucket import TokenBucket
            >>> from edsl.buckets.exceptions import TokenLimitError
            >>> bucket = TokenBucket(bucket_name="api", bucket_type="test", capacity=10, refill_rate=1)
            >>> try:
            ...     asyncio.run(bucket.get_tokens(15, cheat_bucket_capacity=False))
            ... except TokenLimitError as e:
            ...     print("TokenLimitError raised")
            TokenLimitError raised
        """
        self.num_requests += amount
        if amount >= self.capacity:
            if not cheat_bucket_capacity:
                msg = f"Requested amount exceeds bucket capacity. Bucket capacity: {self.capacity}, requested amount: {amount}. As the bucket never overflows, the requested amount will never be available."
                raise TokenLimitError(msg)
            else:
                self.capacity = amount * 1.10
                self._old_capacity = self.capacity

        # Loop until we have enough tokens
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
        """Return the token level log for analysis or visualization.
        
        Returns:
            A list of (timestamp, token_level) tuples representing the token history
            
        Example:
            >>> bucket = TokenBucket(bucket_name="test", bucket_type="test", capacity=10, refill_rate=1)
            >>> import asyncio
            >>> asyncio.run(bucket.get_tokens(5))
            >>> log = bucket.get_log()
            >>> len(log) > 0  # Should have at least one log entry
            True
            >>> isinstance(log[0], tuple) and len(log[0]) == 2  # Each entry should be a (timestamp, tokens) tuple
            True
        """
        return self.log

    def visualize(self):
        """Visualize the token bucket usage over time as a line chart.
        
        Creates and displays a matplotlib plot showing token levels over time.
        This can be useful for analyzing rate limit behavior and usage patterns.
        
        Note:
            Requires matplotlib to be installed
            
        Example:
            >>> bucket = TokenBucket(bucket_name="api", bucket_type="test", capacity=100, refill_rate=10)
            >>> # In practice, you would use the bucket and then visualize:
            >>> # import asyncio
            >>> # for i in range(5):
            >>> #     asyncio.run(bucket.get_tokens(10))
            >>> #     asyncio.sleep(0.2)
            >>> # bucket.visualize()  # This would display a matplotlib chart
        """
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
        """Calculate the empirical bucket throughput in tokens per minute.
        
        Determines the actual usage rate of the bucket over the specified time window,
        which can be useful for monitoring and adjusting rate limits.
        
        Args:
            time_window: The time window in seconds to calculate the throughput for.
                        If None, uses the entire bucket lifetime.
                        
        Returns:
            The throughput in tokens per minute
            
        Note:
            The throughput is based on tokens that were successfully released from
            the bucket, not on tokens that were requested.
            
        Example:
            >>> bucket = TokenBucket(bucket_name="api", bucket_type="test", capacity=100, refill_rate=30)
            >>> import asyncio
            >>> # Consume some tokens
            >>> bucket.num_released = 0  # Reset for testing
            >>> asyncio.run(bucket.get_tokens(50))
            >>> # Fast-forward the creation time to simulate passage of time
            >>> bucket.creation_time = time.monotonic() - 60  # Simulate 1 minute passing
            >>> throughput = bucket.get_throughput()
            >>> throughput > 49  # Should a little less than 50 tokens per minute
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


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
