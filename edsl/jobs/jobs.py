"""The Jobs module is the core orchestration component of the EDSL framework.

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
from importlib import import_module
from typing import (
    Optional,
    Union,
    Any,
    Literal,
    Sequence,
    Generator,
    Tuple,
    TYPE_CHECKING,
)

from ..base import Base
from ..utilities import remove_edsl_version
from ..logger import get_logger

# from ..scenarios import Scenario, ScenarioList
# from ..surveys import Survey

from .exceptions import JobsValueError, JobsImplementationError
from .jobs_pricing_estimation import JobsPrompts
from .remote_inference import JobsRemoteInferenceHandler
from .jobs_checks import JobsChecks
from .data_structures import RunEnvironment, RunParameters, RunConfig
from .check_survey_scenario_compatibility import CheckSurveyScenarioCompatibility
from .decorators import with_config
from ..coop.exceptions import CoopServerResponseError


def get_bucket_collection():
    """Get the BucketCollection class from the buckets module.

    Returns
    -------
        The BucketCollection class.

    """
    buckets_module = import_module("edsl.buckets")
    return buckets_module.BucketCollection


def get_interview():
    """Get the Interview class from the interviews module.

    Returns
    -------
        The Interview class.

    """
    interviews_module = import_module("edsl.interviews.interview")
    return interviews_module.Interview


if TYPE_CHECKING:
    from ..agents import Agent
    from ..agents import AgentList
    from ..language_models import LanguageModel
    from ..scenarios import Scenario, ScenarioList
    from ..surveys import Survey
    from ..results import Results
    from ..dataset import Dataset
    from ..language_models import ModelList
    from ..questions import QuestionBase as Question
    from ..caching import Cache
    from ..key_management import KeyLookup
    from ..buckets import BucketCollection
    from ..interviews.interview import Interview

VisibilityType = Literal["private", "public", "unlisted"]


class Jobs(Base):
    """A collection of agents, scenarios, models, and a survey that orchestrates interviews.

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
    _logger = get_logger(__name__)

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

        Parameters
        ----------
        survey : Survey
            The survey containing questions to be used in the job
        agents : Union[list[Agent], AgentList], optional
            The agents that will take the survey
        models : Union[ModelList, list[LanguageModel]], optional
            The language models to use
        scenarios : Union[ScenarioList, list[Scenario]], optional
            The scenarios to run

        Raises
        ------
            ValueError: If the survey contains questions with invalid names
                       (e.g., names containing template variables)

        Examples
        --------
            >>> from edsl.surveys import Survey
            >>> from edsl.questions import QuestionFreeText
            >>> q = QuestionFreeText(question_name="name", question_text="What is your name?")
            >>> s = Survey(questions=[q])
            >>> j = Jobs(survey = s)
            >>> q = QuestionFreeText(question_name="{{ bad_name }}", question_text="What is your name?")
            >>> s = Survey(questions=[q])

        Notes
        -----
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

        self._post_run_methods = []
        self._depends_on = None

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

    def add_running_env(self, running_env: RunEnvironment) -> Jobs:
        """Add a running environment to the job.

        Args:
        ----
            running_env: A RunEnvironment object containing details about the execution
                environment like API keys and other configuration.

        Returns:
        -------
            Jobs: The Jobs instance with the updated running environment.

        Example:
        -------
            >>> from edsl import Cache
            >>> job = Jobs.example()
            >>> my_cache = Cache.example()
            >>> env = RunEnvironment(cache=my_cache)
            >>> j = job.add_running_env(env)
            >>> j.run_config.environment.cache == my_cache
            True

        """
        self.run_config.add_environment(running_env)
        return self

    def using_cache(self, cache: "Cache") -> "Jobs":
        """Add a Cache object to the job.

        Args:
        ----
            cache: The Cache object to add to the job's configuration.

        Returns:
        -------
            Jobs: The Jobs instance with the updated cache.

        """
        self.run_config.add_cache(cache)
        return self

    def using_bucket_collection(self, bucket_collection: "BucketCollection") -> "Jobs":
        """Add a BucketCollection object to the job.

        Args:
        ----
            bucket_collection: The BucketCollection object to add to the job's configuration.

        Returns:
        -------
            Jobs: The Jobs instance with the updated bucket collection.

        """
        self.run_config.add_bucket_collection(bucket_collection)
        return self

    def using_key_lookup(self, key_lookup: "KeyLookup") -> "Jobs":
        """Add a KeyLookup object to the job.

        Args:
        ----
            key_lookup: The KeyLookup object to add to the job's configuration.

        Returns:
        -------
            Jobs: The Jobs instance with the updated key lookup.

        """
        self.run_config.add_key_lookup(key_lookup)
        return self

    def using(self, obj) -> "Jobs":
        """Add a Cache, BucketCollection, or KeyLookup object to the job.

        Args:
        ----
            obj: The object to add to the job's configuration. Must be one of:
                Cache, BucketCollection, or KeyLookup.

        Returns:
        -------
            Jobs: The Jobs instance with the updated configuration object.

        """
        from ..caching import Cache
        from ..key_management import KeyLookup

        BucketCollection = get_bucket_collection()

        handlers = {
            Cache: self.using_cache,
            BucketCollection: self.using_bucket_collection,
            KeyLookup: self.using_key_lookup,
        }
        handler = next((fn for t, fn in handlers.items() if isinstance(obj, t)), None)
        if handler is None:
            raise ValueError(f"Invalid object type: {type(obj)}")
        handler(obj)
        return self

    @property
    def models(self):
        """Get the models associated with this job.

        Returns
        -------
            ModelList: The models for this job.

        """
        return self._models

    @models.setter
    def models(self, value) -> None:
        from ..language_models import ModelList

        if value:
            if not isinstance(value, ModelList):
                self._models = ModelList(value)
            else:
                self._models = value
        else:
            self._models = ModelList(None)

        # update the bucket collection if it exists
        if self.run_config.environment.bucket_collection is None:
            self.run_config.environment.bucket_collection = (
                self.create_bucket_collection()
            )

    @property
    def agents(self):
        """Get the agents associated with this job.

        Returns
        -------
            AgentList: The agents for this job.

        """
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
        """Filter the agents, scenarios, and models based on a condition.

        :param expression: a condition to filter the agents, scenarios, and models
        """
        self._where_clauses.append(expression)
        return self

    @property
    def scenarios(self) -> ScenarioList:
        """Get the scenarios associated with this job.

        Returns
        -------
            ScenarioList: The scenarios for this job.

        """
        return self._scenarios

    @scenarios.setter
    def scenarios(self, value) -> None:
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
        """Add agents, scenarios, and language models to a job using a fluent interface.

        This method is the primary way to configure a Jobs instance with components.
        It intelligently handles different types of objects and collections, making
        it easy to build complex job configurations with a concise syntax.

        Parameters
        ----------
        *args : Union[Agent, Scenario, LanguageModel, Sequence[Union[Agent, Scenario, LanguageModel]]]
            Objects or sequences of objects to add to the job.
            Supported types are Agent, Scenario, LanguageModel, and sequences of these.

        Returns
        -------
            Jobs: The Jobs instance (self) for method chaining

        Examples
        --------
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

        Notes
        -----
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
            print(self.prompts().to_scenario_list().table())
        else:
            print(
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
        """Estimate the cost of running the prompts.

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
        """Estimate the cost of running the job.

        :param iterations: the number of iterations to run
        """
        return JobsPrompts.from_jobs(self).estimate_job_cost(iterations)

    def estimate_job_cost_from_external_prices(
        self, price_lookup: dict, iterations: int = 1
    ) -> dict:
        """Estimate the cost of running the job using external price lookup.

        Args:
        ----
            price_lookup: Dictionary containing price information.
            iterations: Number of iterations to run.

        Returns:
        -------
            dict: Cost estimation details.

        """
        return JobsPrompts.from_jobs(self).estimate_job_cost_from_external_prices(
            price_lookup, iterations
        )

    @staticmethod
    def compute_job_cost(job_results: Results) -> float:
        """Compute the cost of a completed job in USD."""
        return job_results.compute_job_cost()

    def replace_missing_objects(self) -> None:
        """If the agents, models, or scenarios are not set, replace them with defaults."""
        from ..agents import Agent
        from ..language_models.model import Model
        from ..scenarios import Scenario

        self.agents = self.agents or [Agent()]
        self.models = self.models or [Model()]
        self.scenarios = self.scenarios or [Scenario()]

    def generate_interviews(self) -> Generator:
        """Generate interviews.

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
        """Visualize either the *Job* dependency/post-processing flow **or** the underlying survey flow.

        The method automatically decides which flow to render:

        1. If the job has dependencies created via :py:meth:`Jobs.to` (i.e.
           ``_depends_on`` is not *None*) **or** has post-run methods queued in
           ``_post_run_methods``, the *job* flow (dependencies → post-processing
           chain) is rendered using :class:`edsl.jobs.job_flow_visualization.JobsFlowVisualization`.
        2. Otherwise, it falls back to the original behaviour and shows the
           survey question flow using
           :class:`edsl.surveys.survey_flow_visualization.SurveyFlowVisualization`.

        >>> from edsl.jobs import Jobs
        >>> job = Jobs.example()
        >>> job.show_flow()  # Visualises survey flow (no deps/post-run methods)
        >>> job2 = job.select('how_feeling').to_pandas()  # add post-run methods
        >>> job2.show_flow()  # Now visualises job flow
        """
        # Decide which visualisation to use
        has_dependencies = getattr(self, "_depends_on", None) is not None
        has_post_methods = bool(getattr(self, "_post_run_methods", []))

        if has_dependencies or has_post_methods:
            # Use the new Jobs flow visualisation
            from .job_flow_visualization import JobsFlowVisualization

            JobsFlowVisualization(self).show_flow(filename=filename)
        else:
            # Fallback to survey flow visualisation
            from ..surveys import SurveyFlowVisualization

            scenario = self.scenarios[0] if self.scenarios else None
            SurveyFlowVisualization(
                self.survey, scenario=scenario, agent=None
            ).show_flow(filename=filename)

    def interviews(self) -> list:
        """Return a list of :class:`edsl.jobs.interviews.Interview` objects.

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
    def from_interviews(cls, interview_list: list["Interview"]) -> Jobs:
        """Return a Jobs instance from a list of interviews.

        This is useful when you have, say, a list of failed interviews and you want to create
        a new job with only those interviews.
        """
        if not interview_list:
            raise JobsValueError("Cannot create Jobs from empty interview list")

        survey = interview_list[0].survey
        # get all the models
        models = list(set([interview.model for interview in interview_list]))
        jobs = cls(survey)
        jobs.models = models
        jobs._interviews = interview_list
        return jobs

    def create_bucket_collection(self) -> "BucketCollection":
        """Create a collection of buckets for each model.

        These buckets are used to track API calls and token usage.
        For test models and scripted response models, infinity buckets are used
        to avoid rate limiting delays.

        >>> from edsl.jobs import Jobs
        >>> from edsl import Model
        >>> j = Jobs.example().by(Model(temperature = 1), Model(temperature = 0.5))
        >>> bc = j.create_bucket_collection()
        >>> bc
        BucketCollection(...)
        """
        BucketCollection = get_bucket_collection()

        # Check if we should use infinity buckets for test/scripted models
        use_infinity_buckets = self._should_use_infinity_buckets()

        bc = BucketCollection.from_models(
            self.models, infinity_buckets=use_infinity_buckets
        )

        if self.run_config.environment.key_lookup is not None:
            bc.update_from_key_lookup(self.run_config.environment.key_lookup)
        return bc

    def _should_use_infinity_buckets(self) -> bool:
        """Determine if infinity buckets should be used for the models in this job.

        Infinity buckets (no rate limiting) are used for:
        - Scripted response models (specific class type)
        - Models with _model_ attribute set to "scripted"

        Returns:
            bool: True if infinity buckets should be used, False otherwise
        """
        from ..language_models.scripted_response_model import (
            ScriptedResponseLanguageModel,
        )

        for model in self.models:
            # Check for scripted response model by class
            if isinstance(model, ScriptedResponseLanguageModel):
                self._logger.info(
                    f"Using infinity buckets for scripted response model: {model}"
                )
                return True

            # Check for scripted model by _model_ attribute
            if getattr(model, "_model_", None) == "scripted":
                self._logger.info(f"Using infinity buckets for scripted model: {model}")
                return True

        return False

    def html(self):
        """Return the HTML representations for each scenario."""
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
        """Determine whether to use remote cache for this job.

        Returns
        -------
            bool: True if remote cache should be used, False otherwise.

        """
        import requests

        if self.run_config.parameters.disable_remote_cache:
            return False

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
    ):
        if job_handler is None:
            job_handler = self._create_remote_inference_handler()

        job_info = job_handler.create_remote_inference_job(
            iterations=self.run_config.parameters.n,
            remote_inference_description=self.run_config.parameters.remote_inference_description,
            remote_inference_results_visibility=self.run_config.parameters.remote_inference_results_visibility,
            fresh=self.run_config.parameters.fresh,
            new_format=self.run_config.parameters.new_format,
        )
        return job_info

    def _create_remote_inference_handler(self) -> "JobsRemoteInferenceHandler":
        return JobsRemoteInferenceHandler(
            self,
            verbose=self.run_config.parameters.verbose,
            api_key=self.run_config.parameters.expected_parrot_api_key,
        )

    def _remote_results(
        self,
        config: RunConfig,
    ) -> Tuple[Optional["Results"], Optional[str]]:
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
        """Prepare the job to run and ensure keys are in place for a remote job."""
        CheckSurveyScenarioCompatibility(self.survey, self.scenarios).check()

    def _check_if_remote_keys_ok(self) -> None:
        jc = JobsChecks(self)
        if not jc.user_has_ep_api_key():
            jc.key_process(remote_inference=True)

    def _check_if_local_keys_ok(self) -> None:
        jc = JobsChecks(self)
        if self.run_config.parameters.check_api_keys:
            jc.check_api_keys()

    async def _execute_with_remote_cache(self, run_job_async: bool) -> Results:
        """Core interview execution logic for jobs execution."""
        # Import needed modules inline to avoid early binding
        import time
        import weakref
        from ..caching import Cache
        from ..results import Results
        from ..tasks import TaskHistory
        from .jobs_runner_status import JobsRunnerStatus
        from .async_interview_runner import AsyncInterviewRunner
        from .progress_bar_manager import ProgressBarManager
        from .results_exceptions_handler import ResultsExceptionsHandler

        execution_start = time.time()
        self._logger.info("Starting core interview execution logic")

        assert isinstance(self.run_config.environment.cache, Cache)

        # Create the RunConfig for the job
        run_config = RunConfig(
            parameters=self.run_config.parameters,
            environment=self.run_config.environment,
        )

        # Setup JobsRunnerStatus if needed
        if self.run_config.environment.jobs_runner_status is None:
            self.run_config.environment.jobs_runner_status = JobsRunnerStatus(
                self, n=self.run_config.parameters.n
            )

        # Create a shared function to process interview results
        async def process_interviews(interview_runner, results_obj):
            async for result, interview, idx in interview_runner.run():
                # Set the order attribute on the result for correct ordering
                result.order = idx

                results_obj.add_task_history_entry(interview)
                results_obj.insert_sorted(result)

                # Memory management: Set up reference for next iteration and clear old references
                weakref.ref(interview)
                if hasattr(interview, "clear_references"):
                    interview.clear_references()

                # Force garbage collection
                del result
                del interview

            # Finalize results object with cache and bucket collection
            results_obj.cache = results_obj.relevant_cache(
                self.run_config.environment.cache
            )
            results_obj.bucket_collection = (
                self.run_config.environment.bucket_collection
            )
            return results_obj

        # Core execution logic
        runner_start = time.time()
        self._logger.info("Creating interview runner and results objects")
        interview_runner = AsyncInterviewRunner(self, run_config)

        # Create an initial Results object with appropriate traceback settings
        results = Results(
            survey=self.survey,
            data=[],
            task_history=TaskHistory(
                include_traceback=not self.run_config.parameters.progress_bar
            ),
        )
        self._logger.info(
            f"Interview runner setup completed in {time.time() - runner_start:.3f}s"
        )

        # Execute interviews
        interview_start = time.time()
        if run_job_async:
            # For async execution mode (simplified path without progress bar)
            self._logger.info("Starting async interview execution (no progress bar)")
            await process_interviews(interview_runner, results)
        else:
            # For synchronous execution mode (with progress bar)
            self._logger.info("Starting sync interview execution with progress bar")
            with ProgressBarManager(self, run_config, self.run_config.parameters):
                try:
                    await process_interviews(interview_runner, results)
                except KeyboardInterrupt:
                    self._logger.info("Keyboard interrupt received during execution")
                    print("Keyboard interrupt received. Stopping gracefully...")
                    results = Results(
                        survey=self.survey, data=[], task_history=TaskHistory()
                    )
                except Exception as e:
                    self._logger.error(
                        f"Exception during interview execution: {str(e)}"
                    )
                    if self.run_config.parameters.stop_on_exception:
                        raise
                    results = Results(
                        survey=self.survey, data=[], task_history=TaskHistory()
                    )

        self._logger.info(
            f"Interview execution completed in {time.time() - interview_start:.3f}s"
        )

        # Process any exceptions in the results
        exception_start = time.time()
        if results:
            self._logger.info("Processing exceptions in results")
            ResultsExceptionsHandler(
                results, self.run_config.parameters
            ).handle_exceptions()
            self._logger.info(
                f"Exception handling completed in {time.time() - exception_start:.3f}s"
            )

        self._logger.info(
            f"Total execution time: {time.time() - execution_start:.3f}s, "
            f"final results count: {len(results) if results else 0}"
        )
        return results

    @property
    def num_interviews(self) -> int:
        """Calculate the total number of interviews that will be run.

        >>> Jobs.example().num_interviews
        4

        This is the product of the number of scenarios, agents, and models,
        multiplied by the number of iterations specified in the run configuration.
        """
        if self.run_config.parameters.n is None:
            return len(self)
        else:
            return len(self) * self.run_config.parameters.n

    def _run(self, config: RunConfig) -> Tuple[Optional["Results"], Optional[str]]:
        """Shared code for run and run_async methods.

        This method handles all pre-execution setup including:
        1. Transferring configuration settings from the input config
        2. Ensuring all required objects (agents, models, scenarios) exist
        3. Checking API keys and remote execution availability
        4. Setting up caching and bucket collections
        5. Attempting remote execution if appropriate

        Returns
        -------
            Tuple containing (Results, reason) if remote execution succeeds,
            or (None, reason) if local execution should proceed

        """
        import time

        start_time = time.time()

        self._logger.info("Starting job configuration transfer")
        # Apply configuration from input config to self.run_config
        for attr_name in [
            "cache",
            "jobs_runner_status",
            "bucket_collection",
            "key_lookup",
        ]:
            if getattr(config.environment, attr_name) is not None:
                setattr(
                    self.run_config.environment,
                    attr_name,
                    getattr(config.environment, attr_name),
                )

        # Replace parameters with the ones from the config
        self.run_config.parameters = config.parameters
        self._logger.info(
            f"Configuration transfer completed in {time.time() - start_time:.3f}s"
        )

        # Make sure all required objects exist
        setup_start = time.time()
        self._logger.info("Starting object validation and preparation")
        self.replace_missing_objects()
        self._prepare_to_run()
        self._logger.info(
            f"Object validation completed in {time.time() - setup_start:.3f}s"
        )

        if not self.run_config.parameters.disable_remote_inference:
            key_check_start = time.time()
            self._logger.info("Checking remote inference keys")
            self._check_if_remote_keys_ok()
            self._logger.info(
                f"Remote key check completed in {time.time() - key_check_start:.3f}s"
            )

        # Setup caching
        cache_start = time.time()
        self._logger.info("Setting up caching system")
        from ..caching import CacheHandler, Cache

        if (
            self.run_config.environment.cache is None
            or self.run_config.environment.cache is True
        ):
            self.run_config.environment.cache = CacheHandler().get_cache()
        elif self.run_config.environment.cache is False:
            self.run_config.environment.cache = Cache(immediate_write=False)
        self._logger.info(f"Cache setup completed in {time.time() - cache_start:.3f}s")

        # Try to run the job remotely first
        remote_start = time.time()
        self._logger.info("Attempting remote execution")
        results, reason = self._remote_results(config)
        if results is not None:
            self._logger.info(
                f"Remote execution successful in {time.time() - remote_start:.3f}s"
            )
            return results, reason
        self._logger.info(
            f"Remote execution check completed in {time.time() - remote_start:.3f}s, proceeding with local execution"
        )

        # If we need to run locally, ensure keys and resources are ready
        local_prep_start = time.time()
        self._logger.info("Preparing for local execution")
        self._check_if_local_keys_ok()

        # Create bucket collection if it doesn't exist
        # this is respect API service request limits
        if self.run_config.environment.bucket_collection is None:
            bucket_start = time.time()
            self._logger.info("Creating bucket collection for rate limiting")
            self.run_config.environment.bucket_collection = (
                self.create_bucket_collection()
            )
            self._logger.info(
                f"Bucket collection created in {time.time() - bucket_start:.3f}s"
            )
        else:
            # Ensure models are properly added to the bucket collection
            self._logger.info("Adding models to existing bucket collection")
            for model in self.models:
                self.run_config.environment.bucket_collection.add_model(model)

        # Update bucket collection from key lookup if both exist
        if (
            self.run_config.environment.key_lookup is not None
            and self.run_config.environment.bucket_collection is not None
        ):
            self._logger.info("Updating bucket collection with key lookup")
            self.run_config.environment.bucket_collection.update_from_key_lookup(
                self.run_config.environment.key_lookup
            )

        self._logger.info(
            f"Local execution preparation completed in {time.time() - local_prep_start:.3f}s"
        )
        self._logger.info(
            f"Total _run method execution time: {time.time() - start_time:.3f}s"
        )

        return None, reason

    def then(self, method_name, *args, **kwargs) -> "Jobs":
        """Schedule a method to be called on the results object after the job runs.

        This allows for method chaining like:
        jobs.then('to_scenario_list').then('to_pandas').then('head', 10)

        Args:
        ----
            method_name: Name of the method to call on the results
            *args: Positional arguments to pass to the method
            **kwargs: Keyword arguments to pass to the method

        """
        self._post_run_methods.append((method_name, args, kwargs))
        return self

    def __getattr__(self, name):
        """Safer version of attribute access for method chaining.

        Only captures specific patterns to avoid masking real AttributeErrors.
        """
        # Safeguard: ensure _post_run_methods exists
        if not hasattr(self, "_post_run_methods"):
            raise AttributeError(
                f"'{self.__class__.__name__}' object has no attribute '{name}'"
            )

        # Only capture names that look like result methods (could be customized)
        # This is a whitelist approach - only capture known safe patterns
        safe_method_patterns = {
            "to_pandas",
            "to_dict",
            "to_csv",
            "to_json",
            "to_list",
            "select",
            "filter",
            "sort_values",
            "head",
            "tail",
            "groupby",
            "pivot",
            "melt",
            "drop",
            "rename",
            "to_scenario_list",
            "to_agent_list",
            "concatenate",
            "collapse",
            "expand",
            "store",
            "first",
            "last",
        }

        if name in safe_method_patterns:

            def method_proxy(*args, **kwargs):
                self._post_run_methods.append((name, args, kwargs))
                return self

            return method_proxy

        # For unknown methods, raise AttributeError immediately
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'. "
            f"Use .then('{name}', ...) for post-run method chaining."
        )

    def _apply_post_run_methods(self, results) -> Any:
        """Apply all post-run methods to the results object.

        Returns the transformed results object, or the original results if no methods were applied.
        """
        if not self._post_run_methods:
            return results

        from ..results import Results

        # Mapping of built-in functions to their corresponding dunder methods
        builtin_to_dunder = {
            "len": "__len__",
            "str": "__str__",
            "repr": "__repr__",
            "bool": "__bool__",
            "int": "__int__",
            "float": "__float__",
            "hash": "__hash__",
            "iter": "__iter__",
            "next": "__next__",
            "reversed": "__reversed__",
        }

        converted_object = results
        for method_info in self._post_run_methods:
            if isinstance(method_info, str):
                # Handle old format (just method name)
                method_name = method_info
                args, kwargs = (), {}
            else:
                # Handle new format (method name, args, kwargs)
                method_name, args, kwargs = method_info

            # Convert built-in function names to their dunder method equivalents
            if method_name in builtin_to_dunder:
                method_name = builtin_to_dunder[method_name]

            try:
                converted_object = getattr(converted_object, method_name)(
                    *args, **kwargs
                )
            except AttributeError:
                raise JobsImplementationError(
                    f"Could not apply method '{method_name}' to object."
                )

        if not isinstance(converted_object, Results):
            converted_object._associated_results = results

        return converted_object

    @with_config
    def run(self, *, config: RunConfig) -> Optional["Results"]:
        """Run the job by conducting interviews and return their results.

        This is the main entry point for executing a job. It processes all interviews
        (combinations of agents, scenarios, and models) and returns a Results object
        containing all responses and metadata.

        Parameters
        ----------
        config : RunConfig
            Configuration object containing runtime parameters and environment settings
        n : int, optional
            Number of iterations to run each interview (default: 1)
        progress_bar : bool, optional
            Whether to show a progress bar (default: False)
        stop_on_exception : bool, optional
            Whether to stop the job if an exception is raised (default: False)
        check_api_keys : bool, optional
            Whether to verify API keys before running (default: False)
        verbose : bool, optional
            Whether to print extra messages during execution (default: True)
        print_exceptions : bool, optional
            Whether to print exceptions as they occur (default: True)
        remote_cache_description : str, optional
            Description for entries in the remote cache
        remote_inference_description : str, optional
            Description for the remote inference job
        remote_inference_results_visibility : VisibilityType, optional
            Visibility of results on Coop ("private", "public", "unlisted")
        disable_remote_cache : bool, optional
            Whether to disable the remote cache (default: False)
        disable_remote_inference : bool, optional
            Whether to disable remote inference (default: False)
        fresh : bool, optional
            Whether to ignore cache and force new results (default: False)
        skip_retry : bool, optional
            Whether to skip retrying failed interviews (default: False)
        raise_validation_errors : bool, optional
            Whether to raise validation errors (default: False)
        background : bool, optional
            Whether to run in background mode (default: False)
        job_uuid : str, optional
            UUID for the job, used for tracking
        cache : Cache, optional
            Cache object to store results
        bucket_collection : BucketCollection, optional
            Object to track API keys
        key_lookup : KeyLookup, optional
            Object to manage API keys
        memory_threshold : int, optional
            Memory threshold in bytes for the Results object's SQLList,
            controlling when data is offloaded to SQLite storage
        new_format : bool, optional
            If True, uses remote_inference_create method, if False uses old_remote_inference_create method (default: True)
        expected_parrot_api_key : str, optional
            Custom EXPECTED_PARROT_API_KEY to use for this job run

        Returns
        -------
            Results: A Results object containing all responses and metadata

        Notes
        -----
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
        self._logger.info("Starting job execution")
        self._logger.info(
            f"Job configuration: {self.num_interviews} total interviews, "
            f"remote_inference={'disabled' if config.parameters.disable_remote_inference else 'enabled'}, "
            f"progress_bar={config.parameters.progress_bar}"
        )

        if self._depends_on is not None:
            self._logger.info("Checking job dependencies")
            prior_results = self._depends_on.run(config=config)
            self = self.by(prior_results)
            self._logger.info("Job dependencies resolved successfully")

        self._logger.info("Starting pre-run setup and configuration")
        potentially_completed_results, reason = self._run(config)

        if potentially_completed_results is not None:
            self._logger.info(
                "Job completed via remote execution, applying post-run methods"
            )
            return self._apply_post_run_methods(potentially_completed_results)

        if reason == "insufficient funds":
            self._logger.info("Job cancelled due to insufficient funds")
            return None

        self._logger.info("Starting local execution with remote cache")
        results = asyncio.run(self._execute_with_remote_cache(run_job_async=False))

        self._logger.info("Applying post-run methods to results")
        final_results = self._apply_post_run_methods(results)

        self._logger.info(
            f"Job execution completed successfully with {len(final_results) if final_results else 0} results"
        )
        return final_results

    @with_config
    async def run_async(self, *, config: RunConfig) -> "Results":
        """Asynchronously runs the job by conducting interviews and returns their results.

        This method is the asynchronous version of `run()`. It has the same functionality and
        parameters but can be awaited in an async context for better integration with
        asynchronous code.

        Parameters
        ----------
        config : RunConfig
            Configuration object containing runtime parameters and environment settings
        n : int, optional
            Number of iterations to run each interview (default: 1)
        progress_bar : bool, optional
            Whether to show a progress bar (default: False)
        stop_on_exception : bool, optional
            Whether to stop the job if an exception is raised (default: False)
        check_api_keys : bool, optional
            Whether to verify API keys before running (default: False)
        verbose : bool, optional
            Whether to print extra messages during execution (default: True)
        print_exceptions : bool, optional
            Whether to print exceptions as they occur (default: True)
        remote_cache_description : str, optional
            Description for entries in the remote cache
        remote_inference_description : str, optional
            Description for the remote inference job
        remote_inference_results_visibility : VisibilityType, optional
            Visibility of results on Coop ("private", "public", "unlisted")
        disable_remote_cache : bool, optional
            Whether to disable the remote cache (default: False)
        disable_remote_inference : bool, optional
            Whether to disable remote inference (default: False)
        fresh : bool, optional
            Whether to ignore cache and force new results (default: False)
        skip_retry : bool, optional
            Whether to skip retrying failed interviews (default: False)
        raise_validation_errors : bool, optional
            Whether to raise validation errors (default: False)
        background : bool, optional
            Whether to run in background mode (default: False)
        job_uuid : str, optional
            UUID for the job, used for tracking
        cache : Cache, optional
            Cache object to store results
        bucket_collection : BucketCollection, optional
            Object to track API calls
        key_lookup : KeyLookup, optional
            Object to manage API keys
        memory_threshold : int, optional
            Memory threshold in bytes for the Results object's SQLList,
            controlling when data is offloaded to SQLite storage
        new_format : bool, optional
            If True, uses remote_inference_create method, if False uses old_remote_inference_create method (default: True)
        expected_parrot_api_key : str, optional
            Custom EXPECTED_PARROT_API_KEY to use for this job run

        Returns
        -------
            Results: A Results object containing all responses and metadata

        Notes
        -----
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

    def to(
        self, question_or_survey_or_jobs: Union["Question", "Survey", "Jobs"]
    ) -> "Jobs":
        """Create a new :class:`Jobs` instance from *self* and a target object.

        The target can be one of the following:

        • `Question` – A single question which will be wrapped in a one-question
          survey.
        • `Survey` – A survey object that will be used directly.
        • `Jobs`   – An existing *Jobs* object. In this case the target *Jobs*
          is **returned unchanged**, but its ``_depends_on`` attribute is set to
          reference *self*, establishing an execution dependency chain.

        Args:
        ----
            question_or_survey_or_jobs (Union[Question, Survey, Jobs]):
                The object used to build (or identify) the new *Jobs* instance.

        Returns:
        -------
            Jobs: A new *Jobs* instance that depends on the current instance, or
            the target *Jobs* instance when the target itself is a *Jobs*.

        Raises:
        ------
            ValueError: If *question_or_survey_or_jobs* is not one of the
                supported types.

        Examples:
        --------
            The following doctest demonstrates sending one job to another and
            verifying the dependency link via the private ``_depends_on``
            attribute::

                >>> from edsl.jobs import Jobs
                >>> base_job = Jobs.example()
                >>> downstream_job = Jobs.example()
                >>> new_job = base_job.to(downstream_job)
                >>> new_job is downstream_job  # the same object is returned
                True
                >>> new_job._depends_on is base_job  # dependency recorded
                True

        """
        from ..questions import QuestionBase
        from ..surveys import Survey

        type_handlers = {
            QuestionBase: lambda q: Jobs(survey=Survey(questions=[q])),
            Survey: lambda s: Jobs(survey=s),
            Jobs: lambda j: j,
        }
        handler = next(
            (
                fn
                for t, fn in type_handlers.items()
                if isinstance(question_or_survey_or_jobs, t)
            ),
            None,
        )

        if handler is None:
            raise ValueError(f"Invalid type: {type(question_or_survey_or_jobs)}")

        new_jobs = handler(question_or_survey_or_jobs)
        new_jobs._depends_on = self
        return new_jobs

    def duplicate(self):
        """Create a duplicate copy of this Jobs instance.

        Returns
        -------
            Jobs: A new Jobs instance that is a copy of this one.

        """
        return Jobs.from_dict(self.to_dict())

    def to_dict(self, add_edsl_version=True, full_dict=None):
        """Convert the Jobs instance to a dictionary representation.

        Args:
        ----
            add_edsl_version: Whether to include EDSL version information.
            full_dict: Additional dictionary to merge (currently unused).

        Returns:
        -------
            dict: Dictionary representation of this Jobs instance.

        """
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

        # Add _post_run_methods if not empty
        if self._post_run_methods:
            d["_post_run_methods"] = self._post_run_methods

        # Add _depends_on if not None
        if self._depends_on is not None:
            d["_depends_on"] = self._depends_on.to_dict(
                add_edsl_version=add_edsl_version
            )

        if add_edsl_version:
            from .. import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Jobs"

        return d

    def table(self):
        """Return a table view of the job's prompts.

        Returns
        -------
            Table representation of the job's prompts.

        """
        return self.prompts().to_scenario_list().table()

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> Jobs:
        """Create a Jobs instance from a dictionary."""
        from ..surveys import Survey
        from ..agents import Agent
        from ..language_models import LanguageModel
        from ..scenarios import Scenario

        # Create the base Jobs instance
        job = cls(
            survey=Survey.from_dict(data["survey"]),
            agents=[Agent.from_dict(agent) for agent in data["agents"]],
            models=[LanguageModel.from_dict(model) for model in data["models"]],
            scenarios=[Scenario.from_dict(scenario) for scenario in data["scenarios"]],
        )

        # Restore _post_run_methods if present
        if "_post_run_methods" in data:
            job._post_run_methods = data["_post_run_methods"]

        # Restore _depends_on if present
        if "_depends_on" in data:
            job._depends_on = cls.from_dict(data["_depends_on"])

        return job

    def __eq__(self, other: Jobs) -> bool:
        """Return True if the Jobs instance is the same as another Jobs instance.

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

        scenarios = [
            Scenario({"period": f"morning{addition}"}),
            Scenario({"period": "afternoon"}),
        ]
        scenario_list = ScenarioList(data=scenarios)
        if test_model:
            job = base_survey.by(m).by(scenario_list).by(joy_agent, sad_agent)
        else:
            job = base_survey.by(scenario_list).by(joy_agent, sad_agent)

        assert len(scenario_list) == 2

        return job

    def inspect(self):
        """Create an interactive inspector widget for this job."""
        try:
            from ..widgets.job_inspector import JobInspectorWidget
        except ImportError as e:
            raise ImportError(
                "Job inspector widget is not available. Make sure the widgets module is installed."
            ) from e
        return JobInspectorWidget(self)

    def code(self):
        """Return the code to create this instance."""
        raise JobsImplementationError("Code generation not implemented yet")

    def humanize(
        self,
        project_name: str = "Project",
        scenario_list_method: Optional[
            Literal["randomize", "loop", "single_scenario", "ordered"]
        ] = None,
        survey_description: Optional[str] = None,
        survey_alias: Optional[str] = None,
        survey_visibility: Optional["VisibilityType"] = "unlisted",
        scenario_list_description: Optional[str] = None,
        scenario_list_alias: Optional[str] = None,
        scenario_list_visibility: Optional["VisibilityType"] = "unlisted",
    ):
        """Send the survey and scenario list to Coop.

        Then, create a project on Coop so you can share the survey with human respondents.
        """
        from edsl.coop import Coop
        from edsl.coop.exceptions import CoopValueError

        if len(self.agents) > 0 or len(self.models) > 0:
            raise CoopValueError("We don't support humanize with agents or models yet.")

        if len(self.scenarios) > 0 and scenario_list_method is None:
            raise CoopValueError(
                "You must specify both a scenario list and a scenario list method to use scenarios with your survey."
            )
        elif len(self.scenarios) == 0 and scenario_list_method is not None:
            raise CoopValueError(
                "You must specify both a scenario list and a scenario list method to use scenarios with your survey."
            )
        elif scenario_list_method == "loop":
            questions, long_scenario_list = self.survey.to_long_format(self.scenarios)

            # Replace the questions with new ones from the loop method
            self.survey = Survey(questions)
            self.scenarios = long_scenario_list

            if len(self.scenarios) != 1:
                raise CoopValueError("Something went wrong with the loop method.")
        elif len(self.scenarios) != 1 and scenario_list_method == "single_scenario":
            raise CoopValueError(
                "The single_scenario method requires exactly one scenario. "
                "If you have a scenario list with multiple scenarios, try using the randomize or loop methods."
            )

        if len(self.scenarios) == 0:
            scenario_list = None
        else:
            scenario_list = self.scenarios

        c = Coop()
        project_details = c.create_project(
            self.survey,
            scenario_list,
            scenario_list_method,
            project_name,
            survey_description,
            survey_alias,
            survey_visibility,
            scenario_list_description,
            scenario_list_alias,
            scenario_list_visibility,
        )
        return project_details


def main():
    """Run the module's doctests."""
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
