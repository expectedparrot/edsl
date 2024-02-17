from __future__ import annotations

from collections import UserDict

from abc import ABC, ABCMeta, abstractmethod
from edsl.jobs import Jobs
from edsl.results import Results
from edsl.jobs.TokenBucket import TokenBucket

class RegisterJobsRunnerMeta(ABCMeta):
    "Metaclass to register output elements in a registry i.e., those that have a parent"
    _registry = {}  # Initialize the registry as a dictionary

    def __init__(cls, name, bases, dct):
        super(RegisterJobsRunnerMeta, cls).__init__(name, bases, dct)
        if name != "JobsRunner":
            RegisterJobsRunnerMeta._registry[name] = cls

    @classmethod
    def get_registered_classes(cls):
        return cls._registry

    @classmethod
    def lookup(cls):
        d = {}
        for classname, cls in cls._registry.items():
            if hasattr(cls, "runner_name"):
                d[cls.runner_name] = cls
            else:
                raise Exception(
                    f"Class {classname} does not have a runner_name attribute"
                )
        return d


class ModelBuckets:
    def __init__(self, requests_bucket: TokenBucket, tokens_bucket: TokenBucket):
        self.requests_bucket = requests_bucket
        self.tokens_bucket = tokens_bucket

    def __add__(self, other):
        return ModelBuckets(requests_bucket = self.requests_bucket + other.requests_bucket,
                            tokens_bucket = self.tokens_bucket + other.tokens_bucket
        )  

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

class JobsRunner(ABC, metaclass=RegisterJobsRunnerMeta):
    """ABC for JobRunners, which take in a job, conduct interviews, and return their results."""

    def __init__(self, jobs: Jobs):
        self.jobs = jobs
        # create the interviews here so children can use them
        self.interviews = jobs.interviews()
        self.bucket_collection = BucketCollection()

        for model in self.jobs.models:
            self.bucket_collection.add_model(model)        

    @abstractmethod
    def run(
        self,
        n: int = 1,
        debug: bool = False,
        verbose: bool = False,
        progress_bar: bool = True,
    ) -> Results:  # pragma: no cover
        """
        Runs the job: conducts Interviews and returns their results.
        - `n`: how many times to run each interview
        - `debug`: prints debug messages
        - `verbose`: prints messages
        - `progress_bar`: shows a progress bar
        """
        raise NotImplementedError
