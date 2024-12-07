from collections import UserDict
from edsl.jobs.buckets.TokenBucket import TokenBucket
from edsl.jobs.buckets.ModelBuckets import ModelBuckets

from functools import wraps
from threading import RLock
import inspect

from edsl.jobs.decorators import synchronized_class

# def synchronized_class(wrapped_class):
#     """Class decorator that makes all methods thread-safe."""

#     # Add a lock to the class
#     setattr(wrapped_class, "_lock", RLock())

#     # Get all methods from the class
#     for name, method in inspect.getmembers(wrapped_class, inspect.isfunction):
#         # Skip magic methods except __getitem__, __setitem__, __delitem__
#         if name.startswith("__") and name not in [
#             "__getitem__",
#             "__setitem__",
#             "__delitem__",
#         ]:
#             continue

#         # Create synchronized version of the method
#         def create_synchronized_method(method):
#             @wraps(method)
#             def synchronized_method(*args, **kwargs):
#                 instance = args[0]  # first arg is self
#                 with instance._lock:
#                     return method(*args, **kwargs)

#             return synchronized_method

#         # Replace the original method with synchronized version
#         setattr(wrapped_class, name, create_synchronized_method(method))

#     return wrapped_class


@synchronized_class
class BucketCollection(UserDict):
    """A Jobs object will have a whole collection of model buckets, as multiple models could be used.

    The keys here are the models, and the values are the ModelBuckets objects.
    Models themselves are hashable, so this works.
    """

    def __init__(self, infinity_buckets: bool = False):
        """Create a new BucketCollection.
        An infinity bucket is a bucket that never runs out of tokens or requests.
        """
        super().__init__()
        self.infinity_buckets = infinity_buckets
        self.models_to_services = {}
        self.services_to_buckets = {}
        self._lock = RLock()

    @classmethod
    def from_models(
        cls, models_list: list, infinity_buckets: bool = False
    ) -> "BucketCollection":
        """Create a BucketCollection from a list of models."""
        bucket_collection = cls(infinity_buckets=infinity_buckets)
        for model in models_list:
            bucket_collection.add_model(model)
        return bucket_collection

    def __repr__(self):
        return f"BucketCollection({self.data})"

    def add_model(self, model: "LanguageModel") -> None:
        """Adds a model to the bucket collection.

        This will create the token and request buckets for the model."""

        # compute the TPS and RPS from the model
        if not self.infinity_buckets:
            TPS = model.tpm / 60.0
            RPS = model.rpm / 60.0
        else:
            TPS = float("inf")
            RPS = float("inf")

        if model.model not in self.models_to_services:
            service = model._inference_service_
            if service not in self.services_to_buckets:
                requests_bucket = TokenBucket(
                    bucket_name=service,
                    bucket_type="requests",
                    capacity=RPS,
                    refill_rate=RPS,
                )
                tokens_bucket = TokenBucket(
                    bucket_name=service,
                    bucket_type="tokens",
                    capacity=TPS,
                    refill_rate=TPS,
                )
                self.services_to_buckets[service] = ModelBuckets(
                    requests_bucket, tokens_bucket
                )
            self.models_to_services[model.model] = service
            self[model] = self.services_to_buckets[service]
        else:
            self[model] = self.services_to_buckets[self.models_to_services[model.model]]

    def visualize(self) -> dict:
        """Visualize the token and request buckets for each model."""
        plots = {}
        for model in self:
            plots[model] = self[model].visualize()
        return plots
