# from edsl.jobs.buckets.TokenBucket import TokenBucket

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .TokenBucket import TokenBucket

class ModelBuckets:
    """A class to represent a token or requests buckets for a model.
    
    This is confusingly named because we're dealing with LLMs that use tokens. 
    These are different tokens---these are tokens to control rate of requests.

    Most LLM model services have limits both on requests-per-minute (RPM) and tokens-per-minute (TPM).
    A request is one call to the service. The number of tokens required for a request depends on parameters.
    """

    def __init__(self, requests_bucket: "TokenBucket", tokens_bucket: "TokenBucket"):
        """Initialize the model buckets.

        :param requests_bucket: A TokenBucket object that captures requests per unit of time.
        :param tokens_bucket: A TokenBucket object that captures tokens per unit of time.

        The requests bucket captures requests per unit of time.
        The tokens bucket captures the number of language model tokens.

        """
        self.requests_bucket = requests_bucket
        self.tokens_bucket = tokens_bucket

    def __add__(self, other: "ModelBuckets"):
        """Combine two model buckets."""
        return ModelBuckets(
            requests_bucket=self.requests_bucket + other.requests_bucket,
            tokens_bucket=self.tokens_bucket + other.tokens_bucket,
        )

    def turbo_mode_on(self):
        """Set the refill rate to infinity for both buckets."""
        self.requests_bucket.turbo_mode_on()
        self.tokens_bucket.turbo_mode_on()

    def turbo_mode_off(self):
        """Restore the refill rate to its original value for both buckets."""
        self.requests_bucket.turbo_mode_off()
        self.tokens_bucket.turbo_mode_off()

    @classmethod
    def infinity_bucket(cls, model_name: str = "not_specified") -> "ModelBuckets":
        """Create a bucket with infinite capacity and refill rate."""
        from .TokenBucket import TokenBucket

        return cls(
            requests_bucket=TokenBucket(
                bucket_name=model_name,
                bucket_type="requests",
                capacity=float("inf"),
                refill_rate=float("inf"),
            ),
            tokens_bucket=TokenBucket(
                bucket_name=model_name,
                bucket_type="tokens",
                capacity=float("inf"),
                refill_rate=float("inf"),
            ),
        )

    def visualize(self):
        """Visualize the token and request buckets."""
        plot1 = self.requests_bucket.visualize()
        plot2 = self.tokens_bucket.visualize()
        return plot1, plot2

    def __repr__(self):
        return f"ModelBuckets(requests_bucket={self.requests_bucket}, tokens_bucket={self.tokens_bucket})"
