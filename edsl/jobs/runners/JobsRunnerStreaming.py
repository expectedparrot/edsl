import json
import threading
import time
import uuid
from edsl.data import CRUD
from edsl.jobs.JobsRunner import JobsRunner
from edsl.results import Results


class JobsRunnerStreaming(JobsRunner):
    """This JobRunner conducts interviews serially."""

    runner_name = "streaming"

    def run(
        self,
        debug: bool = False,
        sleep: int = 0,
        n: int = 1,
        verbose: bool = False,
        progress_bar: bool = False,
    ) -> Results:
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
                CRUD.write_result(
                    job_uuid=job_uuid,
                    result_uuid=str(i),
                    agent=json.dumps(interview.agent.to_dict()),
                    scenario=json.dumps(interview.scenario.to_dict()),
                    model=json.dumps(interview.model.to_dict()),
                    answer=json.dumps(answer),
                )
                time.sleep(sleep)

        interview_thread = threading.Thread(target=conduct_and_save_interviews)
        interview_thread.start()

        return Results(
            survey=self.jobs.survey,
            data=[],
            job_uuid=job_uuid,
            total_results=total_results,
        )
