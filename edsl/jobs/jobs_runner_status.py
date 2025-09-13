from __future__ import annotations

import os
import time
import requests
from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Any, Dict, Optional, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from .jobs import Jobs
    from ..interviews import Interview


class StatisticsTracker:
    def __init__(self, total_interviews: int, distinct_models: list[str]):
        self.start_time = time.time()
        self.total_interviews = total_interviews
        self.completed_count = 0
        self.completed_by_model = defaultdict(int)
        self.distinct_models = distinct_models
        self.interviews_with_exceptions = 0
        self.total_exceptions = 0
        self.unfixed_exceptions = 0
        self.exceptions_counter = defaultdict(int)

        # Question-level tracking
        self.total_questions = 0
        self.completed_questions = 0
        self.completed_questions_by_model = defaultdict(int)
        self.questions_with_exceptions = 0
        self.question_start_times = {}  # question_id -> start_time
        self.question_completion_times = []  # List of completion times in seconds
        self.questions_by_interview = defaultdict(int)  # interview_id -> question_count

        # Real-time metrics
        self.questions_per_second = 0.0
        self.last_question_time = None
        self.recent_question_times = []  # Rolling window for rate calculation
        self.max_recent_times = 20  # Keep last 20 question times for moving average

    def add_completed_interview(
        self,
        model: str,
        exceptions: list[dict],
        num_exceptions: int = 0,
        num_unfixed: int = 0,
    ):
        self.completed_count += 1
        self.completed_by_model[model] += 1
        self.total_exceptions += num_exceptions
        self.unfixed_exceptions += num_unfixed
        if num_exceptions > 0:
            self.interviews_with_exceptions += 1

        for exception in exceptions:
            key = (
                exception["exception_type"],
                exception["inference_service"],
                exception["model"],
                exception["question_name"],
            )
            self.exceptions_counter[key] += 1

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

    def set_total_questions(self, total_questions: int):
        """Set total expected questions across all interviews."""
        self.total_questions = total_questions

    def add_question_started(self, question_id: str, model: str, interview_id: str):
        """Track when a question starts processing."""
        _ = model, interview_id  # Parameters available for future use
        self.question_start_times[question_id] = time.time()

    def add_question_completed(
        self,
        question_id: str,
        model: str,
        interview_id: str,
        success: bool = True,
        exception_info: dict = None,
    ):
        """Track when a question completes (successfully or with error)."""
        _ = exception_info  # Parameter available for future use
        current_time = time.time()

        self.completed_questions += 1
        self.completed_questions_by_model[model] += 1
        self.questions_by_interview[interview_id] += 1

        # Track completion time if we have start time
        if question_id in self.question_start_times:
            duration = current_time - self.question_start_times[question_id]
            self.question_completion_times.append(duration)
            del self.question_start_times[question_id]

        # Update real-time metrics with rolling window
        if self.last_question_time:
            time_delta = current_time - self.last_question_time
            self.recent_question_times.append(time_delta)

            # Keep only recent times for moving average
            if len(self.recent_question_times) > self.max_recent_times:
                self.recent_question_times.pop(0)

            # Calculate questions per second as moving average
            if self.recent_question_times:
                avg_time_between = sum(self.recent_question_times) / len(
                    self.recent_question_times
                )
                if avg_time_between > 0:
                    self.questions_per_second = 1.0 / avg_time_between

        self.last_question_time = current_time

        if not success:
            self.questions_with_exceptions += 1

    def get_question_metrics(self) -> dict:
        """Get real-time question completion metrics."""
        avg_question_time = 0
        if self.question_completion_times:
            avg_question_time = sum(self.question_completion_times) / len(
                self.question_completion_times
            )

        remaining_questions = (
            self.total_questions - self.completed_questions
            if self.total_questions > 0
            else 0
        )

        # Estimate time remaining based on question rate
        estimated_time_remaining = 0
        if self.questions_per_second > 0 and remaining_questions > 0:
            estimated_time_remaining = remaining_questions / self.questions_per_second
        elif avg_question_time > 0 and remaining_questions > 0:
            # Fallback to average time if rate not available
            estimated_time_remaining = remaining_questions * avg_question_time

        return {
            "total_questions": self.total_questions,
            "completed_questions": self.completed_questions,
            "questions_remaining": remaining_questions,
            "questions_per_second": round(self.questions_per_second, 2),
            "average_question_time": round(avg_question_time, 2),
            "questions_with_exceptions": self.questions_with_exceptions,
            "completion_percentage": (
                round((self.completed_questions / self.total_questions * 100), 1)
                if self.total_questions > 0
                else 0
            ),
            "estimated_time_remaining_questions": round(estimated_time_remaining, 1),
        }


class JobsRunnerStatusBase(ABC):
    def __init__(
        self,
        jobs: "Jobs",
        n: int,
        refresh_rate: float = 3,
        endpoint_url: Optional[str] = None,
        job_uuid: Optional[UUID] = None,
        api_key: str = None,
    ):
        self.jobs = jobs
        self.job_uuid = job_uuid

        # Use EXPECTED_PARROT_URL from environment if endpoint_url not provided
        if endpoint_url is None:
            endpoint_url = os.getenv("EXPECTED_PARROT_URL", "http://localhost:8000")

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
        self.num_total_interviews = n * len(self.jobs)

        self.distinct_models = list(set(model.model for model in self.jobs.models))

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
                "has_exceptions": self.stats_tracker.interviews_with_exceptions,
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
            "exceptions_counter": [
                {
                    "exception_type": exception_type,
                    "inference_service": inference_service,
                    "model": model,
                    "question_name": question_name,
                    "count": count,
                }
                for (
                    exception_type,
                    inference_service,
                    model,
                    question_name,
                ), count in self.stats_tracker.exceptions_counter.items()
            ],
            "question_progress": self.stats_tracker.get_question_metrics(),
        }

        model_queues = {}
        # Check if bucket collection exists and is not empty
        if (
            hasattr(self.jobs, "run_config")
            and hasattr(self.jobs.run_config, "environment")
            and hasattr(self.jobs.run_config.environment, "bucket_collection")
            and self.jobs.run_config.environment.bucket_collection
        ):
            for (
                model,
                bucket,
            ) in self.jobs.run_config.environment.bucket_collection.items():
                model_name = model.model
                model_queues[model_name] = {
                    "language_model_name": model_name,
                    "requests_bucket": {
                        "completed": bucket.requests_bucket.num_released,
                        "requested": bucket.requests_bucket.num_requests,
                        "tokens_returned": bucket.requests_bucket.tokens_returned,
                        "target_rate": round(bucket.requests_bucket.target_rate, 1),
                        "current_rate": round(
                            bucket.requests_bucket.get_throughput(), 1
                        ),
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

    def add_completed_interview(self, interview: "Interview"):
        """Records a completed interview without storing the full interview data."""
        self.stats_tracker.add_completed_interview(
            model=interview.model.model,
            exceptions=interview.exceptions.list(),
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
