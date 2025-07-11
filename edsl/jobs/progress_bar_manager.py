"""
Progress bar management for asynchronous job execution.

This module provides a context manager for handling progress bar setup and thread
management during job execution. It coordinates the display and updating of progress
bars, particularly for remote tracking via the Expected Parrot API.
"""

import threading
import warnings

from ..coop import Coop
from .jobs_runner_status import JobsRunnerStatus


class ProgressBarManager:
    """Context manager for handling progress bar setup and thread management.

    This class manages the progress bar display and updating during job execution,
    particularly for remote tracking via the Expected Parrot API.

    It handles:
    1. Setting up a status tracking object
    2. Creating and managing a background thread for progress updates
    3. Properly cleaning up resources when execution completes
    """

    def __init__(self, jobs, run_config, parameters):
        self.parameters = parameters
        self.jobs = jobs

        # Set up progress tracking
        coop = Coop()
        endpoint_url = coop.get_progress_bar_url()

        # Set up jobs status object
        params = {
            "jobs": jobs,
            "n": parameters.n,
            "endpoint_url": endpoint_url,
            "job_uuid": parameters.job_uuid,
        }

        # If the jobs_runner_status is already set, use it directly
        if run_config.environment.jobs_runner_status is not None:
            self.jobs_runner_status = run_config.environment.jobs_runner_status
        else:
            # Otherwise create a new one
            self.jobs_runner_status = JobsRunnerStatus(**params)

        # Store on run_config for use by other components
        run_config.environment.jobs_runner_status = self.jobs_runner_status

        self.progress_thread = None
        self.stop_event = threading.Event()

    def __enter__(self):
        if self.parameters.progress_bar and self.jobs_runner_status.has_ep_api_key():
            self.jobs_runner_status.setup()
            self.progress_thread = threading.Thread(
                target=self._run_progress_bar,
                args=(self.stop_event, self.jobs_runner_status),
            )
            self.progress_thread.start()
        elif self.parameters.progress_bar:
            warnings.warn(
                "You need an Expected Parrot API key to view job progress bars."
            )
        return self.stop_event

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        if self.progress_thread is not None:
            self.progress_thread.join()

    @staticmethod
    def _run_progress_bar(stop_event, jobs_runner_status):
        """Runs the progress bar in a separate thread."""
        jobs_runner_status.update_progress(stop_event)
