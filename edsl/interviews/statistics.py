from collections import UserDict
from typing import DefaultDict, Union, Optional

from ..tokens import InterviewTokenUsage

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]

class InterviewStatistic(UserDict):
    """A statistic for an interview."""

    @staticmethod
    def _format_number(number, digits: int = 0, units: str = "") -> str:
        """Format a number.

        :param number: the number to format
        :param digits: the number of digits to display
        :param units: the units to display

        Example usage:

        >>> InterviewStatistic._format_number(1000, 1, "sec.")
        '1,000.0 sec.'
        """
        if isinstance(number, str):
            return number
        else:
            return f"{number:,.{digits}f}" + " " + units

    @property
    def _pretty_name(self) -> str:
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
        pretty_name: Optional[str] = None,
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

    def add_stat(self, statistic: InterviewStatistic) -> None:
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


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
