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


#return {"cache_status": token_usage_type, "details": details, "cost": f"${token_usage.cost(prices):.5f}"}

from dataclasses import dataclass, asdict

from rich.text import Text
from rich.box import SIMPLE
from rich.table import Table

@dataclass
class ModelInfo:
    model_name: str
    TPM_limit_k: float
    RPM_limit_k: float
    num_tasks_waiting: int
    token_usage_info: dict


@dataclass
class ModelTokenUsageStats:
    token_usage_type: str
    details: List[dict]
    cost: str

class Stats:

    def elapsed_time(self):
        InterviewStatistic(
                "elapsed_time", value=elapsed_time, digits=1, units="sec."
            )




class JobsRunnerStatusMixin:

    # @staticmethod
    # def status_dict(interviews: List[Type["Interview"]]) -> List[Type[InterviewStatusDictionary]]:
    #     """
    #     >>> from edsl.jobs.interviews.Interview import Interview
    #     >>> interviews = [Interview.example()]
    #     >>> JobsRunnerStatusMixin().status_dict(interviews)
    #     [InterviewStatusDictionary({<TaskStatus.NOT_STARTED: 1>: 0, <TaskStatus.WAITING_FOR_DEPENDENCIES: 2>: 0, <TaskStatus.CANCELLED: 3>: 0, <TaskStatus.PARENT_FAILED: 4>: 0, <TaskStatus.WAITING_FOR_REQUEST_CAPACITY: 5>: 0, <TaskStatus.WAITING_FOR_TOKEN_CAPACITY: 6>: 0, <TaskStatus.API_CALL_IN_PROGRESS: 7>: 0, <TaskStatus.SUCCESS: 8>: 0, <TaskStatus.FAILED: 9>: 0, 'number_from_cache': 0})]
    #     """
    #     return [interview.interview_status for interview in interviews]

    def _compute_statistic(stat_name: str, completed_tasks, elapsed_time, interviews):

        stat_definitions = {
            "elapsed_time": lambda: InterviewStatistic(
                "elapsed_time", value=elapsed_time, digits=1, units="sec."
            ),
            "total_interviews_requested": lambda: InterviewStatistic(
                "total_interviews_requested", value=len(interviews), units=""
            ),
            "completed_interviews": lambda: InterviewStatistic(
                "completed_interviews", value=len(completed_tasks), units=""
            ),
            "percent_complete": lambda: InterviewStatistic(
                "percent_complete",
                value=(
                    len(completed_tasks) / len(interviews) * 100
                    if len(interviews) > 0
                    else "NA"
                ),
                digits=0,
                units="%",
            ),
            "average_time_per_interview": lambda: InterviewStatistic(
                "average_time_per_interview",
                value=elapsed_time / len(completed_tasks) if completed_tasks else "NA",
                digits=1,
                units="sec.",
            ),
            "task_remaining": lambda: InterviewStatistic(
                "task_remaining", value=len(interviews) - len(completed_tasks), units=""
            ),
            "estimated_time_remaining": lambda: InterviewStatistic(
                "estimated_time_remaining",
                value=(
                    (len(interviews) - len(completed_tasks)) * (elapsed_time / len(completed_tasks))
                    if len(completed_tasks) > 0
                    else "NA"
                ),
                digits=1,
                units="sec.",
            )
            }
        if stat_name not in stat_definitions:
            raise ValueError(f"Invalid stat_name: {stat_name}. The valid stat_names are: {list(stat_definitions.keys())}")
        return stat_definitions[stat_name]()


    @staticmethod
    def _job_level_info(completed_tasks: List[Type[asyncio.Task]], 
                        elapsed_time: float, 
                        interviews: List[Type["Interview"]] 
                        ) -> InterviewStatisticsCollection:

        interview_statistics = InterviewStatisticsCollection()

        default_statistics = ["elapsed_time", "total_interviews_requested", "completed_interviews", "percent_complete", "average_time_per_interview", "task_remaining", "estimated_time_remaining"]
        for stat_name in default_statistics:
            interview_statistics.add_stat(JobsRunnerStatusMixin._compute_statistic(stat_name, completed_tasks, elapsed_time, interviews))

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

    @staticmethod
    def generate_status_summary(
        completed_tasks: List[Type[asyncio.Task]],
        elapsed_time: float,
        interviews: List[Type["Interview"]],
        include_model_queues = False
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
        {'Elapsed time': '0.0 sec.', 'Total interviews requested': '1 ', 'Completed interviews': '0 ', 'Percent complete': '0 %', 'Average time per interview': 'NA', 'Task remaining': '1 ', 'Estimated time remaining': 'NA'}
        """

        interview_status_summary: InterviewStatisticsCollection = JobsRunnerStatusMixin._job_level_info(
            completed_tasks=completed_tasks, 
            elapsed_time=elapsed_time, 
            interviews=interviews
        )
        if include_model_queues:
            interview_status_summary.model_queues = list(JobsRunnerStatusMixin._get_model_queues_info(interviews))
        else:
            interview_status_summary.model_queues = None

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
        ModelInfo(model_name='gpt-4-1106-preview', TPM_limit_k=480.0, RPM_limit_k=4.0, num_tasks_waiting=0, token_usage_info=[ModelTokenUsageStats(token_usage_type='new_token_usage', details=[{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], cost='$0.00000'), ModelTokenUsageStats(token_usage_type='cached_token_usage', details=[{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], cost='$0.00000')])
        """

        ## TODO: This should probably be a coop method
        prices = get_token_pricing(model.model)

        token_usage_info = []
        for token_usage_type in ["new_token_usage", "cached_token_usage"]:
            token_usage_info.append(JobsRunnerStatusMixin._get_token_usage_info(token_usage_type, models_to_tokens, model, prices))

        return ModelInfo(**{
            "model_name": model.model,
            "TPM_limit_k": model.TPM / 1000,
            "RPM_limit_k": model.RPM / 1000,
            "num_tasks_waiting": num_waiting,
            "token_usage_info": token_usage_info,
        })

    @staticmethod
    def _get_token_usage_info(
        token_usage_type: Literal["new_token_usage", "cached_token_usage"],
        models_to_tokens: InterviewTokenUsageMapping,
        model: str,
        prices: "TokenPricing",
    ) -> ModelTokenUsageStats:
        """Get the token usage info for a model.

        >>> from edsl.jobs.interviews.Interview import Interview
        >>> interviews = [Interview.example()]
        >>> models_to_tokens = defaultdict(InterviewTokenUsage)
        >>> model = interviews[0].model
        >>> prices = get_token_pricing(model.model)
        >>> cache_status = "new_token_usage"
        >>> JobsRunnerStatusMixin()._get_token_usage_info(cache_status, models_to_tokens, model, prices)
        ModelTokenUsageStats(token_usage_type='new_token_usage', details=[{'type': 'prompt_tokens', 'tokens': 0}, {'type': 'completion_tokens', 'tokens': 0}], cost='$0.00000')

        """
        all_token_usage: InterviewTokenUsage = models_to_tokens[model]
        token_usage: TokenUsage = getattr(all_token_usage, token_usage_type)    
        
        details = [{"type": token_type, "tokens": getattr(token_usage, token_type)}
                   for token_type in ["prompt_tokens", "completion_tokens"]]
        
        return ModelTokenUsageStats(token_usage_type = token_usage_type, details = details, cost = f"${token_usage.cost(prices):.5f}")
    
    @staticmethod
    def _add_statistics_to_table(table, status_summary):
        table.add_column("Statistic", style="dim", no_wrap=True, width=50)
        table.add_column("Value", width=10)

        for key, value in status_summary.items():
            if key != "model_queues":
                table.add_row(key, value)

    @staticmethod
    def display_status_table(status_summary: InterviewStatisticsCollection) -> 'Table':


        table = Table(
            title="Job Status",
            show_header=True,
            header_style="bold magenta",
            box=SIMPLE,
        )

        ### Job-level statistics
        JobsRunnerStatusMixin._add_statistics_to_table(table, status_summary)

        ## Model-level statistics
        spacing = " "

        if status_summary.model_queues is not None:
            table.add_row(Text("Model Queues", style="bold red"), "")
            for model_info in status_summary.model_queues:

                model_name = model_info.model_name
                tpm = f"TPM (k)={model_info.TPM_limit_k}"
                rpm = f"RPM (k)= {model_info.RPM_limit_k}"
                pretty_model_name = model_name + ";" + tpm + ";" + rpm
                table.add_row(Text(pretty_model_name, style="blue"), "")
                table.add_row("Number question tasks waiting for capacity", str(model_info.num_tasks_waiting))
                # Token usage and cost info
                for token_usage_info in model_info.token_usage_info:
                    token_usage_type = token_usage_info.token_usage_type
                    table.add_row(
                        Text(spacing + token_usage_type.replace("_", " "), style="bold"), ""
                    )
                    for detail in token_usage_info.details:
                        token_type = detail["type"]
                        tokens = detail["tokens"]
                        table.add_row(spacing + f"{token_type}", f"{tokens:,}")
                    #table.add_row(spacing + "cost", cache_info["cost"])

        return table

    def status_table(self, completed_tasks: List[asyncio.Task], elapsed_time: float):
        summary_data = JobsRunnerStatusMixin.generate_status_summary(
            completed_tasks=completed_tasks,
            elapsed_time=elapsed_time,
            interviews=self.total_interviews,
        )
        return self.display_status_table(summary_data)

if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
