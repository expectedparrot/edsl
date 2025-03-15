"""
Progress tracking for EDSL jobs.

This module provides utilities for tracking and displaying job progress,
with support for both local display and remote progress reporting.
"""
import threading
import warnings
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .data_structures import RunConfig
    from .jobs_runner_status import JobsRunnerStatus
    from ..jobs import Jobs


class ProgressTracker:
    """
    Manages progress tracking for job execution.
    
    This class handles setting up and running progress bars, with support
    for both local terminal display and remote progress reporting via Coop.
    """
    
    def __init__(self, jobs: "Jobs", config: "RunConfig"):
        """
        Initialize a progress tracker.
        
        Parameters:
            jobs: The Jobs instance being executed
            config: Configuration parameters and environment
        """
        self.jobs = jobs
        self.config = config
        self.progress_thread = None
        self.stop_event = threading.Event()
    
    def setup(self) -> None:
        """
        Set up the progress tracking system.
        
        This method initializes the progress bar and starts the tracking
        thread if progress tracking is enabled.
        """
        if not self.config.parameters.progress_bar:
            return
            
        # Get the jobs runner status from environment or create a new one
        jobs_runner_status = self._setup_jobs_runner_status()
        self.config.environment.jobs_runner_status = jobs_runner_status
        
        # Start progress tracking thread if conditions are met
        if jobs_runner_status.has_ep_api_key():
            jobs_runner_status.setup()
            self.progress_thread = threading.Thread(
                target=self._run_progress_bar, 
                args=(self.stop_event, jobs_runner_status)
            )
            self.progress_thread.start()
        else:
            warnings.warn(
                "You need an Expected Parrot API key to view job progress bars."
            )
    
    def cleanup(self) -> None:
        """
        Clean up progress tracking resources.
        
        This method signals the progress tracking thread to stop and
        waits for it to finish.
        """
        self.stop_event.set()
        if self.progress_thread is not None:
            self.progress_thread.join()
    
    def _setup_jobs_runner_status(self) -> "JobsRunnerStatus":
        """
        Set up the jobs runner status object for progress tracking.
        
        Returns:
            JobsRunnerStatus: The configured status tracker
        """
        from edsl.coop import Coop
        from .jobs_runner_status import JobsRunnerStatus
        
        # Get remote progress endpoint URL
        coop = Coop()
        endpoint_url = coop.get_progress_bar_url()
        
        # Use existing status tracker or create a new one
        if self.config.environment.jobs_runner_status is not None:
            return self.config.environment.jobs_runner_status(
                self.jobs,
                n=self.config.parameters.n,
                endpoint_url=endpoint_url,
                job_uuid=self.config.parameters.job_uuid,
            )
        else:
            return JobsRunnerStatus(
                self.jobs,
                n=self.config.parameters.n,
                endpoint_url=endpoint_url,
                job_uuid=self.config.parameters.job_uuid,
            )
    
    def _run_progress_bar(self, stop_event: threading.Event, jobs_runner_status: "JobsRunnerStatus") -> None:
        """
        Run the progress bar in a separate thread.
        
        Parameters:
            stop_event: Event to signal when the progress bar should stop
            jobs_runner_status: Status tracker for updating progress
        """
        jobs_runner_status.update_progress(stop_event)