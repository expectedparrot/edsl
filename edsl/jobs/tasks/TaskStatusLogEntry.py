from collections import UserDict


class TaskStatusLogEntry(UserDict):
    def __init__(self, log_time, value):
        self.data = {"log_time": log_time, "value": value}
        super().__init__(self.data)
