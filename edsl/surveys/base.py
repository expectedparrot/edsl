"""Base classes and enumerations for the surveyor package."""

from enum import Enum


class RulePriority(Enum):
    """Enumeration of the priority of a rule."""

    DEFAULT = -1


class EndOfSurveyParent:
    """A named object that represents the end of the survey."""

    pass

    def __repr__(self):
        """Return a string representation of the object."""
        return "EndOfSurvey"

    def __str__(self):
        """Return a string representation of the object."""
        return "EndOfSurvey"

    def __bool__(self):
        """Return False."""
        return False

    def __add__(self, other):
        """Add the object to another object.

        Example:
        >>> e = EndOfSurveyParent()
        >>> e + 1
        EndOfSurvey
        """
        return self

    def __deepcopy__(self, memo):
        # Return the same instance when deepcopy is called
        return self

    def __radd__(self, other):
        """Add the object to another object.

        Example:
        >>> 1 + EndOfSurveyParent()
        EndOfSurvey
        """
        return self


EndOfSurvey = EndOfSurveyParent()
