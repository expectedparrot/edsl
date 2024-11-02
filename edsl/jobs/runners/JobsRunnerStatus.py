from __future__ import annotations

import time
import requests
from dataclasses import dataclass, asdict

from typing import List, DefaultDict, Optional, Type, Literal, Dict
from collections import UserDict, defaultdict

from rich.text import Text
from rich.box import SIMPLE
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.layout import Layout
from rich.console import Group
from rich import box

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


class JobsRunnerStatus:
    def __init__(
        self,
        jobs_runner: "JobsRunnerAsyncio",
        n: int,
        refresh_rate: float = 0.25,
        endpoint_url: Optional[str] = "http://localhost:8000",
    ):
        self.jobs_runner = jobs_runner
        self.job_id = str(hash(jobs_runner.jobs)) + "-" + str(time.time())

        # URLs
        self.base_url = f"{endpoint_url}/{str(self.job_id)}"
        self.viewing_url = f"{self.base_url}/view"
        self.data_url = f"{self.base_url}/data"
        self.update_url = f"{self.base_url}/update"

        self.start_time = time.time()
        self.completed_interviews = []
        self.refresh_rate = refresh_rate
        self.statistics = [
            "elapsed_time",
            "total_interviews_requested",
            "completed_interviews",
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

    def get_status_dict(self) -> Dict[str, Any]:
        """Convert current status into a JSON-serializable dictionary"""
        # Get all statistics
        stats = {}
        for stat_name in self.statistics:
            stat = self._compute_statistic(stat_name)
            name, value = list(stat.items())[0]
            stats[name] = value

        # Calculate overall progress
        total_interviews = len(self.jobs_runner.total_interviews)
        completed = len(self.completed_interviews)

        # Get model-specific progress
        model_progress = {}
        for model in self.distinct_models:
            completed_for_model = len(self.completed_interview_by_model[model])
            target_for_model = int(
                self.num_total_interviews / len(self.distinct_models)
            )
            model_progress[model] = {
                "completed": completed_for_model,
                "total": target_for_model,
                "percent": (
                    (completed_for_model / target_for_model * 100)
                    if target_for_model > 0
                    else 0
                ),
            }

        status_dict = {
            "overall_progress": {
                "completed": completed,
                "total": total_interviews,
                "percent": (
                    (completed / total_interviews * 100) if total_interviews > 0 else 0
                ),
            },
            "model_progress": model_progress,
            "statistics": stats,
            "status": "completed" if completed >= total_interviews else "running",
        }

        model_queues = {}
        for model, bucket in self.jobs_runner.bucket_collection.items():
            model_name = model.model
            model_queues[model_name] = {
                "model_name": model_name,
                "requests_bucket": {
                    "completed": bucket.requests_bucket.num_released,
                    "requested": bucket.requests_bucket.num_requests,
                    "tokens_returned": bucket.requests_bucket.tokens_returned,
                    "target_rate": round(bucket.requests_bucket.target_rate, 1),
                    "current_rate": round(bucket.requests_bucket.get_throughput(), 1),
                },
                "tokens_bucket": {
                    "completed": bucket.tokens_bucket.num_released,
                    "requested": bucket.tokens_bucket.num_requests,
                    "tokens_returned": bucket.tokens_bucket.tokens_returned,
                    "target_rate": round(bucket.tokens_bucket.target_rate, 1),
                    "current_rate": round(bucket.tokens_bucket.get_throughput(), 1),
                },
            }
        status_dict["model_queues"] = model_queues
        return status_dict

    def send_status_update(self) -> None:
        """Send current status to the web endpoint using the instance's job_id"""

        try:
            # Get the status dictionary and add the job_id
            status_dict = self.get_status_dict()
            status_dict["job_id"] = str(self.job_id)  # Ensure job_id is string

            # Send the update
            response = requests.post(
                self.update_url,
                json=status_dict,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to send status update for job {self.job_id}: {e}")

    def add_completed_interview(self, result):
        self.completed_interviews.append(result.interview_hash)

        relevant_model = result.model.model
        self.completed_interview_by_model[relevant_model].append(result.interview_hash)

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
                num_requests = getattr(bucket, bucket_type).num_requests
                num_released = getattr(bucket, bucket_type).num_released
                tokens_returned = getattr(bucket, bucket_type).tokens_returned
                table.add_row(
                    "  Completed vs. Requested", f"{num_released} vs. {num_requests}"
                )
                table.add_row(
                    "  Added tokens (from cache)",
                    str(tokens_returned),
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

        progress_height = min(5, 2 + len(self.distinct_models))
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
        return table

    def update_progress(self, stop_event):
        layout, progress, task_ids = self.generate_layout()

        with Live(
            layout, refresh_per_second=int(1 / self.refresh_rate), transient=True
        ) as live:
            while (
                len(self.completed_interviews) < len(self.jobs_runner.total_interviews)
                and not stop_event.is_set()
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
                self.send_status_update()

                time.sleep(self.refresh_rate)

            # Final update
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
                    title="Final Metrics",
                    border_style="magenta",
                    box=box.ROUNDED,
                )
            )
            self.send_status_update()

            live.update(layout)
            time.sleep(1)  # Show final state for 1 second


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
