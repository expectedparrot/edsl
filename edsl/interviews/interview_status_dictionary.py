from __future__ import annotations

from collections import UserDict
from typing import Dict, Union

from ..tasks.task_status_enum import TaskStatus, get_enum_from_string


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
        self, other: "InterviewStatusDictionary"
    ) -> "InterviewStatusDictionary":
        """Adds two InterviewStatusDictionaries together."""
        if not isinstance(other, InterviewStatusDictionary):
            from .exceptions import InterviewStatusError
            raise InterviewStatusError(f"Can't add {type(other)} to InterviewStatusDictionary")
        new_dict = {}
        for key in self.keys():
            new_dict[key] = self[key] + other[key]
        return InterviewStatusDictionary(new_dict)

    @property
    def waiting(self) -> int:
        """Return the number of tasks that are in a waiting status of some kind."""

        waiting_status_list = [
            TaskStatus.WAITING_FOR_REQUEST_CAPACITY,
            TaskStatus.WAITING_FOR_TOKEN_CAPACITY,
            TaskStatus.WAITING_FOR_DEPENDENCIES,
        ]

        return sum([self[status] for status in waiting_status_list])

    def __repr__(self):
        return f"InterviewStatusDictionary({self.data})"

    def to_dict(self) -> dict:
        """Return a dictionary representation of the InterviewStatusDictionary."""
        new_data = {str(key): value for key, value in self.data.items()}
        return new_data

    # def print(self):
    #     d = {}
    #     for key, value in self.data.items():
    #         d[str(key)] = value
    #     from edsl.utilities.interface import print_dict_with_rich

    #     print_dict_with_rich(d)

    @classmethod
    def from_dict(cls, data: dict) -> "InterviewStatusDictionary":
        """Create an InterviewStatusDictionary from a dictionary."""
        new_data = {get_enum_from_string(key): value for key, value in data.items()}
        return cls(new_data)

    def to_json(self) -> str:
        """Return a JSON representation of the InterviewStatusDictionary."""
        import json

        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, data: str) -> "InterviewStatusDictionary":
        """Create an InterviewStatusDictionary from a JSON string."""
        import json

        data = json.loads(data)
        return cls.from_dict(data)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
