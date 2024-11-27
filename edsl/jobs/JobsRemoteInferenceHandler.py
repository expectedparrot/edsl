from typing import Optional, Union, Literal
import requests
import sys
from edsl.exceptions.coop import CoopServerResponseError

# from edsl.enums import VisibilityType
from edsl.results import Results


class JobsRemoteInferenceHandler:
    def __init__(self, jobs, verbose=False, poll_interval=3):
        """
        >>> from edsl.jobs import Jobs
        >>> jh = JobsRemoteInferenceHandler(Jobs.example(), verbose=True)
        >>> jh.use_remote_inference(True)
        False
        >>> jh._poll_remote_inference_job({'uuid':1234}, testing_simulated_response={"status": "failed"}) # doctest: +NORMALIZE_WHITESPACE
        Job failed.
        ...
        >>> jh._poll_remote_inference_job({'uuid':1234}, testing_simulated_response={"status": "completed"}) # doctest: +NORMALIZE_WHITESPACE
        Job completed and Results stored on Coop: None.
        Results(...)
        """
        self.jobs = jobs
        self.verbose = verbose
        self.poll_interval = poll_interval

        self._remote_job_creation_data = None
        self._job_uuid = None

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
        iterations: int = 1,
        remote_inference_description: Optional[str] = None,
        remote_inference_results_visibility: Optional["VisibilityType"] = "unlisted",
        verbose=False,
    ):
        """ """
        from edsl.config import CONFIG
        from edsl.coop.coop import Coop
        from rich import print as rich_print

        coop = Coop()
        print("Remote inference activated. Sending job to server...")
        remote_job_creation_data = coop.remote_inference_create(
            self.jobs,
            description=remote_inference_description,
            status="queued",
            iterations=iterations,
            initial_results_visibility=remote_inference_results_visibility,
        )
        job_uuid = remote_job_creation_data.get("uuid")
        print(f"Job sent to server. (Job uuid={job_uuid}).")

        expected_parrot_url = CONFIG.get("EXPECTED_PARROT_URL")
        progress_bar_url = f"{expected_parrot_url}/home/remote-job-progress/{job_uuid}"

        rich_print(
            f"View job progress here: [#38bdf8][link={progress_bar_url}]{progress_bar_url}[/link][/#38bdf8]"
        )

        self._remote_job_creation_data = remote_job_creation_data
        self._job_uuid = job_uuid
        # return remote_job_creation_data

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
        remote_job_creation_data: dict,
        verbose=False,
        poll_interval: Optional[float] = None,
        testing_simulated_response: Optional[dict] = None,
    ) -> Union[Results, None]:
        import time
        from datetime import datetime
        from edsl.config import CONFIG
        from edsl.coop.coop import Coop

        if poll_interval is None:
            poll_interval = self.poll_interval

        expected_parrot_url = CONFIG.get("EXPECTED_PARROT_URL")

        job_uuid = remote_job_creation_data.get("uuid")
        coop = Coop()

        if testing_simulated_response is not None:
            remote_job_data_fetcher = lambda job_uuid: testing_simulated_response
            object_fetcher = (
                lambda results_uuid, expected_object_type: Results.example()
            )
        else:
            remote_job_data_fetcher = coop.remote_inference_get
            object_fetcher = coop.get

        job_in_queue = True
        while job_in_queue:
            remote_job_data = remote_job_data_fetcher(job_uuid)
            status = remote_job_data.get("status")
            if status == "cancelled":
                print("\r" + " " * 80 + "\r", end="")
                print("Job cancelled by the user.")
                print(
                    f"See {expected_parrot_url}/home/remote-inference for more details."
                )
                return None
            elif status == "failed":
                print("\r" + " " * 80 + "\r", end="")
                # write to stderr
                latest_error_report_url = remote_job_data.get("latest_error_report_url")
                if latest_error_report_url:
                    print("Job failed.")
                    print(
                        f"Your job generated exceptions. Details on these exceptions can be found in the following report: {latest_error_report_url}"
                    )
                    print(
                        f"Need support? Post a message at the Expected Parrot Discord channel (https://discord.com/invite/mxAYkjfy9m) or send an email to info@expectedparrot.com."
                    )
                else:
                    print("Job failed.")
                    print(
                        f"See {expected_parrot_url}/home/remote-inference for more details."
                    )
                return None
            elif status == "completed":
                results_uuid = remote_job_data.get("results_uuid")
                results_url = remote_job_data.get("results_url")
                results = object_fetcher(results_uuid, expected_object_type="results")
                print("\r" + " " * 80 + "\r", end="")
                print(f"Job completed and Results stored on Coop: {results_url}.")
                return results
            else:
                duration = poll_interval
                time_checked = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                start_time = time.time()
                i = 0
                while time.time() - start_time < duration:
                    print(
                        f"\r{frames[i % len(frames)]} Job status: {status} - last update: {time_checked}",
                        end="",
                        flush=True,
                    )
                    time.sleep(0.1)
                    i += 1

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
