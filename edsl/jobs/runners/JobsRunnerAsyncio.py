import time
import asyncio
from typing import Coroutine, List, AsyncGenerator

from rich.live import Live
from rich.console import Console

from edsl.results import Results, Result
from edsl.jobs.runners.JobsRunner import JobsRunner
from edsl.jobs.interviews.Interview import Interview
from edsl.utilities.decorators import jupyter_nb_handler

from edsl.jobs.runners.JobsRunnerStatusMixin import JobsRunnerStatusMixin
from edsl.jobs.runners.JobsRunHistory import JobsRunHistory

class TaskHistory:

    def __init__(self, total_interviews):
        self.total_interviews = total_interviews


    def get_updates(self):
        updates = []
        for interview in self.total_interviews:
            for question_name, logs in interview.task_status_logs.items():
                updates.append(logs)
        return updates

    def plot_completion_times(self):

        updates = self.get_updates()

        elapsed = [update.max_time - update.min_time for update in updates]
        x = range(len(elapsed))
        y = elapsed

        import matplotlib.pyplot as plt
        plt.bar(x, y)
        plt.title('Per-interview completion times')
        plt.xlabel('Task')
        plt.ylabel('Time (seconds)')
        plt.show()

    def plotting_data(self, num_periods = 100):

        updates = self.get_updates()
        
        min_t = min([update.min_time for update in updates])
        max_t = max([update.max_time for update in updates])
        delta_t = (max_t - min_t)/(num_periods * 1.0)
        time_periods = [min_t + delta_t *i for i in range(num_periods)]
      
        def counts(t):
            d = {}
            for update in updates:
                status = update.status_at_time(t)
                if status in d:
                    d[status] += 1
                else:
                    d[status] = 1
            return d 
  
        status_counts = [counts(t) for t in time_periods]

        new_counts = []
        for status_count in status_counts:
            d = {task_status:0 for task_status in TaskStatus}
            d.update(status_count)
            new_counts.append(d)

        return new_counts
    
    def plot(self, num_periods = 100):
        new_counts = self.plotting_data(num_periods)

        max_count = max([max(entry.values()) for entry in new_counts])

        rows = int(len(TaskStatus) ** 0.5) + 1
        cols = (len(TaskStatus) + rows - 1) // rows  # Ensure all plots fit
        from matplotlib import pyplot as plt
            
        plt.figure(figsize=(15, 10))  # Adjust the figure size as needed
        for i, status in enumerate(TaskStatus, start=1):
            plt.subplot(rows, cols, i)
            x = range(len(new_counts))
            y = [item.get(status, 0) for item in new_counts]  # Use .get() to handle missing keys safely
            plt.plot(x, y, marker='o', linestyle='-')
            plt.title(status.name)
            plt.xlabel('Time Periods')
            plt.ylabel('Count')
            plt.grid(True)
            plt.ylim(0, max_count)

        plt.tight_layout()
        plt.show()

from edsl.jobs.tasks.task_status_enum import TaskStatus



