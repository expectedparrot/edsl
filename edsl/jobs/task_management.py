import asyncio
import enum
from typing import Callable, Union, List
from collections import UserDict, UserList

from edsl import CONFIG
from edsl.jobs.buckets import ModelBuckets
from edsl.jobs.token_tracking import TokenUsage
from edsl.questions import Question
from edsl.exceptions import InterviewErrorPriorTaskCanceled
from edsl.jobs.token_tracking import TokenUsage, InterviewTokenUsage

# from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, AsyncRetrying, before_sleep
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    before_sleep,
)

class TokensUsed(UserDict):
    """"Container for tokens used by a task."""
    def __init__(self, cached_tokens, new_tokens):
        d = {'cached_tokens': cached_tokens, 'new_tokens': new_tokens}
        super().__init__(d)

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
    FINISHED = enum.auto()


class InterviewStatusDictionary(UserDict):
    """A dictionary that keeps track of the status of all the tasks in an interview."""

    def __init__(self, data: Union[List[TaskStatus], None] = None):
        if data:
            # checks to make sure every task status is in the enum
            assert all([task_status in data for task_status in TaskStatus])
            super().__init__(data)
        else:
            # sets all the task statuses to 0
            d = {}
            for task_status in TaskStatus:
                d[task_status] = 0
            d["number_from_cache"] = 0
            super().__init__(d)

    def __add__(
        self, 
        other: "InterviewStatusDictionary"
    ) -> "InterviewStatusDictionary":
        """Adds two InterviewStatusDictionaries together."""
        if not isinstance(other, InterviewStatusDictionary):
            raise ValueError(f"Can't add {type(other)} to InterviewStatusDictionary")
        new_dict = {}
        for key in self.keys():
            new_dict[key] = self[key] + other[key]
        return InterviewStatusDictionary(new_dict)

    @property 
    def waiting(self) -> int:
        """Return the number of tasks that are in a waiting status of some kind."""
    
        waiting_status_list = [
            TaskStatus.WAITING_FOR_REQUEST_CAPCITY, 
            TaskStatus.WAITING_FOR_TOKEN_CAPCITY,
            TaskStatus.WAITING_ON_DEPENDENCIES]
        
        return sum([self[status] for status in waiting_status_list])
    
    def __repr__(self):
        return f"InterviewStatusDictionary({self.data})"


class TaskStatusDescriptor:
    "The descriptor ensures that the task status is always an instance of the TaskStatus enum."

    def __init__(self):
        self._task_status = None

    def __get__(self, instance, owner):
        return self._task_status

    def __set__(self, instance, value):
        """Ensure that the value is an instance of TaskStatus."""
        if not isinstance(value, TaskStatus):
            raise ValueError("Value must be an instance of TaskStatus enum")
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

        def fake_token_estimator(question):
            return 1

        self.token_estimator = token_estimator or fake_token_estimator

        # Assume that the task is *not* from the cache until we know otherwise.
        # the _run_focal_task might flip this bit later.
        self.from_cache = False

        self.cached_token_usage = TokenUsage(from_cache=True)
        self.new_token_usage = TokenUsage(from_cache=False)

        self.task_status = TaskStatus.NOT_STARTED

    def add_dependency(self, task: asyncio.Task) -> None:
        """Adds a task dependency to the list of dependencies."""
        self.append(task)

    def __repr__(self):
        return f"QuestionTaskCreator(question = {repr(self.question)})"

    def generate_task(self, debug) -> asyncio.Task:
        """Creates a task that depends on the passed-in dependencies."""
        task = asyncio.create_task(self._run_task_async(debug))
        # TODO: This is a bit hacky. 
        task.edsl_name = self.question.question_name
        task.depends_on = [x.edsl_name for x in self]
        return task

    def estimated_tokens(self) -> int:
        """Estimates the number of tokens that will be required to run the focal task."""
        return self.token_estimator(self.question)

    def token_usage(self) -> TokensUsed:
        """Returns the token usage for the task."""
        #return {'cached_tokens': self.cached_token_usage, 'new_tokens': self.new_token_usage}
        return TokensUsed(cached_tokens = self.cached_token_usage, 
                          new_tokens = self.new_token_usage)

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
        self.task_status = TaskStatus.FINISHED

        return results

    async def _run_task_async(self, debug) -> None:
        """Runs the task asynchronously, awaiting the tasks that must be completed before this one can be run.
                
        """
        # logger.info(f"Running task for {self.question.question_name}")
        try:
            # This is waiting for the tasks that must be completed before this one can be run.
            # This does *not* use the return_exceptions = True flag, so if any of the tasks fail,
            # it throws the exception immediately, which is what we want.
            self.task_status = TaskStatus.WAITING_ON_DEPENDENCIES
            # The 'self' here is a list of tasks that must be completed before this one can be run.
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


class TaskCreators(UserDict):
    "A dictionary of task creators"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def token_usage(self) -> InterviewTokenUsage:
        """Determins how many tokens were used for the interview."""
        cached_tokens = TokenUsage(from_cache=True)
        new_tokens = TokenUsage(from_cache=False)
        for task_creator in self.values():
            token_usage = task_creator.token_usage()
            cached_tokens += token_usage["cached_tokens"]
            new_tokens += token_usage["new_tokens"]
        return InterviewTokenUsage(
            new_token_usage=new_tokens, cached_token_usage=cached_tokens
        )

    @property
    def interview_status(self) -> InterviewStatusDictionary:
        """Returns a dictionary, InterviewStatusDictionary, mapping task status codes to counts of tasks in that state."""
        status_dict = InterviewStatusDictionary()
        for task_creator in self.values():
            status_dict[task_creator.task_status] += 1
            status_dict["number_from_cache"] += task_creator.from_cache
        return status_dict


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


#from edsl.config import Config

EDSL_BACKOFF_START_SEC = float(CONFIG.get("EDSL_BACKOFF_START_SEC"))
EDSL_MAX_BACKOFF_SEC = float(CONFIG.get("EDSL_MAX_BACKOFF_SEC"))
EDSL_MAX_ATTEMPTS = int(CONFIG.get("EDSL_MAX_ATTEMPTS"))


def print_retry(retry_state):
    "Prints details on tenacity retries."
    attempt_number = retry_state.attempt_number
    exception = retry_state.outcome.exception()
    wait_time = retry_state.next_action.sleep
    print(
        f"Attempt {attempt_number} failed with exception: {exception}; "
        f"now waiting {wait_time:.2f} seconds before retrying."
    )


retry_strategy = retry(
    wait=wait_exponential(
        multiplier=EDSL_BACKOFF_START_SEC, max=EDSL_MAX_BACKOFF_SEC
    ),  # Exponential back-off starting at 1s, doubling, maxing out at 60s
    stop=stop_after_attempt(EDSL_MAX_ATTEMPTS),  # Stop after 5 attempts
    # retry=retry_if_exception_type(Exception),  # Customize this as per your specific retry-able exception
    before_sleep=print_retry,  # Use custom print function for retries
)
