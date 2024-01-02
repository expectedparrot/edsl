"""
This an ABC for a tracker that monitors a Python queue. 

Contained within the namespace is a class called TrackerEvent, which is also an ABC. 
This is the kind of event that will be placed in the queue the tracker is monitoring.
Each child class of TrackerEvent needs to know how to update the state of the tracker.

Each child has to implement a tracked_values method which tells what values the 
tracker is tracking - this is so it can pretty-print them. 

All child classes have to implement an allowed_events class variable. 

"""
import time
from abc import ABC, abstractmethod
from queue import Empty
from edsl.utilities.interface import print_dict_with_rich


class Tracker(ABC):
    "Meant to be single-threaded"

    class TrackerEvent(ABC):
        "Each child event needs to know how to update the state of the tracker."

        @abstractmethod
        def apply(self, tracker):
            pass

    def __init__(self, event_queue, verbose=False):
        self.event_queue = event_queue
        self.observed_events = []
        self.verbose = verbose
        if self.verbose:
            print("Tracker instantiated")

    @abstractmethod
    def allowed_events(self) -> set:
        "What events (classes) are allowed to be placed in the queue?"
        pass

    @abstractmethod
    def tracked_values(self) -> dict:
        "What values are tracked by this tracker (should be flat dictionary)?"
        pass

    def get_from_queue(self):
        """Gets events from the queue and stores them in a list.
        It runs until the event_queue is empty.
        """
        while True:
            try:
                event = self.event_queue.get(block=False)
            except Empty as e:
                if self.verbose:
                    print("The queue is empty.")
                break
            else:
                self.observed_events.append(event)
                self.process_event(event)
                self.event_queue.task_done()

    def __call__(self, all_done, interval=1):
        if self.verbose:
            print("Tracking thread is starting.")
        while not all_done.is_set():
            self.get_from_queue()
            time.sleep(interval)

        # Run one last time to get anything still left in the event_queue
        self.get_from_queue()

    def process_event(self, event):
        """Processes an event from the event queue."""

        ## diabling this for now as two error-prone:
        # https://chat.openai.com/share/6e0e2ae2-30d7-4281-982a-a69a218c4e76

        # if not isinstance(event, tuple(self.allowed_events())):
        #    print(f"Event type: {type(event).__name__}")
        #    print(f"Allowed events: {self.allowed_events()}")
        #    raise ValueError(f"Invalid event type: {type(event).__name__}")

        event.apply(self)
        if self.verbose:
            self.show_status()

    def show_status(self):
        """Prints the status of the interview manager."""
        data = self.tracked_values()
        print_dict_with_rich(data)
