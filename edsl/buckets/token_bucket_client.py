"""
Token Bucket Client for distributed rate limiting in EDSL.

This module provides a client implementation for interacting with a remote token
bucket server. It implements the same interface as TokenBucket, but delegates
operations to a remote server, enabling distributed rate limiting across
multiple processes or machines.
"""

from typing import Union, Optional, Dict, Any
import asyncio
import time
import aiohttp
from matplotlib import pyplot as plt
from matplotlib.figure import Figure

from .exceptions import BucketError, TokenBucketClientError


class TokenBucketClient:
    """
    Client implementation for interacting with a remote token bucket server.
    
    TokenBucketClient implements the same interface as TokenBucket, but
    delegates operations to a remote server via REST API calls. This enables
    distributed rate limiting across multiple processes or machines, ensuring
    that rate limits are properly enforced in distributed environments.
    
    The client maintains minimal local state and fetches most information from
    the server when needed. It creates the bucket on the server during
    initialization if it doesn't already exist.
    
    Attributes:
        bucket_name (str): Name identifier for the bucket (usually service name)
        bucket_type (str): Type of bucket ("requests" or "tokens")
        capacity (float): Maximum tokens the bucket can hold
        refill_rate (float): Rate at which tokens are refilled (tokens per second)
        api_base_url (str): Base URL for the token bucket server API
        bucket_id (str): Unique identifier for this bucket on the server
        creation_time (float): Local timestamp when this client was created
        turbo_mode (bool): Flag indicating if turbo mode is active
        
    Example:
        >>> # Create a client connected to a running token bucket server
        >>> client = TokenBucketClient(
        ...     bucket_name="openai", 
        ...     bucket_type="requests",
        ...     capacity=100, 
        ...     refill_rate=10,
        ...     api_base_url="http://localhost:8000"
        ... )
        >>> # Now use this client just like a regular TokenBucket
    """

    def __init__(
        self,
        *,
        bucket_name: str,
        bucket_type: str,
        capacity: Union[int, float],
        refill_rate: Union[int, float],
        api_base_url: str = "http://localhost:8000",
    ):
        """
        Initialize a new TokenBucketClient connected to a remote token bucket server.
        
        Creates a new TokenBucketClient instance that connects to a remote token
        bucket server. During initialization, it attempts to create the bucket
        on the server if it doesn't already exist.
        
        Args:
            bucket_name: Name identifier for the bucket (usually service name)
            bucket_type: Type of bucket, either "requests" or "tokens" 
            capacity: Maximum tokens the bucket can hold
            refill_rate: Rate at which tokens are added (tokens per second)
            api_base_url: Base URL for the token bucket server API
                         (default: "http://localhost:8000")
                         
        Raises:
            ValueError: If bucket creation on the server fails
            
        Example:
            >>> client = TokenBucketClient(
            ...     bucket_name="openai",
            ...     bucket_type="requests", 
            ...     capacity=100,
            ...     refill_rate=10
            ... )
        """
        self.bucket_name = bucket_name
        self.bucket_type = bucket_type
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.api_base_url = api_base_url
        self.bucket_id = f"{bucket_name}_{bucket_type}"

        # Initialize the bucket on the server
        asyncio.run(self._create_bucket())

        # Cache some values locally
        self.creation_time = time.monotonic()
        self.turbo_mode = False

    async def _create_bucket(self) -> None:
        """
        Create or retrieve the bucket on the remote server.
        
        This private async method sends a request to the server to create a new
        bucket with the specified parameters. If the bucket already exists on
        the server, it updates the local parameters to match the server's values.
        
        Raises:
            ValueError: If the server returns an error
        """
        async with aiohttp.ClientSession() as session:
            # Prepare payload with bucket parameters
            payload = {
                "bucket_name": self.bucket_name,
                "bucket_type": self.bucket_type,
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
            }
            
            # Send request to create/retrieve bucket
            async with session.post(
                f"{self.api_base_url}/bucket",
                json=payload,
            ) as response:
                if response.status != 200:
                    raise TokenBucketClientError(f"Unexpected error: {await response.text()}")

                # Process server response
                result = await response.json()
                if result["status"] == "existing":
                    # Update our local values to match the existing bucket
                    self.capacity = float(result["bucket"]["capacity"])
                    self.refill_rate = float(result["bucket"]["refill_rate"])

    def turbo_mode_on(self) -> None:
        """
        Enable turbo mode to bypass rate limits.
        
        Turbo mode sets the refill rate to infinity on the server,
        effectively bypassing rate limits. This is useful for testing
        or when rate limits are not needed.
        
        Raises:
            ValueError: If the server returns an error
            
        Example:
            >>> client = TokenBucketClient(bucket_name="test", bucket_type="test", 
            ...                           capacity=100, refill_rate=10)
            >>> client.turbo_mode_on()  # Now rate limits are bypassed
        """
        asyncio.run(self._set_turbo_mode(True))
        self.turbo_mode = True

    def turbo_mode_off(self) -> None:
        """
        Disable turbo mode and restore original rate limits.
        
        This method restores the original refill rates on the server,
        re-enabling rate limiting after it was bypassed with turbo_mode_on().
        
        Raises:
            ValueError: If the server returns an error
            
        Example:
            >>> client = TokenBucketClient(bucket_name="test", bucket_type="test", 
            ...                           capacity=100, refill_rate=10)
            >>> client.turbo_mode_on()  # Bypass rate limits
            >>> # Do some work without rate limiting
            >>> client.turbo_mode_off()  # Restore rate limits
        """
        asyncio.run(self._set_turbo_mode(False))
        self.turbo_mode = False

    async def add_tokens(self, amount: Union[int, float]) -> None:
        """
        Add tokens to the bucket on the server.
        
        This async method adds tokens to the bucket on the server.
        It's useful for manually restoring tokens or increasing the 
        available tokens beyond the normal refill rate.
        
        Args:
            amount: Number of tokens to add to the bucket
            
        Raises:
            ValueError: If the server returns an error
            
        Example:
            >>> import asyncio
            >>> client = TokenBucketClient(bucket_name="test", bucket_type="test", 
            ...                           capacity=100, refill_rate=10)
            >>> # Add 50 tokens to the bucket
            >>> asyncio.run(client.add_tokens(50))
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/bucket/{self.bucket_id}/add_tokens",
                params={"amount": amount},
            ) as response:
                if response.status != 200:
                    raise TokenBucketClientError(f"Failed to add tokens: {await response.text()}")

    async def _set_turbo_mode(self, state: bool) -> None:
        """
        Set the turbo mode state on the server.
        
        This private async method sends a request to the server to
        enable or disable turbo mode.
        
        Args:
            state: True to enable turbo mode, False to disable
            
        Raises:
            ValueError: If the server returns an error
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/bucket/{self.bucket_id}/turbo_mode/{str(state).lower()}"
            ) as response:
                if response.status != 200:
                    raise TokenBucketClientError(
                        f"Failed to set turbo mode: {await response.text()}"
                    )

    async def get_tokens(
        self, amount: Union[int, float] = 1, cheat_bucket_capacity: bool = True
    ) -> None:
        """
        Request tokens from the token bucket on the server.
        
        This async method requests tokens from the token bucket on the server.
        It will either return immediately if tokens are available or raise an
        exception if tokens are not available.
        
        Args:
            amount: Number of tokens to request (default: 1)
            cheat_bucket_capacity: If True, allow exceeding capacity temporarily
                                  (default: True)
            
        Raises:
            ValueError: If the server returns an error, which may indicate
                      insufficient tokens are available
                      
        Example:
            >>> import asyncio
            >>> client = TokenBucketClient(bucket_name="test", bucket_type="test", 
            ...                           capacity=100, refill_rate=10)
            >>> # Request 20 tokens
            >>> asyncio.run(client.get_tokens(20))
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/bucket/{self.bucket_id}/get_tokens",
                params={
                    "amount": amount,
                    "cheat_bucket_capacity": int(cheat_bucket_capacity),
                },
            ) as response:
                if response.status != 200:
                    raise TokenBucketClientError(f"Failed to get tokens: {await response.text()}")

    def get_throughput(self, time_window: Optional[float] = None) -> float:
        """
        Calculate the token throughput over a specified time window.
        
        This method calculates the average token throughput (tokens per minute)
        over the specified time window by requesting the bucket status from
        the server and analyzing token usage.
        
        Args:
            time_window: Time window in seconds to calculate throughput over
                        (default: entire bucket lifetime)
                        
        Returns:
            Average throughput in tokens per minute
            
        Example:
            >>> client = TokenBucketClient(bucket_name="test", bucket_type="test", 
            ...                           capacity=100, refill_rate=10)
            >>> # Calculate throughput over the last 60 seconds
            >>> throughput = client.get_throughput(60)
            >>> print(f"Average throughput: {throughput:.1f} tokens/minute")
        """
        # Get current bucket status from server
        status = asyncio.run(self._get_status())
        now = time.monotonic()

        # Determine start time based on time_window parameter
        if time_window is None:
            start_time = self.creation_time
        else:
            start_time = now - time_window

        # Ensure start_time isn't before bucket creation
        if start_time < self.creation_time:
            start_time = self.creation_time

        # Calculate elapsed time and avoid division by zero
        elapsed_time = now - start_time
        if elapsed_time == 0:
            return status["num_released"] / 0.001  # Avoid division by zero

        # Convert to tokens per minute
        return (status["num_released"] / elapsed_time) * 60

    async def _get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the bucket from the server.
        
        This private async method retrieves the current status of the bucket
        from the server, including the current token count, history log,
        and various statistics.
        
        Returns:
            Dictionary containing the bucket status information
            
        Raises:
            ValueError: If the server returns an error
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_base_url}/bucket/{self.bucket_id}/status"
            ) as response:
                if response.status != 200:
                    raise TokenBucketClientError(
                        f"Failed to get bucket status: {await response.text()}"
                    )
                return await response.json()

    def __add__(self, other: "TokenBucketClient") -> "TokenBucketClient":
        """
        Combine two token bucket clients to create a new one with merged limits.
        
        This method combines two token bucket clients by creating a new client
        with the minimum capacity and refill rate of both inputs. This is useful
        for creating a client that respects both sets of rate limits.
        
        Args:
            other: Another TokenBucketClient to combine with this one
            
        Returns:
            A new TokenBucketClient with the combined (minimum) limits
            
        Example:
            >>> client1 = TokenBucketClient(bucket_name="service1", bucket_type="requests",
            ...                            capacity=100, refill_rate=10)
            >>> client2 = TokenBucketClient(bucket_name="service2", bucket_type="requests",
            ...                            capacity=50, refill_rate=5)
            >>> combined = client1 + client2  # Takes the minimum of both limits
        """
        return TokenBucketClient(
            bucket_name=self.bucket_name,
            bucket_type=self.bucket_type,
            capacity=min(self.capacity, other.capacity),
            refill_rate=min(self.refill_rate, other.refill_rate),
            api_base_url=self.api_base_url,
        )

    @property
    def tokens(self) -> float:
        """
        Get the current number of tokens available in the bucket.
        
        This property retrieves the current token count from the server.
        
        Returns:
            Current number of tokens available in the bucket
            
        Example:
            >>> client = TokenBucketClient(bucket_name="test", bucket_type="test",
            ...                           capacity=100, refill_rate=10)
            >>> available = client.tokens
            >>> print(f"Available tokens: {available}")
        """
        status = asyncio.run(self._get_status())
        return float(status["tokens"])

    def wait_time(self, requested_tokens: Union[float, int]) -> float:
        """
        Calculate the time to wait for the requested number of tokens.
        
        This method calculates how long to wait (in seconds) for the requested
        number of tokens to become available, based on the current token count
        and refill rate.
        
        Args:
            requested_tokens: Number of tokens needed
            
        Returns:
            Time to wait in seconds (0.0 if tokens are already available)
            
        Raises:
            ValueError: If an error occurs while calculating wait time
            
        Example:
            >>> client = TokenBucketClient(bucket_name="test", bucket_type="test",
            ...                           capacity=100, refill_rate=10)
            >>> wait_seconds = client.wait_time(50)
            >>> print(f"Need to wait {wait_seconds:.2f} seconds")
        """
        # If we have enough tokens, no need to wait
        if self.tokens >= float(requested_tokens):
            return 0.0
            
        try:
            # Calculate time needed to accumulate the required tokens
            return (requested_tokens - self.tokens) / self.refill_rate
        except Exception as e:
            raise BucketError(f"Error calculating wait time: {e}")

    # Note: The commented out method below is a reminder for future implementation
    # def wait_time(self, num_tokens: Union[int, float]) -> float:
    #     """Server-side wait time calculation (future implementation)"""
    #     return 0  # TODO - Need to implement this on the server side

    def visualize(self) -> Figure:
        """
        Visualize the token bucket usage over time as a matplotlib figure.
        
        This method generates a plot showing the available tokens over time,
        which can be useful for monitoring and debugging rate limit issues.
        
        Returns:
            A matplotlib Figure object that can be displayed or saved
            
        Example:
            >>> client = TokenBucketClient(bucket_name="test", bucket_type="test",
            ...                           capacity=100, refill_rate=10)
            >>> # Do some operations with the bucket
            >>> plot = client.visualize()
            >>> # Now you can display or save the plot
        """
        # Get the bucket history from the server
        status = asyncio.run(self._get_status())
        times, tokens = zip(*status["log"])
        
        # Normalize times to start at 0
        start_time = times[0]
        times = [t - start_time for t in times]

        # Create the plot
        fig = plt.figure(figsize=(10, 6))
        plt.plot(times, tokens, label="Tokens Available")
        plt.xlabel("Time (seconds)", fontsize=12)
        plt.ylabel("Number of Tokens", fontsize=12)
        details = f"{self.bucket_name} ({self.bucket_type}) Bucket Usage Over Time\nCapacity: {self.capacity:.1f}, Refill Rate: {self.refill_rate:.1f}/second"
        plt.title(details, fontsize=14)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        
        return fig


# Examples and doctests
if __name__ == "__main__":
    #import doctest

    # Example showing how to use TokenBucketClient
    def example_usage():
        """
        Example demonstrating how to use TokenBucketClient:
        
        ```python
        import asyncio
        import time
        from edsl.buckets.token_bucket_client import TokenBucketClient
        
        # Create a client connected to a running token bucket server
        bucket = TokenBucketClient(
            bucket_name="openai", 
            bucket_type="requests",
            capacity=100, 
            refill_rate=10,
            api_base_url="http://localhost:8000"
        )
        
        # Get tokens from the bucket
        asyncio.run(bucket.get_tokens(50))
        
        # Wait for a second
        time.sleep(1)
        
        # Get more tokens
        asyncio.run(bucket.get_tokens(30))
        
        # Check throughput
        throughput = bucket.get_throughput(1)
        print(f"Throughput: {throughput:.1f} tokens/minute")
        
        # Enable turbo mode to bypass rate limits
        bucket.turbo_mode_on()
        
        # Do some operations without rate limiting
        asyncio.run(bucket.get_tokens(1000))  # Would normally exceed limits
        
        # Disable turbo mode
        bucket.turbo_mode_off()
        
        # Visualize bucket usage
        plot = bucket.visualize()
        ```
        """
        pass
    
    # Run doctests
    #doctest.testmod()
