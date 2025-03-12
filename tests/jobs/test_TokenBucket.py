import pytest
import asyncio
import time
from edsl.buckets import TokenBucket


@pytest.mark.asyncio
async def test_initial_tokens():
    bucket = TokenBucket(
        bucket_name="test", bucket_type="requests", capacity=5, refill_rate=1
    )
    assert bucket.tokens == 5, "Initial tokens should be equal to the capacity"


@pytest.mark.asyncio
async def test_token_refill():
    bucket = TokenBucket(
        bucket_name="test", bucket_type="requests", capacity=5, refill_rate=1
    )
    bucket.tokens = 0
    bucket.last_refill = time.monotonic() - 5  # Set last refill to 5 seconds ago
    bucket.refill()
    assert bucket.tokens > 0, "Tokens should be refilled over time"


@pytest.mark.asyncio
async def test_get_single_token():
    bucket = TokenBucket(
        bucket_name="test", bucket_type="requests", capacity=5, refill_rate=1
    )
    await bucket.get_tokens(1)
    assert bucket.tokens == 4, "Token count should decrease by 1 after getting 1 token"


@pytest.mark.asyncio
async def test_get_multiple_tokens():
    bucket = TokenBucket(
        bucket_name="test", bucket_type="requests", capacity=5, refill_rate=1
    )
    await bucket.get_tokens(3)
    assert (
        bucket.tokens == 2
    ), "Token count should decrease by the number of tokens requested"


@pytest.mark.asyncio
async def test_wait_for_tokens():
    bucket = TokenBucket(
        bucket_name="test", bucket_type="requests", capacity=5, refill_rate=1
    )
    bucket.tokens = 0
    start_time = time.monotonic()
    await bucket.get_tokens(1)
    elapsed = time.monotonic() - start_time
    assert elapsed >= 1, "Should wait for at least 1 second to get a token"


@pytest.mark.asyncio
async def test_no_overflow():
    bucket = TokenBucket(
        bucket_name="test", bucket_type="requests", capacity=5, refill_rate=1
    )
    # Simulate long time without a refill
    bucket.last_refill = time.monotonic() - 1000
    bucket.refill()
    assert bucket.tokens == 5, "Token count should not exceed capacity"
