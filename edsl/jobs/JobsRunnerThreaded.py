from __future__ import annotations
import threading
import time
from threading import Lock, Event
from queue import Queue
from edsl.jobs import Jobs
from edsl.jobs.Worker import Worker
from edsl.trackers.TrackerAPI import TrackerAPI
from edsl.trackers.TrackerTasks import TrackerTasks
from edsl.results import Results
from edsl.jobs.JobsRunner import JobsRunner

"""
This module contains the JobsRunnerThreaded class, which is a threaded version of the JobsRunner class.
It (cautiously) addes more workers to the workforce if the API tracker observes that the API limit is not being reached.
If the API tracker observes that the API limit is being reached, it stops adding workers to the workforce.
"""


class JobsRunnerThreaded(JobsRunner):
    def __init__(self, jobs: Jobs):
        super().__init__(jobs)
        self.task_queue = Queue()
        self.event_queue = Queue()
        self.results_queue = Queue()
        self.api_queue = self.interviews[0].model.api_queue
        self.worker_threads = []
        self.lock = Lock()
        self.number_of_workers = 1
        self.sleep_time_between_workers_seconds = 0.1
        self.adjustment_interval_seconds = 5

    def change_worker_pace_multiplicatively(self, multiplier):
        "Increases the time between workers by some percentage."
        with self.lock:
            self.sleep_between_workers_seconds *= multiplier

    def add_worker(self, tracker_api, tracker_tasks) -> None:
        "Adds a worker to the worker pool."
        worker_instance = Worker(tracker_api=tracker_api, tracker_tasks=tracker_tasks)
        thread = threading.Thread(
            target=worker_instance,
            args=(
                self.task_queue,
                self.results_queue,
                self.event_queue,
            ),
        )
        thread.start()
        self.worker_threads.append(thread)

    def dynamic_labor_adjustment(self, all_done, tracker_api, tracker_tasks) -> None:
        """Adjusts the number of workers based on the API tracker's observations."""
        limit_ever_exceeded = False
        while not all_done.is_set():
            time.sleep(self.adjustment_interval_seconds)
            usage_rates = tracker_api.usage_rates()
            if usage_rates.pct_of_tpm_limit < 30 and not limit_ever_exceeded:
                self.add_worker(tracker_api, tracker_tasks)
            else:
                limit_ever_exceeded = True

    def run(
        self, n=1, verbose=False, sleep=0, debug=False, progress_bar=False
    ) -> Results:
        """Runs a collection of interviews."""
        all_done = Event()  # a thread-safe event that is set when all tasks are done

        # Add tasks (interviews) to the queue
        [self.task_queue.put(interview) for interview in self.interviews]

        # instantiate the tracker, adding it to a thread and joining the thread
        tracker_tasks = TrackerTasks(
            num_interviews=len(self.interviews),
            lock=self.lock,
            monitored_queue=self.event_queue,
        )
        tasks_monitoring_thread = threading.Thread(
            target=tracker_tasks, args=(all_done,)
        )
        tasks_monitoring_thread.start()

        # instantiate the API tracker, adding it to a thread and joining the thread
        tracker_api = TrackerAPI(lock=self.lock, monitored_queue=self.api_queue)
        api_monitoring_thread = threading.Thread(target=tracker_api, args=(all_done,))
        api_monitoring_thread.start()

        workforce_adjust_thread = threading.Thread(
            target=self.dynamic_labor_adjustment,
            args=(all_done, tracker_api, tracker_tasks),
        )
        workforce_adjust_thread.start()

        # instantiate workers, adding them to threads and joining the threads
        [
            self.add_worker(tracker_api, tracker_tasks)
            for _ in range(self.number_of_workers)
        ]

        # Waiting for tasks to be completed
        self.task_queue.join()

        all_done.set()

        # Shutting down workforce adjustment thread.
        workforce_adjust_thread.join()

        # Shutting down tasks monitoring thread.
        tasks_monitoring_thread.join()

        # "Shutting down API monitoring thread."
        api_monitoring_thread.join()

        # Emptying the results queue
        data = []
        while not self.results_queue.empty():
            data.append(self.results_queue.get())

        return Results(survey=self.jobs.survey, data=data)
