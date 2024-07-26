"""This module contains the Interview class, which is responsible for conducting an interview asynchronously."""

from __future__ import annotations
import asyncio
import time
import traceback
from typing import Generator, Union

from edsl import CONFIG
from edsl.exceptions import InterviewTimeoutError

# from edsl.questions.QuestionBase import QuestionBase
from edsl.surveys.base import EndOfSurvey
from edsl.jobs.buckets.ModelBuckets import ModelBuckets
from edsl.jobs.interviews.interview_exception_tracking import InterviewExceptionEntry
from edsl.jobs.interviews.retry_management import retry_strategy
from edsl.jobs.tasks.task_status_enum import TaskStatus
from edsl.jobs.tasks.QuestionTaskCreator import QuestionTaskCreator

# from edsl.agents.InvigilatorBase import InvigilatorBase

TIMEOUT = float(CONFIG.get("EDSL_API_TIMEOUT"))


class InterviewTaskBuildingMixin:
    def _build_invigilators(
        self, debug: bool
    ) -> Generator['InvigilatorBase', None, None]:
        """Create an invigilator for each question.

        :param debug: whether to use debug mode, in which case `InvigilatorDebug` is used.

        An invigilator is responsible for answering a particular question in the survey.
        """
        for question in self.survey.questions:
            yield self._get_invigilator(question=question, debug=debug)

    def _get_invigilator(self, question: 'QuestionBase', debug: bool) -> "Invigilator":
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
        return tuple(tasks)  # , invigilators

    def _get_tasks_that_must_be_completed_before(
        self, *, tasks: list[asyncio.Task], question: 'QuestionBase'
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
        question: 'QuestionBase',
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

    @retry_strategy
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
        from edsl.data_transfer_models import AgentResponseDict

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
        except Exception as e:
            raise e
        
    def _add_answer(self, response: 'AgentResponseDict', question: 'QuestionBase') -> None:
        """Add the answer to the answers dictionary.

        :param response: the response to the question.
        :param question: the question that was answered.
        """
        self.answers.add_answer(response=response, question=question)

    def _skip_this_question(self, current_question: 'QuestionBase') -> bool:
        """Determine if the current question should be skipped.

        :param current_question: the question to be answered.
        """
        current_question_index = self.to_index[current_question.question_name]

        answers = self.answers | self.scenario | self.agent["traits"]
        skip = self.survey.rule_collection.skip_question_before_running(
            current_question_index, answers
        )
        return skip

    async def _attempt_to_answer_question(
        self, invigilator: InvigilatorBase, task: asyncio.Task
    ) -> AgentResponseDict:
        """Attempt to answer the question, and handle exceptions.

        :param invigilator: the invigilator that will answer the question.
        :param task: the task that is being run.
        """
        try:
            return await asyncio.wait_for(
                invigilator.async_answer_question(), timeout=TIMEOUT
            )
        except asyncio.TimeoutError as e:
            exception_entry = InterviewExceptionEntry(
                exception=repr(e),
                time=time.time(),
                traceback=traceback.format_exc(),
            )
            if task:
                task.task_status = TaskStatus.FAILED
            self.exceptions.add(invigilator.question.question_name, exception_entry)

            raise InterviewTimeoutError(f"Task timed out after {TIMEOUT} seconds.")
        except Exception as e:
            exception_entry = InterviewExceptionEntry(
                exception=repr(e),
                time=time.time(),
                traceback=traceback.format_exc(),
            )
            if task:
                task.task_status = TaskStatus.FAILED
            self.exceptions.add(invigilator.question.question_name, exception_entry)
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
