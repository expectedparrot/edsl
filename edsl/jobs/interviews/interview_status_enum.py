import enum


class InterviewStatus(enum.Enum):
    "These are the possible states an interview can be in."
    NOT_STARTED = enum.auto()
    SUCCESS = enum.auto()
    WAITING_FOR_RESOURCES = enum.auto()
    FAILED = enum.auto()
