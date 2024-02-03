class JobsErrors(Exception):
    pass


class JobsRunError(JobsErrors):
    pass


class InterviewError(Exception):
    pass


class InterviewErrorPriorTaskCanceled(InterviewError):
    pass


class InterviewTimeoutError(InterviewError):
    pass
