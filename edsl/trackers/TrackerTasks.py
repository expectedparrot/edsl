from edsl.trackers.Tracker import Tracker
from edsl.utilities.interface import heartbeat_generator, human_readable_labeler_creator


class TrackerTasks(Tracker):
    """ """

    class WorkerActivated(Tracker.TrackerEvent):
        def apply(self, tracker):
            with tracker.lock:
                tracker.active_workers += 1

    class WorkerDeactivated(Tracker.TrackerEvent):
        def apply(self, tracker):
            with tracker.lock:
                tracker.active_workers -= 1

    class TaskStarted(Tracker.TrackerEvent):
        def apply(self, tracker):
            with tracker.lock:
                tracker.interviews_started += 1

    class TaskCompleted(Tracker.TrackerEvent):
        def apply(self, tracker):
            with tracker.lock:
                tracker.interviews_completed += 1

    class ThreadStatus(Tracker.TrackerEvent):
        def __init__(self, thread_id, status):
            self.thread_id = thread_id
            self.status = status

        def apply(self, tracker):
            with tracker.lock:
                tracker.thread_status[self.thread_id] = self.status

    def __init__(self, num_interviews, lock, monitored_queue):
        self.num_interviews = num_interviews  # how many interviews are there in total
        self.lock = lock
        self.hearbeat = heartbeat_generator()  # generator to show responses coming in
        self.active_workers = 0
        self.interviews_started = 0
        self.interviews_completed = 0
        self.thread_status = dict()
        # this is a function that takes thread IDs and turns them into successive integers
        self.human_readable_labeler = human_readable_labeler_creator()

        super().__init__(monitored_queue)

    def tracked_values(self) -> dict:
        return {
            "Active Workers": self.active_workers,
            "Interviews Started": self.interviews_started,
            "Completed Interviews": self.interviews_completed,
        }

    def allowed_events(self):
        return set(
            [
                TrackerTasks.WorkerActivated,
                TrackerTasks.WorkerDeactivated,
                TrackerTasks.TaskStarted,
                TrackerTasks.TaskCompleted,
                TrackerTasks.ThreadStatus,
            ]
        )

    @property
    def percentage_complete(self):
        return round(100 * self.interviews_completed / self.num_interviews, 2)
