from collections import UserList


class TaskStatusLog(UserList):
    """A list of TaskStatusEntry objects."""

    @property
    def min_time(self):
        return self[0]["log_time"]

    @property
    def max_time(self):
        return self[-1]["log_time"]

    def status_at_time(self, t):
        """Return the status at time t.

        TODO: Could re-factor with bisect to make this faster.
        """
        for entry in self:
            if entry["log_time"] > t:
                return entry["value"]
        return self[-1]["value"]
