"""This module contains the Interview class, which is responsible for conducting an interview asynchronously."""
from __future__ import annotations
import traceback
import asyncio
import time
from typing import Any, Type, List, Generator

from edsl.agents import Agent
from edsl.language_models import LanguageModel
from edsl.scenarios import Scenario
from edsl.surveys import Survey

from edsl.jobs.Answers import Answers
from edsl.surveys.base import EndOfSurvey
from edsl.jobs.buckets.ModelBuckets import ModelBuckets

from edsl.jobs.tasks.TaskCreators import TaskCreators

from edsl.jobs.interviews.InterviewStatusLog import InterviewStatusLog
from edsl.jobs.interviews.interview_exception_tracking import (
    InterviewExceptionCollection,
    InterviewExceptionEntry,
)
from edsl.jobs.interviews.retry_management import retry_strategy
from edsl.jobs.interviews.InterviewTaskBuildingMixin import InterviewTaskBuildingMixin
from edsl.jobs.interviews.InterviewStatusMixin import InterviewStatusMixin


class Interview(InterviewStatusMixin, InterviewTaskBuildingMixin):
    """
    An 'interview' is one agent answering one survey, with one language model, for a given scenario.

    The main method is `async_conduct_interview`, which conducts the interview asynchronously.
    """

    def __init__(
        self,
        agent: Agent,
        survey: Survey,
        scenario: Scenario,
        model: Type[LanguageModel],
        debug: bool = False,
        iteration: int = 0,
        cache=None,
        sidecar_model=None,
    ):
        """Initialize the Interview instance.

        :param agent: the agent being interviewed.
        :param survey: the survey being administered to the agent.
        :param scenario: the scenario that populates the survey questions.
        :param model: the language model used to answer the questions.

        """
        self.agent = agent
        self.survey = survey
        self.scenario = scenario
        self.model = model
        self.debug = debug
        self.iteration = iteration
        self.cache = cache
        # will get filled in as interview progresses
        self.answers: dict[str, str] = Answers()

        # Trackers
        self.task_creators = TaskCreators()  # tracks the task creators
        self.exceptions = InterviewExceptionCollection()
        self._task_status_log_dict = InterviewStatusLog()

        # dictionary mapping question names to their index in the survey."""
        self.to_index = {
            question_name: index
            for index, question_name in enumerate(self.survey.question_names)
        }

    async def async_conduct_interview(
        self,
        *,
        model_buckets: ModelBuckets = None,
        debug: bool = False,
        stop_on_exception: bool = False,
        sidecar_model=None,
    ) -> tuple["Answers", List[dict[str, Any]]]:
        """
        Conduct an Interview asynchronously.

        :param model_buckets: a dictionary of token buckets for the model.
        :param debug: run without calls to LLM.
        :param stop_on_exception: if True, stops the interview if an exception is raised.

        Example usage:

        >>> i = Interview.example()
        >>> answers = asyncio.run(i.async_conduct_interview())
        >>> answers['q0']
        'yes'

        """
        self.sidecar_model = sidecar_model
        # if no model bucket is passed, create an 'infinity' bucket with no rate limits
        model_buckets = model_buckets or ModelBuckets.infinity_bucket()
        # build the tasks using the InterviewTaskBuildingMixin
        self.tasks = self._build_question_tasks(
            debug=debug, model_buckets=model_buckets
        )
        # 'Invigilators' are used to administer the survey
        self.invigilators = list(self._build_invigilators(debug=debug))
        # await the tasks being conducted
        await asyncio.gather(*self.tasks, return_exceptions=not stop_on_exception)
        self.answers.replace_missing_answers_with_none(self.survey)
        valid_results = list(self._extract_valid_results())
        return self.answers, valid_results

    def _extract_valid_results(
        self, print_traceback=False
    ) -> Generator["Answers", None, None]:
        """Extract the valid results from the list of results.

        :param print_traceback: if True, print the traceback of any exceptions.
        """
        # we only need to print the warning once if a task failed.
        # warning_printed = False
        # warning_header = textwrap.dedent(
        #     """\
        #     WARNING: At least one question in the survey was not answered.
        #     """
        # )
        # # there should be one one invigilator for each task
        assert len(self.tasks) == len(self.invigilators)

        for task, invigilator in zip(self.tasks, self.invigilators):
            if task.done():
                try:  # task worked
                    result = task.result()
                except asyncio.CancelledError as e:  # task was cancelled
                    result = invigilator.get_failed_task_result()

                # We don't want to log cancelled tasks, as this is expected behavior
                ## TODO: Currently, we only log errors at the question-answering phase
                ## Do we want to log exceptions here as well?
                #     exception_entry = InterviewExceptionEntry(
                #         exception=repr(e),
                #         time=time.time(),
                #         traceback=traceback.format_exc(),
                #     )
                #     self.exceptions.add(task.edsl_name, exception_entry)
                except Exception as e:  # any other kind of exception in the task
                    exception_entry = InterviewExceptionEntry(
                        exception=repr(e),
                        time=time.time(),
                        traceback=traceback.format_exc(),
                    )
                    self.exceptions.add(task.edsl_name, exception_entry)
                    # if not warning_printed:
                    #     warning_printed = True
                    #     print(warning_header)

                    error_message = f"Task `{task.edsl_name}` failed with `{e.__class__.__name__}`:`{e}`."
                    # print(error_message)
                    # if print_traceback:
                    #    traceback.print_exc()
                    result = invigilator.get_failed_task_result()

                yield result
            else:
                raise ValueError(f"Task {task.edsl_name} is not done.")

    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Return a string representation of the Interview instance."""
        return f"Interview(agent = {self.agent}, survey = {self.survey}, scenario = {self.scenario}, model = {self.model})"


if __name__ == "__main__":
    """Test the Interview class."""
    from edsl.language_models import LanguageModelOpenAIThreeFiveTurbo
    from edsl.agents import Agent
    from edsl.surveys import Survey
    from edsl.scenarios import Scenario
    from edsl.questions import QuestionMultipleChoice

    # from edsl.jobs.Interview import Interview

    #  a survey with skip logic
    q0 = QuestionMultipleChoice(
        question_text="Do you like school?",
        question_options=["yes", "no"],
        question_name="q0",
    )
    q1 = QuestionMultipleChoice(
        question_text="Why not?",
        question_options=["killer bees in cafeteria", "other"],
        question_name="q1",
    )
    q2 = QuestionMultipleChoice(
        question_text="Why?",
        question_options=["**lack*** of killer bees in cafeteria", "other"],
        question_name="q2",
    )
    s = Survey(questions=[q0, q1, q2])
    s = s.add_rule(q0, "q0 == 'yes'", q2)

    # create an interview
    a = Agent(traits=None)

    def direct_question_answering_method(self, question, scenario):
        """Answer a question directly."""
        raise Exception("Error!")
        # return "yes"

    a.add_direct_question_answering_method(direct_question_answering_method)
    scenario = Scenario()
    m = LanguageModelOpenAIThreeFiveTurbo()
    I = Interview(agent=a, survey=s, scenario=scenario, model=m)

    result = asyncio.run(I.async_conduct_interview())
    # # conduct five interviews
    # for _ in range(5):
    #     I.conduct_interview(debug=True)

    # # replace missing answers
    # I
    # repr(I)
    # eval(repr(I))
    # print(I.task_status_logs.status_matrix(20))
    status_matrix = I.task_status_logs.status_matrix(20)
    numerical_matrix = I.task_status_logs.numerical_matrix(20)
    I.task_status_logs.visualize()

    I.exceptions.print()
    I.exceptions.ascii_table()
