from typing import Union, List, Dict
from collections import UserDict, UserList

from edsl import CONFIG
from edsl.jobs.tasks.task_status_enum import TaskStatus, get_enum_from_string


class TokensUsed(UserDict):
    """"Container for tokens used by a task."""
    def __init__(self, cached_tokens, new_tokens):
        d = {'cached_tokens': cached_tokens, 'new_tokens': new_tokens}
        super().__init__(d)



if __name__ == "__main__":
    
    pass