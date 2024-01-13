from __future__ import annotations
from collections.abc import Sequence
from itertools import product
from typing import Union
from edsl import CONFIG
from edsl.agents import Agent
from edsl.exceptions import JobsRunError
from edsl.language_models import LanguageModel, LanguageModelOpenAIThreeFiveTurbo
from edsl.results import Results
from edsl.scenarios import Scenario
from edsl.surveys import Survey
from edsl.jobs.base import JobsRunnersRegistry
from edsl.jobs.Interview import Interview
from edsl.api import JobRunnerAPI, ResultsAPI


class Jobs:
    """
    The Jobs class is a collection of agents, scenarios and models and one survey.

    Methods:
    - `by()`: adds agents, scenarios or models to the job. Its a tricksy little method, be careful.
    - `interviews()`: creates a collection of interviews
    - `run()`: runs a collection of interviews

    """

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
        if len(args) == 1 and isinstance(args[0], Sequence):
            args = args[0]
        # turn the args tuple or the sequence into a list
        args = list(args)
        # grab the first object
        first_object = args[0]
        # use its `get_value` method to get current objects of this type in the Job instance
        current_objects = first_object.get_value(self)
        # if there are no current objects, just store the new objects
        if not current_objects:
            new_objects = args
        # otherwise, combine the current objects with the new objects
        else:
            new_objects = []
            for current_object in current_objects:
                for new_object in args:
                    # use the __add__ method to combine the objects
                    new_objects.append(current_object + new_object)
        # update the Job instance with the new objects
        first_object.set_value(self, new_objects)
        return self

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
        method: str = "serial",
        n: int = 1,
        debug: bool = False,
        verbose: bool = False,
        progress_bar: bool = False,
    ) -> Union[Results, ResultsAPI]:
        """
        Runs the Job: conducts Interviews and returns their results.
        - `method`: "serial" or "threaded", defaults to "serial"
        - `n`: how many times to run each interview
        - `debug`: prints debug messages
        - `verbose`: prints messages
        - `progress_bar`: shows a progress bar
        """
        # local mode
        if CONFIG.get("EMERITUS_API_KEY") == "local":
            if method not in JobsRunnersRegistry:
                raise JobsRunError(
                    f"Incorrect method '{method}' provided to .run(). "
                    f"Valid methods are: {list(JobsRunnersRegistry.keys())}"
                )
            JobRunner = JobsRunnersRegistry.get(method)(jobs=self)
            try:
                results = JobRunner.run(
                    n=n, verbose=verbose, debug=debug, progress_bar=progress_bar
                )
            except Exception as e:
                raise JobsRunError(f"Error running job. Exception: {e}.")
            return results
        # remote mode
        else:
            results = JobRunnerAPI(
                api_key=CONFIG.get("EMERITUS_API_KEY"), job_dict=self.to_dict()
            )
            return results

    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Returns an eval-able string representation of the Jobs instance."""
        return f"Jobs(survey={self.survey}, agents={self.agents}, models={self.models}, scenarios={self.scenarios})"

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
        ).by(Agent({"status": "Super duper unhappy"}), Agent({"status": "Joyful"}))

        return job


def main():
    from edsl.jobs import Jobs

    job = Jobs.example()
    len(job) == 8
    results = job.run(debug=True)
    len(results) == 8
    results
