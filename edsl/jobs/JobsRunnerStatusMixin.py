from typing import List
import asyncio

from rich.table import Table
from rich.text import Text
from rich.box import SIMPLE

from edsl.jobs.token_tracking import TokenPricing

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
    def __init__(self, model, TPM, RPM):
        self.model = model
        self.TPM = TPM
        self.RPM = RPM


from edsl.jobs.token_tracking import InterviewTokenUsage
from edsl.jobs.task_management import InterviewStatusDictionary

from collections import defaultdict


class JobsRunnerStatusMixin:
    def _generate_status_table(self, data: List[asyncio.Task], elapsed_time):
        models_to_tokens = defaultdict(InterviewTokenUsage)
        model_to_status = defaultdict(InterviewStatusDictionary)

        for interview in self.interviews:
            model = interview.model
            models_to_tokens[model] += interview.token_usage
            model_to_status[model] += interview.interview_status

        pct_complete = len(data) / len(self.interviews) * 100
        average_time = elapsed_time / len(data) if len(data) > 0 else 0

        table = Table(
            title="Job Status",
            show_header=True,
            header_style="bold magenta",
            box=SIMPLE,
        )
        table.add_column("Key", style="dim", no_wrap=True)
        table.add_column("Value")

        # Add rows for each key-value pair
        table.add_row(Text("Task status", style="bold red"), "")
        table.add_row("Total interviews requested", str(len(self.interviews)))
        table.add_row("Completed interviews", str(len(data)))
        # table.add_row("Interviews from cache", str(num_from_cache))
        table.add_row("Percent complete", f"{pct_complete:.2f}%")
        table.add_row("", "")

        # table.add_row(Text("Timing", style = "bold red"), "")
        # table.add_row("Elapsed time (seconds)", f"{elapsed_time:.3f}")
        # table.add_row("Average time/interview (seconds)", f"{average_time:.3f}")
        # table.add_row("", "")

        # table.add_row(Text("Model Queues", style = "bold red"), "")
        # for model, num_waiting in waiting_dict.items():
        #     if model.model not in pricing:
        #         raise ValueError(f"Model {model.model} not found in pricing")
        #     prices = pricing[model.model]
        #     table.add_row(Text(f"{model.model}", style="blue"),"")
        #     table.add_row(f"-TPM limit (k)", str(model.TPM/1000))
        #     table.add_row(f"-RPM limit (k)", str(model.RPM/1000))
        #     table.add_row(f"-Num tasks waiting", str(num_waiting))
        #     token_usage = models_to_tokens[model]
        #     for cache_status in ['new_token_usage', 'cached_token_usage']:
        #         table.add_row(Text(f"{cache_status}", style="bold"), "")
        #         token_usage = getattr(models_to_tokens[model], cache_status)
        #         for token_type in ["prompt_tokens", "completion_tokens"]:
        #             tokens = getattr(token_usage, token_type)
        #             table.add_row(f"-{token_type}", str(tokens))
        #             table.add_row("Cost", f"${token_usage.cost(prices):.5f}")

        return table
