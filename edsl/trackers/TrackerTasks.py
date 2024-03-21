"""This module contains a tracker that tracks the progress of a set of tasks."""
from edsl.trackers.Tracker import Tracker
from edsl.utilities.interface import heartbeat_generator, human_readable_labeler_creator


class TrackerTasks(Tracker):
    """This tracker tracks the progress of a set of tasks."""

    class WorkerActivated(Tracker.TrackerEvent):
        """This is the kind of event that will be placed in the queue the tracker is monitoring."""

        def apply(self, tracker):
            """Each child class of TrackerEvent needs to know how to update the state of the tracker."""
            with tracker.lock:
                tracker.active_workers += 1

    class WorkerDeactivated(Tracker.TrackerEvent):
        """This is the kind of event that will be placed in the queue the tracker is monitoring."""

        def apply(self, tracker):
            """Each child class of TrackerEvent needs to know how to update the state of the tracker."""
            with tracker.lock:
                tracker.active_workers -= 1

    class TaskStarted(Tracker.TrackerEvent):
        """This is the kind of event that will be placed in the queue the tracker is monitoring."""

        def apply(self, tracker):
            """Each child class of TrackerEvent needs to know how to update the state of the tracker."""
            with tracker.lock:
                tracker.interviews_started += 1

    class TaskCompleted(Tracker.TrackerEvent):
        """This is the kind of event that will be placed in the queue the tracker is monitoring."""

        def apply(self, tracker):
            """Each child class of TrackerEvent needs to know how to update the state of the tracker."""
            with tracker.lock:
                tracker.interviews_completed += 1

    class ThreadStatus(Tracker.TrackerEvent):
        """This is the kind of event that will be placed in the queue the tracker is monitoring."""

        def __init__(self, thread_id, status):
            """Each child class of TrackerEvent needs to know how to update the state of the tracker."""
            self.thread_id = thread_id
            self.status = status

        def apply(self, tracker):
            """Each child class of TrackerEvent needs to know how to update the state of the tracker."""
            with tracker.lock:
                tracker.thread_status[self.thread_id] = self.status

    def __init__(self, num_interviews, lock, monitored_queue):
        """Initialize the tracker with an event queue."""
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
        """Return the tracked values."""
        return {
            "Active Workers": self.active_workers,
            "Interviews Started": self.interviews_started,
            "Completed Interviews": self.interviews_completed,
        }

    def allowed_events(self):
        """Return the allowed events."""
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
        """Return the percentage of interviews that have been completed."""
        return round(100 * self.interviews_completed / self.num_interviews, 2)
