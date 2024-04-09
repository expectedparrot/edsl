from typing import Callable, Union, List
from collections import UserDict

from edsl.jobs.tokens.TokenUsage import TokenUsage
from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage


class TaskCreators(UserDict):
    "A dictionary of task creators. A task is one question being answered."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def token_usage(self) -> InterviewTokenUsage:
        """Determines how many tokens were used for the interview."""
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

    def status_logs(self):
        """Returns a list of status logs for each task."""
        return [task_creator.status_log for task_creator in self.values()]
