from typing import Callable, Union, List
from collections import UserDict

from edsl.jobs.tokens.TokenUsage import TokenUsage
from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage


class TaskCreators(UserDict):
    """A dictionary of task creators. A task is one question being answered.

    This is used to track the status of the tasks within an interview.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def token_usage(self) -> InterviewTokenUsage:
        """Determines how many tokens were used for the interview.

        This is iterates through all tasks that make up an interview.
        For each task, it determines how many tokens were used and whether they were cached or new.
        It then sums the total number of cached and new tokens used for the interview.

        """
        cached_tokens = TokenUsage(from_cache=True)
        new_tokens = TokenUsage(from_cache=False)
        for task_creator in self.values():
            token_usage = task_creator.token_usage()
            cached_tokens += token_usage["cached_tokens"]
            new_tokens += token_usage["new_tokens"]
        return InterviewTokenUsage(
            new_token_usage=new_tokens, cached_token_usage=cached_tokens
        )

    def print(self) -> None:
        from rich import print

        print({task.get_name(): task.task_status for task in self.values()})

    @property
    def interview_status(self) -> InterviewStatusDictionary:
        """Returns a dictionary, InterviewStatusDictionary, mapping task status codes to counts of tasks in that state.

        >>> t = TaskCreators()
        >>> t.interview_status
        InterviewStatusDictionary({<TaskStatus.NOT_STARTED: 1>: 0, <TaskStatus.WAITING_FOR_DEPENDENCIES: 2>: 0, <TaskStatus.CANCELLED: 3>: 0, <TaskStatus.PARENT_FAILED: 4>: 0, <TaskStatus.WAITING_FOR_REQUEST_CAPACITY: 5>: 0, <TaskStatus.WAITING_FOR_TOKEN_CAPACITY: 6>: 0, <TaskStatus.API_CALL_IN_PROGRESS: 7>: 0, <TaskStatus.SUCCESS: 8>: 0, <TaskStatus.FAILED: 9>: 0, 'number_from_cache': 0})
        """
        status_dict = InterviewStatusDictionary()
        for task_creator in self.values():
            status_dict[task_creator.task_status] += 1
            status_dict["number_from_cache"] += task_creator.from_cache
        return status_dict

    def status_logs(self):
        """Returns a list of status logs for each task."""
        return [task_creator.status_log for task_creator in self.values()]


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
