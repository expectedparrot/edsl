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
        include_model_queues=True,
    ) -> InterviewStatisticsCollection:
        """Generate a summary of the status of the job runner."""

        interview_status_summary: InterviewStatisticsCollection = self._job_level_info()
        if include_model_queues:
            interview_status_summary.model_queues = list(
                self._get_model_queues_info(self.jobs_runner.total_interviews)
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


from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich import box
import time


from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich.console import Group
from rich import box
import time

from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich.console import Group
from rich import box
import time

from collections import defaultdict


class EnhancedJobsRunnerStatus:
    def __init__(
        self, jobs_runner: "JobsRunnerAsyncio", n: int, refresh_rate: float = 0.25
    ):
        self.jobs_runner = jobs_runner
        self.start_time = time.time()
        self.completed_interviews = []
        self.refresh_rate = refresh_rate
        self.statistics = [
            "elapsed_time",
            "total_interviews_requested",
            #            "completed_interviews",
            #            "percent_complete",
            "average_time_per_interview",
            #            "task_remaining",
            "estimated_time_remaining",
            "exceptions",
            "unfixed_exceptions",
            "throughput",
        ]
        self.num_total_interviews = n * len(self.jobs_runner.interviews)

        self.distinct_models = list(
            set(i.model.model for i in self.jobs_runner.interviews)
        )

        self.completed_interview_by_model = defaultdict(list)

    def add_completed_interview(self, result):
        self.completed_interviews.append(result.interview_hash)

        relevant_model = result.model.model
        self.completed_interview_by_model[relevant_model].append(result.interview_hash)
        # breakpoint()

    def _compute_statistic(self, stat_name: str):
        completed_tasks = self.completed_interviews
        elapsed_time = time.time() - self.start_time
        interviews = self.jobs_runner.total_interviews

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
                    else 0
                ),
                digits=1,
                units="%",
            ),
            "average_time_per_interview": lambda: InterviewStatistic(
                "average_time_per_interview",
                value=elapsed_time / len(completed_tasks) if completed_tasks else 0,
                digits=2,
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
                    else 0
                ),
                digits=1,
                units="sec.",
            ),
            "exceptions": lambda: InterviewStatistic(
                "exceptions",
                value=sum(len(i.exceptions) for i in interviews),
                units="",
            ),
            "unfixed_exceptions": lambda: InterviewStatistic(
                "unfixed_exceptions",
                value=sum(i.exceptions.num_unfixed() for i in interviews),
                units="",
            ),
            "throughput": lambda: InterviewStatistic(
                "throughput",
                value=len(completed_tasks) / elapsed_time if elapsed_time > 0 else 0,
                digits=2,
                units="interviews/sec.",
            ),
        }
        return stat_definitions[stat_name]()

    def create_progress_bar(self):
        return Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.completed}/{task.total}"),
        )

    def generate_model_queues_table(self):
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Info", style="cyan")
        table.add_column("Value", style="magenta")
        # table.add_row("Bucket collection", str(self.jobs_runner.bucket_collection))
        for model, bucket in self.jobs_runner.bucket_collection.items():
            table.add_row(Text(model.model, style="bold blue"), "")
            bucket_types = ["requests_bucket", "tokens_bucket"]
            for bucket_type in bucket_types:
                table.add_row(Text(" " + bucket_type, style="green"), "")
                # table.add_row(
                #     f"  Current level (capacity = {round(getattr(bucket, bucket_type).capacity, 3)})",
                #     str(round(getattr(bucket, bucket_type).tokens, 3)),
                # )
                num_requests = getattr(bucket, bucket_type).num_requests
                num_released = getattr(bucket, bucket_type).num_released
                # table.add_row(
                #     f"  Requested",
                #     str(num_requests),
                # )
                # table.add_row(
                #     f"  Completed",
                #     str(num_released),
                # )
                table.add_row(
                    "  Completed vs. Requested", f"{num_released} vs. {num_requests}"
                )
                if bucket_type == "tokens_bucket":
                    rate_name = "TPM"
                else:
                    rate_name = "RPM"
                target_rate = round(getattr(bucket, bucket_type).target_rate, 1)
                table.add_row(
                    f"  Empirical {rate_name} (target = {target_rate})",
                    str(round(getattr(bucket, bucket_type).get_throughput(), 0)),
                )

            # table.add_row("Bucket", str(bucket.tokens))

        # model_queues = (
        #     self.jobs_runner.status_summary.model_queues
        #     if hasattr(self.jobs_runner, "status_summary")
        #     else None
        # )

        # if model_queues is not None:
        #     for model_info in model_queues:
        #         model_name = model_info.model_name
        #         tpm = f"TPM (k)={model_info.TPM_limit_k}"
        #         rpm = f"RPM (k)={model_info.RPM_limit_k}"
        #         pretty_model_name = f"{model_name}; {tpm}; {rpm}"
        #         table.add_row(Text(pretty_model_name, style="bold blue"), "")
        #         table.add_row(
        #             "Tasks waiting for capacity", str(model_info.num_tasks_waiting)
        #         )

        #         for token_usage_info in model_info.token_usage_info:
        #             token_usage_type = token_usage_info.token_usage_type.replace(
        #                 "_", " "
        #             ).title()
        #             table.add_row(Text(token_usage_type, style="bold"), "")
        #             for detail in token_usage_info.details:
        #                 token_type = detail["type"].replace("_", " ").title()
        #                 tokens = detail["tokens"]
        #                 table.add_row(f"  {token_type}", f"{tokens:,}")
        #             table.add_row("  Cost", token_usage_info.cost)

        #         table.add_row("", "")  # Empty row for spacing between models
        # else:
        #     table.add_row("No model queue information available", "")

        return table

    def generate_layout(self):
        progress = self.create_progress_bar()
        task_ids = []
        for model in self.distinct_models:
            task_id = progress.add_task(
                f"[cyan]{model}...",
                total=int(self.num_total_interviews / len(self.distinct_models)),
            )
            task_ids.append((model, task_id))

        # Adjust these heights to sum around 10
        progress_height = min(
            5, 2 + len(self.distinct_models)
        )  # Progress height based on the number of models
        # bottom_height = (
        #     10 - progress_height
        # )  # Bottom height to balance to a total of 10 lines

        layout = Layout()

        # Create the top row with only the progress panel
        layout.split_column(
            Layout(
                Panel(
                    progress,
                    title="Interview Progress",
                    border_style="cyan",
                    box=box.ROUNDED,
                ),
                name="progress",
                size=progress_height,  # Adjusted size
            ),
            Layout(name="bottom_row"),  # Adjusted size
        )

        # Split the bottom row into two columns for metrics and model queues
        layout["bottom_row"].split_row(
            Layout(
                Panel(
                    self.generate_metrics_table(),
                    title="Metrics",
                    border_style="magenta",
                    box=box.ROUNDED,
                ),
                name="metrics",
            ),
            Layout(
                Panel(
                    self.generate_model_queues_table(),
                    title="Model Queues",
                    border_style="yellow",
                    box=box.ROUNDED,
                ),
                name="model_queues",
            ),
        )

        return layout, progress, task_ids

    def generate_metrics_table(self):
        table = Table(show_header=True, header_style="bold magenta", box=box.SIMPLE)
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", justify="right")

        for stat_name in self.statistics:
            pretty_name, value = list(self._compute_statistic(stat_name).items())[0]
            # breakpoint()
            table.add_row(pretty_name, value)
        # from rich.table import Table

        # table = Table(show_header=False, box=None)
        # for stat_name in self.statistics:
        #     stat = self._compute_statistic(stat_name)
        #     table.add_row(f"{stat.name}:", f"{stat.value} {stat.units}")
        return table

    def update_progress(self):
        layout, progress, task_ids = self.generate_layout()

        with Live(
            layout, refresh_per_second=int(1 / self.refresh_rate), transient=True
        ) as live:
            while len(self.completed_interviews) < len(
                self.jobs_runner.total_interviews
            ):
                completed_tasks = len(self.completed_interviews)
                total_tasks = len(self.jobs_runner.total_interviews)

                for model, task_id in task_ids:
                    completed_tasks = len(self.completed_interview_by_model[model])
                    progress.update(
                        task_id,
                        completed=completed_tasks,
                        description=f"[cyan]Conducting interviews for {model}...",
                    )

                layout["metrics"].update(
                    Panel(
                        self.generate_metrics_table(),
                        title="Metrics",
                        border_style="magenta",
                        box=box.ROUNDED,
                    )
                )
                layout["model_queues"].update(
                    Panel(
                        self.generate_model_queues_table(),
                        title="Final Model Queues",
                        border_style="yellow",
                        box=box.ROUNDED,
                    )
                )

                time.sleep(self.refresh_rate)

            # Final update
            for model, task_id in task_ids:
                completed_tasks = len(self.completed_interview_by_model[model])
                progress.update(
                    task_id,
                    completed=completed_tasks,
                    description=f"[cyan]Conducting interviews for {model}...",
                )

            # progress.update(
            #     task_id,
            #     completed=total_tasks,
            #     description=f"[cyan]Interviews completed ({total_tasks}/{total_tasks})",
            # )
            layout["metrics"].update(
                Panel(
                    self.generate_metrics_table(),
                    title="Final Metrics",
                    border_style="magenta",
                    box=box.ROUNDED,
                )
            )
            live.update(layout)
            time.sleep(1)  # Show final state for 1 second


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
