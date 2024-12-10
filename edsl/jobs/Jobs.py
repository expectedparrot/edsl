# """The Jobs class is a collection of agents, scenarios and models and one survey."""
from __future__ import annotations
import warnings
import requests
from typing import Literal, Optional, Union, Sequence, Generator, TYPE_CHECKING

from edsl.Base import Base

from edsl.jobs.buckets.BucketCollection import BucketCollection
from edsl.jobs.JobsPrompts import JobsPrompts
from edsl.jobs.interviews.Interview import Interview
from edsl.jobs.runners.JobsRunnerAsyncio import JobsRunnerAsyncio
from edsl.utilities.decorators import remove_edsl_version

from edsl.data.RemoteCacheSync import RemoteCacheSync
from edsl.exceptions.coop import CoopServerResponseError

if TYPE_CHECKING:
    from edsl.agents.Agent import Agent
    from edsl.agents.AgentList import AgentList
    from edsl.language_models.LanguageModel import LanguageModel
    from edsl.scenarios.Scenario import Scenario
    from edsl.scenarios.ScenarioList import ScenarioList
    from edsl.surveys.Survey import Survey
    from edsl.results.Results import Results
    from edsl.results.Dataset import Dataset
    from edsl.language_models.ModelList import ModelList


class Jobs(Base):
    """
    A collection of agents, scenarios and models and one survey that creates 'interviews'
    """

    __documentation__ = "https://docs.expectedparrot.com/en/latest/jobs.html"

    def __init__(
        self,
        survey: Survey,
        agents: Optional[Union[list[Agent], AgentList]] = None,
        models: Optional[Union[ModelList, list[LanguageModel]]] = None,
        scenarios: Optional[Union[ScenarioList, list[Scenario]]] = None,
    ):
        """Initialize a Jobs instance.

        :param survey: the survey to be used in the job
        :param agents: a list of agents
        :param models: a list of models
        :param scenarios: a list of scenarios
        """
        self.survey = survey
        self.agents: AgentList = agents
        self.scenarios: ScenarioList = scenarios
        self.models = models

        self.__bucket_collection = None

    # these setters and getters are used to ensure that the agents, models, and scenarios
    # are stored as AgentList, ModelList, and ScenarioList objects.

    @property
    def models(self):
        return self._models

    @models.setter
    def models(self, value):
        from edsl import ModelList

        if value:
            if not isinstance(value, ModelList):
                self._models = ModelList(value)
            else:
                self._models = value
        else:
            self._models = ModelList([])

    @property
    def agents(self):
        return self._agents

    @agents.setter
    def agents(self, value):
        from edsl import AgentList

        if value:
            if not isinstance(value, AgentList):
                self._agents = AgentList(value)
            else:
                self._agents = value
        else:
            self._agents = AgentList([])

    @property
    def scenarios(self):
        return self._scenarios

    @scenarios.setter
    def scenarios(self, value):
        from edsl import ScenarioList
        from edsl.results.Dataset import Dataset

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
            Agent,
            Scenario,
            LanguageModel,
            Sequence[Union["Agent", "Scenario", "LanguageModel"]],
        ],
    ) -> Jobs:
        """
        Add Agents, Scenarios and LanguageModels to a job.

        :param args: objects or a sequence (list, tuple, ...) of objects of the same type

        If no objects of this type exist in the Jobs instance, it stores the new objects as a list in the corresponding attribute.
        Otherwise, it combines the new objects with existing objects using the object's `__add__` method.

        This 'by' is intended to create a fluent interface.

        >>> from edsl import Survey
        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText(question_name="name", question_text="What is your name?")
        >>> j = Jobs(survey = Survey(questions=[q]))
        >>> j
        Jobs(survey=Survey(...), agents=AgentList([]), models=ModelList([]), scenarios=ScenarioList([]))
        >>> from edsl import Agent; a = Agent(traits = {"status": "Sad"})
        >>> j.by(a).agents
        AgentList([Agent(traits = {'status': 'Sad'})])


        Notes:
        - all objects must implement the 'get_value', 'set_value', and `__add__` methods
        - agents: traits of new agents are combined with traits of existing agents. New and existing agents should not have overlapping traits, and do not increase the # agents in the instance
        - scenarios: traits of new scenarios are combined with traits of old existing. New scenarios will overwrite overlapping traits, and do not increase the number of scenarios in the instance
        - models: new models overwrite old models.
        """
        from edsl.jobs.JobsComponentConstructor import JobsComponentConstructor

        return JobsComponentConstructor(self).by(*args)

    def prompts(self) -> "Dataset":
        """Return a Dataset of prompts that will be used.


        >>> from edsl.jobs import Jobs
        >>> Jobs.example().prompts()
        Dataset(...)
        """
        return JobsPrompts(self).prompts()

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
        return JobsPrompts(self).estimate_job_cost_from_external_prices(
            price_lookup, iterations
        )

    @staticmethod
    def compute_job_cost(job_results: Results) -> float:
        """
        Computes the cost of a completed job in USD.
        """
        return job_results.compute_job_cost()

    def replace_missing_objects(self) -> None:
        from edsl.agents.Agent import Agent
        from edsl.language_models.registry import Model
        from edsl.scenarios.Scenario import Scenario

        self.agents = self.agents or [Agent()]
        self.models = self.models or [Model()]
        self.scenarios = self.scenarios or [Scenario()]

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
        if hasattr(self, "_interviews"):
            return self._interviews
        else:
            self.replace_missing_objects()
            from edsl.jobs.InterviewsConstructor import InterviewsConstructor

            self._interviews = list(InterviewsConstructor(self).create_interviews())

        return self._interviews

    @classmethod
    def from_interviews(cls, interview_list):
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
        self.replace_missing_objects()  # ensure that all objects are present
        return BucketCollection.from_models(self.models)

    @property
    def bucket_collection(self) -> BucketCollection:
        """Return the bucket collection. If it does not exist, create it."""
        if self.__bucket_collection is None:
            self.__bucket_collection = self.create_bucket_collection()
        return self.__bucket_collection

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
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False))

    def _output(self, message) -> None:
        """Check if a Job is verbose. If so, print the message."""
        if hasattr(self, "verbose") and self.verbose:
            print(message)

    def all_question_parameters(self):
        """Return all the fields in the questions in the survey.
        >>> from edsl.jobs import Jobs
        >>> Jobs.example().all_question_parameters()
        {'period'}
        """
        return set.union(*[question.parameters for question in self.survey.questions])

    def _check_parameters(self, strict=False, warn=False) -> None:
        """Check if the parameters in the survey and scenarios are consistent.

        >>> from edsl import QuestionFreeText
        >>> from edsl import Survey
        >>> from edsl import Scenario
        >>> q = QuestionFreeText(question_text = "{{poo}}", question_name = "ugly_question")
        >>> j = Jobs(survey = Survey(questions=[q]))
        >>> with warnings.catch_warnings(record=True) as w:
        ...     j._check_parameters(warn = True)
        ...     assert len(w) == 1
        ...     assert issubclass(w[-1].category, UserWarning)
        ...     assert "The following parameters are in the survey but not in the scenarios" in str(w[-1].message)

        >>> q = QuestionFreeText(question_text = "{{poo}}", question_name = "ugly_question")
        >>> s = Scenario({'plop': "A", 'poo': "B"})
        >>> j = Jobs(survey = Survey(questions=[q])).by(s)
        >>> j._check_parameters(strict = True)
        Traceback (most recent call last):
        ...
        ValueError: The following parameters are in the scenarios but not in the survey: {'plop'}

        >>> q = QuestionFreeText(question_text = "Hello", question_name = "ugly_question")
        >>> s = Scenario({'ugly_question': "B"})
        >>> j = Jobs(survey = Survey(questions=[q])).by(s)
        >>> j._check_parameters()
        Traceback (most recent call last):
        ...
        ValueError: The following names are in both the survey question_names and the scenario keys: {'ugly_question'}. This will create issues.
        """
        survey_parameters: set = self.survey.parameters
        scenario_parameters: set = self.scenarios.parameters

        msg0, msg1, msg2 = None, None, None

        # look for key issues
        if intersection := set(self.scenarios.parameters) & set(
            self.survey.question_names
        ):
            msg0 = f"The following names are in both the survey question_names and the scenario keys: {intersection}. This will create issues."

            raise ValueError(msg0)

        if in_survey_but_not_in_scenarios := survey_parameters - scenario_parameters:
            msg1 = f"The following parameters are in the survey but not in the scenarios: {in_survey_but_not_in_scenarios}"
        if in_scenarios_but_not_in_survey := scenario_parameters - survey_parameters:
            msg2 = f"The following parameters are in the scenarios but not in the survey: {in_scenarios_but_not_in_survey}"

        if msg1 or msg2:
            message = "\n".join(filter(None, [msg1, msg2]))
            if strict:
                raise ValueError(message)
            else:
                if warn:
                    warnings.warn(message)

        if self.scenarios.has_jinja_braces:
            warnings.warn(
                "The scenarios have Jinja braces ({{ and }}). Converting to '<<' and '>>'. If you want a different conversion, use the convert_jinja_braces method first to modify the scenario."
            )
            self.scenarios = self.scenarios.convert_jinja_braces()

    @property
    def skip_retry(self):
        if not hasattr(self, "_skip_retry"):
            return False
        return self._skip_retry

    @property
    def raise_validation_errors(self):
        if not hasattr(self, "_raise_validation_errors"):
            return False
        return self._raise_validation_errors

    def use_remote_cache(self, disable_remote_cache: bool) -> bool:
        if disable_remote_cache:
            return False
        if not disable_remote_cache:
            try:
                from edsl import Coop

                user_edsl_settings = Coop().edsl_settings
                return user_edsl_settings.get("remote_caching", False)
            except requests.ConnectionError:
                pass
            except CoopServerResponseError as e:
                pass

        return False

    def run(
        self,
        n: int = 1,
        progress_bar: bool = False,
        stop_on_exception: bool = False,
        cache: Union["Cache", bool] = None,
        check_api_keys: bool = False,
        sidecar_model: Optional[LanguageModel] = None,
        verbose: bool = True,
        print_exceptions=True,
        remote_cache_description: Optional[str] = None,
        remote_inference_description: Optional[str] = None,
        remote_inference_results_visibility: Optional[
            Literal["private", "public", "unlisted"]
        ] = "unlisted",
        skip_retry: bool = False,
        raise_validation_errors: bool = False,
        disable_remote_cache: bool = False,
        disable_remote_inference: bool = False,
        bucket_collection: Optional[BucketCollection] = None,
    ) -> Results:
        """
        Runs the Job: conducts Interviews and returns their results.

        :param n: How many times to run each interview
        :param progress_bar: Whether to show a progress bar
        :param stop_on_exception: Stops the job if an exception is raised
        :param cache: A Cache object to store results
        :param check_api_keys: Raises an error if API keys are invalid
        :param verbose: Prints extra messages
        :param remote_cache_description: Specifies a description for this group of entries in the remote cache
        :param remote_inference_description: Specifies a description for the remote inference job
        :param remote_inference_results_visibility: The initial visibility of the Results object on Coop. This will only be used for remote jobs!
        :param disable_remote_cache: If True, the job will not use remote cache. This only works for local jobs!
        :param disable_remote_inference: If True, the job will not use remote inference
        """
        from edsl.coop.coop import Coop
        from edsl.jobs.JobsChecks import JobsChecks
        from edsl.jobs.JobsRemoteInferenceHandler import JobsRemoteInferenceHandler

        self._check_parameters()
        self._skip_retry = skip_retry
        self._raise_validation_errors = raise_validation_errors
        self.verbose = verbose

        jc = JobsChecks(self)

        # check if the user has all the keys they need
        if jc.needs_key_process():
            jc.key_process()

        jh = JobsRemoteInferenceHandler(self, verbose=verbose)
        if jh.use_remote_inference(disable_remote_inference):
            jh.create_remote_inference_job(
                iterations=n,
                remote_inference_description=remote_inference_description,
                remote_inference_results_visibility=remote_inference_results_visibility,
            )
            results = jh.poll_remote_inference_job()
            return results

        if check_api_keys:
            jc.check_api_keys()

        # handle cache
        if cache is None or cache is True:
            from edsl.data.CacheHandler import CacheHandler

            cache = CacheHandler().get_cache()
        if cache is False:
            from edsl.data.Cache import Cache

            cache = Cache()

        if bucket_collection is None:
            bucket_collection = self.create_bucket_collection()

        remote_cache = self.use_remote_cache(disable_remote_cache)
        with RemoteCacheSync(
            coop=Coop(),
            cache=cache,
            output_func=self._output,
            remote_cache=remote_cache,
            remote_cache_description=remote_cache_description,
        ) as r:
            results = self._run_local(
                n=n,
                progress_bar=progress_bar,
                cache=cache,
                stop_on_exception=stop_on_exception,
                sidecar_model=sidecar_model,
                print_exceptions=print_exceptions,
                raise_validation_errors=raise_validation_errors,
                bucket_collection=bucket_collection,
            )
        return results

    async def run_async(
        self,
        cache=None,
        n=1,
        disable_remote_inference: bool = False,
        remote_inference_description: Optional[str] = None,
        remote_inference_results_visibility: Optional[
            Literal["private", "public", "unlisted"]
        ] = "unlisted",
        bucket_collection: Optional[BucketCollection] = None,
        **kwargs,
    ):
        """Run the job asynchronously, either locally or remotely.

        :param cache: Cache object or boolean
        :param n: Number of iterations
        :param disable_remote_inference: If True, forces local execution
        :param remote_inference_description: Description for remote jobs
        :param remote_inference_results_visibility: Visibility setting for remote results
        :param kwargs: Additional arguments passed to local execution
        :return: Results object
        """
        # Check if we should use remote inference
        from edsl.jobs.JobsRemoteInferenceHandler import JobsRemoteInferenceHandler

        jh = JobsRemoteInferenceHandler(self, verbose=False)
        if jh.use_remote_inference(disable_remote_inference):
            results = await jh.create_and_poll_remote_job(
                iterations=n,
                remote_inference_description=remote_inference_description,
                remote_inference_results_visibility=remote_inference_results_visibility,
            )
            return results

        if bucket_collection is None:
            bucket_collection = self.create_bucket_collection()

        # If not using remote inference, run locally with async
        return await JobsRunnerAsyncio(
            self, bucket_collection=bucket_collection
        ).run_async(cache=cache, n=n, **kwargs)

    def _run_local(self, bucket_collection, *args, **kwargs):
        """Run the job locally."""

        results = JobsRunnerAsyncio(self, bucket_collection=bucket_collection).run(
            *args, **kwargs
        )
        return results

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
        """Return the maximum number of questions that will be asked while running this job.
        Note that this is the maximum number of questions, not the actual number of questions that will be asked, as some questions may be skipped.

        >>> from edsl.jobs import Jobs
        >>> len(Jobs.example())
        8
        """
        number_of_questions = (
            len(self.agents or [1])
            * len(self.scenarios or [1])
            * len(self.models or [1])
            * len(self.survey)
        )
        return number_of_questions

    #######################
    # Serialization methods
    #######################

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
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Jobs"

        return d

    def table(self):
        return self.prompts().to_scenario_list().table()

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> Jobs:
        """Creates a Jobs instance from a dictionary."""
        from edsl import Survey
        from edsl.agents.Agent import Agent
        from edsl.language_models.LanguageModel import LanguageModel
        from edsl.scenarios.Scenario import Scenario

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

    #######################
    # Example methods
    #######################
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
        from edsl.questions import QuestionMultipleChoice
        from edsl.agents.Agent import Agent
        from edsl.scenarios.Scenario import Scenario

        addition = "" if not randomize else str(uuid4())

        if test_model:
            from edsl.language_models import LanguageModel

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
                raise Exception("Error!")
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
        from edsl import Survey, ScenarioList

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

    # def rich_print(self):
    #     """Print a rich representation of the Jobs instance."""
    #     from rich.table import Table

    #     table = Table(title="Jobs")
    #     table.add_column("Jobs")
    #     table.add_row(self.survey.rich_print())
    #     return table

    def code(self):
        """Return the code to create this instance."""
        raise NotImplementedError


def main():
    """Run the module's doctests."""
    from edsl.jobs import Jobs
    from edsl.data.Cache import Cache

    job = Jobs.example()
    len(job) == 8
    results = job.run(cache=Cache())
    len(results) == 8
    results


if __name__ == "__main__":
    """Run the module's doctests."""
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
