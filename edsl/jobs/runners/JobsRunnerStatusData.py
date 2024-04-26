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
    # pricing = pricing

    def status_dict(self, interviews):
        status = []
        for interview in interviews:
            # model = interview.model
            status.append(interview.interview_status)

        return status
        # return model_to_status

    def status_counts(self, interviews):
        model_to_status = defaultdict(InterviewStatusDictionary)

        for interview in interviews:
            model = interview.model
            model_to_status[model] += interview.interview_status

        # breakpoint()
        return model_to_status.values()

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
                value=len(completed_tasks) / len(interviews) * 100
                if len(interviews) > 0
                else "NA",
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
    ):
        """Get the status of a model."""
        # if model.model not in self.pricing:
        #     #raise ValueError(f"Model {model.model} not found in pricing")
        #     import warning
        #     warning.warn(f"Model {model.model} not found in pricing")

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
    ):
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
