from typing import Optional, Union, Literal
import requests
import sys
from edsl.exceptions.coop import CoopServerResponseError

# from edsl.enums import VisibilityType
from edsl.results import Results

from IPython.display import display, HTML
import uuid

from IPython.display import display, HTML
import uuid
import json
from datetime import datetime
import re

from edsl.jobs.JobsRemoteInferenceLogger import JupyterJobLogger
from edsl.jobs.JobsRemoteInferenceLogger import StdOutJobLogger

from edsl.utilities.utilities import is_notebook


class JobsRemoteInferenceHandler:
    def __init__(self, jobs, verbose=False, poll_interval=3):
        """ """
        self.jobs = jobs
        self.verbose = verbose
        self.poll_interval = poll_interval

        self._remote_job_creation_data = None
        self._job_uuid = None
        self.logger = None  # Will be initialized when needed

    @property
    def remote_job_creation_data(self):
        return self._remote_job_creation_data

    @property
    def job_uuid(self):
        return self._job_uuid

    def use_remote_inference(self, disable_remote_inference: bool) -> bool:
        if disable_remote_inference:
            return False
        if not disable_remote_inference:
            try:
                from edsl import Coop

                user_edsl_settings = Coop().edsl_settings
                return user_edsl_settings.get("remote_inference", False)
            except requests.ConnectionError:
                pass
            except CoopServerResponseError as e:
                pass

        return False

    def create_remote_inference_job(
        self,
        iterations=1,
        remote_inference_description=None,
        remote_inference_results_visibility="unlisted",
        verbose=False,
    ):
        from edsl.config import CONFIG
        from edsl.coop.coop import Coop
        from rich import print as rich_print

        # Initialize logger
        if is_notebook():
            self.logger = JupyterJobLogger()
        else:
            self.logger = StdOutJobLogger()

        coop = Coop()
        self.logger.update(
            "Remote inference activated. Sending job to server...", "running"
        )
        remote_job_creation_data = coop.remote_inference_create(
            self.jobs,
            description=remote_inference_description,
            status="queued",
            iterations=iterations,
            initial_results_visibility=remote_inference_results_visibility,
        )
        job_uuid = remote_job_creation_data.get("uuid")
        self.logger.update(f"Job sent to server. (Job uuid={job_uuid}).", "running")

        expected_parrot_url = CONFIG.get("EXPECTED_PARROT_URL")
        progress_bar_url = f"{expected_parrot_url}/home/remote-job-progress/{job_uuid}"
        self.logger.update(f"View job progress here: {progress_bar_url}", "running")

        self._remote_job_creation_data = remote_job_creation_data
        self._job_uuid = job_uuid

    @staticmethod
    def check_status(job_uuid):
        from edsl.coop.coop import Coop

        coop = Coop()
        return coop.remote_inference_get(job_uuid)

    def poll_remote_inference_job(self):
        return self._poll_remote_inference_job(
            self.remote_job_creation_data, verbose=self.verbose
        )

    def _poll_remote_inference_job(
        self,
        remote_job_creation_data,
        verbose=False,
        poll_interval=None,
        testing_simulated_response=None,
    ):
        import time
        from datetime import datetime
        from edsl.config import CONFIG

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
            remote_job_data = remote_job_data_fetcher(job_uuid)
            status = remote_job_data.get("status")

            if status == "cancelled":
                self.logger.update("Job cancelled by the user.", "failed")
                self.logger.update(
                    f"See {expected_parrot_url}/home/remote-inference for more details.",
                    "failed",
                )
                return None

            elif status == "failed":
                latest_error_report_url = remote_job_data.get("latest_error_report_url")
                if latest_error_report_url:
                    self.logger.update("Job failed.", "failed")
                    self.logger.update(
                        f"Error report: {latest_error_report_url}", "failed"
                    )
                    self.logger.update(
                        "Need support? Visit Discord: https://discord.com/invite/mxAYkjfy9m",
                        "failed",
                    )
                else:
                    self.logger.update("Job failed.", "failed")
                    self.logger.update(
                        f"See {expected_parrot_url}/home/remote-inference for details.",
                        "failed",
                    )
                return None

            elif status == "completed":
                results_uuid = remote_job_data.get("results_uuid")
                results_url = remote_job_data.get("results_url")
                results = object_fetcher(results_uuid, expected_object_type="results")
                self.logger.update(
                    f"Job completed and Results stored on Coop: {results_url}",
                    "completed",
                )
                return results

            else:
                time_checked = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                self.logger.update(
                    f"Job status: {status} - last update: {time_checked}", "running"
                )
                time.sleep(poll_interval)

    def use_remote_inference(self, disable_remote_inference: bool) -> bool:
        if disable_remote_inference:
            return False
        if not disable_remote_inference:
            try:
                from edsl import Coop

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
        remote_inference_results_visibility: Optional[
            Literal["private", "public", "unlisted"]
        ] = "unlisted",
    ) -> Union[Results, None]:
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
        remote_job_creation_data = await loop.run_in_executor(
            None,
            partial(
                self.create_remote_inference_job,
                iterations=iterations,
                remote_inference_description=remote_inference_description,
                remote_inference_results_visibility=remote_inference_results_visibility,
            ),
        )

        # Poll using existing method but with async sleep
        return await loop.run_in_executor(
            None, partial(self.poll_remote_inference_job, remote_job_creation_data)
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
