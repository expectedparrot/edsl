from enum import Enum


class RulePriority(Enum):
    DEFAULT = -1


class EndOfSurveyParent:
    "A named object that represents the end of the survey."
    pass

    def __repr__(self):
        return "EndOfSurvey"

    def __str__(self):
        return "EndOfSurvey"

    def __bool__(self):
        return False

    def __add__(self, other):
        """
        >>> e = EndOfSurveyParent()
        >>> e + 1
        EndOfSurvey
        """
        return self

    def __radd__(self, other):
        """
        >>> 1 + EndOfSurveyParent()
        EndOfSurvey
        """
        return self


EndOfSurvey = EndOfSurveyParent()
