import json
import threading
import time
import uuid
from typing import Any
from edsl.agents import Agent
from edsl.data import CRUD
from edsl.jobs.JobsRunner import JobsRunner
from edsl.language_models import LanguageModel
from edsl.scenarios import Scenario
from edsl.surveys import Survey


class StreamingResult:
    def __init__(
        self,
        job_uuid: str,
        result_uuid: str,
        agent: Agent,
        scenario: Scenario,
        model: LanguageModel,
        answer: dict[str, Any],
    ):
        self.job_uuid = job_uuid
        self.result_uuid = result_uuid
        self.agent = agent
        self.scenario = scenario
        self.model = model
        self.answer = answer


def save_streaming_result_to_database(result: StreamingResult):
    CRUD.write_StreamingResult(
        job_uuid=result.job_uuid,
        result_uuid=result.result_uuid,
        agent=json.dumps(result.agent.to_dict()),
        scenario=json.dumps(result.scenario.to_dict()),
        model=json.dumps(result.model.to_dict()),
        answer=json.dumps(result.answer),
    )


def read_streaming_results_from_database(job_uuid: str):
    results = CRUD.read_StreamingResults(job_uuid=job_uuid)
    results = [
        StreamingResult(
            job_uuid=result.job_uuid,
            result_uuid=result.result_uuid,
            agent=Agent.from_dict(json.loads(result.agent)),
            scenario=Scenario.from_dict(json.loads(result.scenario)),
            model=LanguageModel.from_dict(json.loads(result.model)),
            answer=json.loads(result.answer),
        )
        for result in results
    ]
    return results


class StreamingResults:
    def __init__(self, job_uuid: str, total_results: int, survey: Survey):
        self.job_uuid = job_uuid
        self.survey = survey
        self.total_results = total_results
        self.data = []

    @property
    def results(self):
        if len(self.data) < self.total_results:
            data = read_streaming_results_from_database(self.job_uuid)
            self.data = data
        return self.data

    def __repr__(self):
        return f"StreamingResults(job_uuid={self.job_uuid}, total_results={self.total_results}, survey={self.survey}, data={self.results})"


class JobsRunnerStreaming(JobsRunner):
    """This JobRunner conducts interviews serially."""

    def run(
        self,
        debug: bool = False,
        sleep: int = 0,
        n: int = 1,
        verbose: bool = False,
        progress_bar: bool = False,
    ) -> StreamingResults:
        """
        Conducts Interviews **serially** and returns their results.
        - `n`: how many times to run each interview
        - `debug`: prints debug messages
        - `verbose`: prints messages
        - `progress_bar`: shows a progress bar
        """
        job_uuid = str(uuid.uuid4())
        total_results = len(self.interviews)

        def conduct_and_save_interviews():
            for i, interview in enumerate(self.interviews):
                answer = interview.conduct_interview(debug=debug)
                result = StreamingResult(
                    job_uuid=job_uuid,
                    result_uuid=str(i),
                    agent=interview.agent,
                    scenario=interview.scenario,
                    model=interview.model,
                    answer=answer,
                )
                save_streaming_result_to_database(result)
                time.sleep(sleep)

        interview_thread = threading.Thread(target=conduct_and_save_interviews)
        interview_thread.start()

        return StreamingResults(
            job_uuid=job_uuid, total_results=total_results, survey=self.jobs.survey
        )
