from typing import Optional, Union
import requests

from edsl.exceptions.coop import CoopServerResponseError

# from edsl.enums import VisibilityType
from edsl.results import Results


class JobsRemoteInferenceHandler:

    def __init__(self, jobs, verbose=False):
        self.jobs = jobs
        self.verbose = verbose

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
        from edsl.coop.coop import Coop

        coop = Coop()
        if self.verbose:
            print("Remote inference activated. Sending job to server...")
        remote_job_creation_data = coop.remote_inference_create(
            self.jobs,
            description=remote_inference_description,
            status="queued",
            iterations=iterations,
            initial_results_visibility=remote_inference_results_visibility,
        )
        job_uuid = remote_job_creation_data.get("uuid")
        if self.verbose:
            print(f"Job sent to server. (Job uuid={job_uuid}).")

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
        self, remote_job_creation_data: dict, verbose=False, poll_interval=5
    ) -> Union[Results, None]:
        from edsl.coop.coop import Coop
        import time
        from datetime import datetime
        from edsl.config import CONFIG

        expected_parrot_url = CONFIG.get("EXPECTED_PARROT_URL")

        job_uuid = remote_job_creation_data.get("uuid")

        coop = Coop()
        job_in_queue = True
        while job_in_queue:
            remote_job_data = coop.remote_inference_get(job_uuid)
            status = remote_job_data.get("status")
            if status == "cancelled":
                if self.verbose:
                    print("\r" + " " * 80 + "\r", end="")
                    print("Job cancelled by the user.")
                    print(
                        f"See {expected_parrot_url}/home/remote-inference for more details."
                    )
                return None
            elif status == "failed":
                if self.verbose:
                    print("\r" + " " * 80 + "\r", end="")
                    print("Job failed.")
                    print(
                        f"See {expected_parrot_url}/home/remote-inference for more details."
                    )
                return None
            elif status == "completed":
                results_uuid = remote_job_data.get("results_uuid")
                results = coop.get(results_uuid, expected_object_type="results")
                if self.verbose:
                    print("\r" + " " * 80 + "\r", end="")
                    url = f"{expected_parrot_url}/content/{results_uuid}"
                    print(f"Job completed and Results stored on Coop: {url}.")
                return results
            else:
                duration = poll_interval
                time_checked = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
                frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
                start_time = time.time()
                i = 0
                while time.time() - start_time < duration:
                    if self.verbose:
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
