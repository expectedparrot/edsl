import json
from typing import List

from .coop_objects import CoopObjects


class CoopJobsObjects(CoopObjects):
    """ScenarioList of remote inference job objects returned by the .list() method.

    This class provides specialized functionality for working with remote inference
    jobs, allowing bulk fetching of jobs.
    """

    def fetch(self) -> List:
        """Fetch each job's details using remote_inference_get and deserialize them.

        Returns:
            list: A list of Jobs objects

        Example:
            >>> jobs = coop.remote_inference_list()  # Get list of remote jobs
            >>> job_objects = jobs.fetch()  # Returns list of Jobs objects
        """
        from ..coop import Coop
        from ..jobs import Jobs

        c = Coop()
        job_details = [
            c.new_remote_inference_get(obj["uuid"], include_json_string=True)
            for obj in self
        ]

        # Deserialize each job from its JSON string
        return [
            Jobs.from_dict(json.loads(details["job_json_string"]))
            for details in job_details
        ]

    def fetch_results(self) -> List:
        """Fetch each job's results using the results_uuid.

        Returns:
            list: A list of Results objects

        Example:
            >>> jobs = coop.remote_inference_list()  # Get list of remote jobs
            >>> results = jobs.fetch_results()  # Returns list of Results objects
        """
        from ..coop import Coop

        c = Coop()
        results = []

        for obj in self:
            if obj.get("results_uuid"):
                result = c.get(obj["results_uuid"])
                results.append(result)

        return results
