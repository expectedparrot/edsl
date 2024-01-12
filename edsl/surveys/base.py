from enum import Enum


class RulePriority(Enum):
    DEFAULT = -1


class EndOfSurvey:
    "A named object that represents the end of the survey."
    pass

    def __repr__(self):
        return "EndOfSurvey"

    def __str__(self):
        return "EndOfSurvey"

    def __bool__(self):
        return False
