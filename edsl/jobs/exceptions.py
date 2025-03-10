from textwrap import dedent

from ..base import BaseException

class JobsErrors(BaseException):
    pass


class JobsRunError(JobsErrors):
    pass


class MissingRemoteInferenceError(JobsErrors):
    pass


class InterviewError(Exception):
    pass


class InterviewErrorPriorTaskCanceled(InterviewError):
    pass


class InterviewTimeoutError(InterviewError):
    pass
