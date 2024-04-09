from __future__ import annotations
from typing import List, DefaultDict
import asyncio

from rich.text import Text
from rich.box import SIMPLE
from rich.table import Table

from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage
from edsl.jobs.runners.JobsRunnerStatusData import JobsRunnerStatusData

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


class JobsRunnerStatusMixin(JobsRunnerStatusData, JobsRunnerStatusPresentation):
    def status_data(self, completed_tasks: List[asyncio.Task], elapsed_time: float):
        # return self.generate_status_summary(
        #     completed_tasks=completed_tasks,
        #     elapsed_time=elapsed_time,
        #     interviews=self.total_interviews).rawplt.figure(figsize=(10, 6))

        # return self.full_status(self.total_interviews)
        return None

    def status_table(self, completed_tasks: List[asyncio.Task], elapsed_time: float):
        summary_data = self.generate_status_summary(
            completed_tasks=completed_tasks,
            elapsed_time=elapsed_time,
            interviews=self.total_interviews,
        )
        return self.display_status_table(summary_data)
