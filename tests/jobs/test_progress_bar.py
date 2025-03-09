import pytest

import time
from edsl.agents import Agent
from edsl.data.Cache import Cache
from edsl.scenarios import Scenario
from edsl.questions import QuestionYesNo
from edsl.jobs.runners.JobsRunnerStatus import JobsRunnerStatusBase
from edsl.jobs import Jobs
from edsl.questions.QuestionFreeText import QuestionFreeText


def test_progress_bar():
    """Just makes sure that the progress bar doesn't throw an error."""

    def is_prime(self, question, scenario):
        time.sleep(0.1)
        number = scenario["number"]
        if number < 2:
            return "Yes"
        for i in range(2, number):
            if number % i == 0:
                return "No"
        return "Yes"

    a = Agent(name="prime_knower")
    a.add_direct_question_answering_method(method=is_prime)

    s = [Scenario({"number": number}) for number in range(20)]
    q = QuestionYesNo(
        question_text="Is this number prime: {{ number }}?", question_name="is_prime"
    )

    class TestJobsRunnerStatus(JobsRunnerStatusBase):

        def setup(self) -> None:
            return

        def has_ep_api_key(self) -> bool:
            return True

        def send_status_update(self) -> None:
            status_dict = self.get_status_dict()

    j = q.by(s).by(a)
    bc = j.create_bucket_collection()
    j.using(bc).using(Cache())

    # results = j.run(
    #     progress_bar=True,
    #     disable_remote_inference=True,
    #     disable_remote_cache=True,
    #     jobs_runner_status=TestJobsRunnerStatus,
    # )


if __name__ == "__main__":
    pytest.main()
