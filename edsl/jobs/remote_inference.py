import re
import math
from typing import Optional, Union, Literal, TYPE_CHECKING, NewType, Callable, Any
from dataclasses import dataclass
from ..coop import CoopServerResponseError
from ..coop.utils import VisibilityType, CostConverter
from ..coop.coop import RemoteInferenceResponse, RemoteInferenceCreationInfo
from .jobs_status_enums import JobsStatus
from .jobs_remote_inference_logger import JobLogger, JobRunExceptionCounter, ModelCost
from .exceptions import RemoteInferenceError


Seconds = NewType("Seconds", float)
JobUUID = NewType("JobUUID", str)

if TYPE_CHECKING:
    from ..results import Results
    from .jobs import Jobs


class RemoteJobConstants:
    """Constants for remote job handling."""

    REMOTE_JOB_POLL_INTERVAL = 4
    REMOTE_JOB_VERBOSE = False
    DISCORD_URL = "https://discord.com/invite/mxAYkjfy9m"


@dataclass
class RemoteJobInfo:
    creation_data: RemoteInferenceCreationInfo
    job_uuid: JobUUID
    logger: JobLogger


class JobsRemoteInferenceHandler:
    def __init__(
        self,
        jobs: "Jobs",
        verbose: bool = RemoteJobConstants.REMOTE_JOB_VERBOSE,
        poll_interval: Seconds = RemoteJobConstants.REMOTE_JOB_POLL_INTERVAL,
    ):
        """Handles the creation and running of a remote inference job."""
        self.jobs = jobs
        self.verbose = verbose
        self.poll_interval = poll_interval

        from ..config import CONFIG

        self.expected_parrot_url = CONFIG.get("EXPECTED_PARROT_URL")
        self.remote_inference_url = f"{self.expected_parrot_url}/home/remote-inference"

    def _create_logger(self) -> JobLogger:
        from ..utilities import is_notebook
        from .jobs_remote_inference_logger import (
            StdOutJobLogger,
        )
        from .html_table_job_logger import HTMLTableJobLogger

        if is_notebook():
            return HTMLTableJobLogger(verbose=self.verbose)
        return StdOutJobLogger(verbose=self.verbose)

    def use_remote_inference(self, disable_remote_inference: bool) -> bool:
        import requests

        if disable_remote_inference:
            return False
        if not disable_remote_inference:
            try:
                from ..coop import Coop

                user_edsl_settings = Coop().edsl_settings
                return user_edsl_settings.get("remote_inference", False)
            except requests.ConnectionError:
                pass
            except CoopServerResponseError:
                pass

        return False

    def create_remote_inference_job(
        self,
        iterations: int = 1,
        remote_inference_description: Optional[str] = None,
        remote_inference_results_visibility: Optional["VisibilityType"] = "unlisted",
        fresh: Optional[bool] = False,
    ) -> RemoteJobInfo:
        from ..coop import Coop

        logger = self._create_logger()

        coop = Coop()
        logger.update(
            "Remote inference activated. Sending job to server...",
            status=JobsStatus.QUEUED,
        )
        logger.add_info(
            "remote_inference_url", f"{self.expected_parrot_url}/home/remote-inference"
        )
        logger.add_info(
            "remote_cache_url", f"{self.expected_parrot_url}/home/remote-cache"
        )
        remote_job_creation_data = coop.remote_inference_create(
            self.jobs,
            description=remote_inference_description,
            status="queued",
            iterations=iterations,
            initial_results_visibility=remote_inference_results_visibility,
            fresh=fresh,
        )
        logger.update(
            "Your survey is running at the Expected Parrot server...",
            status=JobsStatus.RUNNING,
        )
        job_uuid = remote_job_creation_data.get("uuid")
        logger.update(
            message=f"Job sent to server. (Job uuid={job_uuid}).",
            status=JobsStatus.RUNNING,
        )
        logger.add_info("job_uuid", job_uuid)

        remote_inference_url = self.remote_inference_url
        if "localhost" in remote_inference_url:
            remote_inference_url = remote_inference_url.replace("8000", "1234")
        logger.update(
            f"Job details are available at your Coop account. [Go to Remote Inference page]({remote_inference_url})",
            status=JobsStatus.RUNNING,
        )
        progress_bar_url = (
            f"{self.expected_parrot_url}/home/remote-job-progress/{job_uuid}"
        )
        if "localhost" in progress_bar_url:
            progress_bar_url = progress_bar_url.replace("8000", "1234")
        logger.add_info("progress_bar_url", progress_bar_url)
        logger.update(
            f"View job progress [here]({progress_bar_url})", status=JobsStatus.RUNNING
        )

        return RemoteJobInfo(
            creation_data=remote_job_creation_data,
            job_uuid=job_uuid,
            logger=logger,
        )

    @staticmethod
    def check_status(
        job_uuid: JobUUID,
    ) -> "RemoteInferenceResponse":
        from ..coop import Coop

        coop = Coop()
        return coop.remote_inference_get(job_uuid)

    def _construct_remote_job_fetcher(
        self, testing_simulated_response: Optional[Any] = None
    ) -> Callable:
        if testing_simulated_response is not None:
            return lambda job_uuid: testing_simulated_response
        else:
            from ..coop import Coop

            coop = Coop()
            return coop.remote_inference_get

    def _construct_object_fetcher(
        self, testing_simulated_response: Optional[Any] = None
    ) -> Callable:
        "Constructs a function to fetch the results object from Coop."
        if testing_simulated_response is not None:
            return lambda results_uuid, expected_object_type: Results.example()
        else:
            from ..coop import Coop

            coop = Coop()
            return coop.get

    def _handle_cancelled_job(self, job_info: RemoteJobInfo) -> None:
        "Handles a cancelled job by logging the cancellation and updating the job status."

        job_info.logger.update(
            message="Job cancelled by the user.", status=JobsStatus.CANCELLED
        )
        job_info.logger.update(
            f"See [Remote Inference page]({self.expected_parrot_url}/home/remote-inference) for more details.",
            status=JobsStatus.CANCELLED,
        )

    def _handle_failed_job(
        self, job_info: RemoteJobInfo, remote_job_data: RemoteInferenceResponse
    ) -> None:
        "Handles a failed job by logging the error and updating the job status."
        error_report_url = remote_job_data.get("latest_job_run_details", {}).get(
            "error_report_url"
        )

        reason = remote_job_data.get("reason")

        if reason == "insufficient funds":
            job_info.logger.update(
                f"Error: Insufficient balance to start the job. Add funds to your account at the [Credits page]({self.expected_parrot_url}/home/credits)",
                status=JobsStatus.FAILED,
            )

        if error_report_url:
            job_info.logger.add_info("error_report_url", error_report_url)

        job_info.logger.update("Job failed.", status=JobsStatus.FAILED)
        job_info.logger.update(
            f"See [Remote Inference page]({self.expected_parrot_url}/home/remote-inference) for more details.",
            status=JobsStatus.FAILED,
        )
        job_info.logger.update(
            f"Need support? [Visit Discord]({RemoteJobConstants.DISCORD_URL})",
            status=JobsStatus.FAILED,
        )

    def _update_interview_details(
        self, job_info: RemoteJobInfo, remote_job_data: RemoteInferenceResponse
    ) -> None:
        "Updates the interview details in the job info."
        latest_job_run_details = remote_job_data.get("latest_job_run_details", {})
        interview_details = latest_job_run_details.get("interview_details", {}) or {}
        completed_interviews = interview_details.get("completed_interviews", 0)
        interviews_with_exceptions = interview_details.get(
            "interviews_with_exceptions", 0
        )
        interviews_without_exceptions = (
            completed_interviews - interviews_with_exceptions
        )
        job_info.logger.add_info("completed_interviews", interviews_without_exceptions)
        job_info.logger.add_info("failed_interviews", interviews_with_exceptions)

        exception_summary = interview_details.get("exception_summary", []) or []
        if exception_summary:
            job_run_exception_counters = []
            for exception in exception_summary:
                exception_counter = JobRunExceptionCounter(
                    exception_type=exception.get("exception_type"),
                    inference_service=exception.get("inference_service"),
                    model=exception.get("model"),
                    question_name=exception.get("question_name"),
                    exception_count=exception.get("exception_count"),
                )
                job_run_exception_counters.append(exception_counter)
            job_info.logger.add_info("exception_summary", job_run_exception_counters)

    def _handle_partially_failed_job(
        self, job_info: RemoteJobInfo, remote_job_data: RemoteInferenceResponse
    ) -> None:
        "Handles a partially failed job by logging the error and updating the job status."
        error_report_url = remote_job_data.get("latest_job_run_details", {}).get(
            "error_report_url"
        )

        if error_report_url:
            job_info.logger.add_info("error_report_url", error_report_url)

        job_info.logger.update(
            "Job completed with partial results.", status=JobsStatus.PARTIALLY_FAILED
        )
        job_info.logger.update(
            f"See [Remote Inference page]({self.expected_parrot_url}/home/remote-inference) for more details.",
            status=JobsStatus.PARTIALLY_FAILED,
        )
        job_info.logger.update(
            f"Need support? [Visit Discord]({RemoteJobConstants.DISCORD_URL})",
            status=JobsStatus.PARTIALLY_FAILED,
        )

    def _sleep_for_a_bit(self, job_info: RemoteJobInfo, status: str) -> None:
        import time
        from datetime import datetime

        time_checked = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
        job_info.logger.update(
            f"Job status: {status} - last update: {time_checked}",
            status=JobsStatus.RUNNING,
        )
        time.sleep(self.poll_interval)

    def _get_expenses_from_results(
        self, results: "Results", include_cached_responses_in_cost: bool = False
    ) -> dict:
        """
        Calculates expenses from Results object.

        Args:
            results: Results object containing model responses
            include_cached_responses_in_cost: Whether to include cached responses in cost calculation

        Returns:
            Dictionary mapping ExpenseKey to TokenExpense information
        """
        expenses = {}

        for result in results:
            raw_response = result["raw_model_response"]

            # Process each cost field in the response
            for key in raw_response:
                if not key.endswith("_cost"):
                    continue

                result_cost = raw_response[key]
                if not isinstance(result_cost, (int, float)):
                    continue

                question_name = key.removesuffix("_cost")
                cache_used = result["cache_used_dict"][question_name]

                # Skip if we're excluding cached responses and this was cached
                if not include_cached_responses_in_cost and cache_used:
                    continue

                # Get expense keys for input and output tokens
                input_key = (
                    result["model"]._inference_service_,
                    result["model"].model,
                    "input",
                    raw_response[f"{question_name}_input_price_per_million_tokens"],
                )
                output_key = (
                    result["model"]._inference_service_,
                    result["model"].model,
                    "output",
                    raw_response[f"{question_name}_output_price_per_million_tokens"],
                )

                # Update input token expenses
                if input_key not in expenses:
                    expenses[input_key] = {
                        "tokens": 0,
                        "cost_usd": 0,
                    }

                input_price_per_million_tokens = input_key[3]
                input_tokens = raw_response[f"{question_name}_input_tokens"]
                input_cost = (input_price_per_million_tokens / 1_000_000) * input_tokens

                expenses[input_key]["tokens"] += input_tokens
                expenses[input_key]["cost_usd"] += input_cost

                # Update output token expenses
                if output_key not in expenses:
                    expenses[output_key] = {
                        "tokens": 0,
                        "cost_usd": 0,
                    }

                output_price_per_million_tokens = output_key[3]
                output_tokens = raw_response[f"{question_name}_output_tokens"]
                output_cost = (
                    output_price_per_million_tokens / 1_000_000
                ) * output_tokens

                expenses[output_key]["tokens"] += output_tokens
                expenses[output_key]["cost_usd"] += output_cost

        expenses_by_model = {}
        for expense_key, expense_usage in expenses.items():
            service, model, token_type, _ = expense_key
            model_key = (service, model)

            if model_key not in expenses_by_model:
                expenses_by_model[model_key] = {
                    "service": service,
                    "model": model,
                    "input_tokens": 0,
                    "input_cost_usd": 0,
                    "output_tokens": 0,
                    "output_cost_usd": 0,
                }

            if token_type == "input":
                expenses_by_model[model_key]["input_tokens"] += expense_usage["tokens"]
                expenses_by_model[model_key]["input_cost_usd"] += expense_usage[
                    "cost_usd"
                ]
            elif token_type == "output":
                expenses_by_model[model_key]["output_tokens"] += expense_usage["tokens"]
                expenses_by_model[model_key]["output_cost_usd"] += expense_usage[
                    "cost_usd"
                ]

        converter = CostConverter()
        for model_key, model_cost_dict in expenses_by_model.items():
            input_cost = model_cost_dict["input_cost_usd"]
            output_cost = model_cost_dict["output_cost_usd"]
            model_cost_dict["input_cost_credits"] = converter.usd_to_credits(input_cost)
            model_cost_dict["output_cost_credits"] = converter.usd_to_credits(
                output_cost
            )
            # Convert back to USD (to get the rounded value)
            model_cost_dict["input_cost_usd"] = converter.credits_to_usd(
                model_cost_dict["input_cost_credits"]
            )
            model_cost_dict["output_cost_usd"] = converter.credits_to_usd(
                model_cost_dict["output_cost_credits"]
            )

        return list(expenses_by_model.values())

    def _fetch_results_and_log(
        self,
        job_info: RemoteJobInfo,
        job_status: Literal["failed", "partial_failed", "completed"],
        results_uuid: str,
        remote_job_data: RemoteInferenceResponse,
        object_fetcher: Callable,
    ) -> "Results":
        "Fetches the results object and logs the results URL."
        job_info.logger.add_info("results_uuid", results_uuid)
        results = object_fetcher(results_uuid, expected_object_type="results")

        model_cost_dicts = self._get_expenses_from_results(results)

        model_costs = [
            ModelCost(
                service=model_cost_dict.get("service"),
                model=model_cost_dict.get("model"),
                input_tokens=model_cost_dict.get("input_tokens"),
                input_cost_usd=model_cost_dict.get("input_cost_usd"),
                output_tokens=model_cost_dict.get("output_tokens"),
                output_cost_usd=model_cost_dict.get("output_cost_usd"),
            )
            for model_cost_dict in model_cost_dicts
        ]
        job_info.logger.add_info("model_costs", model_costs)

        results_url = remote_job_data.get("results_url")
        if "localhost" in results_url:
            results_url = results_url.replace("8000", "1234")
        job_info.logger.add_info("results_url", results_url)

        if job_status == "completed":
            job_info.logger.add_info("completed_interviews", len(results))
            job_info.logger.add_info("failed_interviews", 0)
            job_info.logger.update(
                f"Job completed and Results stored on Coop. [View Results]({results_url})",
                status=JobsStatus.COMPLETED,
            )
        elif job_status == "partial_failed":
            job_info.logger.update(
                f"View partial results [here]({results_url})",
                status=JobsStatus.PARTIALLY_FAILED,
            )

        results.job_uuid = job_info.job_uuid
        results.results_uuid = results_uuid
        return results

    def _attempt_fetch_job(
        self,
        job_info: RemoteJobInfo,
        remote_job_data_fetcher: Callable,
        object_fetcher: Callable,
    ) -> Union[None, "Results", Literal["continue"]]:
        """Makes one attempt to fetch and process a remote job's status and results."""
        remote_job_data = remote_job_data_fetcher(job_info.job_uuid)
        self._update_interview_details(job_info, remote_job_data)
        status = remote_job_data.get("status")
        reason = remote_job_data.get("reason")
        if status == "cancelled":
            self._handle_cancelled_job(job_info)
            return None, reason

        elif status == "failed" or status == "completed" or status == "partial_failed":
            if status == "failed":
                self._handle_failed_job(job_info, remote_job_data)
            elif status == "partial_failed":
                self._handle_partially_failed_job(job_info, remote_job_data)

            results_uuid = remote_job_data.get("results_uuid")
            if results_uuid:
                results = self._fetch_results_and_log(
                    job_info=job_info,
                    job_status=status,
                    results_uuid=results_uuid,
                    remote_job_data=remote_job_data,
                    object_fetcher=object_fetcher,
                )
                return results, reason
            else:
                return None, reason

        else:
            self._sleep_for_a_bit(job_info, status)
            return "continue", reason

    def poll_remote_inference_job(
        self,
        job_info: RemoteJobInfo,
        testing_simulated_response=None,
    ) -> Union[None, "Results"]:
        """Polls a remote inference job for completion and returns the results."""

        remote_job_data_fetcher = self._construct_remote_job_fetcher(
            testing_simulated_response
        )
        object_fetcher = self._construct_object_fetcher(testing_simulated_response)

        job_in_queue = True
        while job_in_queue:
            result, reason = self._attempt_fetch_job(
                job_info, remote_job_data_fetcher, object_fetcher
            )
            if result != "continue":
                return result, reason

    async def create_and_poll_remote_job(
        self,
        iterations: int = 1,
        remote_inference_description: Optional[str] = None,
        remote_inference_results_visibility: Optional[VisibilityType] = "unlisted",
    ) -> Union["Results", None]:
        """
        Creates and polls a remote inference job asynchronously.
        Reuses existing synchronous methods but runs them in an async context.

        :param iterations: Number of times to run each interview
        :param remote_inference_description: Optional description for the remote job
        :param remote_inference_results_visibility: Visibility setting for results
        :return: Results object if successful, None if job fails or is cancelled
        """
        import asyncio
        from functools import partial

        # Create job using existing method
        loop = asyncio.get_event_loop()
        job_info = await loop.run_in_executor(
            None,
            partial(
                self.create_remote_inference_job,
                iterations=iterations,
                remote_inference_description=remote_inference_description,
                remote_inference_results_visibility=remote_inference_results_visibility,
            ),
        )
        if job_info is None:
            raise RemoteInferenceError("Remote job creation failed.")

        return await loop.run_in_executor(
            None,
            partial(self.poll_remote_inference_job, job_info),
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
