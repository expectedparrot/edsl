"""This module contains the Interview class, which is responsible for conducting an interview asynchronously."""

from __future__ import annotations
import asyncio
from typing import Any, Type, List, Generator, Optional, Union
import copy

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from edsl import CONFIG
from edsl.surveys.base import EndOfSurvey
from edsl.exceptions import QuestionAnswerValidationError
from edsl.exceptions import QuestionAnswerValidationError
from edsl.data_transfer_models import AgentResponseDict, EDSLResultObjectInput

from edsl.jobs.buckets.ModelBuckets import ModelBuckets
from edsl.jobs.Answers import Answers
from edsl.jobs.tasks.QuestionTaskCreator import QuestionTaskCreator
from edsl.jobs.tasks.TaskCreators import TaskCreators
from edsl.jobs.interviews.InterviewStatusLog import InterviewStatusLog
from edsl.jobs.interviews.InterviewExceptionCollection import (
    InterviewExceptionCollection,
)

# from edsl.jobs.interviews.InterviewStatusMixin import InterviewStatusMixin

from edsl.surveys.base import EndOfSurvey
from edsl.jobs.buckets.ModelBuckets import ModelBuckets
from edsl.jobs.interviews.InterviewExceptionEntry import InterviewExceptionEntry
from edsl.jobs.tasks.task_status_enum import TaskStatus
from edsl.jobs.tasks.QuestionTaskCreator import QuestionTaskCreator


from edsl import Agent, Survey, Scenario, Cache
from edsl.language_models import LanguageModel
from edsl.questions import QuestionBase
from edsl.agents.InvigilatorBase import InvigilatorBase

from edsl.exceptions.language_models import LanguageModelNoResponseError

from edsl.jobs.interviews.InterviewStatusLog import InterviewStatusLog
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage
from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary


from edsl import CONFIG

EDSL_BACKOFF_START_SEC = float(CONFIG.get("EDSL_BACKOFF_START_SEC"))
EDSL_BACKOFF_MAX_SEC = float(CONFIG.get("EDSL_BACKOFF_MAX_SEC"))
EDSL_MAX_ATTEMPTS = int(CONFIG.get("EDSL_MAX_ATTEMPTS"))