class JobsRunnerAsyncio(JobsRunner, JobsRunnerStatusMixin):
    runner_name = "asyncio"
   
    history = JobsRunHistory()

    # async def periodic_logger(self, period=1):
    #     """Logs every 'period' seconds."""
    #     self.history.log(self, self.results, self.elapsed_time)
    #     while True:
    #         await asyncio.sleep(period)  # Sleep for the specified period
    #         self.history.log(self, self.results, self.elapsed_time)

    async def run_async(
        self,
        n: int = 1,
        debug: bool = False,
        stop_on_exception: bool = False,
    ) -> AsyncGenerator[Result, None]:
        """Creates the tasks, runs them asynchronously, and returns the results as a Results object.

        Completed tasks are yielded as they are completed.

        :param n: how many times to run each interview
        :param debug:
        :param stop_on_exception:
        """
        tasks = []
        self.populate_total_interviews(
            n=n
        )  # Populate self.total_interviews before creating tasks

        for interview in self.total_interviews:
            interviewing_task = self._interview_task(
                interview=interview, debug=debug, stop_on_exception=stop_on_exception
            )
            tasks.append(asyncio.create_task(interviewing_task))

        for task in asyncio.as_completed(tasks):
            result = await task
            yield result

    async def _interview_task(
        self, *, interview: Interview, debug: bool, stop_on_exception: bool = False
    ) -> Result:
        """Conducts an interview and returns the result.

        :param interview: the interview to conduct
        :param debug: prints debug messages
        """
        # the model buckets are used to track usage rates
        model_buckets = self.bucket_collection[interview.model]

        # get the results of the interview
        answer, valid_results = await interview.async_conduct_interview(
            debug=debug,
            model_buckets=model_buckets,
            stop_on_exception=stop_on_exception,
        )

        # we should have a valid result for each question
        answer_key_names = {k for k in set(answer.keys()) if not k.endswith("_comment")}

        assert len(valid_results) == len(answer_key_names)

        # TODO: move this down into Interview
        question_name_to_prompts = dict({})
        for result in valid_results:
            question_name = result["question_name"]
            question_name_to_prompts[question_name] = {
                "user_prompt": result["prompts"]["user_prompt"],
                "system_prompt": result["prompts"]["system_prompt"],
            }

        prompt_dictionary = {}
        for answer_key_name in answer_key_names:
            prompt_dictionary[
                answer_key_name + "_user_prompt"
            ] = question_name_to_prompts[answer_key_name]["user_prompt"]
            prompt_dictionary[
                answer_key_name + "_system_prompt"
            ] = question_name_to_prompts[answer_key_name]["system_prompt"]

        raw_model_results_dictionary = {}
        for result in valid_results:
            question_name = result["question_name"]
            raw_model_results_dictionary[
                question_name + "_raw_model_response"
            ] = result["raw_model_response"]

        result = Result(
            agent=interview.agent,
            scenario=interview.scenario,
            model=interview.model,
            iteration=interview.iteration,
            answer=answer,
            prompt=prompt_dictionary,
            raw_model_response=raw_model_results_dictionary,
        )
        return result

    @property
    def elapsed_time(self):
        return time.monotonic() - self.start_time

    @jupyter_nb_handler
    async def run(
        self,
        n: int = 1,
        debug: bool = False,
        stop_on_exception: bool = False,
        progress_bar=False,
    ) -> "Coroutine":
        """Runs a collection of interviews, handling both async and sync contexts."""
        console = Console()
        self.results = []
        self.start_time = time.monotonic()
        self.completed = False

        def generate_table():
            return self.status_table(self.results, self.elapsed_time)

        with Live(generate_table(), console=console, refresh_per_second=5) as live:

            async def update_progress_bar():
                """Updates the progress bar at fixed intervals."""
                while True:
                    live.update(generate_table())
                    await asyncio.sleep(0.1)  # Update interval
                    if self.completed:
                        break
            
            async def process_results():
                """Processes results from interviews."""
                async for result in self.run_async(n=n, debug=debug, stop_on_exception=stop_on_exception):
                    self.results.append(result)
                    live.update(generate_table())
                self.completed = True

            #logger_task = asyncio.create_task(self.periodic_logger(period=0.01))
            progress_task = asyncio.create_task(update_progress_bar())

            try:
                await asyncio.gather(process_results(), 
                                     progress_task)
            except asyncio.CancelledError:
                pass
            finally:
                progress_task.cancel()  # Cancel the progress_task when process_results is done
                await progress_task 
            
                await asyncio.sleep(1)  # short delay to show the final status

                # one more update
                live.update(generate_table())            

        ## Compute exceptions         
        exceptions = [i.exceptions for index, i in enumerate(self.total_interviews) if i.exceptions != {}]
        indices = [index for index, i in enumerate(self.total_interviews) if i.exceptions != {}]

        # Assuming Results, TaskHistory, etc. are defined elsewhere
        results = Results(survey=self.jobs.survey, data=self.results)
        results.history = self.history
        results.task_history = TaskHistory(self.total_interviews)
        results.total_interviews = self.total_interviews

        if exceptions:
            print(f"""Exceptions were raised in the following interviews: {indices}
            These are available in `results.exceptions` if you want to inspect them and you 
            names your results object `results`. 
                  
            If you want to plot by-task completion times, you can use 
            `results.task_history.plot_completion_times()`
            If you want to plot by-task status over time, you can use
            `results.task_history.plot()`
            """)
            results.exceptions = exceptions

        return results

