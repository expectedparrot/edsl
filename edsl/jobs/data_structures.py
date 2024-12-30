from typing import Optional, Literal
from dataclasses import dataclass, asdict

# from edsl.data_transfer_models import VisibilityType
from edsl.data.Cache import Cache
from edsl.jobs.buckets.BucketCollection import BucketCollection
from edsl.language_models.key_management.KeyLookup import KeyLookup
from edsl.jobs.runners.JobsRunnerStatus import JobsRunnerStatus

VisibilityType = Literal["private", "public", "unlisted"]
from edsl.Base import Base


@dataclass
class RunEnvironment:
    cache: Optional[Cache] = None
    bucket_collection: Optional[BucketCollection] = None
    key_lookup: Optional[KeyLookup] = None
    jobs_runner_status: Optional["JobsRunnerStatus"] = None


@dataclass
class RunParameters(Base):
    n: int = 1
    progress_bar: bool = False
    stop_on_exception: bool = False
    check_api_keys: bool = False
    verbose: bool = True
    print_exceptions: bool = True
    remote_cache_description: Optional[str] = None
    remote_inference_description: Optional[str] = None
    remote_inference_results_visibility: Optional[VisibilityType] = "unlisted"
    skip_retry: bool = False
    raise_validation_errors: bool = False
    disable_remote_cache: bool = False
    disable_remote_inference: bool = False
    job_uuid: Optional[str] = None

    def to_dict(self, add_edsl_version=False) -> dict:
        d = asdict(self)
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "RunConfig"
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "RunConfig":
        return cls(**data)

    def code(self):
        return f"RunConfig(**{self.to_dict()})"

    @classmethod
    def example(cls) -> "RunConfig":
        return cls()


@dataclass
class RunConfig:
    environment: RunEnvironment
    parameters: RunParameters

    def add_environment(self, environment: RunEnvironment):
        self.environment = environment

    def add_bucket_collection(self, bucket_collection: BucketCollection):
        self.environment.bucket_collection = bucket_collection

    def add_cache(self, cache: Cache):
        self.environment.cache = cache

    def add_key_lookup(self, key_lookup: KeyLookup):
        self.environment.key_lookup = key_lookup
