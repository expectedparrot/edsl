from typing import Optional, Union, Literal, TYPE_CHECKING, NewType


Seconds = NewType("Seconds", float)
JobUUID = NewType("JobUUID", str)

from edsl.exceptions.coop import CoopServerResponseError

if TYPE_CHECKING:
    from edsl.results.Results import Results
    from edsl.jobs.Jobs import Jobs
    from edsl.coop.coop import RemoteInferenceResponse, RemoteInferenceCreationInfo
    from edsl.jobs.JobsRemoteInferenceLogger import JobLogger

from edsl.coop.coop import RemoteInferenceResponse, RemoteInferenceCreationInfo

from edsl.jobs.jobs_status_enums import JobsStatus
from edsl.coop.utils import VisibilityType


class JobsRemoteInferenceHandler:
    def __init__(self, jobs: "Jobs", verbose: bool = False, poll_interval: Seconds = 1):
        """ """
        self.jobs = jobs
        self.verbose = verbose
        self.poll_interval = poll_interval

        self._remote_job_creation_data: Union[None, RemoteInferenceCreationInfo] = None
        self._job_uuid: Union[None, JobUUID] = None  # Will be set when job is created
        self.logger: Union[None, JobLogger] = None  # Will be initialized when needed

    @property
    def remote_job_creation_data(self) -> RemoteInferenceCreationInfo:
        return self._remote_job_creation_data

    @property
    def job_uuid(self) -> JobUUID:
        return self._job_uuid

    def use_remote_inference(self, disable_remote_inference: bool) -> bool:
        import requests

        if disable_remote_inference:
            return False
        if not disable_remote_inference:
            try:
                from edsl.coop.coop import Coop

                user_edsl_settings = Coop().edsl_settings
                return user_edsl_settings.get("remote_inference", False)
            except requests.ConnectionError:
                pass
            except CoopServerResponseError as e:
                pass

        return False

    def create_remote_inference_job(
        self,
        iterations: int = 1,
        remote_inference_description: Optional[str] = None,
        remote_inference_results_visibility: Optional[VisibilityType] = "unlisted",
    ) -> None:
        from edsl.config import CONFIG
        from edsl.coop.coop import Coop

        # Initialize logger
        from edsl.utilities.is_notebook import is_notebook
        from edsl.jobs.JobsRemoteInferenceLogger import JupyterJobLogger
        from edsl.jobs.JobsRemoteInferenceLogger import StdOutJobLogger
        from edsl.jobs.loggers.HTMLTableJobLogger import HTMLTableJobLogger

        if is_notebook():
            self.logger = HTMLTableJobLogger(verbose=self.verbose)
        else:
            self.logger = StdOutJobLogger(verbose=self.verbose)

        coop = Coop()
        self.logger.update(
            "Remote inference activated. Sending job to server...",
            status=JobsStatus.QUEUED,
        )
        remote_job_creation_data = coop.remote_inference_create(
            self.jobs,
            description=remote_inference_description,
            status="queued",
            iterations=iterations,
            initial_results_visibility=remote_inference_results_visibility,
        )
        self.logger.update(
            "Your survey is running at the Expected Parrot server...",
            status=JobsStatus.RUNNING,
        )

        job_uuid = remote_job_creation_data.get("uuid")
        self.logger.update(
            message=f"Job sent to server. (Job uuid={job_uuid}).",
            status=JobsStatus.RUNNING,
        )
        self.logger.add_info("job_uuid", job_uuid)

        expected_parrot_url = CONFIG.get("EXPECTED_PARROT_URL")
        remote_inference_url = f"{expected_parrot_url}/home/remote-inference"

        self.logger.update(
            f"Job details are available at your Coop account {remote_inference_url}{remote_inference_url}",
            status=JobsStatus.RUNNING,
        )
        progress_bar_url = f"{expected_parrot_url}/home/remote-job-progress/{job_uuid}"
        self.logger.add_info("progress_bar_url", progress_bar_url)
        self.logger.update(
            f"View job progress here: {progress_bar_url}", status=JobsStatus.RUNNING
        )

        self._remote_job_creation_data = remote_job_creation_data
        self._job_uuid = job_uuid

    @staticmethod
    def check_status(
        job_uuid: JobUUID,
    ) -> RemoteInferenceResponse:
        from edsl.coop.coop import Coop

        coop = Coop()
        return coop.remote_inference_get(job_uuid)

    def poll_remote_inference_job(self) -> Union[None, "Results"]:
        return self._poll_remote_inference_job(
            self.remote_job_creation_data, verbose=self.verbose
        )

    def _poll_remote_inference_job(
        self,
        remote_job_creation_data: RemoteInferenceCreationInfo,
        verbose: bool = False,
        poll_interval: Optional[Seconds] = None,
        testing_simulated_response=None,
    ) -> Union[None, "Results"]:
        import time
        from datetime import datetime
        from edsl.config import CONFIG
        from edsl.results.Results import Results

        if poll_interval is None:
            poll_interval = self.poll_interval

        job_uuid = remote_job_creation_data.get("uuid")
        expected_parrot_url = CONFIG.get("EXPECTED_PARROT_URL")

        if testing_simulated_response is not None:
            remote_job_data_fetcher = lambda job_uuid: testing_simulated_response
            object_fetcher = (
                lambda results_uuid, expected_object_type: Results.example()
            )
        else:
            from edsl.coop.coop import Coop

            coop = Coop()
            remote_job_data_fetcher = coop.remote_inference_get
            object_fetcher = coop.get

        job_in_queue = True
        while job_in_queue:
            remote_job_data: RemoteInferenceResponse = remote_job_data_fetcher(job_uuid)
            status = remote_job_data.get("status")

            if status == "cancelled":
                self.logger.update(
                    messaged="Job cancelled by the user.", status=JobsStatus.CANCELLED
                )
                self.logger.update(
                    f"See {expected_parrot_url}/home/remote-inference for more details.",
                    status=JobsStatus.CANCELLED,
                )
                return None

            elif status == "failed":
                latest_error_report_url = remote_job_data.get("latest_error_report_url")
                if latest_error_report_url:
                    self.logger.update("Job failed.", status=JobsStatus.FAILED)
                    self.logger.update(
                        f"Error report: {latest_error_report_url}", "failed"
                    )
                    self.logger.add_info("error_report_url", latest_error_report_url)
                    self.logger.update(
                        "Need support? Visit Discord: https://discord.com/invite/mxAYkjfy9m",
                        status=JobsStatus.FAILED,
                    )
                else:
                    self.logger.update("Job failed.", "failed")
                    self.logger.update(
                        f"See {expected_parrot_url}/home/remote-inference for details.",
                        status=JobsStatus.FAILED,
                    )

                results_uuid = remote_job_data.get("results_uuid")
                if results_uuid:
                    self.logger.add_info("results_uuid", results_uuid)
                    results = object_fetcher(
                        results_uuid, expected_object_type="results"
                    )
                    results.job_uuid = job_uuid
                    results.results_uuid = results_uuid
                    return results
                else:
                    return None

            elif status == "completed":
                results_uuid = remote_job_data.get("results_uuid")
                self.logger.add_info("results_uuid", results_uuid)
                results_url = remote_job_data.get("results_url")
                self.logger.add_info("results_url", results_url)
                results = object_fetcher(results_uuid, expected_object_type="results")
                self.logger.update(
                    f"Job completed and Results stored on Coop: {results_url}",
                    status=JobsStatus.COMPLETED,
                )
                results.job_uuid = job_uuid
                results.results_uuid = results_uuid
                return results

            else:
                time_checked = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                self.logger.update(
                    f"Job status: {status} - last update: {time_checked}",
                    status=JobsStatus.RUNNING,
                )
                time.sleep(poll_interval)

    def use_remote_inference(self, disable_remote_inference: bool) -> bool:
        import requests

        if disable_remote_inference:
            return False
        if not disable_remote_inference:
            try:
                from edsl.coop.coop import Coop

                user_edsl_settings = Coop().edsl_settings
                return user_edsl_settings.get("remote_inference", False)
            except requests.ConnectionError:
                pass
            except CoopServerResponseError as e:
                pass

        return False

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
        _ = await loop.run_in_executor(
            None,
            partial(
                self.create_remote_inference_job,
                iterations=iterations,
                remote_inference_description=remote_inference_description,
                remote_inference_results_visibility=remote_inference_results_visibility,
            ),
        )
        # breakpoint()
        # Poll using existing method but with async sleep
        if self._remote_job_creation_data is None:
            raise ValueError("Remote job creation failed.")

        return await loop.run_in_executor(
            None,
            partial(self.poll_remote_inference_job, None),
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
