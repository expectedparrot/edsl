from edsl.jobs.buckets.TokenBucket import TokenBucket


class ModelBuckets:
    """A class to represent the token and request buckets for a model.

    Most LLM model services have limits both on requests-per-minute (RPM) and tokens-per-minute (TPM).
    A request is one call to the service. The number of tokens required for a request depends on parameters.
    """

    def __init__(self, requests_bucket: TokenBucket, tokens_bucket: TokenBucket):
        """Initialize the model buckets.

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

    @classmethod
    def infinity_bucket(cls, model_name: str = "not_specified") -> "ModelBuckets":
        """Create a bucket with infinite capacity and refill rate."""
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
