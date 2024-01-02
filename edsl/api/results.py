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
