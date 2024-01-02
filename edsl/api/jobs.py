import uuid
from edsl.api.results import ResultsAPI


def JobRunnerAPI(api_key: str, job_dict: dict) -> ResultsAPI:
    api_key = api_key
    job_dict = job_dict
    # TODO: API call to send job data and return job_id
    job_id = str(uuid.uuid4())
    # return a ResultsAPI instance with the job_id
    return ResultsAPI(api_key, job_id)
