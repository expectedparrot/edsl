from __future__ import annotations
from collections import defaultdict
from typing import List, Dict, Type
import asyncio

from rich.table import Table
from rich.text import Text
from rich.box import SIMPLE


from edsl.jobs.token_tracking import TokenPricing, InterviewTokenUsage
from edsl.jobs.task_management import InterviewStatusDictionary


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

class JobsRunnerStatusData:

    pricing = pricing

    def generate_status_summary(self, completed_tasks: List[Type[asyncio.Task]], elapsed_time: float, interviews: List[Type['Interview']]) -> Dict:
        models_to_tokens = defaultdict(InterviewTokenUsage)
        model_to_status = defaultdict(InterviewStatusDictionary)

        waiting_dict = defaultdict(int)

        #interviews = self.total_interviews

        # TODO: I'm not sure this is right anymore, given the n > 1 possibility...
        # Change to "total_intervviews"
        for interview in interviews:
            model = interview.model
            models_to_tokens[model] += interview.token_usage
            model_to_status[model] += interview.interview_status
            waiting_dict[model] += interview.interview_status.waiting

        pct_complete = len(completed_tasks) / len(interviews) * 100 if len(interviews) > 0 else 0
        average_time = elapsed_time / len(completed_tasks) if completed_tasks else 0

        task_remaining = len(interviews) - len(completed_tasks)
        estimated_time_remaining = task_remaining * average_time if average_time else 0

        model_queues_info = []
        for model, num_waiting in waiting_dict.items():
            if model.model not in self.pricing:
                raise ValueError(f"Model {model.model} not found in pricing")
            prices = self.pricing[model.model]
            token_usage = models_to_tokens[model]

            model_info = {
                "model_name": model.model,
                "TPM_limit_k": model.TPM / 1000,
                "RPM_limit_k": model.RPM / 1000,
                "num_tasks_waiting": num_waiting,
                "token_usage_info": [],
            }

            for cache_status in ['new_token_usage', 'cached_token_usage']:
                cache_info = {"cache_status": cache_status, "details": []}
                token_usage = getattr(models_to_tokens[model], cache_status)
                for token_type in ["prompt_tokens", "completion_tokens"]:
                    tokens = getattr(token_usage, token_type)
                    cache_info["details"].append({
                        "type": token_type,
                        "tokens": tokens,
                        "cost": f"${token_usage.cost(prices):.5f}"
                    })
                model_info["token_usage_info"].append(cache_info)

            model_queues_info.append(model_info)

        
        status_summary = {
            "elapsed_time": f"{elapsed_time:.2f} seconds",
            "estimated_time_remaining": f"{estimated_time_remaining:.2f} seconds",
            "total_interviews_requested": len(interviews),
            "completed_interviews": len(completed_tasks),
            "percent_complete": pct_complete,
            "average_time_per_interview": f"{average_time:.2f} seconds",
            "model_queues": model_queues_info,
            # Include other status details as needed
        }

        return status_summary
        
class JobsRunnerStatusPresentation:

    @staticmethod
    def display_status_table(status_summary):

        table = Table(
            title="Job Status",
            show_header=True,
            header_style="bold magenta",
            box=SIMPLE,
        )
        table.add_column("Key", style="dim", no_wrap=True)
        table.add_column("Value")

        for key, value in status_summary.items():
            # Format keys for display (replace underscores with spaces, capitalize)
            if key != "model_queues":
                display_key = key.replace("_", " ").capitalize()
                table.add_row(display_key, str(value))

        if "model_queues" in status_summary:
            table.add_row(Text("Model Queues", style="bold red"), "")
            for model_info in status_summary["model_queues"]:
                model_name = model_info["model_name"]
                table.add_row(Text(model_name, style="blue"), "")

                # Basic model queue info
                table.add_row("TPM limit (k)", str(model_info["TPM_limit_k"]))
                table.add_row("RPM limit (k)", str(model_info["RPM_limit_k"]))
                table.add_row("Num tasks waiting", str(model_info["num_tasks_waiting"]))

                # Token usage and cost info
                for cache_info in model_info["token_usage_info"]:
                    cache_status = cache_info["cache_status"]
                    table.add_row(Text(cache_status, style="bold"), "")
                    for detail in cache_info["details"]:
                        token_type = detail["type"]
                        tokens = detail["tokens"]
                        cost = detail["cost"]
                        table.add_row(f"-{token_type}", str(tokens))
                        table.add_row("Cost", cost)

        return table


class JobsRunnerStatusMixin(JobsRunnerStatusData, JobsRunnerStatusPresentation):

    def status_table(self, completed_tasks: List[asyncio.Task], elapsed_time: float):
        summary_data = self.generate_status_summary(completed_tasks = completed_tasks, 
                                                    elapsed_time = elapsed_time, interviews = self.total_interviews)
        return self.display_status_table(summary_data)
    
