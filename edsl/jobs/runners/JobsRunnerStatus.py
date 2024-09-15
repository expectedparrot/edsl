from __future__ import annotations

from dataclasses import dataclass, asdict
from rich.text import Text
from rich.box import SIMPLE
from rich.table import Table

from typing import List, DefaultDict, Optional
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
        InterviewStatistic("elapsed_time", value=elapsed_time, digits=1, units="sec.")


import time


class JobsRunnerStatus:

    def __init__(
        self,
        jobs_runner: "JobsRunnerAsyncio",
        progress_bar_stats: Optional[List[str]] = None,
    ):
        self.jobs_runner = jobs_runner
        self.start_time = time.time()
        self.completed_interviews = []
        self.refresh = False  # only refresh if a new interview is added

        if progress_bar_stats is None:
            self.statistics = [
                "elapsed_time",
                "total_interviews_requested",
                "completed_interviews",
                "percent_complete",
                "average_time_per_interview",
                "task_remaining",
                "estimated_time_remaining",
                "exceptions",
                "unfixed_exceptions",
            ]
        else:
            self.statistics = progress_bar_stats

    @property
    def total_interviews(self):
        return self.jobs_runner.total_interviews

    def add_completed_interview(self, result):
        self.refresh = True
        self.completed_interviews.append(result.interview_hash)

    def _compute_statistic(self, stat_name: str):
        completed_tasks = self.completed_interviews
        elapsed_time = time.time() - self.start_time
        interviews = self.total_interviews

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
                    (len(interviews) - len(completed_tasks))
                    * (elapsed_time / len(completed_tasks))
                    if len(completed_tasks) > 0
                    else "NA"
                ),
                digits=1,
                units="sec.",
            ),
            "exceptions": lambda: InterviewStatistic(
                "exceptions",
                value=sum(len(i.exceptions) for i in self.total_interviews),
                units="",
            ),
            "unfixed_exceptions": lambda: InterviewStatistic(
                "unfixed_exceptions",
                value=sum(i.exceptions.num_unfixed() for i in self.total_interviews),
                units="",
            ),
        }
        if stat_name not in stat_definitions:
            raise ValueError(
                f"Invalid stat_name: {stat_name}. The valid stat_names are: {list(stat_definitions.keys())}"
            )
        return stat_definitions[stat_name]()

    def _job_level_info(self) -> InterviewStatisticsCollection:
        interview_statistics = InterviewStatisticsCollection()

        for stat_name in self.statistics:
            interview_statistics.add_stat(self._compute_statistic(stat_name))

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
            yield JobsRunnerStatus._get_model_info(model, num_waiting, models_to_tokens)

    def generate_status_summary(
        self,
        include_model_queues=False,
    ) -> InterviewStatisticsCollection:
        """Generate a summary of the status of the job runner."""

        interview_status_summary: InterviewStatisticsCollection = self._job_level_info()
        if include_model_queues:
            interview_status_summary.model_queues = list(
                self._get_model_queues_info(interviews)
            )
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
        """

        ## TODO: This should probably be a coop method
        prices = get_token_pricing(model.model)

        token_usage_info = []
        for token_usage_type in ["new_token_usage", "cached_token_usage"]:
            token_usage_info.append(
                JobsRunnerStatus._get_token_usage_info(
                    token_usage_type, models_to_tokens, model, prices
                )
            )

        return ModelInfo(
            **{
                "model_name": model.model,
                "TPM_limit_k": model.TPM / 1000,
                "RPM_limit_k": model.RPM / 1000,
                "num_tasks_waiting": num_waiting,
                "token_usage_info": token_usage_info,
            }
        )

    @staticmethod
    def _get_token_usage_info(
        token_usage_type: Literal["new_token_usage", "cached_token_usage"],
        models_to_tokens: InterviewTokenUsageMapping,
        model: str,
        prices: "TokenPricing",
    ) -> ModelTokenUsageStats:
        """Get the token usage info for a model."""
        all_token_usage: InterviewTokenUsage = models_to_tokens[model]
        token_usage: TokenUsage = getattr(all_token_usage, token_usage_type)

        details = [
            {"type": token_type, "tokens": getattr(token_usage, token_type)}
            for token_type in ["prompt_tokens", "completion_tokens"]
        ]

        return ModelTokenUsageStats(
            token_usage_type=token_usage_type,
            details=details,
            cost=f"${token_usage.cost(prices):.5f}",
        )

    @staticmethod
    def _add_statistics_to_table(table, status_summary):
        table.add_column("Statistic", style="dim", no_wrap=True, width=50)
        table.add_column("Value", width=10)

        for key, value in status_summary.items():
            if key != "model_queues":
                table.add_row(key, value)

    @staticmethod
    def display_status_table(status_summary: InterviewStatisticsCollection) -> "Table":
        table = Table(
            title="Job Status",
            show_header=True,
            header_style="bold magenta",
            box=SIMPLE,
        )

        ### Job-level statistics
        JobsRunnerStatus._add_statistics_to_table(table, status_summary)

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
                table.add_row(
                    "Number question tasks waiting for capacity",
                    str(model_info.num_tasks_waiting),
                )
                # Token usage and cost info
                for token_usage_info in model_info.token_usage_info:
                    token_usage_type = token_usage_info.token_usage_type
                    table.add_row(
                        Text(
                            spacing + token_usage_type.replace("_", " "), style="bold"
                        ),
                        "",
                    )
                    for detail in token_usage_info.details:
                        token_type = detail["type"]
                        tokens = detail["tokens"]
                        table.add_row(spacing + f"{token_type}", f"{tokens:,}")
                    # table.add_row(spacing + "cost", cache_info["cost"])

        return table

    @property
    def summary_data(self):
        "Return the summary data, refreshing it if necessary."
        if self.refresh is True:
            self._summary_data = self.generate_status_summary()
            self.refresh = False
        return self._summary_data

    def status_table(self):
        summary_data = self.generate_status_summary()
        return self.display_status_table(summary_data)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
