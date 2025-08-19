"""Survey execution functionality.

This module provides the SurveyExecution class which handles all execution-related logic
for surveys, including job creation, running surveys, and managing execution parameters.
This separation allows for cleaner Survey class code and more focused execution logic.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from .survey import Survey
    from ..agents import Agent, AgentList
    from ..language_models import LanguageModel, ModelList
    from ..scenarios import Scenario, ScenarioList
    from ..caching import Cache
    from ..jobs import Jobs
    from ..results import Results, Result
    from ..buckets.bucket_collection import BucketCollection
    from ..key_management.key_lookup import KeyLookup


class SurveyExecution:
    """Handles execution logic for Survey objects.
    
    This class is responsible for creating Jobs objects, running surveys,
    managing execution parameters, and coordinating with agents, models, and scenarios.
    """
    
    def __init__(self, survey: "Survey"):
        """Initialize the execution handler.
        
        Args:
            survey: The survey to handle execution for.
        """
        self.survey = survey
    
    def by(
        self,
        *args: Union[
            "Agent",
            "Scenario", 
            "LanguageModel",
            "AgentList",
            "ScenarioList",
            "ModelList",
        ],
    ) -> "Jobs":
        """Add components to the survey and return a runnable Jobs object.

        This method is the primary way to prepare a survey for execution. It adds the
        necessary components (agents, scenarios, language models) to create a Jobs object
        that can be run to generate responses to the survey.

        The method can be chained to add multiple components in sequence.

        Args:
            *args: One or more components to add to the survey. Can include:
                - Agent: The persona that will answer the survey questions
                - Scenario: The context for the survey, with variables to substitute
                - LanguageModel: The model that will generate the agent's responses

        Returns:
            Jobs: A Jobs object that can be run to execute the survey.

        Examples:
            Create a runnable Jobs object with an agent and scenario:

            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> exec_handler = SurveyExecution(s)
            >>> from edsl.agents import Agent
            >>> from edsl import Scenario
            >>> exec_handler.by(Agent.example()).by(Scenario.example())
            Jobs(...)

            Chain all components in a single call:

            >>> from edsl.language_models import LanguageModel
            >>> exec_handler.by(Agent.example(), Scenario.example(), LanguageModel.example())
            Jobs(...)
        """
        from edsl.jobs import Jobs

        return Jobs(survey=self.survey).by(*args)

    def to_jobs(self) -> "Jobs":
        """Convert the survey to a Jobs object without adding components.

        This method creates a Jobs object from the survey without adding any agents,
        scenarios, or language models. You'll need to add these components later
        using the `by()` method before running the job.

        Returns:
            Jobs: A Jobs object based on this survey.

        Examples:
            >>> from edsl.surveys.survey import Survey
            >>> s = Survey.example()
            >>> exec_handler = SurveyExecution(s)
            >>> jobs = exec_handler.to_jobs()
            >>> jobs
            Jobs(...)
        """
        from edsl.jobs import Jobs

        return Jobs(survey=self.survey)

    def using(self, obj: Union["Cache", "KeyLookup", "BucketCollection"]) -> "Jobs":
        """Turn the survey into a Job and append the arguments to the Job.
        
        Args:
            obj: The cache, key lookup, or bucket collection to use with the job.
            
        Returns:
            Jobs: A Jobs object configured with the provided object.
        """
        from ..jobs import Jobs

        return Jobs(survey=self.survey).using(obj)

    def get_job(self, model=None, agent=None, **kwargs) -> "Jobs":
        """Create a Jobs object with the specified model, agent, and scenario parameters.
        
        This is a convenience method that creates a complete Jobs object with default
        components if none are provided.
        
        Args:
            model: The language model to use. If None, a default model is created.
            agent: The agent to use. If None, a default agent is created.
            **kwargs: Key-value pairs to use as scenario parameters.
            
        Returns:
            Jobs: A configured Jobs object ready to run.
        """
        if model is None:
            from edsl.language_models.model import Model
            model = Model()

        from edsl.scenarios import Scenario
        s = Scenario(kwargs)

        if not agent:
            from edsl.agents import Agent
            agent = Agent()

        return self.by(s).by(agent).by(model)

    def show_prompts(self):
        """Display the prompts that will be used when running the survey.

        This method converts the survey to a Jobs object and shows the prompts that
        would be sent to a language model. This is useful for debugging and understanding
        how the survey will be presented.

        Returns:
            The detailed prompts for the survey.
        """
        return self.to_jobs().show_prompts()

    def run(self, *args, **kwargs) -> "Results":
        """Convert the survey to a Job and execute it with the provided parameters.

        This method creates a Jobs object from the survey and runs it immediately with
        the provided arguments. It's a convenient way to run a survey without explicitly
        creating a Jobs object first.

        Args:
            *args: Positional arguments passed to the Jobs.run() method.
            **kwargs: Keyword arguments passed to the Jobs.run() method, which can include:
                - cache: The cache to use for storing results
                - verbose: Whether to show detailed progress
                - disable_remote_cache: Whether to disable remote caching
                - disable_remote_inference: Whether to disable remote inference

        Returns:
            Results: The results of running the survey.

        Examples:
            Run a survey with a test language model:

            >>> from edsl.surveys.survey import Survey
            >>> from edsl import QuestionFreeText
            >>> s = Survey([QuestionFreeText.example()])
            >>> exec_handler = SurveyExecution(s)
            >>> from edsl.language_models import LanguageModel
            >>> m = LanguageModel.example(test_model=True, canned_response="Great!")
            >>> results = exec_handler.by(m).run(cache=False, disable_remote_cache=True, disable_remote_inference=True)
            >>> results.select('answer.*')
            Dataset([{'answer.how_are_you': ['Great!']}])
        """
        from ..jobs import Jobs

        return Jobs(survey=self.survey).run(*args, **kwargs)

    def __call__(
        self,
        model=None,
        agent=None,
        cache=None,
        verbose=False,
        disable_remote_cache: bool = False,
        disable_remote_inference: bool = False,
        **kwargs,
    ) -> "Results":
        """Execute the survey with the given parameters and return results.

        This is a convenient shorthand for creating a Jobs object and running it immediately.
        Any keyword arguments are passed as scenario parameters.

        Args:
            model: The language model to use. If None, a default model is used.
            agent: The agent to use. If None, a default agent is used.
            cache: The cache to use for storing results. If None, no caching is used.
            verbose: If True, show detailed progress information.
            disable_remote_cache: If True, don't use remote cache even if available.
            disable_remote_inference: If True, don't use remote inference even if available.
            **kwargs: Key-value pairs to use as scenario parameters.

        Returns:
            Results: The results of running the survey.

        Examples:
            Run a survey with a functional question that uses scenario parameters:

            >>> from edsl.surveys.survey import Survey
            >>> from edsl.questions import QuestionFunctional
            >>> def f(scenario, agent_traits): return "yes" if scenario["period"] == "morning" else "no"
            >>> q = QuestionFunctional(question_name="q0", func=f)
            >>> s = Survey([q])
            >>> exec_handler = SurveyExecution(s)
            >>> exec_handler(period="morning", cache=False, disable_remote_cache=True, disable_remote_inference=True).select("answer.q0").first()
            'yes'
            >>> exec_handler(period="evening", cache=False, disable_remote_cache=True, disable_remote_inference=True).select("answer.q0").first()
            'no'
        """
        return self.get_job(model, agent, **kwargs).run(
            cache=cache,
            verbose=verbose,
            disable_remote_cache=disable_remote_cache,
            disable_remote_inference=disable_remote_inference,
        )

    async def run_async(
        self,
        model: Optional["LanguageModel"] = None,
        agent: Optional["Agent"] = None,
        cache: Optional["Cache"] = None,
        **kwargs,
    ) -> "Results":
        """Execute the survey asynchronously and return results.

        This method provides an asynchronous way to run surveys, which is useful for
        concurrent execution or integration with other async code. It creates a Jobs
        object and runs it asynchronously.

        Args:
            model: The language model to use. If None, a default model is used.
            agent: The agent to use. If None, a default agent is used.
            cache: The cache to use for storing results. If provided, reuses cached results.
            **kwargs: Key-value pairs to use as scenario parameters. May include:
                - disable_remote_inference: If True, don't use remote inference even if available.
                - disable_remote_cache: If True, don't use remote cache even if available.

        Returns:
            Results: The results of running the survey.

        Examples:
            Run a survey asynchronously with morning parameter:

            >>> import asyncio
            >>> from edsl.surveys.survey import Survey
            >>> from edsl.questions import QuestionFunctional
            >>> def f(scenario, agent_traits): return "yes" if scenario["period"] == "morning" else "no"
            >>> q = QuestionFunctional(question_name="q0", func=f)
            >>> from edsl import Model
            >>> s = Survey([q])
            >>> exec_handler = SurveyExecution(s)
            >>> async def test_run_async():
            ...     result = await exec_handler.run_async(period="morning", disable_remote_inference = True)
            ...     print(result.select("answer.q0").first())
            >>> asyncio.run(test_run_async())
            yes

            Run with evening parameter:

            >>> async def test_run_async2():
            ...     result = await exec_handler.run_async(period="evening", disable_remote_inference = True)
            ...     print(result.select("answer.q0").first())
            >>> asyncio.run(test_run_async2())
            no
        """
        # Create a cache if none provided
        if cache is None:
            from edsl.caching import Cache
            c = Cache()
        else:
            c = cache

        # Get scenario parameters, excluding any that will be passed to run_async
        scenario_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k not in ["disable_remote_inference", "disable_remote_cache"]
        }

        # Get the job options to pass to run_async
        job_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k in ["disable_remote_inference", "disable_remote_cache"]
        }

        jobs: "Jobs" = self.get_job(model=model, agent=agent, **scenario_kwargs).using(c)
        return await jobs.run_async(**job_kwargs)

    def gold_standard(self, q_and_a_dict: dict[str, str]) -> "Result":
        """Run the survey with a gold standard agent

        Args:
            q_and_a_dict: A dictionary of question names and answers.

        Returns:
            The results of the survey.
        """
        try:
            assert set(q_and_a_dict.keys()) == set(
                self.survey.question_names
            ), "q_and_a_dict must have the same keys as the survey"
        except AssertionError:
            raise ValueError(
                "q_and_a_dict must have the same keys as the survey",
                set(q_and_a_dict.keys()),
                set(self.survey.question_names),
            )
        from ..agents import Agent
        from ..language_models import Model

        model = Model('test')

        gold_agent = Agent()

        def f(self, question, scenario):
            return q_and_a_dict[question.question_name]

        gold_agent.add_direct_question_answering_method(f)
        return self.by(gold_agent).by(model).run(disable_remote_inference=True)[0]

    @classmethod
    def create_for_survey(cls, survey: "Survey") -> "SurveyExecution":
        """Factory method to create an execution handler for a specific survey.
        
        Args:
            survey: The survey to create an execution handler for.
            
        Returns:
            SurveyExecution: A new execution handler instance for the given survey.
        """
        return cls(survey)
