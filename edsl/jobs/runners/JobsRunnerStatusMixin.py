from __future__ import annotations
from typing import List, DefaultDict
import asyncio
from typing import Type
from collections import defaultdict

from typing import Literal, List, Type, DefaultDict
from collections import UserDict, defaultdict

from edsl.jobs.interviews.InterviewStatusDictionary import InterviewStatusDictionary
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage
from edsl.jobs.tokens.TokenUsage import TokenUsage
from edsl.enums import get_token_pricing
from edsl.jobs.tasks.task_status_enum import TaskStatus

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]

from edsl.jobs.interviews.InterviewStatistic import InterviewStatistic
from edsl.jobs.interviews.InterviewStatisticsCollection import (
    InterviewStatisticsCollection,
)
from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage

class JobsRunnerStatusMixin:

    @staticmethod
    def status_dict(interviews: List[Type["Interview"]]) -> List[Type[InterviewStatusDictionary]]:
        """
        >>> from edsl.jobs.interviews.Interview import Interview
        >>> interviews = [Interview.example()]
        >>> JobsRunnerStatusMixin().status_dict(interviews)
        [InterviewStatusDictionary({<TaskStatus.NOT_STARTED: 1>: 0, <TaskStatus.WAITING_FOR_DEPENDENCIES: 2>: 0, <TaskStatus.CANCELLED: 3>: 0, <TaskStatus.PARENT_FAILED: 4>: 0, <TaskStatus.WAITING_FOR_REQUEST_CAPACITY: 5>: 0, <TaskStatus.WAITING_FOR_TOKEN_CAPACITY: 6>: 0, <TaskStatus.API_CALL_IN_PROGRESS: 7>: 0, <TaskStatus.SUCCESS: 8>: 0, <TaskStatus.FAILED: 9>: 0, 'number_from_cache': 0})]
        """
        return [interview.interview_status for interview in interviews]

    def _job_level_info(self, completed_tasks: List[Type[asyncio.Task]], elapsed_time: float, interviews: List[Type["Interview"]]):
        interview_statistics = InterviewStatisticsCollection()

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
        return interview_statistics

    @staticmethod
    def _get_model_queues_info(interviews):

        models_to_tokens = defaultdict(InterviewTokenUsage)
        model_to_status = defaultdict(InterviewStatusDictionary)
        waiting_dict = defaultdict(int)

        for interview in interviews:
            models_to_tokens[interview.model] += interview.token_usage
            model_to_status[interview.model] += interview.interview_status
            waiting_dict[interview.model] += interview.interview_status.waiting

        for model, num_waiting in waiting_dict.items():
            yield JobsRunnerStatusMixin._get_model_info(model, num_waiting, models_to_tokens)
 
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
        >>> JobsRunnerStatusMixin().generate_status_summary(completed_tasks, elapsed_time, interviews)
        {'Elapsed time': '0.0 sec.', 'Total interviews requested': '1 ', 'Completed interviews': '0 ', 'Percent complete': '0 %', 'Average time per interview': 'NA', 'Task remaining': '1 ', 'Estimated time remaining': 'NA', 'model_queues': [{'model_name': '...', 'TPM_limit_k': ..., 'RPM_limit_k': ..., 'num_tasks_waiting': 0, 'token_usage_info': [{'cache_status': 'new_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}, {'cache_status': 'cached_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}]}]}
        """

        interview_status_summary: InterviewStatisticsCollection = self._job_level_info(
            completed_tasks=completed_tasks, 
            elapsed_time=elapsed_time, 
            interviews=interviews
        )
        interview_status_summary["model_queues"] = list(JobsRunnerStatusMixin._get_model_queues_info(interviews))

        return interview_status_summary

    @staticmethod
    def _get_model_info(
        model: str,
        num_waiting: int,
        models_to_tokens: InterviewTokenUsageMapping,
    ) -> dict:
        """Get the status of a model.

        :param model: the model name
        :param num_waiting: the number of tasks waiting for capacity
        :param models_to_tokens: a mapping of models to token usage

        >>> from edsl.jobs.interviews.Interview import Interview
        >>> interviews = [Interview.example()]
        >>> models_to_tokens = defaultdict(InterviewTokenUsage)
        >>> model = interviews[0].model
        >>> num_waiting = 0
        >>> JobsRunnerStatusMixin()._get_model_info(model, num_waiting, models_to_tokens)
        {'model_name': 'gpt-4-1106-preview', 'TPM_limit_k': ..., 'RPM_limit_k': ..., 'num_tasks_waiting': 0, 'token_usage_info': [{'cache_status': 'new_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}, {'cache_status': 'cached_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}]}
        """

        ## TODO: This should probably be a coop method
        prices = get_token_pricing(model.model)

        token_usage_info = []
        for token_usage_type in ["new_token_usage", "cached_token_usage"]:
            token_usage_info.append(JobsRunnerStatusMixin._get_token_usage_info(token_usage_type, models_to_tokens, model, prices))

        return {
            "model_name": model.model,
            "TPM_limit_k": model.TPM / 1000,
            "RPM_limit_k": model.RPM / 1000,
            "num_tasks_waiting": num_waiting,
            "token_usage_info": token_usage_info,
        }

    @staticmethod
    def _get_token_usage_info(
        token_usage_type: Literal["new_token_usage", "cached_token_usage"],
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
        >>> JobsRunnerStatusMixin()._get_token_usage_info(cache_status, models_to_tokens, model, prices)
        {'cache_status': 'new_token_usage', 'details': [{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], 'cost': '$0.00000'}

        """
        all_token_usage: InterviewTokenUsage = models_to_tokens[model]
        token_usage: TokenUsage = getattr(all_token_usage, token_usage_type)    
        
        details = [{"type": token_type, "tokens": getattr(token_usage, token_type)}
                   for token_type in ["prompt_tokens", "completion_tokens"]]
        
        return {"cache_status": token_usage_type, "details": details, "cost": f"${token_usage.cost(prices):.5f}"}
    
    @staticmethod
    def display_status_table(status_summary) -> 'Table':

        from rich.text import Text
        from rich.box import SIMPLE
        from rich.table import Table

        table = Table(
            title="Job Status",
            show_header=True,
            header_style="bold magenta",
            box=SIMPLE,
        )
        table.max_width = 100
        table.add_column("Statistic", style="dim", no_wrap=True, width=50)
        table.add_column("Value", width=10)

        for key, value in status_summary.items():
            if key != "model_queues":
                table.add_row(key, value)

        spacing = " "
        if "model_queues" in status_summary:
            table.add_row(Text("Model Queues", style="bold red"), "")
            for model_info in status_summary["model_queues"]:
                model_name = model_info["model_name"]
                tpm = "TPM (k)=" + str(model_info["TPM_limit_k"])
                rpm = "RPM (k)=" + str(model_info["RPM_limit_k"])
                pretty_model_name = model_name + ";" + tpm + ";" + rpm
                table.add_row(Text(pretty_model_name, style="blue"), "")
                table.add_row(
                    "Number question tasks waiting for capacity",
                    str(model_info["num_tasks_waiting"]),
                )
                # Token usage and cost info
                for cache_info in model_info["token_usage_info"]:
                    cache_status = cache_info["cache_status"]
                    table.add_row(
                        Text(spacing + cache_status.replace("_", " "), style="bold"), ""
                    )
                    for detail in cache_info["details"]:
                        token_type = detail["type"]
                        tokens = detail["tokens"]
                        #                 cost = detail["cost"]
                        table.add_row(spacing + f"{token_type}", f"{tokens:,}")
                    table.add_row(spacing + "cost", cache_info["cost"])

        return table

    def status_table(self, completed_tasks: List[asyncio.Task], elapsed_time: float):
        summary_data = self.generate_status_summary(
            completed_tasks=completed_tasks,
            elapsed_time=elapsed_time,
            interviews=self.total_interviews,
        )
        return self.display_status_table(summary_data)

if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
