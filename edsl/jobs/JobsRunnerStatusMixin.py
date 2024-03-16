from __future__ import annotations
from typing import List, DefaultDict
import asyncio

from rich.text import Text
from rich.box import SIMPLE
from rich.table import Table

from edsl.jobs.token_tracking import InterviewTokenUsage
from edsl.jobs.jobs_run_history import JobsRunnerStatusData

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]

class JobsRunnerStatusPresentation:
    @staticmethod
    def display_status_table(status_summary):
        table = Table(
            title="Job Status",
            show_header=True,
            header_style="bold magenta",
            box=SIMPLE,
        )
        table.add_column("Statistic", style="dim", no_wrap=True)
        table.add_column("Value")

        for key, value in status_summary.items():
            if key != "model_queues":
                table.add_row(key, value)

        if "model_queues" in status_summary:
            table.add_row(Text("Model Queues", style="bold red"), "")
            for model_info in status_summary["model_queues"]:
                model_name = model_info["model_name"]
                table.add_row(Text(model_name, style="blue"), "")

                # Basic model queue info
                table.add_row("TPM limit (k)", str(model_info["TPM_limit_k"]))
                table.add_row("RPM limit (k)", str(model_info["RPM_limit_k"]))
                table.add_row(
                    "Number question tasks waiting for capacity",
                    str(model_info["num_tasks_waiting"]),
                )

                # Token usage and cost info
                for cache_info in model_info["token_usage_info"]:
                    cache_status = cache_info["cache_status"]
                    table.add_row(Text(cache_status, style="bold"), "")
                    for detail in cache_info["details"]:
                        token_type = detail["type"]
                        tokens = detail["tokens"]
                        cost = detail["cost"]
                        table.add_row(f"{token_type}", f"{tokens:,}")
                        table.add_row("cost", cost)

        return table


class JobsRunnerStatusMixin(JobsRunnerStatusData, JobsRunnerStatusPresentation):
    
    def status_data(self, completed_tasks: List[asyncio.Task], elapsed_time: float):
        # return self.generate_status_summary(
        #     completed_tasks=completed_tasks,
        #     elapsed_time=elapsed_time,
        #     interviews=self.total_interviews).raw
        #return self.full_status(self.total_interviews)
        return None
     
    def status_table(self, completed_tasks: List[asyncio.Task], elapsed_time: float):
        summary_data = self.generate_status_summary(
            completed_tasks=completed_tasks,
            elapsed_time=elapsed_time,
            interviews=self.total_interviews,
        )
        return self.display_status_table(summary_data)
