"""This module contains the Interview class, which is responsible for conducting an interview asynchronously."""

from __future__ import annotations
import asyncio
from typing import Any, Type, List, Generator, Optional, Union

from edsl import CONFIG

from edsl.surveys.base import EndOfSurvey
from edsl.exceptions import QuestionAnswerValidationError
from edsl.exceptions import InterviewTimeoutError
from edsl.data_transfer_models import AgentResponseDict

from edsl.jobs.FailedQuestion import FailedQuestion
from edsl.jobs.buckets.ModelBuckets import ModelBuckets
from edsl.jobs.Answers import Answers
from edsl.jobs.tasks.QuestionTaskCreator import QuestionTaskCreator
from edsl.jobs.tasks.TaskCreators import TaskCreators
from edsl.jobs.interviews.InterviewStatusLog import InterviewStatusLog
from edsl.jobs.interviews.interview_exception_tracking import (
    InterviewExceptionCollection,
)
from edsl.jobs.interviews.InterviewExceptionEntry import InterviewExceptionEntry
from edsl.jobs.interviews.retry_management import retry_strategy
from edsl.jobs.interviews.InterviewStatusMixin import InterviewStatusMixin

from edsl.surveys.base import EndOfSurvey
from edsl.jobs.buckets.ModelBuckets import ModelBuckets
from edsl.jobs.interviews.InterviewExceptionEntry import InterviewExceptionEntry
from edsl.jobs.interviews.retry_management import retry_strategy
from edsl.jobs.tasks.task_status_enum import TaskStatus
from edsl.jobs.tasks.QuestionTaskCreator import QuestionTaskCreator

from edsl.exceptions import QuestionAnswerValidationError

# from rich.console import Console
# from rich.traceback import Traceback

TIMEOUT = float(CONFIG.get("EDSL_API_TIMEOUT"))


# def run_async(coro):
#    return asyncio.run(coro)

from edsl import Agent, Survey, Scenario, Cache
from edsl.language_models import LanguageModel
from edsl.questions import QuestionBase
from edsl.agents.InvigilatorBase import InvigilatorBase


