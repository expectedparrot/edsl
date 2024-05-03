import asyncio
from typing import Callable, Union, List
from collections import UserList

from edsl.jobs.buckets import ModelBuckets
from edsl.exceptions import InterviewErrorPriorTaskCanceled

from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary
from edsl.jobs.tasks.task_status_enum import TaskStatus, TaskStatusDescriptor
from edsl.jobs.tasks.task_management import TokensUsed
from edsl.jobs.tasks.TaskStatusLog import TaskStatusLog
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage
from edsl.jobs.tokens.TokenUsage import TokenUsage
from edsl.jobs.Answers import Answers

from edsl.questions.QuestionBase import QuestionBase


class QuestionTaskCreator(UserList):
    """Class to create and manage a single question and its dependencies.

    It is a UserList with all the tasks that must be completed before the focal task can be run.
    """

    task_status = TaskStatusDescriptor()

    def __init__(
        self,
        *,
        question: QuestionBase,
        answer_question_func: Callable,
        model_buckets: ModelBuckets,
        token_estimator: Union[Callable, None] = None,
        iteration: int = 0,
    ):
        super().__init__([])
        self.answer_question_func = answer_question_func
        self.question = question
        self.iteration = iteration

        self.model_buckets = model_buckets
        self.requests_bucket = self.model_buckets.requests_bucket
        self.tokens_bucket = self.model_buckets.tokens_bucket
        self.status_log = TaskStatusLog()

        def fake_token_estimator(question):
            return 1

        self.token_estimator = token_estimator or fake_token_estimator

        # Assume that the task is *not* from the cache until we know otherwise; the _run_focal_task might flip this bit later.
        self.from_cache = False

        self.cached_token_usage = TokenUsage(from_cache=True)
        self.new_token_usage = TokenUsage(from_cache=False)

        self.task_status = TaskStatus.NOT_STARTED

    def add_dependency(self, task: asyncio.Task) -> None:
        """Adds a task dependency to the list of dependencies."""
        self.append(task)

    # def __repr__(self):
    #     return f"QuestionTaskCreator(question = {repr(self.question)})"

    def generate_task(self, debug: bool) -> asyncio.Task:
        """Create a task that depends on the passed-in dependencies."""
        task = asyncio.create_task(
            self._run_task_async(debug), name=self.question.question_name
        )
        #        task.set_name(self.question.question_name)
        task.depends_on = [t.get_name() for t in self]
        return task

    def estimated_tokens(self) -> int:
        """Estimates the number of tokens that will be required to run the focal task."""
        return self.token_estimator(self.question)

    def token_usage(self) -> TokensUsed:
        """Returns the token usage for the task."""
        return TokensUsed(
            cached_tokens=self.cached_token_usage, new_tokens=self.new_token_usage
        )

    async def _run_focal_task(self, debug: bool) -> Answers:
        """Run the focal task i.e., the question that we are interested in answering.

        It is only called after all the dependency tasks are completed.
        """

        requested_tokens = self.estimated_tokens()
        if (estimated_wait_time := self.tokens_bucket.wait_time(requested_tokens)) > 0:
            self.task_status = TaskStatus.WAITING_FOR_TOKEN_CAPACITY

        await self.tokens_bucket.get_tokens(requested_tokens)

        if (estimated_wait_time := self.requests_bucket.wait_time(1)) > 0:
            self.waiting = True
            self.task_status = TaskStatus.WAITING_FOR_REQUEST_CAPACITY

        await self.requests_bucket.get_tokens(1)

        self.task_status = TaskStatus.API_CALL_IN_PROGRESS
        try:
            results = await self.answer_question_func(
                question=self.question, debug=debug, task=None  # self
            )
            self.task_status = TaskStatus.SUCCESS
        except Exception as e:
            self.task_status = TaskStatus.FAILED
            raise e

        if "cached_response" in results:
            if results["cached_response"]:
                # Gives back the tokens b/c the API was not called.
                self.tokens_bucket.add_tokens(requested_tokens)
                self.requests_bucket.add_tokens(1)
                self.from_cache = True

        tracker = self.cached_token_usage if self.from_cache else self.new_token_usage

        # TODO: This is hacky. The 'func' call should return an object that definitely has a 'usage' key.
        usage = results.get("usage", {"prompt_tokens": 0, "completion_tokens": 0})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        tracker.add_tokens(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        )

        return results

    async def _run_task_async(self, debug) -> None:
        """Run the task asynchronously, awaiting the tasks that must be completed before this one can be run.


        The method follows these steps:
            1. Set the task_status to TaskStatus.WAITING_FOR_DEPENDENCIES, indicating that the task is waiting for its dependencies to complete.
            2. Await asyncio.gather(*self, return_exceptions=True) to run all the dependent tasks concurrently.

            - the return_exceptions=True flag ensures that the task does not raise an exception if any of the dependencies fail.

            3. If any of the dependencies raise an exception:
            - If it is a CancelledError, set the current task's task_status to TaskStatus.CANCELLED, and re-raise the CancelledError,
                terminating the execution of the current task.
            - If it is any other exception, set the task_status to TaskStatus.PARENT_FAILED, and raise a custom exception
                InterviewErrorPriorTaskCanceled with the original exception as the cause, terminating the execution of the current task.
            4. If all the dependencies complete successfully without raising any exceptions, the code reaches the else block.
            5. In the else block, run the focal task (self._run_focal_task(debug)).

            If any of the dependencies fail (raise an exception), the focal task will not run. The execution will be terminated,
            and an exception will be raised to indicate the failure of the dependencies.

            The focal task (self._run_focal_task(debug)) is only executed if all the dependencies complete successfully.

            Args:
                debug: A boolean value indicating whether to run the task in debug mode.

            Returns:
                None
        """
        try:
            self.task_status = TaskStatus.WAITING_FOR_DEPENDENCIES
            # If this were set to 'return_exceptions=False', then the first exception would be raised immediately.
            # and it would cancel all the other tasks. This is not the behavior we want.

            gather_results = await asyncio.gather(*self, return_exceptions=True)

            for result in gather_results:
                if isinstance(result, Exception):
                    raise result

            return await self._run_focal_task(debug)

        except asyncio.CancelledError:
            self.task_status = TaskStatus.CANCELLED
            raise
        except Exception as e:
            # one of the dependencies failed
            self.task_status = TaskStatus.PARENT_FAILED
            # turns the parent exception into a custom exception
            # So the task gets canceled but this InterviewErrorPriorTaskCanceled exception
            raise InterviewErrorPriorTaskCanceled(
                f"Required tasks failed for {self.question.question_name}"
            ) from e
        # else:
        # @    # This is the actual task that we want to run.
        #    # it never runs if the dependencies fail
        #    return await self._run_focal_task(debug)


if __name__ == "__main__":
    pass
