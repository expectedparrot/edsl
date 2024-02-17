import asyncio
import time

## TPM: Tokens-per-minute
## RPM: Requests-per-minute 

class TokenBucket:
    
    def __init__(self, capacity, refill_rate):
        self.capacity = capacity  # Maximum number of tokens
        self.tokens = capacity  # Current number of available tokens
        self.refill_rate = refill_rate  # Rate at which tokens are refilled
        self.last_refill = time.monotonic()  # Last refill time

    def refill(self):
        """Refill the bucket with new tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        #print(f"Elapsed time: {elapsed}")
        refill_amount = elapsed * self.refill_rate
        #print(f"Refill amount: {refill_amount}")
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now

    def wait_time(self, requested_tokens):
        """Calculate the time to wait for the requested number of tokens."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        available_tokens = min(self.capacity, self.tokens + refill_amount)
        return max(0, requested_tokens - available_tokens) / self.refill_rate

    async def get_tokens(self, amount=1):
        """Wait for the specified number of tokens to become available."""
        if amount > self.capacity:
            raise ValueError("Requested tokens exceed bucket capacity")
        while self.tokens < amount:
            self.refill()
            #print(f"Refilling tokens; current balance is {self.tokens}")
            await asyncio.sleep(0.1)  # Sleep briefly to prevent busy waiting
        self.tokens -= amount


# async def my_task(task_id, token_amount, bucket):
#     await bucket.get_tokens(token_amount)  # Request specified number of tokens from the bucket
#     print(f"Executing task {task_id} with {token_amount} tokens")
#     # Simulate task execution
#     await asyncio.sleep(1)

# async def main():
#     bucket = TokenBucket(capacity=10, refill_rate=2)  # Customize parameters as needed

#     # Example tasks with varying token requirements
#     tasks = [
#         my_task(1, 3, bucket),
#         my_task(2, 2, bucket),
#         my_task(3, 5, bucket),
#         my_task(4, 1, bucket)
#     ]
#     await asyncio.gather(*tasks)

# asyncio.run(main())
