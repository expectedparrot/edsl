"""This module contains the Interview class, which is responsible for conducting an interview asynchronously."""

from __future__ import annotations
import traceback
import asyncio
import time
from typing import Any, Type, List, Generator, Optional

from edsl.jobs.Answers import Answers
from edsl.surveys.base import EndOfSurvey
from edsl.jobs.buckets.ModelBuckets import ModelBuckets
from edsl.jobs.tasks.TaskCreators import TaskCreators

from edsl.jobs.interviews.InterviewStatusLog import InterviewStatusLog
from edsl.jobs.interviews.interview_exception_tracking import (
    InterviewExceptionCollection,
)
from edsl.jobs.interviews.InterviewExceptionEntry import InterviewExceptionEntry
from edsl.jobs.interviews.retry_management import retry_strategy
from edsl.jobs.interviews.InterviewTaskBuildingMixin import InterviewTaskBuildingMixin
from edsl.jobs.interviews.InterviewStatusMixin import InterviewStatusMixin

import asyncio


def run_async(coro):
    return asyncio.run(coro)


class Interview(InterviewStatusMixin, InterviewTaskBuildingMixin):
    """
    An 'interview' is one agent answering one survey, with one language model, for a given scenario.

    The main method is `async_conduct_interview`, which conducts the interview asynchronously.
    """

    def __init__(
        self,
        agent: "Agent",
        survey: "Survey",
        scenario: "Scenario",
        model: Type["LanguageModel"],
        debug: Optional[bool] = False,
        iteration: int = 0,
        cache: Optional["Cache"] = None,
        sidecar_model: Optional["LanguageModel"] = None,
        skip_retry = False,
    ):
        """Initialize the Interview instance.

        :param agent: the agent being interviewed.
        :param survey: the survey being administered to the agent.
        :param scenario: the scenario that populates the survey questions.
        :param model: the language model used to answer the questions.
        :param debug: if True, run without calls to the language model.
        :param iteration: the iteration number of the interview.
        :param cache: the cache used to store the answers.
        :param sidecar_model: a sidecar model used to answer questions.

        >>> i = Interview.example()
        >>> i.task_creators
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
        self.survey = survey
        self.scenario = scenario
        self.model = model
        self.debug = debug
        self.iteration = iteration
        self.cache = cache
        self.answers: dict[
            str, str
        ] = Answers()  # will get filled in as interview progresses
        self.sidecar_model = sidecar_model

        # Trackers
        self.task_creators = TaskCreators()  # tracks the task creators
        self.exceptions = InterviewExceptionCollection()
        self._task_status_log_dict = InterviewStatusLog()
        self.skip_retry = skip_retry

        # dictionary mapping question names to their index in the survey.
        self.to_index = {
            question_name: index
            for index, question_name in enumerate(self.survey.question_names)
        }

    def _to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the Interview instance.
        This is just for hashing purposes.

        >>> i = Interview.example()
        >>> hash(i)   
        820421918298871814
        """
        return {
            "agent": self.agent._to_dict(),
            "survey": self.survey._to_dict(),
            "scenario": self.scenario._to_dict(),
            "model": self.model._to_dict(),
            "iteration": self.iteration,
            "exceptions": self.exceptions.to_dict(),
         }

    def __hash__(self) -> int:
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self._to_dict())


    async def async_conduct_interview(
        self,
        *,
        model_buckets: ModelBuckets = None,
        debug: bool = False,
        stop_on_exception: bool = False,
        sidecar_model: Optional["LanguageModel"] = None,
    ) -> tuple["Answers", List[dict[str, Any]]]:
        """
        Conduct an Interview asynchronously.
        It returns a tuple with the answers and a list of valid results.

        :param model_buckets: a dictionary of token buckets for the model.
        :param debug: run without calls to LLM.
        :param stop_on_exception: if True, stops the interview if an exception is raised.
        :param sidecar_model: a sidecar model used to answer questions.

        Example usage:

        >>> i = Interview.example()
        >>> result, _ = asyncio.run(i.async_conduct_interview())
        >>> result['q0']
        'yes'

        >>> i = Interview.example(throw_exception = True)
        >>> result, _ = asyncio.run(i.async_conduct_interview())
        Attempt 1 failed with exception:This is a test error now waiting 1.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.
        <BLANKLINE>
        <BLANKLINE>
        Attempt 2 failed with exception:This is a test error now waiting 2.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.
        <BLANKLINE>
        <BLANKLINE>
        Attempt 3 failed with exception:This is a test error now waiting 4.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.
        <BLANKLINE>
        <BLANKLINE>
        Attempt 4 failed with exception:This is a test error now waiting 8.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.
        <BLANKLINE>
        <BLANKLINE>

        >>> i.exceptions
        {'q0': ...
        >>> i = Interview.example()
        >>> result, _ = asyncio.run(i.async_conduct_interview(stop_on_exception = True))
        Traceback (most recent call last):
        ...
        asyncio.exceptions.CancelledError
        """
        self.sidecar_model = sidecar_model

        # if no model bucket is passed, create an 'infinity' bucket with no rate limits
        if model_buckets is None or hasattr(self.agent, "answer_question_directly"):
            model_buckets = ModelBuckets.infinity_bucket()

        ## build the tasks using the InterviewTaskBuildingMixin
        ## This is the key part---it creates a task for each question,
        ## with dependencies on the questions that must be answered before this one can be answered.
        self.tasks = self._build_question_tasks(
            debug=debug, model_buckets=model_buckets
        )

        ## 'Invigilators' are used to administer the survey
        self.invigilators = list(self._build_invigilators(debug=debug))
        # await the tasks being conducted
        await asyncio.gather(*self.tasks, return_exceptions=not stop_on_exception)
        self.answers.replace_missing_answers_with_none(self.survey)
        valid_results = list(self._extract_valid_results())
        return self.answers, valid_results

    def _extract_valid_results(self) -> Generator["Answers", None, None]:
        """Extract the valid results from the list of results.

        It iterates through the tasks and invigilators, and yields the results of the tasks that are done.
        If a task is not done, it raises a ValueError.
        If an exception is raised in the task, it records the exception in the Interview instance except if the task was cancelled, which is expected behavior.

        >>> i = Interview.example()
        >>> result, _ = asyncio.run(i.async_conduct_interview())
        >>> results = list(i._extract_valid_results())
        >>> len(results) == len(i.survey)
        True
        >>> type(results[0])
        <class 'edsl.data_transfer_models.AgentResponseDict'>
        """
        assert len(self.tasks) == len(self.invigilators)

        for task, invigilator in zip(self.tasks, self.invigilators):
            if not task.done():
                raise ValueError(f"Task {task.get_name()} is not done.")

            try:
                result = task.result()
            except asyncio.CancelledError as e:  # task was cancelled
                result = invigilator.get_failed_task_result()
            except Exception as e:  # any other kind of exception in the task
                result = invigilator.get_failed_task_result()
                self._record_exception(task, e)
            yield result

    def _record_exception(self, task, exception: Exception) -> None:
        """Record an exception in the Interview instance.

        It records the exception in the Interview instance, with the task name and the exception entry.

        >>> i = Interview.example()
        >>> result, _ = asyncio.run(i.async_conduct_interview())
        >>> i.exceptions
        {}
        >>> i._record_exception(i.tasks[0], Exception("An exception occurred."))
        >>> i.exceptions
        {'q0': ...
        """
        exception_entry = InterviewExceptionEntry(exception)
        self.exceptions.add(task.get_name(), exception_entry)

    @property
    def dag(self) -> "DAG":
        """Return the directed acyclic graph for the survey.

        The DAG, or directed acyclic graph, is a dictionary that maps question names to their dependencies.
        It is used to determine the order in which questions should be answered.
        This reflects both agent 'memory' considerations and 'skip' logic.
        The 'textify' parameter is set to True, so that the question names are returned as strings rather than integer indices.

        >>> i = Interview.example()
        >>> i.dag == {'q2': {'q0'}, 'q1': {'q0'}}
        True
        """
        return self.survey.dag(textify=True)

    #######################
    # Dunder methods
    #######################
    def __repr__(self) -> str:
        """Return a string representation of the Interview instance."""
        return f"Interview(agent = {repr(self.agent)}, survey = {repr(self.survey)}, scenario = {repr(self.scenario)}, model = {repr(self.model)})"

    def duplicate(self, iteration: int, cache: "Cache") -> Interview:
        """Duplicate the interview, but with a new iteration number and cache.

        >>> i = Interview.example()
        >>> i2 = i.duplicate(1, None)
        >>> i.iteration + 1 == i2.iteration
        True

        """
        return Interview(
            agent=self.agent,
            survey=self.survey,
            scenario=self.scenario,
            model=self.model,
            iteration=iteration,
            cache=cache,
            skip_retry=self.skip_retry,
        )

    @classmethod
    def example(self, throw_exception: bool = False) -> Interview:
        """Return an example Interview instance."""
        from edsl.agents import Agent
        from edsl.surveys import Survey
        from edsl.scenarios import Scenario
        from edsl.language_models import LanguageModel

        def f(self, question, scenario):
            return "yes"

        agent = Agent.example()
        agent.add_direct_question_answering_method(f)
        survey = Survey.example()
        scenario = Scenario.example()
        model = LanguageModel.example()
        if throw_exception:
            model = LanguageModel.example(test_model=True, throw_exception=True)
            agent = Agent.example()
            return Interview(agent=agent, survey=survey, scenario=scenario, model=model)
        return Interview(agent=agent, survey=survey, scenario=scenario, model=model)


if __name__ == "__main__":
    import doctest

    # add ellipsis
    doctest.testmod(optionflags=doctest.ELLIPSIS)
