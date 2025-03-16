"""
This module provides the QuestionTaskCreator class for executing individual questions as tasks.

The QuestionTaskCreator is responsible for executing a single question within the EDSL system. 
It manages the entire lifecycle of a question task, including dependency resolution, rate 
limiting, token management, execution, and status tracking. It serves as the fundamental 
execution unit in EDSL's task system.
"""

import asyncio
from typing import Callable, Optional, TYPE_CHECKING
from collections import UserList, UserDict

from ..jobs.exceptions import InterviewErrorPriorTaskCanceled
from ..tokens import TokenUsage
from ..data_transfer_models import Answers

from .task_status_enum import TaskStatus, TaskStatusDescriptor
from .task_status_log import TaskStatusLog

if TYPE_CHECKING:
    from ..questions import QuestionBase
    from ..buckets import ModelBuckets


class TokensUsed(UserDict):
    """
    Container for tracking token usage for a task, separating cached and new tokens.
    
    This class provides a structured way to track token usage for a single task,
    distinguishing between tokens reused from cache and tokens freshly generated.
    It uses a UserDict interface for convenient access to the underlying data.
    
    Attributes:
        cached_tokens: TokenUsage object tracking reused tokens from cache
        new_tokens: TokenUsage object tracking freshly generated tokens
    """

    def __init__(self, cached_tokens: TokenUsage, new_tokens: TokenUsage):
        """
        Initialize a TokensUsed container.
        
        Parameters:
            cached_tokens: TokenUsage object for tokens reused from cache
            new_tokens: TokenUsage object for newly generated tokens
        """
        d = {"cached_tokens": cached_tokens, "new_tokens": new_tokens}
        super().__init__(d)


