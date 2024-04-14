"""This module contains the Interview class, which is responsible for conducting an interview asynchronously."""

from __future__ import annotations
import asyncio
import time
import traceback
from typing import Generator
from edsl import CONFIG
from edsl.exceptions import InterviewTimeoutError
from edsl.data_transfer_models import AgentResponseDict
from edsl.questions.QuestionBase import QuestionBase
from edsl.surveys.base import EndOfSurvey
from edsl.jobs.buckets.ModelBuckets import ModelBuckets
from edsl.jobs.interviews.interview_exception_tracking import InterviewExceptionEntry
from edsl.jobs.interviews.retry_management import retry_strategy
from edsl.jobs.tasks.task_status_enum import TaskStatus
from edsl.jobs.tasks.TasksList import TasksList
from edsl.jobs.tasks.QuestionTaskCreator import QuestionTaskCreator
from edsl.data.Cache import Cache

TIMEOUT = float(CONFIG.get("EDSL_API_TIMEOUT"))


class InterviewTaskBuildingMixin:
    def _build_invigilators(self, debug: bool) -> Generator["Invigilator", None, None]:
        """Create an invigilator for each question."""
        for question in self.survey.questions:
            yield self.get_invigilator(question=question, debug=debug)

    def get_invigilator(self, question: QuestionBase, debug: bool) -> "Invigilator":
        """Return an invigilator for the given question."""
        invigilator = self.agent.create_invigilator(
            question=question,
            scenario=self.scenario,
            model=self.model,
            debug=debug,
            memory_plan=self.survey.memory_plan,
            current_answers=self.answers,
            iteration=self.iteration,
            cache=self.cache,
            sidecar_model=self.sidecar_model,
        )
        """Return an invigilator for the given question."""
        return invigilator

    @property
    def dag(self) -> "DAG":
        """Return the directed acyclic graph for the survey.

        The DAG, or directed acyclic graph, is a dictionary that maps question names to their dependencies.
        It is used to determine the order in which questions should be answered.
        This reflects both agent 'memory' considerations and 'skip' logic.
        The 'textify' parameter is set to True, so that the question names are returned as strings rather than integer indices.
        """
        return self.survey.dag(textify=True)

    def _build_question_tasks(
        self,
        debug: bool,
        model_buckets: ModelBuckets,
    ) -> list[asyncio.Task]:
        """Create a task for each question, with dependencies on the questions that must be answered before this one can be answered."""
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
        return TasksList(tasks)  # , invigilators

    def _get_tasks_that_must_be_completed_before(
        self, *, tasks: list[asyncio.Task], question: QuestionBase
    ) -> Generator[asyncio.Task, None, None]:
        """Return the tasks that must be completed before the given question can be answered.

        If a question has no dependencies, this will be an empty list, [].
        """
        parents_of_focal_question = self.dag.get(question.question_name, [])
        for parent_question_name in parents_of_focal_question:
            parent_index = self.to_index[parent_question_name]
            parent_task = tasks[parent_index]
            yield parent_task

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

        The task is created by a QuestionTaskCreator, which is responsible for creating the task and managing its dependencies.
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
        invigilator = self.get_invigilator(question=question, debug=False)
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
        question: QuestionBase,
        debug: bool,
        task=None,
    ) -> AgentResponseDict:
        """Answer a question and records the task.

        This in turn calls the the passed-in agent's async_answer_question method, which returns a response dictionary.
        Note that is updates answers with the response.
        """
        invigilator = self.get_invigilator(question, debug=debug)

        async def attempt_to_answer_question(invigilator):
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
                self.exceptions.add(question.question_name, exception_entry)

                raise InterviewTimeoutError(f"Task timed out after {TIMEOUT} seconds.")
            except Exception as e:
                exception_entry = InterviewExceptionEntry(
                    exception=repr(e),
                    time=time.time(),
                    traceback=traceback.format_exc(),
                )
                if task:
                    task.task_status = TaskStatus.FAILED
                self.exceptions.add(question.question_name, exception_entry)
                raise e

        response: AgentResponseDict = await attempt_to_answer_question(invigilator)

        self.answers.add_answer(response=response, question=question)
        self._cancel_skipped_questions(question)

        return AgentResponseDict(**response)

    def _cancel_skipped_questions(self, current_question: Question) -> None:
        """Cancel the tasks for questions that are skipped.

        It first determines the next question, given the current question and the current answers.
        If the next question is the end of the survey, it cancels all remaining tasks.
        If the next question is after the current question, it cancels all tasks between the current question and the next question.
        """
        current_question_index = self.to_index[current_question.question_name]
        next_question = self.survey.rule_collection.next_question(
            q_now=current_question_index, answers=self.answers
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
