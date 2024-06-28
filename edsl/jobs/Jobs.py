# """The Jobs class is a collection of agents, scenarios and models and one survey."""
from __future__ import annotations
import os
from itertools import product
from typing import Optional, Union, Sequence, Generator
from edsl import Model
from edsl.agents import Agent
from edsl.Base import Base
from edsl.data.Cache import Cache
from edsl.data.CacheHandler import CacheHandler
from edsl.results.Dataset import Dataset

from edsl.exceptions.jobs import MissingRemoteInferenceError
from edsl.exceptions import MissingAPIKeyError
from edsl.jobs.buckets.BucketCollection import BucketCollection
from edsl.jobs.interviews.Interview import Interview
from edsl.language_models import LanguageModel
from edsl.results import Results
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.jobs.runners.JobsRunnerAsyncio import JobsRunnerAsyncio


from edsl.utilities.decorators import add_edsl_version, remove_edsl_version


class Jobs(Base):
    """
    A collection of agents, scenarios and models and one survey.
    The actual running of a job is done by a `JobsRunner`, which is a subclass of `JobsRunner`.
    The `JobsRunner` is chosen by the user, and is stored in the `jobs_runner_name` attribute.
    """

    def __init__(
        self,
        survey: Survey,
        agents: Optional[list[Agent]] = None,
        models: Optional[list[LanguageModel]] = None,
        scenarios: Optional[list[Scenario]] = None,
    ):
        """Initialize a Jobs instance.

        :param survey: the survey to be used in the job
        :param agents: a list of agents
        :param models: a list of models
        :param scenarios: a list of scenarios
        """
        self.survey = survey
        self.agents = agents or []
        self.models = models or []
        self.scenarios = scenarios or []
        self.__bucket_collection = None

    def by(
        self,
        *args: Union[
            Agent,
            Scenario,
            LanguageModel,
            Sequence[Union[Agent, Scenario, LanguageModel]],
        ],
    ) -> Jobs:
        """
        Add Agents, Scenarios and LanguageModels to a job. If no objects of this type exist in the Jobs instance, it stores the new objects as a list in the corresponding attribute. Otherwise, it combines the new objects with existing objects using the object's `__add__` method.

        This 'by' is intended to create a fluent interface.

        >>> from edsl import Survey
        >>> from edsl import QuestionFreeText
        >>> q = QuestionFreeText(question_name="name", question_text="What is your name?")
        >>> j = Jobs(survey = Survey(questions=[q]))
        >>> j
        Jobs(survey=Survey(...), agents=[], models=[], scenarios=[])
        >>> from edsl import Agent; a = Agent(traits = {"status": "Sad"})
        >>> j.by(a).agents
        [Agent(traits = {'status': 'Sad'})]

        :param args: objects or a sequence (list, tuple, ...) of objects of the same type

        Notes:
        - all objects must implement the 'get_value', 'set_value', and `__add__` methods
        - agents: traits of new agents are combined with traits of existing agents. New and existing agents should not have overlapping traits, and do not increase the # agents in the instance
        - scenarios: traits of new scenarios are combined with traits of old existing. New scenarios will overwrite overlapping traits, and do not increase the number of scenarios in the instance
        - models: new models overwrite old models.
        """
        passed_objects = self._turn_args_to_list(args)

        current_objects, objects_key = self._get_current_objects_of_this_type(
            passed_objects[0]
        )

        if not current_objects:
            new_objects = passed_objects
        else:
            new_objects = self._merge_objects(passed_objects, current_objects)

        setattr(self, objects_key, new_objects)  # update the job
        return self

    def prompts(self) -> Dataset:
        """Return a Dataset of prompts that will be used.


        >>> from edsl.jobs import Jobs
        >>> Jobs.example().prompts()
        Dataset([{'interview_index': [0, 0, 1, 1, 2, 2, 3, 3]}, {'question_index': ['how_feeling', 'how_feeling_yesterday', 'how_feeling', 'how_feeling_yesterday', 'how_feeling', 'how_feeling_yesterday', 'how_feeling', 'how_feeling_yesterday']}, {'user_prompt': [Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA')]}, {'scenario_index': [Scenario({'period': 'morning'}), Scenario({'period': 'morning'}), Scenario({'period': 'afternoon'}), Scenario({'period': 'afternoon'}), Scenario({'period': 'morning'}), Scenario({'period': 'morning'}), Scenario({'period': 'afternoon'}), Scenario({'period': 'afternoon'})]}, {'system_prompt': [Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA'), Prompt(text='NA')]}])
        """

        interviews = self.interviews()
        # data = []
        interview_indices = []
        question_indices = []
        user_prompts = []
        system_prompts = []
        scenario_indices = []

        for interview_index, interview in enumerate(interviews):
            invigilators = list(interview._build_invigilators(debug=False))
            for _, invigilator in enumerate(invigilators):
                prompts = invigilator.get_prompts()
                user_prompts.append(prompts["user_prompt"])
                system_prompts.append(prompts["system_prompt"])
                interview_indices.append(interview_index)
                scenario_indices.append(invigilator.scenario)
                question_indices.append(invigilator.question.question_name)
        return Dataset(
            [
                {"interview_index": interview_indices},
                {"question_index": question_indices},
                {"user_prompt": user_prompts},
                {"scenario_index": scenario_indices},
                {"system_prompt": system_prompts},
            ]
        )

    @staticmethod
    def _turn_args_to_list(args):
        """Return a list of the first argument if it is a sequence, otherwise returns a list of all the arguments."""

        def did_user_pass_a_sequence(args):
            """Return True if the user passed a sequence, False otherwise.

            Example:

            >>> did_user_pass_a_sequence([1,2,3])
            True

            >>> did_user_pass_a_sequence(1)
            False
            """
            return len(args) == 1 and isinstance(args[0], Sequence)

        if did_user_pass_a_sequence(args):
            return list(args[0])
        else:
            return list(args)

    def _get_current_objects_of_this_type(
        self, object: Union[Agent, Scenario, LanguageModel]
    ) -> tuple[list, str]:
        """Return the current objects of the same type as the first argument.

        >>> from edsl.jobs import Jobs
        >>> j = Jobs.example()
        >>> j._get_current_objects_of_this_type(j.agents[0])
        ([Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Sad'})], 'agents')
        """
        class_to_key = {
            Agent: "agents",
            Scenario: "scenarios",
            LanguageModel: "models",
        }
        for class_type in class_to_key:
            if isinstance(object, class_type) or issubclass(
                object.__class__, class_type
            ):
                key = class_to_key[class_type]
                break
        else:
            raise ValueError(
                f"First argument must be an Agent, Scenario, or LanguageModel, not {object}"
            )
        current_objects = getattr(self, key, None)
        return current_objects, key

    @staticmethod
    def _merge_objects(passed_objects, current_objects) -> list:
        """
        Combine all the existing objects with the new objects.

        For example, if the user passes in 3 agents,
        and there are 2 existing agents, this will create 6 new agents

        >>> Jobs(survey = [])._merge_objects([1,2,3], [4,5,6])
        [5, 6, 7, 6, 7, 8, 7, 8, 9]
        """
        new_objects = []
        for current_object in current_objects:
            for new_object in passed_objects:
                new_objects.append(current_object + new_object)
        return new_objects

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
            return list(self._create_interviews())

    @classmethod
    def from_interviews(cls, interview_list):
        """Return a Jobs instance from a list of interviews."""
        survey = interview_list[0].survey
        # get all the models
        models = list(set([interview.model for interview in interview_list]))
        jobs = cls(survey)
        jobs.models = models
        jobs._interviews = interview_list
        return jobs

    def _create_interviews(self) -> Generator[Interview, None, None]:
        """
        Generate interviews.

        Note that this sets the agents, model and scenarios if they have not been set. This is a side effect of the method.
        This is useful because a user can create a job without setting the agents, models, or scenarios, and the job will still run,
        with us filling in defaults.
        """
        # if no agents, models, or scenarios are set, set them to defaults
        self.agents = self.agents or [Agent()]
        self.models = self.models or [Model()]
        # if remote, set all the models to remote
        if hasattr(self, "remote") and self.remote:
            for model in self.models:
                model.remote = True
        self.scenarios = self.scenarios or [Scenario()]
        for agent, scenario, model in product(self.agents, self.scenarios, self.models):
            yield Interview(
                survey=self.survey, agent=agent, scenario=scenario, model=model
            )

    def create_bucket_collection(self) -> BucketCollection:
        """
        Create a collection of buckets for each model.

        These buckets are used to track API calls and token usage.

        >>> from edsl.jobs import Jobs
        >>> j = Jobs.example().by(Model(temperature = 1), Model(temperature = 0.5))
        >>> bc = j.create_bucket_collection()
        >>> bc
        BucketCollection(...)
        """
        bucket_collection = BucketCollection()
        for model in self.models:
            bucket_collection.add_model(model)
        return bucket_collection

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

    def _output(self, message) -> None:
        """Check if a Job is verbose. If so, print the message."""
        if self.verbose:
            print(message)

    def run(
        self,
        n: int = 1,
        debug: bool = False,
        progress_bar: bool = False,
        stop_on_exception: bool = False,
        cache: Union[Cache, bool] = None,
        remote: bool = (
            False if os.getenv("DEFAULT_RUN_MODE", "local") == "local" else True
        ),
        check_api_keys: bool = False,
        sidecar_model: Optional[LanguageModel] = None,
        batch_mode: Optional[bool] = None,
        verbose: bool = False,
        print_exceptions=False,
    ) -> Results:
        """
        Runs the Job: conducts Interviews and returns their results.

        :param n: how many times to run each interview
        :param debug: prints debug messages
        :param progress_bar: shows a progress bar
        :param stop_on_exception: stops the job if an exception is raised
        :param cache: a cache object to store results
        :param remote: run the job remotely
        :param check_api_keys: check if the API keys are valid
        :param batch_mode: run the job in batch mode i.e., no expecation of interaction with the user
        :param verbose: prints messages
        """
        from edsl.coop.coop import Coop

        if batch_mode is not None:
            raise NotImplementedError(
                "Batch mode is deprecated. Please update your code to not include 'batch_mode' in the 'run' method."
            )

        self.remote = remote
        self.verbose = verbose

        try:
            coop = Coop()
            remote_cache = coop.edsl_settings["remote_caching"]
        except Exception:
            remote_cache = False

        if self.remote:
            ## TODO: This should be a coop check
            if os.getenv("EXPECTED_PARROT_API_KEY", None) is None:
                raise MissingRemoteInferenceError()

        if not self.remote:
            if check_api_keys:
                for model in self.models + [Model()]:
                    if not model.has_valid_api_key():
                        raise MissingAPIKeyError(
                            model_name=str(model.model),
                            inference_service=model._inference_service_,
                        )

        # handle cache
        if cache is None:
            cache = CacheHandler().get_cache()
        if cache is False:
            cache = Cache()

        if not remote_cache:
            results = self._run_local(
                n=n,
                debug=debug,
                progress_bar=progress_bar,
                cache=cache,
                stop_on_exception=stop_on_exception,
                sidecar_model=sidecar_model,
                print_exceptions=print_exceptions,
            )

            results.cache = cache.new_entries_cache()
        else:
            cache_difference = coop.remote_cache_get_diff(cache.keys())

            client_missing_cacheentries = cache_difference.get(
                "client_missing_cacheentries", []
            )

            missing_entry_count = len(client_missing_cacheentries)
            if missing_entry_count > 0:
                self._output(
                    f"Updating local cache with {missing_entry_count:,} new "
                    f"{'entry' if missing_entry_count == 1 else 'entries'} from remote..."
                )
                cache.add_from_dict(
                    {entry.key: entry for entry in client_missing_cacheentries}
                )
                self._output("Local cache updated!")
            else:
                self._output("No new entries to add to local cache.")

            server_missing_cacheentry_keys = cache_difference.get(
                "server_missing_cacheentry_keys", []
            )
            server_missing_cacheentries = [
                entry
                for key in server_missing_cacheentry_keys
                if (entry := cache.data.get(key)) is not None
            ]
            old_entry_keys = [key for key in cache.keys()]

            self._output("Running job...")
            results = self._run_local(
                n=n,
                debug=debug,
                progress_bar=progress_bar,
                cache=cache,
                stop_on_exception=stop_on_exception,
                sidecar_model=sidecar_model,
                print_exceptions=print_exceptions,
            )
            self._output("Job completed!")

            new_cache_entries = list(
                [entry for entry in cache.values() if entry.key not in old_entry_keys]
            )
            server_missing_cacheentries.extend(new_cache_entries)

            new_entry_count = len(server_missing_cacheentries)
            if new_entry_count > 0:
                self._output(
                    f"Updating remote cache with {new_entry_count:,} new "
                    f"{'entry' if new_entry_count == 1 else 'entries'}..."
                )
                coop.remote_cache_create_many(
                    server_missing_cacheentries, visibility="private"
                )
                self._output("Remote cache updated!")
            else:
                self._output("No new entries to add to remote cache.")

            results.cache = cache.new_entries_cache()

            self._output(
                f"There are {len(results.cache.keys()):,} entries in the local cache."
            )

        return results

    def _run_local(self, *args, **kwargs):
        """Run the job locally."""

        results = JobsRunnerAsyncio(self).run(*args, **kwargs)
        return results

    #######################
    # Dunder methods
    #######################
    def print(self):
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __repr__(self) -> str:
        """Return an eval-able string representation of the Jobs instance."""
        return f"Jobs(survey={repr(self.survey)}, agents={repr(self.agents)}, models={repr(self.models)}, scenarios={repr(self.scenarios)})"

    def _repr_html_(self) -> str:
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

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
    @add_edsl_version
    def to_dict(self) -> dict:
        """Convert the Jobs instance to a dictionary."""
        return {
            "survey": self.survey.to_dict(),
            "agents": [agent.to_dict() for agent in self.agents],
            "models": [model.to_dict() for model in self.models],
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict) -> Jobs:
        """Creates a Jobs instance from a dictionary."""
        return cls(
            survey=Survey.from_dict(data["survey"]),
            agents=[Agent.from_dict(agent) for agent in data["agents"]],
            models=[LanguageModel.from_dict(model) for model in data["models"]],
            scenarios=[Scenario.from_dict(scenario) for scenario in data["scenarios"]],
        )

    def __eq__(self, other: Jobs) -> bool:
        """Return True if the Jobs instance is equal to another Jobs instance."""
        return self.to_dict() == other.to_dict()

    #######################
    # Example methods
    #######################
    @classmethod
    def example(cls, throw_exception_probability=0) -> Jobs:
        """Return an example Jobs instance.

        :param throw_exception_probability: the probability that an exception will be thrown when answering a question. This is useful for testing error handling.

        >>> Jobs.example()
        Jobs(...)

        """
        import random
        from edsl.questions import QuestionMultipleChoice
        from edsl import Agent

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
        base_survey = Survey(questions=[q1, q2])

        job = base_survey.by(
            Scenario({"period": "morning"}), Scenario({"period": "afternoon"})
        ).by(joy_agent, sad_agent)

        return job

    def rich_print(self):
        """Print a rich representation of the Jobs instance."""
        from rich.table import Table

        table = Table(title="Jobs")
        table.add_column("Jobs")
        table.add_row(self.survey.rich_print())
        return table

    def code(self):
        """Return the code to create this instance."""
        raise NotImplementedError


def main():
    """Run the module's doctests."""
    from edsl.jobs import Jobs
    from edsl.data.Cache import Cache

    job = Jobs.example()
    len(job) == 8
    results = job.run(debug=True, cache=Cache())
    len(results) == 8
    results


if __name__ == "__main__":
    """Run the module's doctests."""
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    # from edsl.jobs import Jobs

    # job = Jobs.example()
    # len(job) == 8
    # results, info = job.run(debug=True)
    # len(results) == 8
    # results
