from typing import Optional, Literal
from dataclasses import dataclass, asdict

# from edsl.data_transfer_models import VisibilityType
from ..data import Cache
from ..buckets import BucketCollection
from ..key_management import KeyLookup

from .runners.JobsRunnerStatus import JobsRunnerStatus

VisibilityType = Literal["private", "public", "unlisted"]
from edsl.base import Base

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
    background: bool = False
    disable_remote_cache: bool = False
    disable_remote_inference: bool = False
    job_uuid: Optional[str] = None
    fresh: Optional[
        bool
    ] = False  # if True, will not use cache and will save new results to cache

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


"""This module contains the Answers class, which is a helper class to hold the answers to a survey."""

from collections import UserDict
from edsl.data_transfer_models import EDSLResultObjectInput


class Answers(UserDict):
    """Helper class to hold the answers to a survey."""

    def add_answer(
        self, response: EDSLResultObjectInput, question: "QuestionBase"
    ) -> None:
        """Add a response to the answers dictionary."""
        answer = response.answer
        comment = response.comment
        generated_tokens = response.generated_tokens
        # record the answer
        if generated_tokens:
            self[question.question_name + "_generated_tokens"] = generated_tokens
        self[question.question_name] = answer
        if comment:
            self[question.question_name + "_comment"] = comment

    def replace_missing_answers_with_none(self, survey: "Survey") -> None:
        """Replace missing answers with None. Answers can be missing if the agent skips a question."""
        for question_name in survey.question_names:
            if question_name not in self:
                self[question_name] = None

    def to_dict(self):
        """Return a dictionary of the answers."""
        return self.data

    @classmethod
    def from_dict(cls, d):
        """Return an Answers object from a dictionary."""
        return cls(d)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
