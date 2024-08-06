import asyncio
from enum import Enum
from typing import Literal, List, Type, DefaultDict
from collections import UserDict, defaultdict

from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage

# from edsl.enums import pricing, TokenPricing
from edsl.enums import get_token_pricing
from edsl.jobs.tasks.task_status_enum import TaskStatus

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]

from edsl.jobs.interviews.InterviewStatistic import InterviewStatistic
from edsl.jobs.interviews.InterviewStatisticsCollection import (
    InterviewStatisticsCollection,
)


class JobsRunnerStatusData:
    def status_dict(
        self, interviews: List[Type["Interview"]]
    ) -> List[Type[InterviewStatusDictionary]]:
        """
        >>> from edsl.jobs.interviews.Interview import Interview
        >>> interviews = [Interview.example()]
        >>> JobsRunnerStatusData().status_dict(interviews)
        [InterviewStatusDictionary({<TaskStatus.NOT_STARTED: 1>: 0, <TaskStatus.WAITING_FOR_DEPENDENCIES: 2>: 0, <TaskStatus.CANCELLED: 3>: 0, <TaskStatus.PARENT_FAILED: 4>: 0, <TaskStatus.WAITING_FOR_REQUEST_CAPACITY: 5>: 0, <TaskStatus.WAITING_FOR_TOKEN_CAPACITY: 6>: 0, <TaskStatus.API_CALL_IN_PROGRESS: 7>: 0, <TaskStatus.SUCCESS: 8>: 0, <TaskStatus.FAILED: 9>: 0, 'number_from_cache': 0})]
        """
        status = []
        for interview in interviews:
            status.append(interview.interview_status)

        return status

    # def status_counts(self, interviews: List[Type["Interview"]]):
    #     """
    #     Takes a collection of interviews and returns a dictionary of the counts of each status.

    #     :param interviews: a collection of interviews.

    #     This creates a dictionary of the counts of each status in the collection of interviews.

    #     >>> from edsl.jobs.interviews.Interview import Interview
    #     >>> interviews = [Interview.example() for _ in range(100)]
    #     >>> jd = JobsRunnerStatusData()
    #     >>> jd.status_counts(interviews)
    #     dict_values([InterviewStatusDictionary({<TaskStatus.NOT_STARTED: 1>: 0, <TaskStatus.WAITING_FOR_DEPENDENCIES: 2>: 0, <TaskStatus.CANCELLED: 3>: 0, <TaskStatus.PARENT_FAILED: 4>: 0, <TaskStatus.WAITING_FOR_REQUEST_CAPACITY: 5>: 0, <TaskStatus.WAITING_FOR_TOKEN_CAPACITY: 6>: 0, <TaskStatus.API_CALL_IN_PROGRESS: 7>: 0, <TaskStatus.SUCCESS: 8>: 0, <TaskStatus.FAILED: 9>: 0, 'number_from_cache': 0})])
    #     >>> len(jd.status_counts(interviews))
    #     1
    #     """
    #     model_to_status = defaultdict(InterviewStatusDictionary)

    #     # InterviewStatusDictionary objects can be added together
    #     for interview in interviews:
    #         model_to_status[interview.model] += interview.interview_status 

    #     return list(model_to_status.values())
    #       # return the values of the dictionary, which is a list of dictionaries

    def generate_status_summary(
        self,
        completed_tasks: List[Type[asyncio.Task]],
        elapsed_time: float,
        interviews: List[Type["Interview"]],
    ) -> InterviewStatisticsCollection:
        """Generate a summary of the status of the job runner.

        :param completed_tasks: list of completed tasks
        :param elapsed_time: time elapsed since the start of the job
        :param interviews: list of interviews to be conducted

        >>> from edsl.jobs.interviews.Interview import Interview
        >>> interviews = [Interview.example()]
        >>> completed_tasks = []
        >>> elapsed_time = 0
        >>> JobsRunnerStatusData().generate_status_summary(completed_tasks, elapsed_time, interviews)
        {'Elapsed time': '0.0 sec.', 'Total interviews requested': '1 ', 'Completed interviews': '0 ', 'Percent complete': '0 %', 'Average time per interview': 'NA', 'Task remaining': '1 ', 'Estimated time remaining': 'NA', 'model_queues': [{'model_name': '...', 'TPM_limit_k': ..., 'RPM_limit_k': ..., 'num_tasks_waiting': 0, 'token_usage_info': [{'cache_status': 'new_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}, {'cache_status': 'cached_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}]}]}
        """

        models_to_tokens = defaultdict(InterviewTokenUsage)
        model_to_status = defaultdict(InterviewStatusDictionary)
        waiting_dict = defaultdict(int)

        interview_statistics = InterviewStatisticsCollection()

        for interview in interviews:
            model = interview.model
            models_to_tokens[model] += interview.token_usage
            model_to_status[model] += interview.interview_status
            waiting_dict[model] += interview.interview_status.waiting

        interview_statistics.add_stat(
            InterviewStatistic(
                "elapsed_time", value=elapsed_time, digits=1, units="sec."
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "total_interviews_requested", value=len(interviews), units=""
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "completed_interviews", value=len(completed_tasks), units=""
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "percent_complete",
                value=(
                    len(completed_tasks) / len(interviews) * 100
                    if len(interviews) > 0
                    else "NA"
                ),
                digits=0,
                units="%",
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "average_time_per_interview",
                value=elapsed_time / len(completed_tasks) if completed_tasks else "NA",
                digits=1,
                units="sec.",
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "task_remaining", value=len(interviews) - len(completed_tasks), units=""
            )
        )
        number_remaining = len(interviews) - len(completed_tasks)
        time_per_task = (
            elapsed_time / len(completed_tasks) if len(completed_tasks) > 0 else "NA"
        )
        estimated_time_remaining = (
            number_remaining * time_per_task if time_per_task != "NA" else "NA"
        )

        interview_statistics.add_stat(
            InterviewStatistic(
                "estimated_time_remaining",
                value=estimated_time_remaining,
                digits=1,
                units="sec.",
            )
        )
        model_queues_info = []
        for model, num_waiting in waiting_dict.items():
            model_info = self._get_model_info(model, num_waiting, models_to_tokens)
            model_queues_info.append(model_info)

        interview_statistics["model_queues"] = model_queues_info

        return interview_statistics

    def _get_model_info(
        self,
        model: str,
        num_waiting: int,
        models_to_tokens: InterviewTokenUsageMapping,
    ) -> dict:
        """Get the status of a model.

        >>> from edsl.jobs.interviews.Interview import Interview
        >>> interviews = [Interview.example()]
        >>> models_to_tokens = defaultdict(InterviewTokenUsage)
        >>> model = interviews[0].model
        >>> num_waiting = 0
        >>> JobsRunnerStatusData()._get_model_info(model, num_waiting, models_to_tokens)
        {'model_name': 'gpt-4-1106-preview', 'TPM_limit_k': ..., 'RPM_limit_k': ..., 'num_tasks_waiting': 0, 'token_usage_info': [{'cache_status': 'new_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}, {'cache_status': 'cached_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}]}
        """

        prices = get_token_pricing(model.model)

        model_info = {
            "model_name": model.model,
            "TPM_limit_k": model.TPM / 1000,
            "RPM_limit_k": model.RPM / 1000,
            "num_tasks_waiting": num_waiting,
            "token_usage_info": [],
        }

        token_usage_types = ["new_token_usage", "cached_token_usage"]
        for token_usage_type in token_usage_types:
            cache_info = self._get_token_usage_info(
                token_usage_type, models_to_tokens, model, prices
            )
            model_info["token_usage_info"].append(cache_info)

        return model_info

    def _get_token_usage_info(
        self,
        cache_status: Literal["new_token_usage", "cached_token_usage"],
        models_to_tokens: InterviewTokenUsageMapping,
        model: str,
        prices: "TokenPricing",
    ) -> dict:
        """Get the token usage info for a model.

        >>> from edsl.jobs.interviews.Interview import Interview
        >>> interviews = [Interview.example()]
        >>> models_to_tokens = defaultdict(InterviewTokenUsage)
        >>> model = interviews[0].model
        >>> prices = get_token_pricing(model.model)
        >>> cache_status = "new_token_usage"
        >>> JobsRunnerStatusData()._get_token_usage_info(cache_status, models_to_tokens, model, prices)
        {'cache_status': 'new_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}

        """
        cache_info = {"cache_status": cache_status, "details": []}
        token_usage = getattr(models_to_tokens[model], cache_status)
        for token_type in ["prompt_tokens", "completion_tokens"]:
            tokens = getattr(token_usage, token_type)
            cache_info["details"].append(
                {
                    "type": token_type,
                    "tokens": tokens,
                }
            )
        cache_info["cost"] = f"${token_usage.cost(prices):.5f}"
        return cache_info


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
