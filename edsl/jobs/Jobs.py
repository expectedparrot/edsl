from __future__ import annotations
import asyncio
from collections.abc import Sequence
from itertools import product
from typing import Union
from edsl import CONFIG
from edsl.agents import Agent
from edsl.exceptions import JobsRunError
from edsl.language_models import LanguageModel, LanguageModelOpenAIThreeFiveTurbo
from edsl.language_models import GeminiPro

from edsl.results import Results
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.jobs.base import JobsRunnersRegistry, JobsRunnerDescriptor
from edsl.jobs.Interview import Interview
from edsl.api import JobRunnerAPI, ResultsAPI

from edsl.Base import Base


class Jobs(Base):
    """
    The Jobs class is a collection of agents, scenarios and models and one survey.

    Methods:
    - `by()`: adds agents, scenarios or models to the job. Its a tricksy little method, be careful.
    - `interviews()`: creates a collection of interviews
    - `run()`: runs a collection of interviews

    """

    jobs_runner_name = JobsRunnerDescriptor()

    def __init__(
        self,
        survey: Survey,
        agents: list[Agent] = None,
        models: list[LanguageModel] = None,
        scenarios: list[Scenario] = None,
    ):
        self.survey = survey
        self.agents = agents or []
        self.models = models or []
        self.scenarios = scenarios or []

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
        Adds Agents, Scenarios and LanguageModels to a job. If no objects of this type exist in the Jobs instance, it stores the new objects as a list in the corresponding attribute. Otherwise, it combines the new objects with existing objects using the object's `__add__` method.

        Arguments:
        - objects or a sequence (list, tuple, ...) of objects of the same type

        Notes:
        - all objects must implement the 'get_value', 'set_value', and `__add__` methods
        - agents: traits of new agents are combined with traits of existing agents. New and existing agents should not have overlapping traits, and do not increase the # agents in the instance
        - scenarios: traits of new scenarios are combined with traits of old existing. New scenarios will overwrite overlapping traits, and do not increase the number of scenarios in the instance
        - models: new models overwrite old models.
        """
        # if the first argument is a sequence, grab it and ignore other arguments

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
        def did_user_pass_a_sequence(args):
            """
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

    def _get_current_objects_of_this_type(self, object):
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
    def _merge_objects(passed_objects, current_objects):
        """
        Combines all the existing objects with the new objects
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
        Returns a list of Interviews, that will eventually be used by the JobRunner.
        - Returns one Interview for each combination of Agent, Scenario, and LanguageModel.
        - If any of Agents, Scenarios, or LanguageModels are missing, fills in with defaults. Note that this will change the corresponding class attributes.
        """
        self.agents = self.agents or [Agent()]
        self.models = self.models or [LanguageModelOpenAIThreeFiveTurbo(use_cache=True)]
        self.scenarios = self.scenarios or [Scenario()]
        interviews = []
        for agent, scenario, model in product(self.agents, self.scenarios, self.models):
            interview = Interview(
                survey=self.survey, agent=agent, scenario=scenario, model=model
            )
            interviews.append(interview)
        return interviews

    def run(
        self,
        n: int = 1,
        debug: bool = False,
        verbose: bool = False,
        progress_bar: bool = False,
        dry_run=False,
        streaming=False,
    ) -> Union[Results, ResultsAPI, None]:
        """
        Runs the Job: conducts Interviews and returns their results.
        - `method`: "serial" or "threaded", defaults to "serial"
        - `n`: how many times to run each interview
        - `debug`: prints debug messages
        - `verbose`: prints messages
        - `progress_bar`: shows a progress bar
        """
        # self.job_runner_name = method
        if dry_run:
            self.job_runner_name = "dry_run"
        elif streaming:
            self.job_runner_name = "streaming"
        else:
            self.job_runner_name = "asyncio"

        if (
            emeritus_api_key := CONFIG.get("EMERITUS_API_KEY")
        ) == "local":  # local mode
            return self._run_local(
                n=n, verbose=verbose, debug=debug, progress_bar=progress_bar
            )
        else:
            results = self._run_remote(
                api_key=emeritus_api_key, job_dict=self.to_dict()
            )
        return results

    def _run_local(self, *args, **kwargs):
        """Runs the job locally."""
        JobRunner = JobsRunnersRegistry[self.job_runner_name](jobs=self)
        results = JobRunner.run(*args, **kwargs)
        return results

    def _run_remote(self, *args, **kwargs):
        """Runs the job remotely."""
        results = JobRunnerAPI(*args, **kwargs)
        return results

    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Returns an eval-able string representation of the Jobs instance."""
        return f"Jobs(survey={repr(self.survey)}, agents={repr(self.agents)}, models={repr(self.models)}, scenarios={repr(self.scenarios)})"

    def __len__(self) -> int:
        """Returns the number of questions that will be asked while running this job."""
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
        """Converts the Jobs instance to a dictionary."""
        return {
            "survey": self.survey.to_dict(),
            "agents": [agent.to_dict() for agent in self.agents],
            "models": [model.to_dict() for model in self.models],
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Jobs:
        """Creates a Jobs instance from a JSON string."""
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
            return agent_answers[
                (self.traits["status"], question.question_name, scenario["period"])
            ]

        sad_agent = Agent({"status": "Sad"})
        joy_agent = Agent({"status": "Joyful"})

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
        """Prints a rich representation of the Jobs instance."""
        from rich.table import Table

        table = Table(title="Jobs")
        table.add_column("Jobs")
        table.add_row(self.survey.rich_print())
        return table

    def code(self):
        raise NotImplementedError


def main():
    from edsl.jobs import Jobs

    job = Jobs.example()
    len(job) == 8
    results = job.run(debug=True)
    len(results) == 8
    results


if __name__ == "__main__":
    import doctest

    doctest.testmod()
