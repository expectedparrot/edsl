import asyncio
from enum import Enum
from typing import Literal, List, Type, DefaultDict
from collections import UserDict, defaultdict

from edsl.jobs.tasks.task_management import InterviewStatusDictionary
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage
from edsl.jobs.pricing import pricing, TokenPricing
from edsl.jobs.tasks.task_status_enum import TaskStatus

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]


class InterviewStatistic(UserDict):
    @staticmethod
    def _format_number(number, digits=0, units=""):
        """Format a number.

        :param number: the number to format
        :param digits: the number of digits to display
        :param units: the units to display

        Example usage:

        >>> InterviewStatistic._format_number(1000, 1, "sec.")
        '1,000.0 sec.'
        """
        if type(number) == str:
            return number
        else:
            return f"{number:,.{digits}f}" + " " + units

    @property
    def _pretty_name(self):
        """Return a pretty name for the statistic.

        Example usage:

        >>> InterviewStatistic("elapsed_time", value=100, digits=1, units="sec.").pretty_name
        'Elapsed time'
        """
        return self.name.replace("_", " ").capitalize()

    def __init__(
        self,
        name: str,
        value: float,
        digits: int = 0,
        units: str = "",
        pretty_name: str = None,
    ):
        """Create a new InterviewStatistic object."""
        self.name = name
        self.value = value
        self.digits = digits
        self.units = units
        self.pretty_name = pretty_name or self._pretty_name

        super().__init__(
            {self.pretty_name: self._format_number(self.value, self.digits, self.units)}
        )

        self.raw: dict = {self.name: self.value}


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


def enum_converter(obj):
    if isinstance(obj, Enum):
        return obj.name  # or obj.value if you prefer the enum's value
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


if __name__ == "__main__":
    # pass
    import doctest

    doctest.testmod()
    # Create a JobsRunHistory object
    # jrh = JobsRunHistory()

    # # Add some data to it
    # jrh.append({"elapsed_time": 0, "completed_interviews": 0})
    # jrh.append({"elapsed_time": 1, "completed_interviews": 1})
    # jrh.append({"elapsed_time": 2, "completed_interviews": 2})

    # # Save the data to a file
    # jrh.to_json("jobs_run_history.json")

    # # Read the data from the file
    # jrh2 = JobsRunHistory.from_json("jobs_run_history.json")

    # # Plot the data
    # jrh2.plot_completion_times()
