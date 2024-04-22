from textwrap import dedent


class JobsErrors(Exception):
    pass


class JobsRunError(JobsErrors):
    pass


class MissingRemoteInferenceError(JobsErrors):
    def __init__(self):
        message = dedent(
            """\\
                        You are trying to run the job remotely, but you have not set the EXPECTED_PARROT_INFERENCE_URL environment variable.
                        This remote running service is not quite ready yet! 
                        But please see https://docs.expectedparrot.com/en/latest/coop.html for what we are working on.
                        """
        )
        super().__init__(message)


class InterviewError(Exception):
    pass


class InterviewErrorPriorTaskCanceled(InterviewError):
    pass


class InterviewTimeoutError(InterviewError):
    pass
