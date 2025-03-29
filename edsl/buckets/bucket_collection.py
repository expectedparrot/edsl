"""
BucketCollection module for managing rate limits across multiple language models.

This module provides the BucketCollection class, which manages rate limits for
multiple language models, organizing them by service provider. It ensures that
API rate limits are respected while allowing models from the same service to
share the same rate limit buckets.
"""

from typing import TYPE_CHECKING, Dict, List, Tuple
from collections import UserDict
from threading import RLock
from matplotlib.figure import Figure

from .token_bucket import TokenBucket
from .model_buckets import ModelBuckets
from ..jobs.decorators import synchronized_class

if TYPE_CHECKING:
    from ..language_models import LanguageModel
    from ..key_management import KeyLookup
    
@synchronized_class
class BucketCollection(UserDict):
    """
    Collection of ModelBuckets for managing rate limits across multiple language models.
    
    BucketCollection is a thread-safe dictionary-like container that maps language models
    to their corresponding ModelBuckets objects. It helps manage rate limits for multiple
    models, organizing them by service provider to ensure that API rate limits are
    respected across all models using the same service.
    
    The class maps models to services, and services to buckets, allowing models from
    the same service to share rate limit buckets. This approach ensures accurate
    rate limiting when multiple models use the same underlying service.
    
    Attributes:
        infinity_buckets (bool): If True, all buckets have infinite capacity and refill rate
        models_to_services (dict): Maps model names to their service provider names
        services_to_buckets (dict): Maps service names to their ModelBuckets instances
        remote_url (str, optional): URL for remote token bucket server if using distributed mode
        
    Example:
        >>> from edsl import Model
        >>> bucket_collection = BucketCollection()
        >>> model = Model('gpt-4')
        >>> bucket_collection.add_model(model)
        >>> # Now rate limits for the model are being tracked
    """

    def __init__(self, infinity_buckets: bool = False):
        """
        Initialize a new BucketCollection.
        
        Creates a new BucketCollection to manage rate limits across multiple language
        models. If infinity_buckets is True, all buckets will have unlimited capacity
        and refill rate, effectively bypassing rate limits.
        
        Args:
            infinity_buckets: If True, creates buckets with unlimited capacity
                             and refill rate (default: False)
                             
        Example:
            >>> # Create a standard bucket collection with rate limiting
            >>> bucket_collection = BucketCollection()
            >>> # Create a bucket collection with unlimited capacity (for testing)
            >>> unlimited_collection = BucketCollection(infinity_buckets=True)
        """
        super().__init__()
        self.infinity_buckets = infinity_buckets
        self.models_to_services = {}  # Maps model names to service names
        self.services_to_buckets = {} # Maps service names to ModelBuckets
        self._lock = RLock()

        # Check for remote token bucket server URL in environment
        import os

        url = os.environ.get("EDSL_REMOTE_TOKEN_BUCKET_URL", None)

        if url == "None" or url is None:
            self.remote_url = None
        else:
            self.remote_url = url

    @classmethod
    def from_models(
        cls, models_list: List["LanguageModel"], infinity_buckets: bool = False
    ) -> "BucketCollection":
        """
        Create a BucketCollection pre-populated with a list of models.
        
        This factory method creates a new BucketCollection and adds multiple
        models to it at initialization time.
        
        Args:
            models_list: List of LanguageModel instances to add to the collection
            infinity_buckets: If True, creates buckets with unlimited capacity
                             and refill rate (default: False)
                             
        Returns:
            A new BucketCollection containing the specified models
            
        Example:
            >>> from edsl import Model
            >>> models = [Model('gpt-4'), Model('gpt-3.5-turbo')]
            >>> collection = BucketCollection.from_models(models)
        """
        bucket_collection = cls(infinity_buckets=infinity_buckets)
        for model in models_list:
            bucket_collection.add_model(model)
        return bucket_collection

    def get_tokens(
        self, model: 'LanguageModel', bucket_type: str, num_tokens: int
    ) -> int:
        """
        [DEPRECATED] Get the number of tokens remaining in the bucket.
        
        This method is deprecated and will raise an exception if called.
        It is kept for reference purposes only.
        
        Args:
            model: The language model to get tokens for
            bucket_type: The type of bucket ('requests' or 'tokens')
            num_tokens: The number of tokens to retrieve
            
        Raises:
            Exception: This method is deprecated
            
        Example:
            >>> bucket_collection = BucketCollection()
            >>> from edsl import Model 
            >>> m = Model('test')
            >>> bucket_collection.add_model(m)
            >>> # The following would raise an exception:
            >>> # bucket_collection.get_tokens(m, 'tokens', 10)
        """
        from .exceptions import BucketError
        raise BucketError("This method is deprecated and should not be used")
        # The following code is kept for reference only
        # relevant_bucket = getattr(self[model], bucket_type)
        # return relevant_bucket.get_tokens(num_tokens)

    def __repr__(self) -> str:
        """
        Generate a string representation of the BucketCollection.
        
        Returns:
            String representation showing the collection's contents
        """
        return f"BucketCollection({self.data})"

    def add_model(self, model: "LanguageModel") -> None:
        """
        Add a language model to the bucket collection.
        
        This method adds a language model to the BucketCollection, creating the
        necessary token buckets for its service provider if they don't already exist.
        Models from the same service share the same buckets.
        
        Args:
            model: The LanguageModel instance to add to the collection
            
        Example:
            >>> from edsl import Model 
            >>> model = Model('gpt-4')
            >>> bucket_collection = BucketCollection()
            >>> bucket_collection.add_model(model)
        """
        # Calculate tokens-per-second (TPS) and requests-per-second (RPS) rates
        if not self.infinity_buckets:
            TPS = model.tpm / 60.0  # Convert tokens-per-minute to tokens-per-second
            RPS = model.rpm / 60.0  # Convert requests-per-minute to requests-per-second
        else:
            TPS = float("inf")  # Infinite tokens per second
            RPS = float("inf")  # Infinite requests per second

        # If this is a new model we haven't seen before
        if model.model not in self.models_to_services:
            service = model._inference_service_
            
            # If this is a new service we haven't created buckets for yet
            if service not in self.services_to_buckets:
                # Create request rate limiting bucket
                requests_bucket = TokenBucket(
                    bucket_name=service,
                    bucket_type="requests",
                    capacity=RPS,
                    refill_rate=RPS,
                    remote_url=self.remote_url,
                )
                
                # Create token rate limiting bucket
                tokens_bucket = TokenBucket(
                    bucket_name=service,
                    bucket_type="tokens",
                    capacity=TPS,
                    refill_rate=TPS,
                    remote_url=self.remote_url,
                )
                
                # Store the buckets for this service
                self.services_to_buckets[service] = ModelBuckets(
                    requests_bucket, tokens_bucket
                )
                
            # Map this model to its service and buckets
            self.models_to_services[model.model] = service
            self[model] = self.services_to_buckets[service]
        else:
            # Model already exists, just retrieve its existing buckets
            self[model] = self.services_to_buckets[self.models_to_services[model.model]]

    def update_from_key_lookup(self, key_lookup: "KeyLookup") -> None:
        """
        Update bucket rate limits based on information from KeyLookup.
        
        This method updates the capacity and refill rates of all buckets based on
        the RPM (requests per minute) and TPM (tokens per minute) limits specified
        in the provided KeyLookup. This is useful when API keys are rotated or
        rate limits change.
        
        Args:
            key_lookup: KeyLookup object containing service rate limit information
            
        Example:
            >>> from edsl.key_management import KeyLookup
            >>> key_lookup = KeyLookup()  # Assume this has rate limit info
            >>> bucket_collection = BucketCollection()
            >>> # Add some models to the collection
            >>> bucket_collection.update_from_key_lookup(key_lookup)
            >>> # Now rate limits are updated based on key_lookup
        """
        # Skip updates if we're using infinite buckets
        if self.infinity_buckets:
            return
            
        # Update each service with new rate limits
        for model_name, service in self.models_to_services.items():
            if service in key_lookup:
                # Update request rate limits if available
                if key_lookup[service].rpm is not None:
                    new_rps = key_lookup[service].rpm / 60.0  # Convert to per-second
                    new_requests_bucket = TokenBucket(
                        bucket_name=service,
                        bucket_type="requests",
                        capacity=new_rps,
                        refill_rate=new_rps,
                        remote_url=self.remote_url,
                    )
                    self.services_to_buckets[service].requests_bucket = new_requests_bucket

                # Update token rate limits if available
                if key_lookup[service].tpm is not None:
                    new_tps = key_lookup[service].tpm / 60.0  # Convert to per-second
                    new_tokens_bucket = TokenBucket(
                        bucket_name=service,
                        bucket_type="tokens",
                        capacity=new_tps,
                        refill_rate=new_tps,
                        remote_url=self.remote_url,
                    )
                    self.services_to_buckets[service].tokens_bucket = new_tokens_bucket

    def visualize(self) -> Dict["LanguageModel", Tuple[Figure, Figure]]:
        """
        Visualize the token and request buckets for all models.
        
        This method generates visualization plots for each model's token and
        request buckets, which can be useful for monitoring rate limit usage
        and debugging rate limiting issues.
        
        Returns:
            Dictionary mapping language models to tuples of (request_plot, token_plot)
            
        Example:
            >>> bucket_collection = BucketCollection()
            >>> # Add some models
            >>> plots = bucket_collection.visualize()
            >>> # Now you can display or save these plots
        """
        plots = {}
        for model in self:
            plots[model] = self[model].visualize()
        return plots


# Examples and doctests
if __name__ == "__main__":
    import doctest
    
    # Example showing how to use BucketCollection
    def example_usage():
        """
        Example demonstrating how to use BucketCollection:
        
        >>> from edsl import Model
        >>> # Create models
        >>> gpt4 = Model('gpt-4')
        >>> gpt35 = Model('gpt-3.5-turbo')
        >>> claude = Model('claude-3-opus-20240229')
        >>> 
        >>> # Create bucket collection
        >>> collection = BucketCollection()
        >>> 
        >>> # Add models to the collection
        >>> collection.add_model(gpt4)
        >>> collection.add_model(gpt35)
        >>> collection.add_model(claude)
        >>> 
        >>> # Models from the same service share rate limits
        >>> print(collection[gpt4] is collection[gpt35])  # Both OpenAI
        True
        >>> print(collection[gpt4] is collection[claude])  # Different services
        False
        >>> 
        >>> # Visualize rate limits
        >>> # plots = collection.visualize()
        """
        pass
    
    # Run doctests
    doctest.testmod(optionflags=doctest.ELLIPSIS)
