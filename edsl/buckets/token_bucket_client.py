from typing import Union, Optional
import asyncio
import time
import aiohttp


class TokenBucketClient:
    """REST API client version of TokenBucket that maintains the same interface
    by delegating to a server running the original TokenBucket implementation."""

    def __init__(
        self,
        *,
        bucket_name: str,
        bucket_type: str,
        capacity: Union[int, float],
        refill_rate: Union[int, float],
        api_base_url: str = "http://localhost:8000",
    ):
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

    async def _create_bucket(self):
        async with aiohttp.ClientSession() as session:
            payload = {
                "bucket_name": self.bucket_name,
                "bucket_type": self.bucket_type,
                "capacity": self.capacity,
                "refill_rate": self.refill_rate,
            }
            async with session.post(
                f"{self.api_base_url}/bucket",
                json=payload,
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Unexpected error: {await response.text()}")

                result = await response.json()
                if result["status"] == "existing":
                    # Update our local values to match the existing bucket
                    self.capacity = float(result["bucket"]["capacity"])
                    self.refill_rate = float(result["bucket"]["refill_rate"])

    def turbo_mode_on(self):
        """Set the refill rate to infinity."""
        asyncio.run(self._set_turbo_mode(True))
        self.turbo_mode = True

    def turbo_mode_off(self):
        """Restore the refill rate to its original value."""
        asyncio.run(self._set_turbo_mode(False))
        self.turbo_mode = False

    async def add_tokens(self, amount: Union[int, float]):
        """Add tokens to the bucket."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/bucket/{self.bucket_id}/add_tokens",
                params={"amount": amount},
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to add tokens: {await response.text()}")

    async def _set_turbo_mode(self, state: bool):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/bucket/{self.bucket_id}/turbo_mode/{str(state).lower()}"
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Failed to set turbo mode: {await response.text()}"
                    )

    async def get_tokens(
        self, amount: Union[int, float] = 1, cheat_bucket_capacity=True
    ) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base_url}/bucket/{self.bucket_id}/get_tokens",
                params={
                    "amount": amount,
                    "cheat_bucket_capacity": int(cheat_bucket_capacity),
                },
            ) as response:
                if response.status != 200:
                    raise ValueError(f"Failed to get tokens: {await response.text()}")

    def get_throughput(self, time_window: Optional[float] = None) -> float:
        status = asyncio.run(self._get_status())
        now = time.monotonic()

        if time_window is None:
            start_time = self.creation_time
        else:
            start_time = now - time_window

        if start_time < self.creation_time:
            start_time = self.creation_time

        elapsed_time = now - start_time

        if elapsed_time == 0:
            return status["num_released"] / 0.001

        return (status["num_released"] / elapsed_time) * 60

    async def _get_status(self) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.api_base_url}/bucket/{self.bucket_id}/status"
            ) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Failed to get bucket status: {await response.text()}"
                    )
                return await response.json()

    def __add__(self, other) -> "TokenBucketClient":
        """Combine two token buckets."""
        return TokenBucketClient(
            bucket_name=self.bucket_name,
            bucket_type=self.bucket_type,
            capacity=min(self.capacity, other.capacity),
            refill_rate=min(self.refill_rate, other.refill_rate),
            api_base_url=self.api_base_url,
        )

    @property
    def tokens(self) -> float:
        """Get the number of tokens remaining in the bucket."""
        status = asyncio.run(self._get_status())
        return float(status["tokens"])

    def wait_time(self, requested_tokens: Union[float, int]) -> float:
        """Calculate the time to wait for the requested number of tokens."""
        # self.refill()  # Update the current token count
        if self.tokens >= float(requested_tokens):
            return 0.0
        try:
            return (requested_tokens - self.tokens) / self.refill_rate
        except Exception as e:
            raise ValueError(f"Error calculating wait time: {e}")

    # def wait_time(self, num_tokens: Union[int, float]) -> float:
    #     return 0  # TODO - Need to implement this on the server side

    def visualize(self):
        """Visualize the token bucket over time."""
        status = asyncio.run(self._get_status())
        times, tokens = zip(*status["log"])
        start_time = times[0]
        times = [t - start_time for t in times]

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


if __name__ == "__main__":
    import doctest

    doctest.testmod()
    # bucket = TokenBucketClient(
    #     bucket_name="test", bucket_type="test", capacity=100, refill_rate=10
    # )
    # asyncio.run(bucket.get_tokens(50))
    # time.sleep(1)  # Wait for 1 second
    # asyncio.run(bucket.get_tokens(30))
    # throughput = bucket.get_throughput(1)
    # print(throughput)
    # bucket.visualize()
