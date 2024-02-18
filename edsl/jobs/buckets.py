import asyncio
import time
from collections import UserDict
from matplotlib import pyplot as plt

class TokenBucket:
    
    def __init__(self, *, bucket_name, bucket_type, capacity, refill_rate):
        self.bucket_name = bucket_name
        self.bucket_type = bucket_type
        self.capacity = capacity  # Maximum number of tokens
        self.tokens = capacity  # Current number of available tokens
        self.refill_rate = refill_rate  # Rate at which tokens are refilled
        self.last_refill = time.monotonic()  # Last refill time

        self.log = []

    def __add__(self, other):
        return TokenBucket(
            bucket_name = self.bucket_name,
            bucket_type = self.bucket_type,
            capacity = min(self.capacity, other.capacity), 
            refil_rate = min(self.refill_rate, other.refill_rate)
        )
    
    def add_tokens(self, tokens):
        self.tokens = min(self.capacity, self.tokens + tokens)
        self.log.append((time.monotonic(), self.tokens))

    def refill(self):
        """Refill the bucket with new tokens based on elapsed time."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        #print(f"Elapsed time: {elapsed}")
        refill_amount = elapsed * self.refill_rate
        #print(f"Refill amount: {refill_amount}")
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now

        self.log.append((now, self.tokens))

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
            raise ValueError(f"Requested tokens exceed bucket capacity. Bucket capacity: {self.capacity}, requested amount: {amount}")
        while self.tokens < amount:
            self.refill()
            await asyncio.sleep(0.1)  # Sleep briefly to prevent busy waiting
        self.tokens -= amount

        now = time.monotonic()
        self.log.append((now, self.tokens))

    def get_log(self):
        return self.log
    
    def visualize(self):
        times, tokens = zip(*self.get_log())
        start_time = times[0]
        times = [t - start_time for t in times]  # Normalize time to start from 0

        # Plotting
        plt.figure(figsize=(10, 6))
        plt.plot(times, tokens, label='Tokens Available')
        plt.xlabel('Time (seconds)', fontsize=12)
        plt.ylabel('Number of Tokens', fontsize=12)
        details = f'{self.bucket_name} ({self.bucket_type}) Bucket Usage Over Time\nCapacity: {self.capacity:.1f}, Refill Rate: {self.refill_rate:.1f}/second'
        plt.title(details, fontsize=14)

        # Display bucket information
        # plt.text(0.95, 0.01, 
        #         details,
        #         verticalalignment='bottom', horizontalalignment='right',
        #         transform=plt.gca().transAxes,
        #         color='green', fontsize=10)

        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.show()

class ModelBuckets:
    def __init__(self, requests_bucket: TokenBucket, tokens_bucket: TokenBucket):
        self.requests_bucket = requests_bucket
        self.tokens_bucket = tokens_bucket

    def __add__(self, other):
        return ModelBuckets(requests_bucket = self.requests_bucket + other.requests_bucket,
                            tokens_bucket = self.tokens_bucket + other.tokens_bucket
        )  
    
    def visualize(self):
        plot1 = self.requests_bucket.visualize()
        plot2 = self.tokens_bucket.visualize()
        return plot1, plot2

class BucketCollection(UserDict):
    """When passed a model, will look up the associated buckets.
    The keys are models, the value is a ModelBuckets 
    """
    def __init__(self):
        super().__init__()

    def add_model(self, model):
        # compute the TPS and RPS from the model
        TPS = model.TPM() / 60.0
        RPS = model.RPM() / 60.0    
        # create the buckets
        requests_bucket = TokenBucket(bucket_name = model.model, 
                                      bucket_type = "requests",
                                      capacity=RPS, 
                                      refill_rate=RPS)
        tokens_bucket = TokenBucket(bucket_name = model.model, 
                                    bucket_type = "tokens",
                                    capacity=TPS, 
                                    refill_rate=TPS)
        model_buckets = ModelBuckets(requests_bucket, tokens_bucket)
        if model in self:
            # it if already exists, combine the buckets
            self[model] += model_buckets
        else:          
            self[model] = model_buckets

    def visualize(self):
        plots = {}
        for model in self:
            plots[model] = self[model].visualize()
        return plots

    
