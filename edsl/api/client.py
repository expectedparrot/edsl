import json
import requests
from edsl import CONFIG
from edsl.jobs import Jobs

api_url = {
    "development": "http://127.0.0.1:8000",
    "production": "https://api.goemeritus.com",
}


class Client:
    def __init__(self, api_key: str = None, run_mode: str = None) -> None:
        self.api_key = api_key or CONFIG.EMERITUS_API_KEY
        self.run_mode = run_mode or CONFIG.EDSL_RUN_MODE

    def __repr__(self):
        return f"Client(api_key='{self.api_key}', run_mode='{self.run_mode}')"

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}

    @property
    def url(self) -> str:
        return api_url[self.run_mode]

    # JOBS METHODS edit
    @property
    def jobs(self) -> list:
        """Returns a list of all jobs on the server."""
        url = f"{self.url}/api/v0/jobs"
        response = requests.get(url, headers=self.headers)
        for k in response.json():
            print(k)

    def send_job(self, job: Jobs) -> dict:
        """Sends a job to the server."""
        url = f"{self.url}/api/v0/jobs"
        payload = {"json_string": json.dumps(job.to_dict())}
        response = requests.post(url, json=payload, headers=self.headers)
        return response.json()

    def run_job(self, job_id: str) -> dict:
        """Runs a job on the server."""
        url = f"{self.url}/api/v0/jobs/{job_id}/run"
        response = requests.post(url, headers=self.headers)
        return response.json()

    def get_results(self, results_id: str) -> dict:
        """Returns the results of a job on the server."""
        url = f"{self.url}/api/v0/results/{results_id}"
        response = requests.get(url, headers=self.headers)
        return response.json()


if __name__ == "__main__":

    def create_example_job() -> Jobs:
        from edsl.agents.Agent import Agent
        from edsl.questions import QuestionMultipleChoice
        from edsl.scenarios.Scenario import Scenario
        from edsl.surveys.Survey import Survey

        q = QuestionMultipleChoice(
            question_text="How are you this {{ period }}?",
            question_options=["Good", "Great", "OK", "Terrible"],
            question_name="how_feeling",
        )
        base_survey = Survey(questions=[q])

        job = base_survey.by(
            Scenario({"period": "morning"}), Scenario({"period": "afternoon"})
        ).by(Agent({"status": "Super duper unhappy"}), Agent({"status": "Joyful"}))

        return job

    # start a client
    client = Client(run_mode="development")

    # basics
    client
    client.headers
    client.url

    # check jobs on server
    client.jobs

    # send a job to the server
    job = create_example_job()
    client.send_job(job)

    client.jobs
    client.run_job(job_id="1")

    client.jobs
    client.get_results(results_id="1")
