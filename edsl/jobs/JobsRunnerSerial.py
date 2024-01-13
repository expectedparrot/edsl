import time
from tqdm import tqdm
from edsl.jobs.JobsRunner import JobsRunner
from edsl.results import Result, Results


class JobsRunnerSerial(JobsRunner):
    """This JobRunner conducts interviews serially."""

    def run(
        self,
        n: int = 1,
        verbose: bool = False,
        sleep: int = 0,
        debug: bool = False,
        progress_bar: bool = True,
    ) -> Results:
        """
        Conducts Interviews **serially** and returns their results.
        - `n`: how many times to run each interview
        - `debug`: prints debug messages
        - `verbose`: prints messages
        - `progress_bar`: shows a progress bar
        """
        data = []
        for i in range(n):
            desc = "Running surveys" if n == 1 else f"Running surveys ({i+1}/{n})"
            interviews = (
                tqdm(self.interviews, desc=desc) if progress_bar else self.interviews
            )
            for interview in interviews:
                answer = interview.conduct_interview(debug=debug)
                result = Result(
                    agent=interview.agent,
                    scenario=interview.scenario,
                    model=interview.model,
                    iteration=i,
                    answer=answer,
                )
                data.append(result)
                time.sleep(sleep)

        return Results(survey=self.jobs.survey, data=data)
