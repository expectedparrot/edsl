"""
ModelBuckets module for managing rate limits for language model calls.

This module provides the ModelBuckets class, which manages both requests-per-minute
and tokens-per-minute rate limits for language model API services. Each ModelBuckets
instance contains two TokenBucket instances - one for requests and one for tokens.
"""

from typing import TYPE_CHECKING, Tuple
from matplotlib.figure import Figure

if TYPE_CHECKING:
    from .token_bucket import TokenBucket

class ModelBuckets:
    """
    Manages rate limits for a language model with separate request and token buckets.
    
    ModelBuckets encapsulates two TokenBucket instances - one for tracking API request
    limits (requests-per-minute) and another for tracking token usage limits 
    (tokens-per-minute). Most language model providers enforce both types of limits.
    
    Note on terminology: While language models use "tokens" as units of text, 
    the term "token" in this context refers to rate limiting tokens in the 
    token bucket algorithm. This is different from the language model tokens.
    
    Attributes:
        requests_bucket (TokenBucket): Controls request rate limits (RPM)
        tokens_bucket (TokenBucket): Controls token usage rate limits (TPM)
        
    Example:
        >>> from ..buckets.token_bucket import TokenBucket
        >>> requests_bucket = TokenBucket(bucket_name="gpt-4", bucket_type="requests", 
        ...                              capacity=100, refill_rate=10)
        >>> tokens_bucket = TokenBucket(bucket_name="gpt-4", bucket_type="tokens", 
        ...                            capacity=100000, refill_rate=10000)
        >>> model_buckets = ModelBuckets(requests_bucket, tokens_bucket)
    """

    def __init__(self, requests_bucket: "TokenBucket", tokens_bucket: "TokenBucket"):
        """
        Initialize a ModelBuckets instance with request and token rate limiting buckets.
        
        Args:
            requests_bucket: TokenBucket controlling requests-per-minute (RPM) limits
            tokens_bucket: TokenBucket controlling tokens-per-minute (TPM) limits
            
        Example:
            >>> from edsl.buckets import TokenBucket
            >>> requests_bucket = TokenBucket(bucket_name="gpt-4", bucket_type="requests", capacity=100, refill_rate=10)
            >>> tokens_bucket = TokenBucket(bucket_name="gpt-4", bucket_type="tokens", capacity=100000, refill_rate=10000)
            >>> buckets = ModelBuckets(requests_bucket, tokens_bucket)
        """
        self.requests_bucket = requests_bucket
        self.tokens_bucket = tokens_bucket

    def __add__(self, other: "ModelBuckets") -> "ModelBuckets":
        """
        Combine two ModelBuckets instances to create a merged bucket.
        
        This method allows combining rate limits from two different ModelBuckets 
        instances. The resulting bucket will have the combined capacity and refill 
        rates of both the input buckets.
        
        Args:
            other: Another ModelBuckets instance to combine with this one
            
        Returns:
            A new ModelBuckets instance with combined rate limits
            
        Example:
            >>> # Create two model buckets and combine them
            >>> from edsl.buckets.token_bucket import TokenBucket
            >>> bucket1 = ModelBuckets.infinity_bucket("model1")
            >>> bucket2 = ModelBuckets.infinity_bucket("model2")
            >>> combined = bucket1 + bucket2
        """
        return ModelBuckets(
            requests_bucket=self.requests_bucket + other.requests_bucket,
            tokens_bucket=self.tokens_bucket + other.tokens_bucket,
        )

    def turbo_mode_on(self) -> None:
        """
        Enable turbo mode for both request and token buckets.
        
        Turbo mode sets the refill rate to infinity for both buckets,
        effectively bypassing rate limits. This is useful for testing
        or when rate limits are not needed.
        
        Example:
            >>> buckets = ModelBuckets.infinity_bucket("test")
            >>> buckets.turbo_mode_on()  # Now rate limits are bypassed
        """
        self.requests_bucket.turbo_mode_on()
        self.tokens_bucket.turbo_mode_on()

    def turbo_mode_off(self) -> None:
        """
        Disable turbo mode and restore original rate limits.
        
        This method restores the original refill rates for both buckets,
        re-enabling rate limiting after it was bypassed with turbo_mode_on().
        
        Example:
            >>> buckets = ModelBuckets.infinity_bucket("test")
            >>> buckets.turbo_mode_on()  # Bypass rate limits
            >>> # Do some work without rate limiting
            >>> buckets.turbo_mode_off()  # Restore rate limits
        """
        self.requests_bucket.turbo_mode_off()
        self.tokens_bucket.turbo_mode_off()

    @classmethod
    def infinity_bucket(cls, model_name: str = "not_specified") -> "ModelBuckets":
        """
        Create a ModelBuckets instance with unlimited capacity and refill rate.
        
        This factory method creates a ModelBuckets with infinite capacity and
        refill rate for both request and token buckets, effectively creating
        a bucket with no rate limits.
        
        Args:
            model_name: Name identifier for the model (default: "not_specified")
            
        Returns:
            A ModelBuckets instance with unlimited rate limits
            
        Example:
            >>> unlimited = ModelBuckets.infinity_bucket("gpt-4")
            >>> # This bucket will never throttle requests
        """
        from .token_bucket import TokenBucket

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

    def visualize(self) -> Tuple[Figure, Figure]:
        """
        Create visualizations of token usage over time for both buckets.
        
        This method generates matplotlib plots showing token usage over time
        for both the request bucket and token bucket, which can be useful for
        monitoring and debugging rate limit issues.
        
        Returns:
            A tuple containing two matplotlib Figures (requests_plot, tokens_plot)
            
        Example:
            >>> ## buckets = ModelBuckets.infinity_bucket("test")
            >>> ## request_plot, token_plot = buckets.visualize()
            >>> ## Now you can display or save these plots
        """
        plot1 = self.requests_bucket.visualize()
        plot2 = self.tokens_bucket.visualize()
        return plot1, plot2

    def __repr__(self) -> str:
        """
        Generate a string representation of the ModelBuckets instance.
        
        Returns:
            A string showing the requests and tokens buckets contained in this instance
        """
        return f"ModelBuckets(requests_bucket={self.requests_bucket}, tokens_bucket={self.tokens_bucket})"


# Example usage and doctests
if __name__ == "__main__":
    import doctest
    
    # Example showing how to create and use ModelBuckets
    def example_usage():
        """
        Example demonstrating how to use ModelBuckets:
        
        >>> from edsl.buckets.token_bucket import TokenBucket
        >>> # Create buckets for a model with RPM=100, TPM=100000
        >>> requests_bucket = TokenBucket("gpt-4", "requests", 100, 10)
        >>> tokens_bucket = TokenBucket("gpt-4", "tokens", 100000, 10000)
        >>> model_buckets = ModelBuckets(requests_bucket, tokens_bucket)
        >>> 
        >>> # Use turbo mode to temporarily bypass rate limits
        >>> model_buckets.turbo_mode_on()
        >>> model_buckets.turbo_mode_off()
        >>> 
        >>> # Visualize the current state of the buckets
        >>> # plots = model_buckets.visualize()
        """
        pass
    
    # Run doctests
    doctest.testmod(optionflags=doctest.ELLIPSIS)
