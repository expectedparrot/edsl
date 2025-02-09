from typing import Optional
from collections import UserDict
from edsl.jobs.buckets.TokenBucket import TokenBucket
from edsl.jobs.buckets.ModelBuckets import ModelBuckets

# from functools import wraps
from threading import RLock

from edsl.jobs.decorators import synchronized_class


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

        from edsl.config import CONFIG
        import os

        url = os.environ.get("EDSL_REMOTE_TOKEN_BUCKET_URL", None)

        if url == "None" or url is None:
            self.remote_url = None
            # print(f"Using remote token bucket URL: {url}")
        else:
            self.remote_url = url

    @classmethod
    def from_models(
        cls, models_list: list, infinity_buckets: bool = False
    ) -> "BucketCollection":
        """Create a BucketCollection from a list of models."""
        bucket_collection = cls(infinity_buckets=infinity_buckets)
        for model in models_list:
            bucket_collection.add_model(model)
        return bucket_collection

    def get_tokens(
        self, model: "LanguageModel", bucket_type: str, num_tokens: int
    ) -> int:
        """Get the number of tokens remaining in the bucket."""
        relevant_bucket = getattr(self[model], bucket_type)
        return relevant_bucket.get_tokens(num_tokens)

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
                    remote_url=self.remote_url,
                )
                tokens_bucket = TokenBucket(
                    bucket_name=service,
                    bucket_type="tokens",
                    capacity=TPS,
                    refill_rate=TPS,
                    remote_url=self.remote_url,
                )
                self.services_to_buckets[service] = ModelBuckets(
                    requests_bucket, tokens_bucket
                )
            self.models_to_services[model.model] = service
            self[model] = self.services_to_buckets[service]
        else:
            self[model] = self.services_to_buckets[self.models_to_services[model.model]]

    def update_from_key_lookup(self, key_lookup: "KeyLookup") -> None:
        """Updates the bucket collection rates based on model RPM/TPM from KeyLookup"""

        for model_name, service in self.models_to_services.items():
            if service in key_lookup and not self.infinity_buckets:

                if key_lookup[service].rpm is not None:
                    new_rps = key_lookup[service].rpm / 60.0
                    new_requests_bucket = TokenBucket(
                        bucket_name=service,
                        bucket_type="requests",
                        capacity=new_rps,
                        refill_rate=new_rps,
                        remote_url=self.remote_url,
                    )
                    self.services_to_buckets[service].requests_bucket = (
                        new_requests_bucket
                    )

                if key_lookup[service].tpm is not None:
                    new_tps = key_lookup[service].tpm / 60.0
                    new_tokens_bucket = TokenBucket(
                        bucket_name=service,
                        bucket_type="tokens",
                        capacity=new_tps,
                        refill_rate=new_tps,
                        remote_url=self.remote_url,
                    )
                    self.services_to_buckets[service].tokens_bucket = new_tokens_bucket

    def visualize(self) -> dict:
        """Visualize the token and request buckets for each model."""
        plots = {}
        for model in self:
            plots[model] = self[model].visualize()
        return plots
