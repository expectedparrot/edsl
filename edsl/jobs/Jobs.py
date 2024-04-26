# """The Jobs class is a collection of agents, scenarios and models and one survey."""
from __future__ import annotations

import os
from textwrap import dedent
from typing import Optional, Union, Sequence, Generator
from itertools import product

from edsl.config import CONFIG
from edsl import Model
from edsl.agents import Agent
from edsl.Base import Base
from edsl.data.Cache import Cache
from edsl.data.SQLiteDict import SQLiteDict
from edsl.data.CacheHandler import CacheHandler

from edsl.exceptions.jobs import MissingRemoteInferenceError
from edsl.exceptions import MissingAPIKeyError

# from edsl.enums import LanguageModelType
from edsl.jobs.buckets.BucketCollection import BucketCollection
from edsl.jobs.interviews.Interview import Interview
from edsl.results import Results
from edsl.language_models import LanguageModel
from edsl.scenarios import Scenario
from edsl.surveys import Survey


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

        Arguments:
        - objects or a sequence (list, tuple, ...) of objects of the same type

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
        """Return the current objects of the same type as the first argument."""
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
        Return a list of Interviews, that will eventually be used by the JobRunner.

        - Returns one Interview for each combination of Agent, Scenario, and LanguageModel.
        - If any of Agents, Scenarios, or LanguageModels are missing, fills in with defaults. Note that this will change the corresponding class attributes.
        """
        return list(self._create_interviews())

    def _create_interviews(self) -> Generator[Interview, None, None]:
        """
        Generate interviews.

        Note that this sets the agents, model and scenarios if they have not been set. This is a side effect of the method.
        This is useful because a user can create a job without setting the agents, models, or scenarios, and the job will still run,
        with us filling in defaults.
        """
        self.agents = self.agents or [Agent()]
        self.models = self.models or [Model()]
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

    def run(
        self,
        n: int = 1,
        debug: bool = False,
        progress_bar: bool = False,
        stop_on_exception: bool = False,
        cache: Optional[Cache] = None,
        remote: bool = False
        if os.getenv("DEFAULT_RUN_MODE", "local") == "local"
        else True,
        check_api_keys=True,
        sidecar_model=None,
        batch_mode=False,
    ) -> Union[Results, ResultsAPI, None]:
        """
        Runs the Job: conducts Interviews and returns their results.

        :param n: how many times to run each interview
        :param debug: prints debug messages
        :param verbose: prints messages
        :param progress_bar: shows a progress bar
        :param stop_on_exception: stops the job if an exception is raised
        :param cache: a cache object to store results
        :param remote: run the job remotely
        :param check_api_keys: check if the API keys are valid
        :batch_mode: run the job in batch mode i.e., no expecation of interaction with the user

        """
        self.remote = remote

        if self.remote:
            if os.getenv("EXPECTED_PARROT_API_KEY", None) is None:
                raise MissingRemoteInferenceError()

        # only check API keys is the user is not running remotely
        if check_api_keys and not self.remote:
            for model in self.models + [Model()]:
                if not model.has_valid_api_key():
                    raise MissingAPIKeyError(
                        model_name=str(model.model),
                        inference_service=model._inference_service_,
                    )

        if cache is None:
            cache = CacheHandler().get_cache()

        results = self._run_local(
            n=n,
            debug=debug,
            progress_bar=progress_bar,
            cache=cache,
            stop_on_exception=stop_on_exception,
            sidecar_model=sidecar_model,
            batch_mode=batch_mode,
        )

        return results

    def _run_local(self, *args, **kwargs):
        """Run the job locally."""
        from edsl.jobs.runners.JobsRunnerAsyncio import JobsRunnerAsyncio

        results = JobsRunnerAsyncio(self).run(*args, **kwargs)
        return results

    # def _run_remote(self, *args, **kwargs):
    #     """Run the job remotely."""
    #     results = JobRunnerAPI(*args, **kwargs)
    #     return results

    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Return an eval-able string representation of the Jobs instance."""
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))
        return f"Jobs(survey={repr(self.survey)}, agents={repr(self.agents)}, models={repr(self.models)}, scenarios={repr(self.scenarios)})"

    def _repr_html_(self) -> str:
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))

    def __len__(self) -> int:
        """Return the number of questions that will be asked while running this job."""
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
    def to_dict(self) -> dict:
        """Convert the Jobs instance to a dictionary."""
        return {
            "survey": self.survey.to_dict(),
            "agents": [agent.to_dict() for agent in self.agents],
            "models": [model.to_dict() for model in self.models],
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Jobs:
        """Creates a Jobs instance from a dictionary."""
        return cls(
            survey=Survey.from_dict(data["survey"]),
            agents=[Agent.from_dict(agent) for agent in data["agents"]],
            models=[LanguageModel.from_dict(model) for model in data["models"]],
            scenarios=[Scenario.from_dict(scenario) for scenario in data["scenarios"]],
        )

    #######################
    # Example methods
    #######################
    @classmethod
    def example(cls) -> Jobs:
        """Return an example Jobs instance."""
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

    doctest.testmod()
    from edsl.jobs import Jobs

    job = Jobs.example()
    len(job) == 8
    results, info = job.run(debug=True)
    len(results) == 8
    results