class QuestionTaskCreator(UserList):
    """
    Creates and manages the execution of a single question as an asyncio task.
    
    The QuestionTaskCreator is a fundamental component of EDSL's task system,
    responsible for executing a single question with its dependencies. It extends
    UserList to maintain a list of dependent tasks that must complete before this
    task can execute.
    
    Key responsibilities:
    1. Task Dependency Management - Tracks prerequisite tasks that must complete first
    2. Resource Management - Handles rate limiting and token quota management
    3. Task Status Tracking - Monitors and logs task state transitions
    4. Token Usage Tracking - Records token consumption for both cached and new tokens
    5. Task Execution - Runs the question answering function when dependencies are met
    
    The class follows the state machine pattern, with task_status transitioning through
    various TaskStatus states (NOT_STARTED, WAITING_FOR_DEPENDENCIES, etc.) as execution
    progresses. All status changes are automatically logged to enable detailed analysis
    and visualization.
    
    This class is designed to work with asyncio for concurrent task execution, enabling
    efficient processing of interviews with multiple questions and dependencies.
    """
    task_status = TaskStatusDescriptor()

    def __init__(
        self,
        *,
        question: "QuestionBase",
        answer_question_func: Callable,
        model_buckets: "ModelBuckets",
        token_estimator: Optional[Callable] = None,
        iteration: int = 0,
    ):
        """
        Initialize a QuestionTaskCreator for a specific question.
        
        Parameters:
            question: The Question object to be answered
            answer_question_func: Function that will execute the LLM call to answer the question
            model_buckets: Container for rate limiting buckets (requests and tokens)
            token_estimator: Function to estimate token usage for the question (for quota management)
            iteration: The iteration number of this question (for repeated questions)
            
        Notes:
            - The QuestionTaskCreator starts in the NOT_STARTED state
            - Dependencies can be added after initialization with add_dependency()
            - Token usage is tracked separately for cached vs. new tokens
            - This class works with asyncio for concurrent execution
        """
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
        """Adds a task dependency to the list of dependencies.

        >>> qt1 = QuestionTaskCreator.example()
        >>> qt2 = QuestionTaskCreator.example()
        >>> qt2.add_dependency(qt1)
        >>> len(qt2)
        1
        """
        self.append(task)

    def generate_task(self) -> asyncio.Task:
        """Create a task that depends on the passed-in dependencies."""
        task = asyncio.create_task(
            self._run_task_async(), name=self.question.question_name
        )
        task.depends_on = [t.get_name() for t in self]
        return task

    def estimated_tokens(self) -> int:
        """Estimates the number of tokens that will be required to run the focal task."""
        return self.token_estimator(self.question)

    def token_usage(self) -> TokensUsed:
        """Returns the token usage for the task.

        >>> qt = QuestionTaskCreator.example()
        >>> answers = asyncio.run(qt._run_focal_task())
        >>> qt.token_usage()
        {'cached_tokens': TokenUsage(from_cache=True, prompt_tokens=0, completion_tokens=0), 'new_tokens': TokenUsage(from_cache=False, prompt_tokens=0, completion_tokens=0)}
        """
        return TokensUsed(
            cached_tokens=self.cached_token_usage, new_tokens=self.new_token_usage
        )

    async def _run_focal_task(self) -> Answers:
        """Run the focal task i.e., the question that we are interested in answering.

        It is only called after all the dependency tasks are completed.

        >>> qt = QuestionTaskCreator.example()
        >>> answers = asyncio.run(qt._run_focal_task())
        >>> answers.answer
        'This is an example answer'
        """

        requested_tokens = self.estimated_tokens()
        if (self.tokens_bucket.wait_time(requested_tokens)) > 0:
            self.task_status = TaskStatus.WAITING_FOR_TOKEN_CAPACITY

        await self.tokens_bucket.get_tokens(requested_tokens)

        if self.model_buckets.requests_bucket.wait_time(1) > 0:
            self.waiting = True  #  do we need this?
            self.task_status = TaskStatus.WAITING_FOR_REQUEST_CAPACITY

        await self.model_buckets.requests_bucket.get_tokens(
            1, cheat_bucket_capacity=True
        )

        self.task_status = TaskStatus.API_CALL_IN_PROGRESS
        try:
            results = await self.answer_question_func(
                question=self.question, task=None  # self
            )
            self.task_status = TaskStatus.SUCCESS
        except Exception as e:
            self.task_status = TaskStatus.FAILED
            raise e

        if results.cache_used:
            self.model_buckets.tokens_bucket.add_tokens(requested_tokens)
            self.model_buckets.requests_bucket.add_tokens(1)
            self.from_cache = True
            # Turbo mode means that we don't wait for tokens or requests.
            self.model_buckets.tokens_bucket.turbo_mode_on()
            self.model_buckets.requests_bucket.turbo_mode_on()
        else:
            self.model_buckets.tokens_bucket.turbo_mode_off()
            self.model_buckets.requests_bucket.turbo_mode_off()

        return results

    @classmethod
    def example(cls):
        """Return an example instance of the class."""
        from ..questions import QuestionFreeText
        from ..buckets import ModelBuckets

        m = ModelBuckets.infinity_bucket()

        from collections import namedtuple

        AnswerDict = namedtuple("AnswerDict", ["answer", "cache_used"])
        answer = AnswerDict(answer="This is an example answer", cache_used=False)

        async def answer_question_func(question, task):
            return answer

        return cls(
            question=QuestionFreeText.example(),
            answer_question_func=answer_question_func,
            model_buckets=m,
            token_estimator=None,
            iteration=0,
        )

    async def _run_task_async(self) -> Answers:
        """
        Execute the task with its dependencies in an async workflow.
        
        This method implements the core task execution logic with dependency handling.
        It manages the complete lifecycle of a task:
        
        1. Waiting for dependencies to complete
        2. Handling dependency failures appropriately
        3. Executing the task itself when dependencies are satisfied
        4. Tracking status transitions throughout execution
        
        The method maintains the state machine pattern by updating task_status
        at each stage of execution, allowing for detailed monitoring and visualization
        of task progress.
        
        Returns:
            Answers object containing the question's answer and metadata
            
        Raises:
            asyncio.CancelledError: If the task is cancelled
            InterviewErrorPriorTaskCanceled: If any dependency task fails
            
        Example:
            >>> qt1 = QuestionTaskCreator.example()
            >>> qt2 = QuestionTaskCreator.example()
            >>> qt2.add_dependency(qt1)
        
        Implementation details:
        
        1. Set status to WAITING_FOR_DEPENDENCIES and await all dependencies
           - Using gather with return_exceptions=True allows collecting all results
        
        2. Check dependency results for exceptions:
           - If CancelledError: Set status to CANCELLED and propagate the cancellation
           - If other exception: Set status to PARENT_FAILED and wrap in InterviewErrorPriorTaskCanceled
        
        3. If all dependencies succeed, execute the focal task (_run_focal_task)
           - The focal task handles its own status transitions during execution
        """
        try:
            self.task_status = TaskStatus.WAITING_FOR_DEPENDENCIES
            # If this were set to 'return_exceptions=False', then the first exception would be raised immediately.
            # and it would cancel all the other tasks. This is not the behavior we want.

            gather_results = await asyncio.gather(*self, return_exceptions=True)

            for result in gather_results:
                if isinstance(result, Exception):
                    raise result

        except asyncio.CancelledError:
            self.task_status = TaskStatus.CANCELLED
            raise
        except Exception as e:
            # one of the dependencies failed
            self.task_status = TaskStatus.PARENT_FAILED
            # turns the parent exception into a custom exception so the task gets canceled but this InterviewErrorPriorTaskCanceled exception
            raise InterviewErrorPriorTaskCanceled(
                f"Required tasks failed for {self.question.question_name}"
            ) from e

        # this only runs if all the dependencies are successful
        return await self._run_focal_task()


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
