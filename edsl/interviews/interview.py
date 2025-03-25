"""Interview implementation for asynchronously running agents through surveys.

This module provides the Interview class, which manages the process of an agent answering
a survey with a specific language model and scenario. It handles the complete workflow including:

1. Determining which questions to ask based on survey skip logic
2. Managing memory to control what previous answers are available for each question
3. Tracking token usage and ensuring rate limits are respected
4. Handling exceptions and retry logic
5. Managing the asynchronous execution of question answering tasks

The Interview class serves as the execution layer between high-level Jobs objects and 
the individual API calls to language models, with support for caching and distributed execution.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generator, List, Optional, Type

if TYPE_CHECKING:
    from ..jobs.data_structures import RunConfig
    from .interview_status_log import InterviewStatusLog

# from jobs module
from ..buckets import ModelBuckets
from ..jobs.data_structures import Answers
from ..jobs.fetch_invigilator import FetchInvigilator
from ..surveys import Survey
from ..utilities.utilities import dict_hash

# from interviews module
from .answering_function import AnswerQuestionFunctionConstructor
from .exception_tracking import InterviewExceptionCollection, InterviewExceptionEntry
from .interview_status_dictionary import InterviewStatusDictionary
from .interview_task_manager import InterviewTaskManager
from .request_token_estimator import RequestTokenEstimator

if TYPE_CHECKING:
    from ..agents import Agent
    from ..caching import Cache
    from ..invigilators import InvigilatorBase
    from ..language_models import LanguageModel
    from ..scenarios import Scenario
    from ..surveys import Survey
    from ..tokens import InterviewTokenUsage


@dataclass
class InterviewRunningConfig:
    """Configuration parameters for interview execution.
    
    This dataclass contains settings that control how an interview is conducted,
    including error handling, caching behavior, and validation options.
    
    Attributes:
        cache: Optional cache for storing and retrieving model responses
        skip_retry: Whether to skip retrying failed questions (default: False)
        raise_validation_errors: Whether to raise exceptions for validation errors (default: True)
        stop_on_exception: Whether to stop the entire interview when an exception occurs (default: False)
    """

    cache: Optional["Cache"] = (None,)
    skip_retry: bool = (False,)
    raise_validation_errors: bool = (True,)
    stop_on_exception: bool = (False,)


class Interview:
    """Manages the process of an agent answering a survey asynchronously.
    
    An Interview represents a single execution unit - one agent answering one survey with one
    language model and one scenario. It handles the complete workflow of navigating through
    the survey based on skip logic, creating tasks for each question, tracking execution status,
    and collecting results.
    
    The core functionality is implemented in the `async_conduct_interview` method, which
    orchestrates the asynchronous execution of all question-answering tasks while respecting
    dependencies and rate limits. The class maintains detailed state about the interview progress,
    including answers collected so far, task statuses, token usage, and any exceptions encountered.
    
    Key components:
    - Task management: Creating and scheduling tasks for each question
    - Memory management: Controlling what previous answers are visible for each question
    - Exception handling: Tracking and potentially retrying failed questions
    - Status tracking: Monitoring the state of each task and the overall interview
    - Token tracking: Measuring and limiting API token usage
    
    This class serves as the execution layer that translates a high-level survey definition
    into concrete API calls to language models, with support for caching and fault tolerance.
    """

    def __init__(
        self,
        agent: Agent,
        survey: Survey,
        scenario: Scenario,
        model: Type["LanguageModel"],
        iteration: int = 0,
        indices: dict = None,
        cache: Optional["Cache"] = None,
        skip_retry: bool = False,
        raise_validation_errors: bool = True,
    ):
        """Initialize a new Interview instance.

        Args:
            agent: The agent that will answer the survey questions
            survey: The survey containing questions to be answered
            scenario: The scenario providing context for the questions
            model: The language model used to generate agent responses
            iteration: The iteration number of this interview (for batch processing)
            indices: Optional dictionary mapping question names to custom indices
            cache: Optional cache for storing and retrieving model responses
            skip_retry: Whether to skip retrying failed questions
            raise_validation_errors: Whether to raise exceptions for validation errors
            
        The initialization process sets up the interview state including:
        1. Creating the task manager for handling question execution
        2. Initializing empty containers for answers and exceptions
        3. Setting up configuration and tracking structures
        4. Computing question indices for quick lookups
        
        Examples:
            >>> i = Interview.example()
            >>> i.task_manager.task_creators
            {}

            >>> i.exceptions
            {}

            >>> _ = asyncio.run(i.async_conduct_interview())
            >>> i.task_status_logs['q0']
            [{'log_time': ..., 'value': <TaskStatus.NOT_STARTED: 1>}, {'log_time': ..., 'value': <TaskStatus.WAITING_FOR_DEPENDENCIES: 2>}, {'log_time': ..., 'value': <TaskStatus.API_CALL_IN_PROGRESS: 7>}, {'log_time': ..., 'value': <TaskStatus.SUCCESS: 8>}]

            >>> i.to_index
            {'q0': 0, 'q1': 1, 'q2': 2}
        """
        self.agent = agent
        self.survey = copy.deepcopy(survey)  # why do we need to deepcopy the survey?
        self.scenario = scenario
        self.model = model
        self.iteration = iteration

        self.answers = Answers()  # will get filled in as interview progresses

        self.task_manager = InterviewTaskManager(
            survey=self.survey,
            iteration=iteration,
        )

        self.exceptions = InterviewExceptionCollection()

        self.running_config = InterviewRunningConfig(
            cache=cache,
            skip_retry=skip_retry,
            raise_validation_errors=raise_validation_errors,
        )

        # dictionary mapping question names to their index in the survey.
        self.to_index = {
            question_name: index
            for index, question_name in enumerate(self.survey.question_names)
        }

        self.failed_questions = []

        self.indices = indices
        self.initial_hash = hash(self)

    @property
    def cache(self) -> "Cache":
        """Get the cache used for storing and retrieving model responses.
        
        Returns:
            Cache: The cache object associated with this interview
        """
        return self.running_config.cache

    @cache.setter
    def cache(self, value: "Cache") -> None:
        """Set the cache used for storing and retrieving model responses.
        
        Args:
            value: The cache object to use
        """
        self.running_config.cache = value

    @property
    def skip_retry(self) -> bool:
        """Get whether the interview should skip retrying failed questions.
        
        Returns:
            bool: True if failed questions should not be retried
        """
        return self.running_config.skip_retry

    @property
    def raise_validation_errors(self) -> bool:
        """Get whether validation errors should raise exceptions.
        
        Returns:
            bool: True if validation errors should raise exceptions
        """
        return self.running_config.raise_validation_errors

    @property
    def has_exceptions(self) -> bool:
        """Check if any exceptions have occurred during the interview.
        
        Returns:
            bool: True if any exceptions have been recorded
        """
        return len(self.exceptions) > 0

    @property
    def task_status_logs(self) -> 'InterviewStatusLog':
        """Get the complete status history for all tasks in the interview.
        
        This property provides access to the status logs for all questions,
        showing how each task progressed through various states during execution.
        
        Returns:
            InterviewStatusLog: Dictionary mapping question names to their status log histories
        """
        return self.task_manager.task_status_logs

    @property
    def token_usage(self) -> "InterviewTokenUsage":
        """Get the token usage statistics for the entire interview.
        
        This tracks how many tokens were used for prompts and completions
        across all questions in the interview.
        
        Returns:
            InterviewTokenUsage: Token usage statistics for the interview
        """
        return self.task_manager.token_usage

    @property
    def interview_status(self) -> InterviewStatusDictionary:
        """Get the current status summary for all tasks in the interview.
        
        This provides a count of tasks in each status category (not started,
        in progress, completed, failed, etc.).
        
        Returns:
            InterviewStatusDictionary: Dictionary mapping status codes to counts
        """
        return self.task_manager.interview_status

    def to_dict(self, include_exceptions=True, add_edsl_version=True) -> dict[str, Any]:
        """Serialize the interview to a dictionary representation.
        
        This method creates a dictionary containing all the essential components
        of the interview, which can be used for hashing, serialization, and
        creating duplicate interviews.
        
        Args:
            include_exceptions: Whether to include exception information (default: True)
            add_edsl_version: Whether to include EDSL version in component dicts (default: True)
            
        Returns:
            dict: Dictionary representation of the interview
            
        Examples:
            >>> i = Interview.example()
            >>> hash(i)
            1670837906923478736
        """
        # Create the base dictionary with core components
        d = {
            "agent": self.agent.to_dict(add_edsl_version=add_edsl_version),
            "survey": self.survey.to_dict(add_edsl_version=add_edsl_version),
            "scenario": self.scenario.to_dict(add_edsl_version=add_edsl_version),
            "model": self.model.to_dict(add_edsl_version=add_edsl_version),
            "iteration": self.iteration,
            "exceptions": {},
        }

        # Optionally include exceptions
        if include_exceptions:
            d["exceptions"] = self.exceptions.to_dict()

        # Include custom indices if present
        if hasattr(self, "indices"):
            d["indices"] = self.indices

        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Interview":
        """Create an Interview instance from a dictionary representation.
        
        This class method deserializes an interview from a dictionary created by
        the to_dict method, recreating all components including agent, survey,
        scenario, model, and any exceptions.
        
        Args:
            d: Dictionary representation of an interview
            
        Returns:
            Interview: A reconstructed Interview instance
        """
        # Import necessary classes
        from ..agents import Agent
        from ..language_models import LanguageModel
        from ..scenarios import Scenario
        from ..surveys import Survey

        # Deserialize each component
        agent = Agent.from_dict(d["agent"])
        survey = Survey.from_dict(d["survey"])
        scenario = Scenario.from_dict(d["scenario"])
        model = LanguageModel.from_dict(d["model"])
        iteration = d["iteration"]

        # Prepare constructor parameters
        params = {
            "agent": agent,
            "survey": survey,
            "scenario": scenario,
            "model": model,
            "iteration": iteration,
        }

        # Add optional indices if present
        if "indices" in d:
            params["indices"] = d["indices"]

        # Create the interview instance
        interview = cls(**params)

        # Restore exceptions if present
        if "exceptions" in d:
            exceptions = InterviewExceptionCollection.from_dict(d["exceptions"])
            interview.exceptions = exceptions

        return interview

    def __hash__(self) -> int:
        """Generate a hash value for the interview.
        
        This hash is based on the essential components of the interview
        (agent, survey, scenario, model, and iteration) but excludes mutable
        state like exceptions to ensure consistent hashing.
        
        Returns:
            int: A hash value that uniquely identifies this interview configuration
        """
        return dict_hash(self.to_dict(include_exceptions=False, add_edsl_version=False))

    def __eq__(self, other: "Interview") -> bool:
        """Check if two interviews are equivalent.
        
        Two interviews are considered equal if they have the same agent, survey,
        scenario, model, and iteration number.
        
        Args:
            other: Another interview to compare with
            
        Returns:
            bool: True if the interviews are equivalent, False otherwise
            
        Examples:
            >>> from . import Interview
            >>> i = Interview.example()
            >>> d = i.to_dict()
            >>> i2 = Interview.from_dict(d)
            >>> i == i2
            True
        """
        return hash(self) == hash(other)

    async def async_conduct_interview(
        self,
        run_config: Optional["RunConfig"] = None,
    ) -> tuple["Answers", List[dict[str, Any]]]:
        """Execute the interview process asynchronously.
        
        This is the core method that conducts the entire interview, creating tasks
        for each question, managing dependencies between them, handling rate limits,
        and collecting results. It orchestrates the asynchronous execution of all
        question-answering tasks in the correct order based on survey rules.
        
        Args:
            run_config: Optional configuration for the interview execution,
                including parameters like stop_on_exception and environment
                settings like bucket_collection and key_lookup
                
        Returns:
            tuple: A tuple containing:
                - Answers: Dictionary of all question answers
                - List[dict]: List of valid results with detailed information
                
        Examples:
            Basic usage:
            
            >>> i = Interview.example()
            >>> result, _ = asyncio.run(i.async_conduct_interview())
            >>> result['q0']
            'yes'
            
            Handling exceptions:
            
            >>> i = Interview.example(throw_exception=True)
            >>> result, _ = asyncio.run(i.async_conduct_interview())
            >>> i.exceptions
            {'q0': ...
            
            Using custom configuration:
            
            >>> i = Interview.example()
            >>> from edsl.jobs import RunConfig, RunParameters, RunEnvironment
            >>> run_config = RunConfig(parameters=RunParameters(), environment=RunEnvironment())
            >>> run_config.parameters.stop_on_exception = True
            >>> result, _ = asyncio.run(i.async_conduct_interview(run_config))
        """
        from ..jobs import RunConfig, RunEnvironment, RunParameters

        if run_config is None:
            run_config = RunConfig(
                parameters=RunParameters(),
                environment=RunEnvironment(),
            )
        self.stop_on_exception = run_config.parameters.stop_on_exception

        # if no model bucket is passed, create an 'infinity' bucket with no rate limits
        bucket_collection = run_config.environment.bucket_collection

        if bucket_collection:
            model_buckets = bucket_collection.get(self.model)
        else:
            model_buckets = None

        if model_buckets is None or hasattr(self.agent, "answer_question_directly"):
            model_buckets = ModelBuckets.infinity_bucket()

        self.skip_flags = {q.question_name: False for q in self.survey.questions}

        self.tasks = self.task_manager.build_question_tasks(
            answer_func=AnswerQuestionFunctionConstructor(
                self, key_lookup=run_config.environment.key_lookup
            )(),
            token_estimator=RequestTokenEstimator(self),
            model_buckets=model_buckets,
        )

        ## This is the key part---it creates a task for each question,
        ## with dependencies on the questions that must be answered before this one can be answered.

        ## 'Invigilators' are used to administer the survey.
        fetcher = FetchInvigilator(
            interview=self,
            current_answers=self.answers,
            key_lookup=run_config.environment.key_lookup,
        )
        self.invigilators = [fetcher(question) for question in self.survey.questions]
        await asyncio.gather(
            *self.tasks, return_exceptions=not run_config.parameters.stop_on_exception
        )
        self.answers.replace_missing_answers_with_none(self.survey)
        valid_results = list(
            self._extract_valid_results(self.tasks, self.invigilators, self.exceptions)
        )
        return self.answers, valid_results

    @staticmethod
    def _extract_valid_results(
        tasks: List["asyncio.Task"],
        invigilators: List["InvigilatorBase"],
        exceptions: InterviewExceptionCollection,
    ) -> Generator["Answers", None, None]:
        """Extract valid results from completed tasks and handle exceptions.
        
        This method processes the completed asyncio tasks, extracting successful
        results and handling any exceptions that occurred. It maintains the
        relationship between tasks, invigilators, and the questions they represent.
        
        Args:
            tasks: List of asyncio tasks for each question
            invigilators: List of invigilators corresponding to each task
            exceptions: Collection for storing any exceptions that occurred
            
        Yields:
            Answers: Valid results from each successfully completed task
            
        Notes:
            - Tasks and invigilators must have the same length and be in the same order
            - Cancelled tasks are expected and don't trigger exception recording
            - Other exceptions are recorded in the exceptions collection
            
        Examples:
            >>> i = Interview.example()
            >>> result, _ = asyncio.run(i.async_conduct_interview())
        """
        assert len(tasks) == len(invigilators)

        def handle_task(task, invigilator):
            try:
                result: Answers = task.result()
                if result == "skipped":
                    result = invigilator.get_failed_task_result(
                        failure_reason="Task was skipped."
                    )
            except asyncio.CancelledError:  # task was cancelled
                result = invigilator.get_failed_task_result(
                    failure_reason="Task was cancelled."
                )
            except Exception as e:  # any other kind of exception in the task
                result = invigilator.get_failed_task_result(
                    failure_reason=f"Task failed with exception: {str(e)}."
                )
                exception_entry = InterviewExceptionEntry(
                    exception=e,
                    invigilator=invigilator,
                )
                exceptions.add(task.get_name(), exception_entry)
            return result

        for task, invigilator in zip(tasks, invigilators):
            if not task.done():
                from edsl.interviews.exceptions import InterviewTaskError
                raise InterviewTaskError(f"Task {task.get_name()} is not done.")

            yield handle_task(task, invigilator)

    def __repr__(self) -> str:
        """Generate a string representation of the interview.
        
        This representation includes the key components of the interview
        (agent, survey, scenario, and model) for debugging and display purposes.
        
        Returns:
            str: A string representation of the interview instance
        """
        return f"Interview(agent = {repr(self.agent)}, survey = {repr(self.survey)}, scenario = {repr(self.scenario)}, model = {repr(self.model)})"

    def duplicate(
        self, iteration: int, cache: "Cache", randomize_survey: Optional[bool] = True
    ) -> "Interview":
        """Create a duplicate of this interview with a new iteration number and cache.
        
        This method creates a new Interview instance with the same components but
        a different iteration number. It can optionally randomize the survey questions
        (for surveys that support randomization) and use a different cache.
        
        Args:
            iteration: The new iteration number for the duplicated interview
            cache: The cache to use for the new interview (can be None)
            randomize_survey: Whether to randomize the survey questions (default: True)
            
        Returns:
            Interview: A new interview instance with updated iteration and cache
            
        Examples:
            >>> i = Interview.example()
            >>> i2 = i.duplicate(1, None)
            >>> i.iteration + 1 == i2.iteration
            True
        """
        # Get a randomized copy of the survey if requested
        if randomize_survey:
            new_survey = self.survey.draw()
        else:
            new_survey = self.survey

        # Create a new interview with the same components but different iteration
        return Interview(
            agent=self.agent,
            survey=new_survey,
            scenario=self.scenario,
            model=self.model,
            iteration=iteration,
            cache=self.running_config.cache,
            skip_retry=self.running_config.skip_retry,
            indices=self.indices,
        )

    @classmethod
    def example(self, throw_exception: bool = False) -> "Interview":
        """Create an example Interview instance for testing and demonstrations.
        
        This method provides a convenient way to create a fully configured
        Interview instance with default components. It can be configured to
        either work normally or deliberately throw exceptions for testing
        error handling scenarios.
        
        Args:
            throw_exception: If True, creates an interview that will throw
                exceptions when run (useful for testing error handling)
                
        Returns:
            Interview: A fully configured example interview instance
            
        Examples:
            Creating a normal interview:
            
            >>> i = Interview.example()
            >>> result, _ = asyncio.run(i.async_conduct_interview())
            >>> result['q0']
            'yes'
            
            Creating an interview that will throw exceptions:
            
            >>> i = Interview.example(throw_exception=True)
            >>> result, _ = asyncio.run(i.async_conduct_interview())
            >>> i.has_exceptions
            True
        """
        from ..agents import Agent
        from ..language_models import LanguageModel
        from ..scenarios import Scenario
        from ..surveys import Survey

        # Define a simple direct answering method that always returns "yes"
        def f(self, question, scenario):
            return "yes"

        # Create standard components
        agent = Agent.example()
        agent.add_direct_question_answering_method(f)
        survey = Survey.example()
        scenario = Scenario.example()
        model = LanguageModel.example()

        # If we want an interview that throws exceptions, configure it accordingly
        if throw_exception:
            model = LanguageModel.example(test_model=True, throw_exception=True)
            agent = Agent.example()  # Without direct answering method

        # Create and return the interview
        return Interview(agent=agent, survey=survey, scenario=scenario, model=model)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
