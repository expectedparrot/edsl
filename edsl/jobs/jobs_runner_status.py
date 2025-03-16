from __future__ import annotations

import os
import time
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass
from collections import defaultdict
from typing import Any, Dict, Optional, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from .jobs_runner_asyncio import JobsRunnerAsyncio


@dataclass
class ModelInfo:
    model_name: str
    TPM_limit_k: float
    RPM_limit_k: float
    num_tasks_waiting: int
    token_usage_info: dict


class StatisticsTracker:
    def __init__(self, total_interviews: int, distinct_models: list[str]):
        self.start_time = time.time()
        self.total_interviews = total_interviews
        self.completed_count = 0
        self.completed_by_model = defaultdict(int)
        self.distinct_models = distinct_models
        self.total_exceptions = 0
        self.unfixed_exceptions = 0

    def add_completed_interview(
        self, model: str, num_exceptions: int = 0, num_unfixed: int = 0
    ):
        self.completed_count += 1
        self.completed_by_model[model] += 1
        self.total_exceptions += num_exceptions
        self.unfixed_exceptions += num_unfixed

    def get_elapsed_time(self) -> float:
        return time.time() - self.start_time

    def get_average_time_per_interview(self) -> float:
        return (
            self.get_elapsed_time() / self.completed_count
            if self.completed_count > 0
            else 0
        )

    def get_throughput(self) -> float:
        elapsed = self.get_elapsed_time()
        return self.completed_count / elapsed if elapsed > 0 else 0

    def get_estimated_time_remaining(self) -> float:
        if self.completed_count == 0:
            return 0
        avg_time = self.get_average_time_per_interview()
        remaining = self.total_interviews - self.completed_count
        return avg_time * remaining


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
        self.job_uuid = job_uuid
        self.base_url = f"{endpoint_url}"
        self.refresh_rate = refresh_rate
        self.statistics = [
            "elapsed_time",
            "total_interviews_requested",
            "completed_interviews",
            "average_time_per_interview",
            "estimated_time_remaining",
            "exceptions",
            "unfixed_exceptions",
            "throughput",
        ]
        self.num_total_interviews = n * len(self.jobs_runner)

        self.distinct_models = list(
            set(model.model for model in self.jobs_runner.jobs.models)
        )

        self.stats_tracker = StatisticsTracker(
            total_interviews=self.num_total_interviews,
            distinct_models=self.distinct_models,
        )

        self.api_key = api_key or os.getenv("EXPECTED_PARROT_API_KEY")

    @abstractmethod
    def has_ep_api_key(self):
        """Checks if the user has an Expected Parrot API key."""
        pass

    def get_status_dict(self) -> Dict[str, Any]:
        """Converts current status into a JSON-serializable dictionary."""
        # Get all statistics
        stats = {}
        for stat_name in self.statistics:
            stat = self._compute_statistic(stat_name)
            name, value = list(stat.items())[0]
            stats[name] = value

        # Get model-specific progress
        model_progress = {}
        target_per_model = int(self.num_total_interviews / len(self.distinct_models))

        for model in self.distinct_models:
            completed = self.stats_tracker.completed_by_model[model]
            model_progress[model] = {
                "completed": completed,
                "total": target_per_model,
                "percent": (
                    (completed / target_per_model * 100) if target_per_model > 0 else 0
                ),
            }

        status_dict = {
            "overall_progress": {
                "completed": self.stats_tracker.completed_count,
                "total": self.num_total_interviews,
                "percent": (
                    (
                        self.stats_tracker.completed_count
                        / self.num_total_interviews
                        * 100
                    )
                    if self.num_total_interviews > 0
                    else 0
                ),
            },
            "language_model_progress": model_progress,
            "statistics": stats,
            "status": (
                "completed"
                if self.stats_tracker.completed_count >= self.num_total_interviews
                else "running"
            ),
        }

        model_queues = {}
        # for model, bucket in self.jobs_runner.bucket_collection.items():
        for model, bucket in self.jobs_runner.environment.bucket_collection.items():
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

    def add_completed_interview(self, interview):
        """Records a completed interview without storing the full interview data."""
        self.stats_tracker.add_completed_interview(
            model=interview.model.model,
            num_exceptions=interview.exceptions.num_exceptions(),
            num_unfixed=interview.exceptions.num_unfixed_exceptions(),
        )

    def _compute_statistic(self, stat_name: str):
        """Computes individual statistics based on the stats tracker."""
        if stat_name == "elapsed_time":
            value = self.stats_tracker.get_elapsed_time()
            return {"elapsed_time": (value, 1, "sec.")}

        elif stat_name == "total_interviews_requested":
            return {"total_interviews_requested": (self.num_total_interviews, None, "")}

        elif stat_name == "completed_interviews":
            return {
                "completed_interviews": (self.stats_tracker.completed_count, None, "")
            }

        elif stat_name == "average_time_per_interview":
            value = self.stats_tracker.get_average_time_per_interview()
            return {"average_time_per_interview": (value, 2, "sec.")}

        elif stat_name == "estimated_time_remaining":
            value = self.stats_tracker.get_estimated_time_remaining()
            return {"estimated_time_remaining": (value, 1, "sec.")}

        elif stat_name == "exceptions":
            return {"exceptions": (self.stats_tracker.total_exceptions, None, "")}

        elif stat_name == "unfixed_exceptions":
            return {
                "unfixed_exceptions": (self.stats_tracker.unfixed_exceptions, None, "")
            }

        elif stat_name == "throughput":
            value = self.stats_tracker.get_throughput()
            return {"throughput": (value, 2, "interviews/sec.")}

    def update_progress(self, stop_event):
        while not stop_event.is_set():
            self.send_status_update()
            time.sleep(self.refresh_rate)
        self.send_status_update()

    @abstractmethod
    def setup(self):
        """Conducts any setup needed prior to sending status updates."""
        pass

    @abstractmethod
    def send_status_update(self):
        """Updates the current status of the job."""
        pass


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
        """Creates a local job on Coop if one does not already exist."""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or 'None'}",
        }

        if self.job_uuid is None:
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
        """Sends current status to the web endpoint using the instance's job_uuid."""
        try:
            status_dict = self.get_status_dict()
            status_dict["job_id"] = str(self.job_uuid)

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key or 'None'}",
            }

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
        """Returns True if the user has an Expected Parrot API key."""
        return self.api_key is not None


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
