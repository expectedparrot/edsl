"""Remote fetching and polling functionality for Results objects.

This module provides the ResultsRemoteFetcher class which handles remote job
polling, status checking, and data retrieval operations for Results objects.
"""

from typing import TYPE_CHECKING, Any, Union
import time

if TYPE_CHECKING:
    from .results import Results

from .exceptions import ResultsError


class ResultsRemoteFetcher:
    """Handles remote job polling and data fetching for Results objects.

    This class encapsulates the functionality for polling remote job status,
    fetching completed results from remote servers, and updating Results objects
    with retrieved data.

    Attributes:
        results: The Results object to update with remote data
    """

    def __init__(self, results: "Results"):
        """Initialize the remote fetcher with a Results object.

        Args:
            results: The Results object to manage remote fetching for
        """
        self.results = results

    def fetch_remote(self, job_info: Any) -> bool:
        """Fetch remote Results object and update the Results instance with the data.

        This is useful when you have a Results object that was created locally but want to sync it with
        the latest data from the remote server.

        Args:
            job_info: RemoteJobInfo object containing the job_uuid and other remote job details

        Returns:
            bool: True if the fetch was successful, False if the job is not yet completed.

        Raises:
            ResultsError: If there's an error during the fetch process.

        Examples:
            >>> # This is a simplified example since we can't actually test this without a remote server
            >>> from unittest.mock import Mock, patch
            >>> from edsl.results import Results
            >>> # Create a mock job_info and Results
            >>> job_info = Mock()
            >>> job_info.job_uuid = "test_uuid"
            >>> results = Results()
            >>> fetcher = ResultsRemoteFetcher(results)
            >>> # In a real scenario:
            >>> # fetcher.fetch_remote(job_info)
            >>> # results.completed  # Would be True if successful
        """
        try:
            from ..coop import Coop
            from ..jobs import JobsRemoteInferenceHandler

            # Get the remote job data
            remote_job_data = JobsRemoteInferenceHandler.check_status(job_info.job_uuid)

            if remote_job_data.get("status") not in ["completed", "failed"]:
                return False

            results_uuid = remote_job_data.get("results_uuid")
            if not results_uuid:
                raise ResultsError("No results_uuid found in remote job data")

            # Fetch the remote Results object
            coop = Coop()
            remote_results = coop.pull(results_uuid, expected_object_type="results")

            # Replace this instance's results with the remote results
            # Since Results is immutable, we replace the reference entirely
            # The remote results should already have all necessary data in its store
            remote_results.completed = True
            self.results = remote_results

            return True

        except Exception as e:
            raise ResultsError(f"Failed to fetch remote results: {str(e)}")

    def fetch(self, polling_interval: Union[float, int] = 1.0) -> "Results":
        """Poll the server for job completion and update the Results instance.

        This method continuously polls the remote server until the job is completed or
        fails, then updates the Results object with the final data.

        Args:
            polling_interval: Number of seconds to wait between polling attempts (default: 1.0)

        Returns:
            Results: The updated Results instance

        Raises:
            ResultsError: If no job info is available or if there's an error during fetch.

        Examples:
            >>> # This is a simplified example since we can't actually test polling
            >>> from unittest.mock import Mock, patch
            >>> from edsl.results import Results
            >>> # Create a mock results object
            >>> results = Results()
            >>> fetcher = ResultsRemoteFetcher(results)
            >>> # In a real scenario with a running job:
            >>> # results.job_info = remote_job_info
            >>> # fetcher.fetch()  # Would poll until complete
            >>> # results.completed  # Would be True if successful
        """
        if not hasattr(self.results, "job_info"):
            raise ResultsError(
                "No job info available - this Results object wasn't created from a remote job"
            )

        from ..jobs import JobsRemoteInferenceHandler

        try:
            # Get the remote job data
            remote_job_data = JobsRemoteInferenceHandler.check_status(
                self.results.job_info.job_uuid
            )

            while remote_job_data.get("status") not in ["completed", "failed"]:
                print("Waiting for remote job to complete...")
                time.sleep(polling_interval)
                remote_job_data = JobsRemoteInferenceHandler.check_status(
                    self.results.job_info.job_uuid
                )

            # Once complete, fetch the full results
            self.fetch_remote(self.results.job_info)
            return self.results

        except Exception as e:
            raise ResultsError(f"Failed to fetch remote results: {str(e)}")
