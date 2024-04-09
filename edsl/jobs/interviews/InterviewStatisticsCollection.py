from collections import UserDict
from edsl.jobs.interviews.InterviewStatistic import InterviewStatistic


class InterviewStatisticsCollection(UserDict):
    """A collection of interview statistics."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw: dict = {}

    def add_stat(self, statistic: InterviewStatistic):
        """Add a statistic to the collection.

        Each statistic is a dictionary with a single key-value pair.

        Example usage:

        >>> isc = InterviewStatisticsCollection()
        >>> isc.add_stat(InterviewStatistic("elapsed_time", value=100, digits=1, units="sec."))
        >>> isc.raw
        {'elapsed_time': 100}
        """
        self.update(statistic)
        self.raw.update(statistic.raw)