class Interview:
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
        raise_validation_errors: bool = True,
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
        self.survey = copy.deepcopy(survey)
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
        self.raise_validation_errors = raise_validation_errors

        # dictionary mapping question names to their index in the survey.
        self.to_index = {
            question_name: index
            for index, question_name in enumerate(self.survey.question_names)
        }

        self.failed_questions = []

    @property
    def has_exceptions(self) -> bool:
        """Return True if there are exceptions."""
        return len(self.exceptions) > 0

    @property
    def task_status_logs(self) -> InterviewStatusLog:
        """Return the task status logs for the interview.

        The keys are the question names; the values are the lists of status log changes for each task.
        """
        for task_creator in self.task_creators.values():
            self._task_status_log_dict[
                task_creator.question.question_name
            ] = task_creator.status_log
        return self._task_status_log_dict

    @property
    def token_usage(self) -> InterviewTokenUsage:
        """Determine how many tokens were used for the interview."""
        return self.task_creators.token_usage

    @property
    def interview_status(self) -> InterviewStatusDictionary:
        """Return a dictionary mapping task status codes to counts."""
        return self.task_creators.interview_status

    # region: Serialization
    def to_dict(self, include_exceptions=True, add_edsl_version=True) -> dict[str, Any]:
        """Return a dictionary representation of the Interview instance.
        This is just for hashing purposes.

        >>> i = Interview.example()
        >>> hash(i)
        1217840301076717434
        """
        d = {
            "agent": self.agent.to_dict(add_edsl_version=add_edsl_version),
            "survey": self.survey.to_dict(add_edsl_version=add_edsl_version),
            "scenario": self.scenario.to_dict(add_edsl_version=add_edsl_version),
            "model": self.model.to_dict(add_edsl_version=add_edsl_version),
            "iteration": self.iteration,
            "exceptions": {},
        }
        if include_exceptions:
            d["exceptions"] = self.exceptions.to_dict()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Interview":
        """Return an Interview instance from a dictionary."""
        agent = Agent.from_dict(d["agent"])
        survey = Survey.from_dict(d["survey"])
        scenario = Scenario.from_dict(d["scenario"])
        model = LanguageModel.from_dict(d["model"])
        iteration = d["iteration"]
        interview = cls(
            agent=agent,
            survey=survey,
            scenario=scenario,
            model=model,
            iteration=iteration,
        )
        if "exceptions" in d:
            exceptions = InterviewExceptionCollection.from_dict(d["exceptions"])
            interview.exceptions = exceptions
        return interview

    def __hash__(self) -> int:
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(include_exceptions=False, add_edsl_version=False))

    def __eq__(self, other: "Interview") -> bool:
        """
        >>> from edsl.jobs.interviews.Interview import Interview; i = Interview.example(); d = i.to_dict(); i2 = Interview.from_dict(d); i == i2
        True
        """
        return hash(self) == hash(other)

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

    def _build_question_tasks(
        self,
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
        return task_creator.generate_task()

    def _get_estimated_request_tokens(self, question) -> float:
        """Estimate the number of tokens that will be required to run the focal task."""
        from edsl.scenarios.FileStore import FileStore

        invigilator = self._get_invigilator(question=question)
        # TODO: There should be a way to get a more accurate estimate.
        combined_text = ""
        file_tokens = 0
        for prompt in invigilator.get_prompts().values():
            if hasattr(prompt, "text"):
                combined_text += prompt.text
            elif isinstance(prompt, str):
                combined_text += prompt
            elif isinstance(prompt, list):
                for file in prompt:
                    if isinstance(file, FileStore):
                        file_tokens += file.size * 0.25
            else:
                raise ValueError(f"Prompt is of type {type(prompt)}")
        return len(combined_text) / 4.0 + file_tokens

    async def _answer_question_and_record_task(
        self,
        *,
        question: "QuestionBase",
        task=None,
    ) -> "AgentResponseDict":
        """Answer a question and records the task."""

        had_language_model_no_response_error = False

        @retry(
            stop=stop_after_attempt(EDSL_MAX_ATTEMPTS),
            wait=wait_exponential(
                multiplier=EDSL_BACKOFF_START_SEC, max=EDSL_BACKOFF_MAX_SEC
            ),
            retry=retry_if_exception_type(LanguageModelNoResponseError),
            reraise=True,
        )
        async def attempt_answer():
            nonlocal had_language_model_no_response_error

            invigilator = self._get_invigilator(question)

            if self._skip_this_question(question):
                return invigilator.get_failed_task_result(
                    failure_reason="Question skipped."
                )

            try:
                response: EDSLResultObjectInput = (
                    await invigilator.async_answer_question()
                )
                if response.validated:
                    self.answers.add_answer(response=response, question=question)
                    self._cancel_skipped_questions(question)
                else:
                    # When a question is not validated, it is not added to the answers.
                    # this should also cancel and dependent children questions.
                    # Is that happening now?
                    if (
                        hasattr(response, "exception_occurred")
                        and response.exception_occurred
                    ):
                        raise response.exception_occurred

            except QuestionAnswerValidationError as e:
                self._handle_exception(e, invigilator, task)
                return invigilator.get_failed_task_result(
                    failure_reason="Question answer validation failed."
                )

            except asyncio.TimeoutError as e:
                self._handle_exception(e, invigilator, task)
                had_language_model_no_response_error = True
                raise LanguageModelNoResponseError(
                    f"Language model timed out for question '{question.question_name}.'"
                )

            except Exception as e:
                self._handle_exception(e, invigilator, task)

            if "response" not in locals():
                had_language_model_no_response_error = True
                raise LanguageModelNoResponseError(
                    f"Language model did not return a response for question '{question.question_name}.'"
                )

            # if it gets here, it means the no response error was fixed
            if (
                question.question_name in self.exceptions
                and had_language_model_no_response_error
            ):
                self.exceptions.record_fixed_question(question.question_name)

            return response

        try:
            return await attempt_answer()
        except RetryError as retry_error:
            # All retries have failed for LanguageModelNoResponseError
            original_error = retry_error.last_attempt.exception()
            self._handle_exception(
                original_error, self._get_invigilator(question), task
            )
            raise original_error  # Re-raise the original error after handling

    def _get_invigilator(self, question: QuestionBase) -> InvigilatorBase:
        """Return an invigilator for the given question.

        :param question: the question to be answered
        :param debug: whether to use debug mode, in which case `InvigilatorDebug` is used.
        """
        invigilator = self.agent.create_invigilator(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=False,
            survey=self.survey,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
            iteration=self.iteration,
            cache=self.cache,
            sidecar_model=self.sidecar_model,
            raise_validation_errors=self.raise_validation_errors,
        )
        """Return an invigilator for the given question."""
        return invigilator

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
        import copy

        # breakpoint()

        answers = copy.copy(self.answers)
        exception_entry = InterviewExceptionEntry(
            exception=e,
            invigilator=invigilator,
            answers=answers,
        )
        if task:
            task.task_status = TaskStatus.FAILED
        self.exceptions.add(invigilator.question.question_name, exception_entry)

        if self.raise_validation_errors:
            if isinstance(e, QuestionAnswerValidationError):
                raise e

        if hasattr(self, "stop_on_exception"):
            stop_on_exception = self.stop_on_exception
        else:
            stop_on_exception = False

        if stop_on_exception:
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
        model_buckets: Optional[ModelBuckets] = None,
        stop_on_exception: bool = False,
        sidecar_model: Optional["LanguageModel"] = None,
        raise_validation_errors: bool = True,
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
        >>> i.exceptions
        {'q0': ...
        >>> i = Interview.example()
        >>> result, _ = asyncio.run(i.async_conduct_interview(stop_on_exception = True))
        Traceback (most recent call last):
        ...
        asyncio.exceptions.CancelledError
        """
        self.sidecar_model = sidecar_model
        self.stop_on_exception = stop_on_exception

        # if no model bucket is passed, create an 'infinity' bucket with no rate limits
        if model_buckets is None or hasattr(self.agent, "answer_question_directly"):
            model_buckets = ModelBuckets.infinity_bucket()

        ## This is the key part---it creates a task for each question,
        ## with dependencies on the questions that must be answered before this one can be answered.
        self.tasks = self._build_question_tasks(model_buckets=model_buckets)

        ## 'Invigilators' are used to administer the survey
        self.invigilators = [
            self._get_invigilator(question) for question in self.survey.questions
        ]
        await asyncio.gather(
            *self.tasks, return_exceptions=not stop_on_exception
        )  # not stop_on_exception)
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
        """
        assert len(self.tasks) == len(self.invigilators)

        for task, invigilator in zip(self.tasks, self.invigilators):
            if not task.done():
                raise ValueError(f"Task {task.get_name()} is not done.")

            try:
                result = task.result()
            except asyncio.CancelledError as e:  # task was cancelled
                result = invigilator.get_failed_task_result(
                    failure_reason="Task was cancelled."
                )
            except Exception as e:  # any other kind of exception in the task
                result = invigilator.get_failed_task_result(
                    failure_reason=f"Task failed with exception: {str(e)}."
                )
                exception_entry = InterviewExceptionEntry(
                    exception=e,
                    invigilator=invigilator,
                )
                self.exceptions.add(task.get_name(), exception_entry)

            yield result

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
