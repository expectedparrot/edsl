from edsl.jobs.TokenBucket import TokenBucket
from collections import UserDict

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
        requests_bucket = TokenBucket(capacity=2 * RPS, refill_rate=RPS)
        tokens_bucket = TokenBucket(capacity=2 * TPS, refill_rate=TPS)
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

    
