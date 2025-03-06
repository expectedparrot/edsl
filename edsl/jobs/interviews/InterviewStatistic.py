from typing import Literal, List, Type, DefaultDict
from collections import UserDict

from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]


class InterviewStatistic(UserDict):
    @staticmethod
    def _format_number(number, digits=0, units="") -> str:
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


if __name__ == "__main__":
    import doctest
    doctest.testmod()