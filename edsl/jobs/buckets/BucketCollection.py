from collections import UserDict
from edsl.jobs.buckets.TokenBucket import TokenBucket
from edsl.jobs.buckets.ModelBuckets import ModelBuckets


class BucketCollection(UserDict):
    """A Jobs object will have a whole collection of model buckets, as multiple models could be used.

    The keys here are the models, and the values are the ModelBuckets objects.
    Models themselves are hashable, so this works.
    """

    def __init__(self, infinity_buckets=False):
        super().__init__()
        self.infinity_buckets = infinity_buckets
        self.models_to_services = {}
        self.services_to_buckets = {}

    def __repr__(self):
        return f"BucketCollection({self.data})"

    def add_model(self, model: "LanguageModel") -> None:
        """Adds a model to the bucket collection.

        This will create the token and request buckets for the model."""

        # compute the TPS and RPS from the model
        if not self.infinity_buckets:
            TPS = model.TPM / 60.0
            RPS = model.RPM / 60.0
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
