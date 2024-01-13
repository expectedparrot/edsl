import random
import time
import threading
from queue import Empty
from rich import print as rprint
from edsl.results.Result import Result
from edsl.utilities.interface import heartbeat_generator
from edsl.trackers.TrackerTasks import TrackerTasks


class Worker:
    """A worker does the task of taking interviews off the queue and conducting them.
    It sends updates to the event queue about its status.

    - A worker is taking events off the task_queue (get)
    - A worker is sending events to the event_queue describing its status (put)
    - A worker is monitoring the api_tracker to see if it is rate limited

    """

    def __init__(self, tracker_api, tracker_tasks, config=None):
        self.config = config
        self.tracker_api = tracker_api
        self.tracker_tasks = tracker_tasks
        self.wait_time_after_rate_limit_error = 60

        self.heartbeat_gen = heartbeat_generator()

    def print_status_update(self):
        usage_rates = self.tracker_api.usage_rates()
        pct_complete = round(self.tracker_tasks.percentage_complete)
        active_workers = self.tracker_tasks.active_workers
        estimated_length = 100
        heartbeat = next(self.heartbeat_gen)
        status_str = (
            f"{heartbeat}; "
            f"{pct_complete}% of tasks complete; "
            f"{active_workers} worker(s); "
            f"Est. TPM (k): {usage_rates.estimated_tokens_per_minute_k: ,} ({usage_rates.pct_of_tpm_limit}% of lim.); "
            f"Est. RPM (k): {usage_rates.estimated_requests_per_minute_k:,} ({usage_rates.pct_of_rpm_limit}% of lim.)); "
        )
        # Pad with spaces to reach the estimated length
        padded_status_str = status_str.ljust(estimated_length)
        print(f"\r{padded_status_str}", end="", flush=True)

    def __call__(self, task_queue, results_queue, event_queue, debug=False):
        event_queue.put(TrackerTasks.WorkerActivated())
        thread_status = TrackerTasks.ThreadStatus(
            thread_id=threading.get_ident(), status="Running"
        )
        event_queue.put(thread_status)
        while True:
            self.print_status_update()
            sleep_time = random.random() * 0.1
            time.sleep(sleep_time)  # prevent thundering herd of synchronization
            try:
                interview = task_queue.get(block=True, timeout=1)
            except Empty as e:
                break

            try:
                event_queue.put(TrackerTasks.TaskStarted())
                answer = interview.conduct_interview(debug=debug)
                result = Result(
                    agent=interview.agent,
                    scenario=interview.scenario,
                    model=interview.model,
                    iteration=0,
                    answer=answer,
                )
                results_queue.put(result)
            except Exception as e:  # get the actual name of the exception
                print(f"Caught an exception of type {type(e).__name__}")
                print(f"Text:{e}")
                rprint("[red]Rate limit error[/red]")
                sleep_amount = round(random.random() * 60)
                print(f"Putting this worker to sleep for {sleep_amount} seconds")
                time.sleep(sleep_amount)
                task_queue.put(interview)
                # raise Exception
            else:
                event_queue.put(TrackerTasks.TaskCompleted())
                task_queue.task_done()

        event_queue.put(TrackerTasks.WorkerActivated())
