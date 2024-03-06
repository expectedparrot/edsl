import asyncio
import enum
from typing import Callable
from collections import UserDict, UserList

from edsl.jobs.buckets import ModelBuckets
from edsl.jobs.token_tracking import TokenUsage
from edsl.questions import Question

from edsl.exceptions import InterviewErrorPriorTaskCanceled


class TaskStatus(enum.Enum):
    "These are the possible statuses for a task."
    NOT_STARTED = enum.auto()
    WAITING_ON_DEPENDENCIES = enum.auto()
    CANCELLED = enum.auto()
    PARENT_FAILED = enum.auto()
    DEPENDENCIES_COMPLETE = enum.auto()
    WAITING_FOR_REQUEST_CAPCITY = enum.auto()
    REQUEST_CAPACITY_ACQUIRED = enum.auto()
    WAITING_FOR_TOKEN_CAPCITY = enum.auto()
    TOKEN_CAPACITY_ACQUIRED = enum.auto()
    API_CALL_IN_PROGRESS = enum.auto()
    API_CALL_COMPLETE = enum.auto()


class InterviewStatusDictionary(UserDict):
    def __init__(self, data=None):
        if data:
            assert all([task_status in data for task_status in TaskStatus])
            super().__init__(data)
        else:
            d = {}
            for task_status in TaskStatus:
                d[task_status] = 0
            d["number_from_cache"] = 0
            super().__init__(d)

    def __add__(
        self, other: "InterviewStatusDictionary"
    ) -> "InterviewStatusDictionary":
        if not isinstance(other, InterviewStatusDictionary):
            raise ValueError(f"Can't add {type(other)} to InterviewStatusDictionary")
        new_dict = {}
        for key in self.keys():
            new_dict[key] = self[key] + other[key]
        return InterviewStatusDictionary(new_dict)

    def __repr__(self):
        return f"InterviewStatusDictionary({self.data})"


# Configure logging
# logging.basicConfig(level=logging.INFO)


class TaskStatusDescriptor:
    def __init__(self):
        self._task_status = None

    def __get__(self, instance, owner):
        return self._task_status

    def __set__(self, instance, value):
        if not isinstance(value, TaskStatus):
            raise ValueError("Value must be an instance of TaskStatus enum")
        # logging.info(f"TaskStatus changed for {instance} from {self._task_status} to {value}")
        self._task_status = value

    def __delete__(self, instance):
        self._task_status = None


class QuestionTaskCreator(UserList):
    """Class to create and manage question tasks with dependencies.
    It is a UserList with all the tasks that must be completed before the focal task can be run.
    When called, it returns an asyncio.Task that depends on the tasks that must be completed before it can be run.
    """

    task_status = TaskStatusDescriptor()

    def __init__(
        self,
        *,
        question: Question,
        answer_question_func: Callable,
        model_buckets: ModelBuckets,
        token_estimator: Callable = None,
    ):
        super().__init__([])
        self.answer_question_func = answer_question_func
        self.question = question

        self.model_buckets = model_buckets
        self.requests_bucket = self.model_buckets.requests_bucket
        self.tokens_bucket = self.model_buckets.tokens_bucket
        self.token_estimator = token_estimator

        self.from_cache = False

        self.cached_token_usage = TokenUsage(from_cache=True)
        self.new_token_usage = TokenUsage(from_cache=False)

        self.task_status = TaskStatus.NOT_STARTED

    def add_dependency(self, task) -> None:
        """Adds a task dependency to the list of dependencies."""
        self.append(task)

    def __repr__(self):
        return f"QuestionTaskCreator for {self.question.question_name}"

    def generate_task(self, debug) -> asyncio.Task:
        """Creates a task that depends on the passed-in dependencies."""
        task = asyncio.create_task(self._run_task_async(debug))
        task.edsl_name = self.question.question_name
        task.depends_on = [x.edsl_name for x in self]
        return task

    def estimated_tokens(self) -> int:
        """Estimates the number of tokens that will be required to run the focal task."""
        token_estimate = self.token_estimator(self.question)
        return token_estimate

    def token_usage(self) -> dict:
        """Returns the token usage for the task."""
        return {
            "cached_tokens": self.cached_token_usage,
            "new_tokens": self.new_token_usage,
        }

    async def _run_focal_task(self, debug) -> "Answers":
        """Runs the focal task i.e., the question that we are interested in answering.
        It is only called after all the dependency tasks are completed.
        """

        requested_tokens = self.estimated_tokens()
        if (estimated_wait_time := self.tokens_bucket.wait_time(requested_tokens)) > 0:
            self.task_status = TaskStatus.WAITING_FOR_TOKEN_CAPCITY

        await self.tokens_bucket.get_tokens(requested_tokens)
        self.task_status = TaskStatus.TOKEN_CAPACITY_ACQUIRED

        if (estimated_wait_time := self.requests_bucket.wait_time(1)) > 0:
            self.waiting = True
            self.task_status = TaskStatus.WAITING_FOR_REQUEST_CAPCITY

        await self.requests_bucket.get_tokens(1)
        self.task_status = TaskStatus.REQUEST_CAPACITY_ACQUIRED

        self.task_status = TaskStatus.API_CALL_IN_PROGRESS
        results = await self.answer_question_func(self.question, debug)
        self.task_status = TaskStatus.API_CALL_COMPLETE

        if "cached_response" in results:
            if results["cached_response"]:
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
        """Runs the task asynchronously, awaiting the tasks that must be completed before this one can be run."""
        # logger.info(f"Running task for {self.question.question_name}")
        try:
            # This is waiting for the tasks that must be completed before this one can be run.
            # This does *not* use the return_exceptions = True flag, so if any of the tasks fail,
            # it throws the exception immediately, which is what we want.
            self.task_status = TaskStatus.WAITING_ON_DEPENDENCIES
            await asyncio.gather(*self)
        except asyncio.CancelledError:
            self.status = TaskStatus.CANCELLED
            # logger.info(f"Task for {self.question.question_name} was cancelled, most likely because it was skipped.")
            raise
        except Exception as e:
            self.task_status = TaskStatus.PARENT_FAILED
            # logger.error(f"Required tasks for {self.question.question_name} failed: {e}")
            # turns the parent exception into a custom exception
            # So the task gets canceled but this InterviewErrorPriorTaskCanceled exception
            # So we never get the question details we need.
            raise InterviewErrorPriorTaskCanceled(
                f"Required tasks failed for {self.question.question_name}"
            ) from e
        else:
            # logger.info(f"Tasks for {self.question.question_name} completed")
            # This is the actual task that we want to run.
            self.task_status = TaskStatus.DEPENDENCIES_COMPLETE
            return await self._run_focal_task(debug)


class TasksList(UserList):
    def status(self, debug=False):
        if debug:
            for task in self:
                print(f"Task {task.edsl_name}")
                print(f"\t DEPENDS ON: {task.depends_on}")
                print(f"\t DONE: {task.done()}")
                print(f"\t CANCELLED: {task.cancelled()}")
                if not task.cancelled():
                    if task.done():
                        print(f"\t RESULT: {task.result()}")
                    else:
                        print(f"\t RESULT: None - Not done yet")

            print("---------------------")