class Interview(InterviewStatusMixin):
    """
    An 'interview' is one agent answering one survey, with one language model, for a given scenario.

    The main method is `async_conduct_interview`, which conducts the interview asynchronously.
    Most of the class is dedicated to creating the tasks for each question in the survey, and then running them.
    """

    def __init__(
        self,
        agent: Agent,
        survey: Survey,
        scenario: Scenario,
        model: Type["LanguageModel"],
        debug: Optional[bool] = False,
        iteration: int = 0,
        cache: Optional["Cache"] = None,
        sidecar_model: Optional["LanguageModel"] = None,
        skip_retry: bool = False,
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

        self.failed_questions = []

    # region: Serialization
    def _to_dict(self, include_exceptions=False) -> dict[str, Any]:
        """Return a dictionary representation of the Interview instance.
        This is just for hashing purposes.

        >>> i = Interview.example()
        >>> hash(i)
        1646262796627658719
        """
        d = {
            "agent": self.agent._to_dict(),
            "survey": self.survey._to_dict(),
            "scenario": self.scenario._to_dict(),
            "model": self.model._to_dict(),
            "iteration": self.iteration,
            "exceptions": {},
        }
        if include_exceptions:
            d["exceptions"] = self.exceptions.to_dict()

    def __hash__(self) -> int:
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self._to_dict())

    # endregion

    # region: Creating tasks
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

    def _build_invigilators(
        self, debug: bool
    ) -> Generator[InvigilatorBase, None, None]:
        """Create an invigilator for each question.

        :param debug: whether to use debug mode, in which case `InvigilatorDebug` is used.

        An invigilator is responsible for answering a particular question in the survey.
        """
        for question in self.survey.questions:
            yield self._get_invigilator(question=question, debug=debug)

    def _get_invigilator(self, question: QuestionBase, debug: bool) -> InvigilatorBase:
        """Return an invigilator for the given question.

        :param question: the question to be answered
        :param debug: whether to use debug mode, in which case `InvigilatorDebug` is used.
        """
        invigilator = self.agent.create_invigilator(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=debug,
            survey=self.survey,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
            iteration=self.iteration,
            cache=self.cache,
            sidecar_model=self.sidecar_model,
        )
        """Return an invigilator for the given question."""
        return invigilator

    def _build_question_tasks(
        self,
        debug: bool,
        model_buckets: ModelBuckets,
    ) -> list[asyncio.Task]:
        """Create a task for each question, with dependencies on the questions that must be answered before this one can be answered.

        :param debug: whether to use debug mode, in which case `InvigilatorDebug` is used.
        :param model_buckets: the model buckets used to track and control usage rates.
        """
        tasks = []
        for question in self.survey.questions:
            tasks_that_must_be_completed_before = list(
                self._get_tasks_that_must_be_completed_before(
                    tasks=tasks, question=question
                )
            )
            question_task = self._create_question_task(
                question=question,
                tasks_that_must_be_completed_before=tasks_that_must_be_completed_before,
                model_buckets=model_buckets,
                debug=debug,
                iteration=self.iteration,
            )
            tasks.append(question_task)
        return tuple(tasks)

    def _get_tasks_that_must_be_completed_before(
        self, *, tasks: list[asyncio.Task], question: "QuestionBase"
    ) -> Generator[asyncio.Task, None, None]:
        """Return the tasks that must be completed before the given question can be answered.

        :param tasks: a list of tasks that have been created so far.
        :param question: the question for which we are determining dependencies.

        If a question has no dependencies, this will be an empty list, [].
        """
        parents_of_focal_question = self.dag.get(question.question_name, [])
        for parent_question_name in parents_of_focal_question:
            yield tasks[self.to_index[parent_question_name]]

    def _create_question_task(
        self,
        *,
        question: QuestionBase,
        tasks_that_must_be_completed_before: list[asyncio.Task],
        model_buckets: ModelBuckets,
        debug: bool,
        iteration: int = 0,
    ) -> asyncio.Task:
        """Create a task that depends on the passed-in dependencies that are awaited before the task is run.

        :param question: the question to be answered. This is the question we are creating a task for.
        :param tasks_that_must_be_completed_before: the tasks that must be completed before the focal task is run.
        :param model_buckets: the model buckets used to track and control usage rates.
        :param debug: whether to use debug mode, in which case `InvigilatorDebug` is used.
        :param iteration: the iteration number for the interview.

        The task is created by a `QuestionTaskCreator`, which is responsible for creating the task and managing its dependencies.
        It is passed a reference to the function that will be called to answer the question.
        It is passed a list "tasks_that_must_be_completed_before" that are awaited before the task is run.
        These are added as a dependency to the focal task.
        """
        task_creator = QuestionTaskCreator(
            question=question,
            answer_question_func=self._answer_question_and_record_task,
            token_estimator=self._get_estimated_request_tokens,
            model_buckets=model_buckets,
            iteration=iteration,
        )
        for task in tasks_that_must_be_completed_before:
            task_creator.add_dependency(task)

        self.task_creators.update(
            {question.question_name: task_creator}
        )  # track this task creator
        return task_creator.generate_task(debug)

    def _get_estimated_request_tokens(self, question) -> float:
        """Estimate the number of tokens that will be required to run the focal task."""
        invigilator = self._get_invigilator(question=question, debug=False)
        # TODO: There should be a way to get a more accurate estimate.
        combined_text = ""
        for prompt in invigilator.get_prompts().values():
            if hasattr(prompt, "text"):
                combined_text += prompt.text
            elif isinstance(prompt, str):
                combined_text += prompt
            else:
                raise ValueError(f"Prompt is of type {type(prompt)}")
        return len(combined_text) / 4.0

    def create_failed_question(self, invigilator, e) -> FailedQuestion:
        failed_question = FailedQuestion(
            question=invigilator.question,
            scenario=invigilator.scenario,
            model=invigilator.model,
            agent=invigilator.agent,
            raw_model_response=invigilator.raw_model_response,
            exception=e,
            prompts=invigilator.get_prompts(),
        )
        return failed_question

    async def _answer_question_and_record_task(
        self,
        *,
        question: "QuestionBase",
        debug: bool,
        task=None,
    ) -> "AgentResponseDict":
        """Answer a question and records the task.

        This in turn calls the the passed-in agent's async_answer_question method, which returns a response dictionary.
        Note that is updates answers dictionary with the response.
        """

        async def _inner():
            try:
                invigilator = self._get_invigilator(question, debug=debug)

                if self._skip_this_question(question):
                    return invigilator.get_failed_task_result()

                response: AgentResponseDict = await self._attempt_to_answer_question(
                    invigilator, task
                )

                self._add_answer(response=response, question=question)
                self._cancel_skipped_questions(question)
                return AgentResponseDict(**response)
            except QuestionAnswerValidationError as e:
                failed_question = self.create_failed_question(invigilator, e)
                self.failed_questions.append(failed_question)
                raise e
            except Exception as e:
                failed_question = self.create_failed_question(invigilator, e)
                self.failed_questions.append(failed_question)
                raise e

        skip_retry = getattr(self, "skip_retry", False)
        if not skip_retry:

            def retry_if_not_validation_error(func):
                async def wrapper(*args, **kwargs):
                    try:
                        return await func(*args, **kwargs)
                    except QuestionAnswerValidationError:
                        raise  # Do not retry for QuestionAnswerValidationError
                    except Exception as e:
                        return await retry_strategy(func)(
                            *args, **kwargs
                        )  # Retry for other exceptions

                return wrapper

            _inner = retry_if_not_validation_error(_inner)

        return await _inner()

    def _add_answer(
        self, response: "AgentResponseDict", question: "QuestionBase"
    ) -> None:
        """Add the answer to the answers dictionary.

        :param response: the response to the question.
        :param question: the question that was answered.
        """
        self.answers.add_answer(response=response, question=question)

    def _skip_this_question(self, current_question: "QuestionBase") -> bool:
        """Determine if the current question should be skipped.

        :param current_question: the question to be answered.
        """
        current_question_index = self.to_index[current_question.question_name]

        answers = self.answers | self.scenario | self.agent["traits"]
        skip = self.survey.rule_collection.skip_question_before_running(
            current_question_index, answers
        )
        return skip

    def _handle_exception(
        self, e: Exception, invigilator: "InvigilatorBase", task=None
    ):
        exception_entry = InterviewExceptionEntry(
            exception=e,
            failed_question=self.create_failed_question(invigilator, e),
            invigilator=invigilator,
        )
        if task:
            task.task_status = TaskStatus.FAILED
        self.exceptions.add(invigilator.question.question_name, exception_entry)

    async def _attempt_to_answer_question(
        self, invigilator: "InvigilatorBase", task: asyncio.Task
    ) -> "AgentResponseDict":
        """Attempt to answer the question, and handle exceptions.

        :param invigilator: the invigilator that will answer the question.
        :param task: the task that is being run.

        """
        try:
            return await asyncio.wait_for(
                invigilator.async_answer_question(), timeout=TIMEOUT
            )
        except asyncio.TimeoutError as e:
            self._handle_exception(e, invigilator, task)
            raise InterviewTimeoutError(f"Task timed out after {TIMEOUT} seconds.")
        except Exception as e:
            self._handle_exception(e, invigilator, task)
            raise e

    def _cancel_skipped_questions(self, current_question: QuestionBase) -> None:
        """Cancel the tasks for questions that are skipped.

        :param current_question: the question that was just answered.

        It first determines the next question, given the current question and the current answers.
        If the next question is the end of the survey, it cancels all remaining tasks.
        If the next question is after the current question, it cancels all tasks between the current question and the next question.
        """
        current_question_index: int = self.to_index[current_question.question_name]

        next_question: Union[
            int, EndOfSurvey
        ] = self.survey.rule_collection.next_question(
            q_now=current_question_index,
            answers=self.answers | self.scenario | self.agent["traits"],
        )

        next_question_index = next_question.next_q

        def cancel_between(start, end):
            """Cancel the tasks between the start and end indices."""
            for i in range(start, end):
                self.tasks[i].cancel()

        if next_question_index == EndOfSurvey:
            cancel_between(current_question_index + 1, len(self.survey.questions))
            return

        if next_question_index > (current_question_index + 1):
            cancel_between(current_question_index + 1, next_question_index)

    # endregion

    # region: Conducting the interview
    async def async_conduct_interview(
        self,
        *,
        model_buckets: Optional[ModelBuckets] = None,
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
        Attempt 1 failed with exception 'Exception':This is a test error now waiting 1.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.
        <BLANKLINE>
        <BLANKLINE>
        Attempt 2 failed with exception 'Exception':This is a test error now waiting 2.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.
        <BLANKLINE>
        <BLANKLINE>
        Attempt 3 failed with exception 'Exception':This is a test error now waiting 4.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.
        <BLANKLINE>
        <BLANKLINE>
        Attempt 4 failed with exception 'Exception':This is a test error now waiting 8.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.
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

    # endregion

    # region: Extracting results and recording errors
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

                # This is only after the re-tries have failed.
                failed_question = FailedQuestion(
                    question=invigilator.question,
                    scenario=invigilator.scenario,
                    model=invigilator.model,
                    agent=invigilator.agent,
                    raw_model_response=invigilator.raw_model_response,
                    exception=e,
                    prompts=invigilator.get_prompts(),
                )
                self.failed_questions.append(failed_question)
                self._record_exception(
                    task=task,
                    exception=e,
                    failed_question=failed_question,
                    invigilator=invigilator,
                )
            yield result

    def _record_exception(
        self,
        task,
        exception: Exception,
        failed_question: Optional[FailedQuestion],
        invigilator: Optional["Invigilator"],
    ) -> None:
        """Record an exception in the Interview instance.

        It records the exception in the Interview instance, with the task name and the exception entry.

        >>> i = Interview.example()
        >>> result, _ = asyncio.run(i.async_conduct_interview())
        >>> i.exceptions
        {}
        >>> i = Interview.example(throw_exception = True)
        >>> i.skip_retry = True
        >>> result, _ = asyncio.run(i.async_conduct_interview())
        >>> i.exceptions
        {'q0': ...
        """
        exception_entry = InterviewExceptionEntry(
            exception=exception,
            failed_question=failed_question,
            invigilator=invigilator,
        )
        self.exceptions.add(task.get_name(), exception_entry)

    # endregion

    # region: Magic methods
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
