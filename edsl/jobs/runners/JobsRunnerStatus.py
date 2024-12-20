from __future__ import annotations

import os
import time
import requests
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass

from typing import Any, List, DefaultDict, Optional, Dict
from collections import defaultdict
from uuid import UUID

from edsl.jobs.tokens.InterviewTokenUsage import InterviewTokenUsage

InterviewTokenUsageMapping = DefaultDict[str, InterviewTokenUsage]

from edsl.jobs.interviews.InterviewStatistic import InterviewStatistic
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


class JobsRunnerStatusBase(ABC):
    def __init__(
        self,
        jobs_runner: "JobsRunnerAsyncio",
        n: int,
        refresh_rate: float = 1,
        endpoint_url: Optional[str] = "http://localhost:8000",
        job_uuid: Optional[UUID] = None,
        api_key: str = None,
    ):
        self.jobs_runner = jobs_runner

        # The uuid of the job on Coop
        self.job_uuid = job_uuid

        self.base_url = f"{endpoint_url}"

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

        self.api_key = api_key or os.getenv("EXPECTED_PARROT_API_KEY")

    @abstractmethod
    def has_ep_api_key(self):
        """
        Checks if the user has an Expected Parrot API key.
        """
        pass

    def get_status_dict(self) -> Dict[str, Any]:
        """
        Converts current status into a JSON-serializable dictionary.
        """
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
            "language_model_progress": model_progress,
            "statistics": stats,
            "status": "completed" if completed >= total_interviews else "running",
        }

        model_queues = {}
        for model, bucket in self.jobs_runner.bucket_collection.items():
            model_name = model.model
            model_queues[model_name] = {
                "language_model_name": model_name,
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
        status_dict["language_model_queues"] = model_queues
        return status_dict

    @abstractmethod
    def setup(self):
        """
        Conducts any setup that needs to happen prior to sending status updates.

        Ex. For a local job, creates a job in the Coop database.
        """
        pass

    @abstractmethod
    def send_status_update(self):
        """
        Updates the current status of the job.
        """
        pass

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

    def update_progress(self, stop_event):
        while not stop_event.is_set():
            self.send_status_update()
            time.sleep(self.refresh_rate)

        self.send_status_update()


class JobsRunnerStatus(JobsRunnerStatusBase):
    @property
    def create_url(self) -> str:
        return f"{self.base_url}/api/v0/local-job"

    @property
    def viewing_url(self) -> str:
        return f"{self.base_url}/home/local-job-progress/{str(self.job_uuid)}"

    @property
    def update_url(self) -> str:
        return f"{self.base_url}/api/v0/local-job/{str(self.job_uuid)}"

    def setup(self) -> None:
        """
        Creates a local job on Coop if one does not already exist.
        """

        headers = {"Content-Type": "application/json"}

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        else:
            headers["Authorization"] = f"Bearer None"

        if self.job_uuid is None:
            # Create a new local job
            response = requests.post(
                self.create_url,
                headers=headers,
                timeout=1,
            )
        response.raise_for_status()
        data = response.json()
        self.job_uuid = data.get("job_uuid")

        print(f"Running with progress bar. View progress at {self.viewing_url}")

    def send_status_update(self) -> None:
        """
        Sends current status to the web endpoint using the instance's job_uuid.
        """
        try:
            # Get the status dictionary and add the job_id
            status_dict = self.get_status_dict()

            # Make the UUID JSON serializable
            status_dict["job_id"] = str(self.job_uuid)

            headers = {"Content-Type": "application/json"}

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                headers["Authorization"] = f"Bearer None"

            # Send the update
            response = requests.patch(
                self.update_url,
                json=status_dict,
                headers=headers,
                timeout=1,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Failed to send status update for job {self.job_uuid}: {e}")

    def has_ep_api_key(self) -> bool:
        """
        Returns True if the user has an Expected Parrot API key. Otherwise, returns False.
        """

        if self.api_key is not None:
            return True
        else:
            return False


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
