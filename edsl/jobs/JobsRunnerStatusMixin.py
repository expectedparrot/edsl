from __future__ import annotations
from collections import defaultdict, UserDict
from typing import List, Dict, Type, Any, Literal, DefaultDict
import asyncio

from rich.text import Text
from rich.box import SIMPLE
from rich.table import Table

from edsl.jobs.token_tracking import TokenPricing, InterviewTokenUsage
from edsl.jobs.task_management import InterviewStatusDictionary

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]


# TODO: Move this to a more appropriate location
pricing = {
    "gpt-3.5-turbo": TokenPricing(
        model_name="gpt-3.5-turbo",
        prompt_token_price_per_k=0.0005,
        completion_token_price_per_k=0.0015,
    ),
    "gpt-4-1106-preview": TokenPricing(
        model_name="gpt-4",
        prompt_token_price_per_k=0.01,
        completion_token_price_per_k=0.03,
    ),
    "test": TokenPricing(
        model_name="test",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
    "gemini_pro": TokenPricing(
        model_name="gemini_pro",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
    "llama-2-13b-chat-hf": TokenPricing(
        model_name="llama-2-13b-chat-hf",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
    "llama-2-70b-chat-hf": TokenPricing(
        model_name="llama-2-70b-chat-hf",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
    "mixtral-8x7B-instruct-v0.1": TokenPricing(
        model_name="mixtral-8x7B-instruct-v0.1",
        prompt_token_price_per_k=0.0,
        completion_token_price_per_k=0.0,
    ),
}


class ModelStatus:
    """Hold the status of a model."""

    def __init__(self, model, TPM, RPM):
        """Initialize the model status."""
        self.model = model
        self.TPM = TPM
        self.RPM = RPM



class InterviewStatistic(UserDict):

    @staticmethod
    def _format_number(number, digits=0, units=""):
        """Format a number."""
        if type(number) == str:
            return number
        else:
            return f"{number:,.{digits}f}" + " " + units

    @property
    def _pretty_name(self):
        return self.name.replace("_", " ").capitalize()

    def __init__(self, 
                 name: str, 
                 value: float, 
                 digits:int =0, 
                 units: str="", 
                 pretty_name: str = None):
        self.name = name
        self.value = value
        self.digits = digits
        self.units = units
        self.pretty_name = pretty_name or self._pretty_name

        super().__init__(
            {self.pretty_name: self._format_number(self.value, self.digits, self.units)}
        )

        self.raw = {self.name: self.value}


class InterviewStatisticsCollection(UserDict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw = {}

    def add_stat(self, statistic: InterviewStatistic):
        """Add a statistic to the collection.
        
        Each statistic is a dictionary with a single key-value pair.
        """
        self.update(statistic)
        self.raw.update(statistic.raw)

class JobsRunnerStatusData:
    pricing = pricing

    def full_status(self, interviews):

        model_to_status = defaultdict(InterviewStatusDictionary)

        for interview in interviews:
            model = interview.model
            model_to_status[model] += interview.interview_status

        #breakpoint()
        return list(model_to_status.values())        

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
            InterviewStatistic("elapsed_time", value=elapsed_time, digits=1, units="sec.")
        )
        interview_statistics.add_stat(
            InterviewStatistic("total_interviews_requested", value=len(interviews), units="")
        )
        interview_statistics.add_stat(
            InterviewStatistic("completed_interviews", value=len(completed_tasks), units="")
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "percent_complete",
                value = len(completed_tasks) / len(interviews) * 100
                if len(interviews) > 0
                else "NA",
                digits=0,
                units="%",
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "average_time_per_interview",
                value = elapsed_time / len(completed_tasks) if completed_tasks else "NA",
                digits=1,
                units="sec.",
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "task_remaining", value=len(interviews) - len(completed_tasks), units=""
            )
        )
        interview_statistics.add_stat(
            InterviewStatistic(
                "estimated_time_remaining",
                value = (len(interviews) - len(completed_tasks))
                * (elapsed_time / len(completed_tasks) if len(completed_tasks) > 0 else "NA"),
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
        if model.model not in self.pricing:
            raise ValueError(f"Model {model.model} not found in pricing")

        prices = self.pricing[model.model]

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
        prices: TokenPricing,
    ):
        cache_info = {"cache_status": cache_status, "details": []}
        token_usage = getattr(models_to_tokens[model], cache_status)
        for token_type in ["prompt_tokens", "completion_tokens"]:
            tokens = getattr(token_usage, token_type)
            cache_info["details"].append(
                {
                    "type": token_type,
                    "tokens": tokens,
                    "cost": f"${token_usage.cost(prices):.5f}",
                }
            )
        return cache_info


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
        return self.full_status(self.total_interviews)
      
    def status_table(self, completed_tasks: List[asyncio.Task], elapsed_time: float):
        summary_data = self.generate_status_summary(
            completed_tasks=completed_tasks,
            elapsed_time=elapsed_time,
            interviews=self.total_interviews,
        )
        return self.display_status_table(summary_data)
