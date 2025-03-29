from typing import Optional, Literal, TYPE_CHECKING
from dataclasses import dataclass, asdict
from collections import UserDict
from ..data_transfer_models import EDSLResultObjectInput

# from edsl.data_transfer_models import VisibilityType
from ..caching import Cache
from ..buckets import BucketCollection
from ..key_management import KeyLookup
from ..base import Base

from .jobs_runner_status import JobsRunnerStatus

if TYPE_CHECKING:
    from ..questions.question_base import QuestionBase
    from ..surveys import Survey

VisibilityType = Literal["private", "public", "unlisted"]

@dataclass
class RunEnvironment:
    """
    Contains environment-related resources for job execution.
    
    This dataclass holds references to shared resources and infrastructure components 
    needed for job execution. These components are typically long-lived and may be 
    shared across multiple job runs.
    
    Attributes:
        cache (Cache, optional): Cache for storing and retrieving interview results
        bucket_collection (BucketCollection, optional): Collection of token rate limit buckets
        key_lookup (KeyLookup, optional): Manager for API keys across models
        jobs_runner_status (JobsRunnerStatus, optional): Tracker for job execution progress
    """
    cache: Optional[Cache] = None
    bucket_collection: Optional[BucketCollection] = None
    key_lookup: Optional[KeyLookup] = None
    jobs_runner_status: Optional["JobsRunnerStatus"] = None


@dataclass
class RunParameters(Base):
    """
    Contains execution-specific parameters for job runs.
    
    This dataclass holds parameters that control the behavior of a specific job run,
    such as iteration count, error handling preferences, and remote execution options.
    Unlike RunEnvironment, these parameters are specific to a single job execution.
    
    Attributes:
        n (int): Number of iterations to run each interview, default is 1
        progress_bar (bool): Whether to show a progress bar, default is False
        stop_on_exception (bool): Whether to stop if an exception occurs, default is False
        check_api_keys (bool): Whether to validate API keys before running, default is False
        verbose (bool): Whether to print detailed execution information, default is True
        print_exceptions (bool): Whether to print exceptions as they occur, default is True
        remote_cache_description (str, optional): Description for entries in the remote cache
        remote_inference_description (str, optional): Description for the remote inference job
        remote_inference_results_visibility (VisibilityType): Visibility setting for results
            on Coop: "private", "public", or "unlisted" (default is "unlisted")
        skip_retry (bool): Whether to skip retry attempts for failed interviews, default is False
        raise_validation_errors (bool): Whether to raise validation errors, default is False
        background (bool): Whether to run in background mode, default is False
        disable_remote_cache (bool): Whether to disable remote cache usage, default is False
        disable_remote_inference (bool): Whether to disable remote inference, default is False
        job_uuid (str, optional): UUID for the job, used for tracking
        fresh (bool): If True, ignore cache and generate new results, default is False
    """
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
    fresh: bool = False  # if True, will not use cache and will save new results to cache

    def to_dict(self, add_edsl_version=False) -> dict:
        d = asdict(self)
        if add_edsl_version:
            from .. import __version__

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
    """
    Combines environment resources and execution parameters for a job run.
    
    This class brings together the two aspects of job configuration:
    1. Environment resources (caches, API keys, etc.) via RunEnvironment
    2. Execution parameters (iterations, error handling, etc.) via RunParameters
    
    It provides helper methods for modifying environment components after construction.
    
    Attributes:
        environment (RunEnvironment): The environment resources for the job
        parameters (RunParameters): The execution parameters for the job
    """
    environment: RunEnvironment
    parameters: RunParameters

    def add_environment(self, environment: RunEnvironment) -> None:
        """
        Replace the entire environment configuration.
        
        Parameters:
            environment (RunEnvironment): The new environment configuration
        """
        self.environment = environment

    def add_bucket_collection(self, bucket_collection: BucketCollection) -> None:
        """
        Set or replace the bucket collection in the environment.
        
        Parameters:
            bucket_collection (BucketCollection): The bucket collection to use
        """
        self.environment.bucket_collection = bucket_collection

    def add_cache(self, cache: Cache) -> None:
        """
        Set or replace the cache in the environment.
        
        Parameters:
            cache (Cache): The cache to use
        """
        self.environment.cache = cache

    def add_key_lookup(self, key_lookup: KeyLookup) -> None:
        """
        Set or replace the key lookup in the environment.
        
        Parameters:
            key_lookup (KeyLookup): The key lookup to use
        """
        self.environment.key_lookup = key_lookup


"""
Additional data structures for working with job results and answers.
"""


class Answers(UserDict):
    """
    A specialized dictionary for holding interview response data.
    
    This class extends UserDict to provide a flexible container for survey answers,
    with special handling for response metadata like comments and token usage.
    
    Key features:
    - Stores answers by question name
    - Associates comments with their respective questions
    - Tracks token usage for generation
    - Handles missing answers automatically
    """

    def add_answer(
        self, response: EDSLResultObjectInput, question: "QuestionBase"
    ) -> None:
        """
        Add a response to the answers dictionary.
        
        This method processes a response and stores it in the dictionary with appropriate
        naming conventions for the answer itself, comments, and token usage tracking.
        
        Parameters:
            response (EDSLResultObjectInput): The response object containing answer data
            question (QuestionBase): The question that was answered
            
        Notes:
            - The main answer is stored with the question's name as the key
            - Comments are stored with "_comment" appended to the question name
            - Token usage is stored with "_generated_tokens" appended
        """
        answer = response.answer
        comment = response.comment
        generated_tokens = response.generated_tokens
        
        # Record token usage if available
        if generated_tokens:
            self[question.question_name + "_generated_tokens"] = generated_tokens
            
        # Record the primary answer
        self[question.question_name] = answer
        
        # Record comment if present
        if comment:
            self[question.question_name + "_comment"] = comment

    def replace_missing_answers_with_none(self, survey: "Survey") -> None:
        """
        Replace missing answers with None for all questions in the survey.
        
        This method ensures that all questions in the survey have an entry in the
        answers dictionary, even if they were skipped during the interview.
        
        Parameters:
            survey (Survey): The survey containing the questions to check
            
        Notes:
            - Answers can be missing if the agent skips a question due to skip logic
            - This ensures consistent data structure even with partial responses
        """
        for question_name in survey.question_names:
            if question_name not in self:
                self[question_name] = None

    def to_dict(self) -> dict:
        """
        Convert the answers to a standard dictionary.
        
        Returns:
            dict: A plain dictionary containing all the answers data
        """
        return self.data

    @classmethod
    def from_dict(cls, d: dict) -> "Answers":
        """
        Create an Answers object from a dictionary.
        
        Parameters:
            d (dict): The dictionary containing answer data
            
        Returns:
            Answers: A new Answers instance with the provided data
        """
        return cls(d)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
