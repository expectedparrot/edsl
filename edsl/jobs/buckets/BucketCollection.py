from collections import UserDict
from edsl.jobs.buckets.TokenBucket import TokenBucket
from edsl.jobs.buckets.ModelBuckets import ModelBuckets


class BucketCollection(UserDict):
    """A Jobs object will have a whole collection of model buckets, as multiple models could be used.

    The keys here are the models, and the values are the ModelBuckets objects.
    Models themselves are hashable, so this works.
    """

    def __init__(self):
        super().__init__()

    def __repr__(self):
        return f"BucketCollection({self.data})"

    def add_model(self, model: "LanguageModel") -> None:
        """Adds a model to the bucket collection.

        This will create the token and request buckets for the model."""
        # compute the TPS and RPS from the model
        TPS = model.TPM / 60.0
        RPS = model.RPM / 60.0
        # create the buckets
        requests_bucket = TokenBucket(
            bucket_name=model.model,
            bucket_type="requests",
            capacity=RPS,
            refill_rate=RPS,
        )
        tokens_bucket = TokenBucket(
            bucket_name=model.model, bucket_type="tokens", capacity=TPS, refill_rate=TPS
        )
        model_buckets = ModelBuckets(requests_bucket, tokens_bucket)
        if model in self:
            # it if already exists, combine the buckets
            self[model] += model_buckets
        else:
            self[model] = model_buckets

    def visualize(self) -> dict:
        """Visualize the token and request buckets for each model."""
        plots = {}
        for model in self:
            plots[model] = self[model].visualize()
        return plots
