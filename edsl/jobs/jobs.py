"""
The Jobs module is the core orchestration component of the EDSL framework.

It provides functionality to define, configure, and execute computational jobs that 
involve multiple agents, scenarios, models, and a survey. Jobs are the primary way 
that users run large-scale experiments or simulations in EDSL.

The Jobs class handles:
1. Organizing all components (agents, scenarios, models, survey)
2. Configuring execution parameters
3. Managing resources like caches and API keys
4. Running interviews in parallel
5. Collecting and structuring results

This module is designed to be used by both application developers and researchers
who need to run complex simulations with language models.
"""
from __future__ import annotations
import asyncio
from typing import Optional, Union, TypeVar, Callable, cast
from functools import wraps

from typing import (
    Literal,
    Sequence,
    Generator,
    TYPE_CHECKING,
)

from ..base import Base
from ..utilities import remove_edsl_version
from ..coop import CoopServerResponseError

from ..buckets import BucketCollection
from ..scenarios import Scenario, ScenarioList
from ..surveys import Survey
from ..interviews import Interview
from .exceptions import JobsValueError, JobsImplementationError

from .jobs_pricing_estimation import JobsPrompts
from .remote_inference import JobsRemoteInferenceHandler
from .jobs_checks import JobsChecks
from .data_structures import RunEnvironment, RunParameters, RunConfig
from .check_survey_scenario_compatibility import CheckSurveyScenarioCompatibility


if TYPE_CHECKING:
    from ..agents import Agent
    from ..agents import AgentList
    from ..language_models import LanguageModel
    from ..scenarios import Scenario, ScenarioList
    from ..surveys import Survey
    from ..results import Results
    from ..dataset import Dataset
    from ..language_models import ModelList
    from ..caching import Cache
    from ..key_management import KeyLookup

VisibilityType = Literal["private", "public", "unlisted"]


try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec


P = ParamSpec("P")
T = TypeVar("T")


