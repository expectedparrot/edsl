from typing import Union, List, Dict
from collections import UserDict, UserList

from edsl import CONFIG
from edsl.jobs.task_status_enum import TaskStatus, get_enum_from_string


class TokensUsed(UserDict):
    """"Container for tokens used by a task."""
    def __init__(self, cached_tokens, new_tokens):
        d = {'cached_tokens': cached_tokens, 'new_tokens': new_tokens}
        super().__init__(d)


class InterviewStatusDictionary(UserDict):
    """A dictionary that keeps track of the status of all the tasks in an interview."""

    def __init__(self, data: Union[Dict[TaskStatus, int], None] = None):
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
    
    def to_dict(self):
        new_data = {str(key):value for key, value in self.data.items()}
        return new_data

    @classmethod
    def from_dict(cls, data):
        new_data = {get_enum_from_string(key):value for key, value in data.items()}
        return cls(new_data)

    def to_json(self):
        import json
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, data):
        import json
        data = json.loads(data)
        return cls.from_dict(data)


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


if __name__ == "__main__":
    
    status = {task:0 for task in TaskStatus}

    id = InterviewStatusDictionary(data = status)
    new_id = InterviewStatusDictionary.from_json(id.to_json())

#from edsl.config import Config

# EDSL_BACKOFF_START_SEC = float(CONFIG.get("EDSL_BACKOFF_START_SEC"))
# EDSL_MAX_BACKOFF_SEC = float(CONFIG.get("EDSL_MAX_BACKOFF_SEC"))
# EDSL_MAX_ATTEMPTS = int(CONFIG.get("EDSL_MAX_ATTEMPTS"))


# def print_retry(retry_state):
#     "Prints details on tenacity retries."
#     attempt_number = retry_state.attempt_number
#     exception = retry_state.outcome.exception()
#     wait_time = retry_state.next_action.sleep
#     print(
#         f"Attempt {attempt_number} failed with exception: {exception}; "
#         f"now waiting {wait_time:.2f} seconds before retrying."
#     )


# retry_strategy = retry(
#     wait=wait_exponential(
#         multiplier=EDSL_BACKOFF_START_SEC, max=EDSL_MAX_BACKOFF_SEC
#     ),  # Exponential back-off starting at 1s, doubling, maxing out at 60s
#     stop=stop_after_attempt(EDSL_MAX_ATTEMPTS),  # Stop after 5 attempts
#     # retry=retry_if_exception_type(Exception),  # Customize this as per your specific retry-able exception
#     before_sleep=print_retry,  # Use custom print function for retries
# )
