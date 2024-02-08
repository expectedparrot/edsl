import uuid


class ResultsAPI:
    """
    While results = None, repr will be calling the api to get the results or the estimated time to completion. When it does, results will be stored here, and the API will no longer be called.
    """

    def __init__(self, api_key: str, job_id: str) -> None:
        self.api_key = api_key
        self.job_id = job_id
        self.status = None
        self.results = None

    def _get_results(self) -> dict:
        # TODO: API call to get status & results
        return ("Running", None)

    def __repr__(self) -> str:
        if self.results is None:
            self.status, self.results = self._get_results()
        return f"Results(api_key={self.api_key}, job_id={self.job_id}, status={self.status}, results={self.results})"


def JobRunnerAPI(api_key: str, job_dict: dict) -> ResultsAPI:
    api_key = api_key
    job_dict = job_dict
    # TODO: API call to send job data and return job_id
    job_id = str(uuid.uuid4())
    # return a ResultsAPI instance with the job_id
    return ResultsAPI(api_key, job_id)
