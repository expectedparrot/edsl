from edsl.jobs.interviews.InterviewStatusLog import InterviewStatusLog
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage

from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary


class InterviewStatusMixin:
    @property
    def has_exceptions(self) -> bool:
        """Return True if there are exceptions."""
        return len(self.exceptions) > 0

    @property
    def task_status_logs(self) -> InterviewStatusLog:
        """Return the task status logs for the interview.

        The keys are the question names; the values are the lists of status log changes for each task.
        """
        for task_creator in self.task_creators.values():
            self._task_status_log_dict[
                task_creator.question.question_name
            ] = task_creator.status_log
        return self._task_status_log_dict

    @property
    def token_usage(self) -> InterviewTokenUsage:
        """Determine how many tokens were used for the interview."""
        return self.task_creators.token_usage

    @property
    def interview_status(self) -> InterviewStatusDictionary:
        """Return a dictionary mapping task status codes to counts."""
        return self.task_creators.interview_status