def with_config(f: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator that processes function parameters to match the RunConfig dataclass structure.

    This decorator is used primarily with the run() and run_async() methods to provide
    a consistent interface for job configuration while maintaining a clean API.

    The decorator:
    1. Extracts environment-related parameters into a RunEnvironment instance
    2. Extracts execution-related parameters into a RunParameters instance
    3. Combines both into a single RunConfig object
    4. Passes this RunConfig to the decorated function as a keyword argument

    Parameters:
        f (Callable): The function to decorate, typically run() or run_async()

    Returns:
        Callable: A wrapped function that accepts all RunConfig parameters directly

    Example:
        @with_config
        def run(self, *, config: RunConfig) -> Results:
            # Function can now access config.parameters and config.environment
    """
    parameter_fields = {
        name: field.default
        for name, field in RunParameters.__dataclass_fields__.items()
    }
    environment_fields = {
        name: field.default
        for name, field in RunEnvironment.__dataclass_fields__.items()
    }
    # Combined fields dict used for reference during development
    # combined = {**parameter_fields, **environment_fields}

    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        environment = RunEnvironment(
            **{k: v for k, v in kwargs.items() if k in environment_fields}
        )
        parameters = RunParameters(
            **{k: v for k, v in kwargs.items() if k in parameter_fields}
        )
        config = RunConfig(environment=environment, parameters=parameters)
        return f(*args, config=config)

    return cast(Callable[P, T], wrapper)


class Jobs(Base):
    """
    A collection of agents, scenarios, models, and a survey that orchestrates interviews.

    The Jobs class is the central component for running large-scale experiments or simulations
    in EDSL. It manages the execution of interviews where agents interact with surveys through
    language models, possibly in different scenarios.

    Key responsibilities:
    1. Managing collections of agents, scenarios, and models
    2. Configuring execution parameters (caching, API keys, etc.)
    3. Managing parallel execution of interviews
    4. Handling remote cache and inference capabilities
    5. Collecting and organizing results

    A typical workflow involves:
    1. Creating a survey with questions
    2. Creating a Jobs instance with that survey
    3. Adding agents, scenarios, and models using the `by()` method
    4. Running the job with `run()` or `run_async()`
    5. Analyzing the results

    Jobs implements a fluent interface pattern, where methods return self to allow
    method chaining for concise, readable configuration.
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/jobs.html"

    def __init__(
        self,
        survey: "Survey",
        agents: Optional[Union[list["Agent"], "AgentList"]] = None,
        models: Optional[Union["ModelList", list["LanguageModel"]]] = None,
        scenarios: Optional[Union["ScenarioList", list["Scenario"]]] = None,
    ):
        """Initialize a Jobs instance with a survey and optional components.

        The Jobs constructor requires a survey and optionally accepts collections of
        agents, models, and scenarios. If any of these optional components are not provided,
        they can be added later using the `by()` method or will be automatically populated
        with defaults when the job is run.

        Parameters:
            survey (Survey): The survey containing questions to be used in the job
            agents (Union[list[Agent], AgentList], optional): The agents that will take the survey
            models (Union[ModelList, list[LanguageModel]], optional): The language models to use
            scenarios (Union[ScenarioList, list[Scenario]], optional): The scenarios to run

        Raises:
            ValueError: If the survey contains questions with invalid names
                       (e.g., names containing template variables)

        Examples:
            >>> from edsl.surveys import Survey
            >>> from edsl.questions import QuestionFreeText
            >>> q = QuestionFreeText(question_name="name", question_text="What is your name?")
            >>> s = Survey(questions=[q])
            >>> j = Jobs(survey = s)
            >>> q = QuestionFreeText(question_name="{{ bad_name }}", question_text="What is your name?")
            >>> s = Survey(questions=[q])

        Notes:
            - The survey's questions must have valid names without templating variables
            - If agents, models, or scenarios are not provided, defaults will be used when running
            - Upon initialization, a RunConfig is created with default environment and parameters
        """
        self.run_config = RunConfig(
            environment=RunEnvironment(), parameters=RunParameters()
        )

        self.survey = survey
        self.agents: AgentList = agents
        self.scenarios: ScenarioList = scenarios
        self.models: ModelList = models

        self._where_clauses = []

        try:
            assert self.survey.question_names_valid()
        except Exception:
            invalid_question_names = [
                q.question_name
                for q in self.survey.questions
                if not q.is_valid_question_name()
            ]
            raise JobsValueError(
                f"At least some question names are not valid: {invalid_question_names}"
            )

    def add_running_env(self, running_env: RunEnvironment):
        self.run_config.add_environment(running_env)
        return self

    def using_cache(self, cache: "Cache") -> Jobs:
        """
        Add a Cache to the job.

        :param cache: the cache to add
        """
        self.run_config.add_cache(cache)
        return self

    def using_bucket_collection(self, bucket_collection: "BucketCollection") -> Jobs:
        """
        Add a BucketCollection to the job.

        :param bucket_collection: the bucket collection to add
        """
        self.run_config.add_bucket_collection(bucket_collection)
        return self

    def using_key_lookup(self, key_lookup: "KeyLookup") -> Jobs:
        """
        Add a KeyLookup to the job.

        :param key_lookup: the key lookup to add
        """
        self.run_config.add_key_lookup(key_lookup)
        return self

    def using(self, obj: Union[Cache, BucketCollection, KeyLookup]) -> Jobs:
        """
        Add a Cache, BucketCollection, or KeyLookup to the job.

        :param obj: the object to add
        """
        from ..caching import Cache
        from ..key_management import KeyLookup

        if isinstance(obj, Cache):
            self.using_cache(obj)
        elif isinstance(obj, BucketCollection):
            self.using_bucket_collection(obj)
        elif isinstance(obj, KeyLookup):
            self.using_key_lookup(obj)
        return self

    @property
    def models(self):
        return self._models

    @models.setter
    def models(self, value):
        from ..language_models import ModelList

        if value:
            if not isinstance(value, ModelList):
                self._models = ModelList(value)
            else:
                self._models = value
        else:
            self._models = ModelList([])

        # update the bucket collection if it exists
        if self.run_config.environment.bucket_collection is None:
            self.run_config.environment.bucket_collection = (
                self.create_bucket_collection()
            )

    @property
    def agents(self):
        return self._agents

    @agents.setter
    def agents(self, value):
        from ..agents import AgentList

        if value:
            if not isinstance(value, AgentList):
                self._agents = AgentList(value)
            else:
                self._agents = value
        else:
            self._agents = AgentList([])

    def where(self, expression: str) -> Jobs:
        """
        Filter the agents, scenarios, and models based on a condition.

        :param expression: a condition to filter the agents, scenarios, and models
        """
        self._where_clauses.append(expression)
        return self

    @property
    def scenarios(self):
        return self._scenarios

    @scenarios.setter
    def scenarios(self, value):
        from ..scenarios import ScenarioList
        from ..dataset import Dataset

        if value:
            if isinstance(
                value, Dataset
            ):  # if the user passes in a Dataset, convert it to a ScenarioList
                value = value.to_scenario_list()

            if not isinstance(value, ScenarioList):
                self._scenarios = ScenarioList(value)
            else:
                self._scenarios = value
        else:
            self._scenarios = ScenarioList([])

    def by(
        self,
        *args: Union[
            "Agent",
            "Scenario",
            "LanguageModel",
            Sequence[Union["Agent", "Scenario", "LanguageModel"]],
        ],
    ) -> "Jobs":
        """
        Add agents, scenarios, and language models to a job using a fluent interface.

        This method is the primary way to configure a Jobs instance with components.
        It intelligently handles different types of objects and collections, making
        it easy to build complex job configurations with a concise syntax.

        Parameters:
            *args: Objects or sequences of objects to add to the job.
                  Supported types are Agent, Scenario, LanguageModel, and sequences of these.

        Returns:
            Jobs: The Jobs instance (self) for method chaining

        Examples:
            >>> from edsl.surveys import Survey
            >>> from edsl.questions import QuestionFreeText
            >>> q = QuestionFreeText(question_name="name", question_text="What is your name?")
            >>> j = Jobs(survey = Survey(questions=[q]))
            >>> j
            Jobs(survey=Survey(...), agents=AgentList([]), models=ModelList([]), scenarios=ScenarioList([]))
            >>> from edsl.agents import Agent; a = Agent(traits = {"status": "Sad"})
            >>> j.by(a).agents
            AgentList([Agent(traits = {'status': 'Sad'})])

            # Adding multiple components at once
            >>> from edsl.language_models import Model
            >>> from edsl.scenarios import Scenario
            >>> j = Jobs.example()
            >>> _ = j.by(Agent(traits={"mood": "happy"})).by(Model(temperature=0.7)).by(Scenario({"time": "morning"}))

            # Adding a sequence of the same type
            >>> agents = [Agent(traits={"age": i}) for i in range(5)]
            >>> _ = j.by(agents)

        Notes:
            - All objects must implement 'get_value', 'set_value', and '__add__' methods
            - Agent traits: When adding agents with traits to existing agents, the traits are
              combined. Avoid overlapping trait names to prevent unexpected behavior.
            - Scenario traits: When adding scenarios with traits to existing scenarios, new
              traits overwrite existing ones with the same name.
            - Models: New models with the same attributes will override existing models.
            - The method detects object types automatically and routes them to the appropriate
              collection (agents, scenarios, or models).
        """
        from .jobs_component_constructor import JobsComponentConstructor

        return JobsComponentConstructor(self).by(*args)

    def prompts(self, iterations=1) -> "Dataset":
        """Return a Dataset of prompts that will be used.


        >>> from edsl.jobs import Jobs
        >>> Jobs.example().prompts()
        Dataset(...)
        """
        return JobsPrompts.from_jobs(self).prompts(iterations=iterations)

    def show_prompts(self, all: bool = False) -> None:
        """Print the prompts."""
        if all:
            return self.prompts().to_scenario_list().table()
        else:
            return (
                self.prompts().to_scenario_list().table("user_prompt", "system_prompt")
            )

    @staticmethod
    def estimate_prompt_cost(
        system_prompt: str,
        user_prompt: str,
        price_lookup: dict,
        inference_service: str,
        model: str,
    ) -> dict:
        """
        Estimate the cost of running the prompts.
        :param iterations: the number of iterations to run
        :param system_prompt: the system prompt
        :param user_prompt: the user prompt
        :param price_lookup: the price lookup
        :param inference_service: the inference service
        :param model: the model name
        """
        return JobsPrompts.estimate_prompt_cost(
            system_prompt, user_prompt, price_lookup, inference_service, model
        )

    def estimate_job_cost(self, iterations: int = 1) -> dict:
        """
        Estimate the cost of running the job.

        :param iterations: the number of iterations to run
        """
        return JobsPrompts(self).estimate_job_cost(iterations)

    def estimate_job_cost_from_external_prices(
        self, price_lookup: dict, iterations: int = 1
    ) -> dict:
        return JobsPrompts.from_jobs(self).estimate_job_cost_from_external_prices(
            price_lookup, iterations
        )

    @staticmethod
    def compute_job_cost(job_results: Results) -> float:
        """
        Computes the cost of a completed job in USD.
        """
        return job_results.compute_job_cost()

    def replace_missing_objects(self) -> None:
        from ..agents import Agent
        from ..language_models.model import Model
        from ..scenarios import Scenario

        self.agents = self.agents or [Agent()]
        self.models = self.models or [Model()]
        self.scenarios = self.scenarios or [Scenario()]

    def generate_interviews(self) -> Generator[Interview, None, None]:
        """
        Generate interviews.

        Note that this sets the agents, model and scenarios if they have not been set. This is a side effect of the method.
        This is useful because a user can create a job without setting the agents, models, or scenarios, and the job will still run,
        with us filling in defaults.

        """
        from .jobs_interview_constructor import InterviewsConstructor

        self.replace_missing_objects()
        yield from InterviewsConstructor(
            self, cache=self.run_config.environment.cache
        ).create_interviews()

    def show_flow(self, filename: Optional[str] = None) -> None:
        """Show the flow of the survey.

        >>> from edsl.jobs import Jobs
        >>> Jobs.example().show_flow()
        """
        from ..surveys import SurveyFlowVisualization

        if self.scenarios:
            scenario = self.scenarios[0]
        else:
            scenario = None
        SurveyFlowVisualization(self.survey, scenario=scenario, agent=None).show_flow(
            filename=filename
        )

    def interviews(self) -> list[Interview]:
        """
        Return a list of :class:`edsl.jobs.interviews.Interview` objects.

        It returns one Interview for each combination of Agent, Scenario, and LanguageModel.
        If any of Agents, Scenarios, or LanguageModels are missing, it fills in with defaults.

        >>> from edsl.jobs import Jobs
        >>> j = Jobs.example()
        >>> len(j.interviews())
        4
        >>> j.interviews()[0]
        Interview(agent = Agent(traits = {'status': 'Joyful'}), survey = Survey(...), scenario = Scenario({'period': 'morning'}), model = Model(...))
        """
        return list(self.generate_interviews())

    @classmethod
    def from_interviews(cls, interview_list) -> "Jobs":
        """Return a Jobs instance from a list of interviews.

        This is useful when you have, say, a list of failed interviews and you want to create
        a new job with only those interviews.
        """
        survey = interview_list[0].survey
        # get all the models
        models = list(set([interview.model for interview in interview_list]))
        jobs = cls(survey)
        jobs.models = models
        jobs._interviews = interview_list
        return jobs

    def create_bucket_collection(self) -> BucketCollection:
        """
        Create a collection of buckets for each model.

        These buckets are used to track API calls and token usage.

        >>> from edsl.jobs import Jobs
        >>> from edsl import Model
        >>> j = Jobs.example().by(Model(temperature = 1), Model(temperature = 0.5))
        >>> bc = j.create_bucket_collection()
        >>> bc
        BucketCollection(...)
        """
        bc = BucketCollection.from_models(self.models)

        if self.run_config.environment.key_lookup is not None:
            bc.update_from_key_lookup(self.run_config.environment.key_lookup)
        return bc

    def html(self):
        """Return the HTML representations for each scenario"""
        links = []
        for index, scenario in enumerate(self.scenarios):
            links.append(
                self.survey.html(
                    scenario=scenario, return_link=True, cta=f"Scenario {index}"
                )
            )
        return links

    def __hash__(self):
        """Allow the model to be used as a key in a dictionary.

        >>> from edsl.jobs import Jobs
        >>> hash(Jobs.example())
        846655441787442972

        """
        from ..utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    def _output(self, message) -> None:
        """Check if a Job is verbose. If so, print the message."""
        if self.run_config.parameters.verbose:
            print(message)

    def all_question_parameters(self) -> set:
        """Return all the fields in the questions in the survey.
        >>> from edsl.jobs import Jobs
        >>> Jobs.example().all_question_parameters()
        {'period'}
        """
        return set.union(*[question.parameters for question in self.survey.questions])

    def use_remote_cache(self) -> bool:
        import requests

        if self.run_config.parameters.disable_remote_cache:
            return False
        if not self.run_config.parameters.disable_remote_cache:
            try:
                from ..coop import Coop

                user_edsl_settings = Coop().edsl_settings
                return user_edsl_settings.get("remote_caching", False)
            except requests.ConnectionError:
                pass
            except CoopServerResponseError:
                pass

        return False

    def _start_remote_inference_job(
        self, job_handler: Optional[JobsRemoteInferenceHandler] = None
    ) -> Union["Results", None]:
        if job_handler is None:
            job_handler = self._create_remote_inference_handler()

        job_info = job_handler.create_remote_inference_job(
            iterations=self.run_config.parameters.n,
            remote_inference_description=self.run_config.parameters.remote_inference_description,
            remote_inference_results_visibility=self.run_config.parameters.remote_inference_results_visibility,
            fresh=self.run_config.parameters.fresh,
        )
        return job_info

    def _create_remote_inference_handler(self) -> "JobsRemoteInferenceHandler":
        return JobsRemoteInferenceHandler(
            self, verbose=self.run_config.parameters.verbose
        )

    def _remote_results(
        self,
        config: RunConfig,
    ) -> Union["Results", None]:
        from .remote_inference import RemoteJobInfo

        background = config.parameters.background

        jh = self._create_remote_inference_handler()
        if jh.use_remote_inference(self.run_config.parameters.disable_remote_inference):
            job_info: RemoteJobInfo = self._start_remote_inference_job(jh)
            if background:
                from ..results import Results

                results = Results.from_job_info(job_info)
                return results, None
            else:
                results, reason = jh.poll_remote_inference_job(job_info)
                return results, reason
        else:
            return None, None

    def _prepare_to_run(self) -> None:
        "This makes sure that the job is ready to run and that keys are in place for a remote job."
        CheckSurveyScenarioCompatibility(self.survey, self.scenarios).check()

    def _check_if_remote_keys_ok(self):
        jc = JobsChecks(self)
        if jc.needs_key_process():
            jc.key_process()

    def _check_if_local_keys_ok(self):
        jc = JobsChecks(self)
        if self.run_config.parameters.check_api_keys:
            jc.check_api_keys()

    async def _execute_with_remote_cache(self, run_job_async: bool) -> Results:
        # Remote cache usage determination happens inside this method
        # use_remote_cache = self.use_remote_cache()

        from .jobs_runner_asyncio import JobsRunnerAsyncio
        from ..caching import Cache

        assert isinstance(self.run_config.environment.cache, Cache)

        runner = JobsRunnerAsyncio(self, environment=self.run_config.environment)
        if run_job_async:
            results = await runner.run_async(self.run_config.parameters)
        else:
            results = runner.run(self.run_config.parameters)
        return results

    @property
    def num_interviews(self):
        if self.run_config.parameters.n is None:
            return len(self)
        else:
            return len(self) * self.run_config.parameters.n

    def _run(self, config: RunConfig) -> Union[None, "Results"]:
        "Shared code for run and run_async"
        if config.environment.cache is not None:
            self.run_config.environment.cache = config.environment.cache
        if config.environment.jobs_runner_status is not None:
            self.run_config.environment.jobs_runner_status = (
                config.environment.jobs_runner_status
            )

        if config.environment.bucket_collection is not None:
            self.run_config.environment.bucket_collection = (
                config.environment.bucket_collection
            )

        if config.environment.key_lookup is not None:
            self.run_config.environment.key_lookup = config.environment.key_lookup

        # replace the parameters with the ones from the config
        self.run_config.parameters = config.parameters

        self.replace_missing_objects()

        self._prepare_to_run()
        self._check_if_remote_keys_ok()

        if (
            self.run_config.environment.cache is None
            or self.run_config.environment.cache is True
        ):
            from ..caching import CacheHandler

            self.run_config.environment.cache = CacheHandler().get_cache()

        if self.run_config.environment.cache is False:
            from ..caching import Cache

            self.run_config.environment.cache = Cache(immediate_write=False)

        # first try to run the job remotely
        results, reason = self._remote_results(config)
        if results is not None:
            return results, reason

        self._check_if_local_keys_ok()

        if config.environment.bucket_collection is None:
            self.run_config.environment.bucket_collection = (
                self.create_bucket_collection()
            )

        if (
            self.run_config.environment.key_lookup is not None
            and self.run_config.environment.bucket_collection is not None
        ):
            self.run_config.environment.bucket_collection.update_from_key_lookup(
                self.run_config.environment.key_lookup
            )

        return None, reason

    @with_config
    def run(self, *, config: RunConfig) -> "Results":
        """
        Runs the job by conducting interviews and returns their results.

        This is the main entry point for executing a job. It processes all interviews
        (combinations of agents, scenarios, and models) and returns a Results object
        containing all responses and metadata.

        Parameters:
            n (int): Number of iterations to run each interview (default: 1)
            progress_bar (bool): Whether to show a progress bar (default: False)
            stop_on_exception (bool): Whether to stop the job if an exception is raised (default: False)
            check_api_keys (bool): Whether to verify API keys before running (default: False)
            verbose (bool): Whether to print extra messages during execution (default: True)
            print_exceptions (bool): Whether to print exceptions as they occur (default: True)
            remote_cache_description (str, optional): Description for entries in the remote cache
            remote_inference_description (str, optional): Description for the remote inference job
            remote_inference_results_visibility (VisibilityType): Visibility of results on Coop ("private", "public", "unlisted")
            disable_remote_cache (bool): Whether to disable the remote cache (default: False)
            disable_remote_inference (bool): Whether to disable remote inference (default: False)
            fresh (bool): Whether to ignore cache and force new results (default: False)
            skip_retry (bool): Whether to skip retrying failed interviews (default: False)
            raise_validation_errors (bool): Whether to raise validation errors (default: False)
            background (bool): Whether to run in background mode (default: False)
            job_uuid (str, optional): UUID for the job, used for tracking
            cache (Cache, optional): Cache object to store results
            bucket_collection (BucketCollection, optional): Object to track API calls
            key_lookup (KeyLookup, optional): Object to manage API keys

        Returns:
            Results: A Results object containing all responses and metadata

        Notes:
            - This method will first try to use remote inference if available
            - If remote inference is not available, it will run locally
            - For long-running jobs, consider using progress_bar=True
            - For maximum performance, ensure appropriate caching is configured

        Example:
            >>> from edsl.jobs import Jobs
            >>> from edsl.caching import Cache
            >>> job = Jobs.example()
            >>> from edsl import Model
            >>> m = Model('test')
            >>> results = job.by(m).run(cache=Cache(), progress_bar=False, n=2, disable_remote_inference=True)
            ...
        """
        potentially_completed_results, reason = self._run(config)

        if potentially_completed_results is not None:
            return potentially_completed_results

        if reason == "insufficient funds":
            return None

        return asyncio.run(self._execute_with_remote_cache(run_job_async=False))

    @with_config
    async def run_async(self, *, config: RunConfig) -> "Results":
        """
        Asynchronously runs the job by conducting interviews and returns their results.

        This method is the asynchronous version of `run()`. It has the same functionality and
        parameters but can be awaited in an async context for better integration with
        asynchronous code.

        Parameters:
            n (int): Number of iterations to run each interview (default: 1)
            progress_bar (bool): Whether to show a progress bar (default: False)
            stop_on_exception (bool): Whether to stop the job if an exception is raised (default: False)
            check_api_keys (bool): Whether to verify API keys before running (default: False)
            verbose (bool): Whether to print extra messages during execution (default: True)
            print_exceptions (bool): Whether to print exceptions as they occur (default: True)
            remote_cache_description (str, optional): Description for entries in the remote cache
            remote_inference_description (str, optional): Description for the remote inference job
            remote_inference_results_visibility (VisibilityType): Visibility of results on Coop ("private", "public", "unlisted")
            disable_remote_cache (bool): Whether to disable the remote cache (default: False)
            disable_remote_inference (bool): Whether to disable remote inference (default: False)
            fresh (bool): Whether to ignore cache and force new results (default: False)
            skip_retry (bool): Whether to skip retrying failed interviews (default: False)
            raise_validation_errors (bool): Whether to raise validation errors (default: False)
            background (bool): Whether to run in background mode (default: False)
            job_uuid (str, optional): UUID for the job, used for tracking
            cache (Cache, optional): Cache object to store results
            bucket_collection (BucketCollection, optional): Object to track API calls
            key_lookup (KeyLookup, optional): Object to manage API keys

        Returns:
            Results: A Results object containing all responses and metadata

        Notes:
            - This method should be used in async contexts (e.g., with `await`)
            - For non-async contexts, use the `run()` method instead
            - This method is particularly useful in notebook environments or async applications

        Example:
            >>> import asyncio
            >>> from edsl.jobs import Jobs
            >>> from edsl.caching import Cache
            >>> job = Jobs.example()
            >>> # In an async context
            >>> async def run_job():
            ...     results = await job.run_async(cache=Cache(), progress_bar=True)
            ...     return results
        """
        self._run(config)

        return await self._execute_with_remote_cache(run_job_async=True)

    def __repr__(self) -> str:
        """Return an eval-able string representation of the Jobs instance."""
        return f"Jobs(survey={repr(self.survey)}, agents={repr(self.agents)}, models={repr(self.models)}, scenarios={repr(self.scenarios)})"

    def _summary(self):
        return {
            "questions": len(self.survey),
            "agents": len(self.agents or [1]),
            "models": len(self.models or [1]),
            "scenarios": len(self.scenarios or [1]),
        }

    def __len__(self) -> int:
        """Return the number of interviews that will be conducted for one iteration of this job.
        An interview is the result of one survey, taken by one agent, with one model, with one scenario.

        >>> from edsl.jobs import Jobs
        >>> len(Jobs.example())
        4
        """
        number_of_interviews = (
            len(self.agents or [1])
            * len(self.scenarios or [1])
            * len(self.models or [1])
        )
        return number_of_interviews

    def to_dict(self, add_edsl_version=True):
        d = {
            "survey": self.survey.to_dict(add_edsl_version=add_edsl_version),
            "agents": [
                agent.to_dict(add_edsl_version=add_edsl_version)
                for agent in self.agents
            ],
            "models": [
                model.to_dict(add_edsl_version=add_edsl_version)
                for model in self.models
            ],
            "scenarios": [
                scenario.to_dict(add_edsl_version=add_edsl_version)
                for scenario in self.scenarios
            ],
        }
        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Jobs"

        return d

    def table(self):
        return self.prompts().to_scenario_list().table()

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> Jobs:
        """Creates a Jobs instance from a dictionary."""
        from ..surveys import Survey
        from ..agents import Agent
        from ..language_models import LanguageModel
        from ..scenarios import Scenario

        return cls(
            survey=Survey.from_dict(data["survey"]),
            agents=[Agent.from_dict(agent) for agent in data["agents"]],
            models=[LanguageModel.from_dict(model) for model in data["models"]],
            scenarios=[Scenario.from_dict(scenario) for scenario in data["scenarios"]],
        )

    def __eq__(self, other: Jobs) -> bool:
        """Return True if the Jobs instance is equal to another Jobs instance.

        >>> from edsl.jobs import Jobs
        >>> Jobs.example() == Jobs.example()
        True

        """
        return hash(self) == hash(other)

    @classmethod
    def example(
        cls,
        throw_exception_probability: float = 0.0,
        randomize: bool = False,
        test_model=False,
    ) -> Jobs:
        """Return an example Jobs instance.

        :param throw_exception_probability: the probability that an exception will be thrown when answering a question. This is useful for testing error handling.
        :param randomize: whether to randomize the job by adding a random string to the period
        :param test_model: whether to use a test model

        >>> Jobs.example()
        Jobs(...)

        """
        import random
        from uuid import uuid4
        from ..questions import QuestionMultipleChoice
        from ..agents import Agent
        from ..scenarios import Scenario

        addition = "" if not randomize else str(uuid4())

        if test_model:
            from ..language_models import LanguageModel

            m = LanguageModel.example(test_model=True)

        # (status, question, period)
        agent_answers = {
            ("Joyful", "how_feeling", "morning"): "OK",
            ("Joyful", "how_feeling", "afternoon"): "Great",
            ("Joyful", "how_feeling_yesterday", "morning"): "Great",
            ("Joyful", "how_feeling_yesterday", "afternoon"): "Good",
            ("Sad", "how_feeling", "morning"): "Terrible",
            ("Sad", "how_feeling", "afternoon"): "OK",
            ("Sad", "how_feeling_yesterday", "morning"): "OK",
            ("Sad", "how_feeling_yesterday", "afternoon"): "Terrible",
        }

        def answer_question_directly(self, question, scenario):
            """Return the answer to a question. This is a method that can be added to an agent."""

            if random.random() < throw_exception_probability:
                from .exceptions import JobsErrors

                raise JobsErrors("Simulated error during question answering")
            return agent_answers[
                (self.traits["status"], question.question_name, scenario["period"])
            ]

        sad_agent = Agent(traits={"status": "Sad"})
        joy_agent = Agent(traits={"status": "Joyful"})

        sad_agent.add_direct_question_answering_method(answer_question_directly)
        joy_agent.add_direct_question_answering_method(answer_question_directly)

        q1 = QuestionMultipleChoice(
            question_text="How are you this {{ period }}?",
            question_options=["Good", "Great", "OK", "Terrible"],
            question_name="how_feeling",
        )
        q2 = QuestionMultipleChoice(
            question_text="How were you feeling yesterday {{ period }}?",
            question_options=["Good", "Great", "OK", "Terrible"],
            question_name="how_feeling_yesterday",
        )
        from ..surveys import Survey
        from ..scenarios import ScenarioList

        base_survey = Survey(questions=[q1, q2])

        scenario_list = ScenarioList(
            [
                Scenario({"period": f"morning{addition}"}),
                Scenario({"period": "afternoon"}),
            ]
        )
        if test_model:
            job = base_survey.by(m).by(scenario_list).by(joy_agent, sad_agent)
        else:
            job = base_survey.by(scenario_list).by(joy_agent, sad_agent)

        return job

    def code(self):
        """Return the code to create this instance."""
        raise JobsImplementationError("Code generation not implemented yet")


def main():
    """Run the module's doctests."""
    from .jobs import Jobs
    from ..caching import Cache

    job = Jobs.example()
    len(job) == 4
    results = job.run(cache=Cache())
    len(results) == 4
    results


if __name__ == "__main__":
    """Run the module's doctests."""
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
