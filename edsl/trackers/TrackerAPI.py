"""This tracker tracks API calls."""
import json
import time
from collections import namedtuple
from threading import Lock, Event
from edsl.trackers.Tracker import Tracker

UsageRates = namedtuple(
    "UsageRates",
    [
        "estimated_tokens_per_minute_k",
        "pct_of_tpm_limit",
        "estimated_requests_per_minute_k",
        "pct_of_rpm_limit",
    ],
)


class TrackerAPI(Tracker):
    """ """

    class APICallDetails(Tracker.TrackerEvent):
        def __init__(self, details):
            self.details = details

        def apply(self, tracker):
            with tracker.lock:
                tracker.usage.append(self.details)

    def __init__(
        self, lock, monitored_queue, tokens_per_minute_k=90, requests_per_minute_k=2
    ):
        self.lock = lock
        self.tokens_per_minute_k = tokens_per_minute_k
        self.requests_per_minute_k = requests_per_minute_k
        self.usage = []

        super().__init__(monitored_queue)

    def usage_rates(self, last_seconds=60):
        with self.lock:
            right_now = time.time()
            relevant_usage = [
                x
                for x in self.usage
                if (x["timestamp"] > right_now - last_seconds)
                and not x["cached_response"]
            ]
            if relevant_usage == []:
                return UsageRates(**{k: 0 for k in UsageRates._fields})
            else:
                elapsed_seconds = right_now - relevant_usage[0]["timestamp"]
                total_tokens = sum([x["total_tokens"] for x in relevant_usage])

                estimated_tokens_per_minute_k = round(
                    total_tokens / (elapsed_seconds / 60.0) / 1000, 0
                )
                pct_of_tpm_limit = round(
                    100 * estimated_tokens_per_minute_k / self.tokens_per_minute_k
                )

                estimated_requests_per_minute_k = round(
                    len(relevant_usage) / (elapsed_seconds / 60.0) / 1000, 2
                )
                pct_of_rpm_limit = round(
                    100 * estimated_requests_per_minute_k / self.requests_per_minute_k
                )

                usage_rates = UsageRates(
                    estimated_tokens_per_minute_k=estimated_tokens_per_minute_k,
                    pct_of_tpm_limit=pct_of_tpm_limit,
                    estimated_requests_per_minute_k=estimated_requests_per_minute_k,
                    pct_of_rpm_limit=pct_of_rpm_limit,
                )

                return usage_rates

    def tracked_values(self) -> dict:
        return {
            "Calls": len(self.usage),
        }

    def allowed_events(self):
        return set([TrackerAPI.APICallDetails])

    @classmethod
    def fromJSON(cls, filename):
        """This loads a tracker from a JSON file. Just for testing purposes"""
        with open(filename, "r") as f:
            json_dict = f.read()
        usage = json.loads(json_dict)
        # pretend responses are not cached for each testing, as the
        # usage_rate methods only compute w/ non-cached responses
        [x.update({"cached_response": False}) for x in usage]
        instance = cls(Lock(), None)
        instance.usage = usage
        return instance

    def toJSON(self, filename="sample_data.json"):
        with open(filename, "w") as f:
            json.dump(self.usage, f)

    def status(self):
        """This prints the status of the interview manager, while interviews are doing on."""
        estimated_length = 100
        completed = self.status_tracker.complete
        pct_completed = self.status_tracker.percentage_complete
        usage_rates = self.current_tpm(10)
        heartbeat = next(self.status_tracker.hearbeat)
        status_str = (
            f"{heartbeat} Completed: {completed} ({pct_completed} of total); "
            f"Est. TPM (k): {usage_rates.estimated_tokens_per_minute_k: ,} ({usage_rates.frac_of_tpm_limit}% of lim.); "
            f"Est. RPM (k): {usage_rates.estimated_requests_per_minute_k:,} ({usage_rates.frac_of_rpm_limit}% of lim.)); "
        )
        # Pad with spaces to reach the estimated length
        padded_status_str = status_str.ljust(estimated_length)
        print(f"\r{padded_status_str}", end="", flush=True)


if __name__ == "__main__":
    import textwrap
    from language_models import LanguageModelOpenAIThreeFiveTurbo

    m = LanguageModelOpenAIThreeFiveTurbo(use_cache=True)

    # the language model is attached to the queue
    print(m.api_queue)

    # the tracker expects a lock and an event
    lock = Lock()
    all_done = Event()

    # tracker attached to the queue
    tracker = TrackerAPI(lock=lock, monitored_queue=m.api_queue)

    # the queue is empty to start
    print(f"Queue size: {m.api_queue.qsize()}")

    # a call is made to the language model
    raw = m.get_raw_response(
        prompt="What is your favorite color?",
        system_prompt=textwrap.dedent(
            """\
                            You are pretending to be a human taking a survey.
                            Do not break character. 
                            """
        ),
    )

    # sleep for a second, as queue puts are non-blocking
    import time

    print("Sleeping for 1 second")
    time.sleep(1)
    # see that the queue updated
    print(f"Queue size: {m.api_queue.qsize()}")
    print(m.parse_response(raw))
    # indicate we are all done
    all_done.set()
    # have the tracker finish up
    tracker(all_done, interval=1)
    # how many calls did the API observe?
    print(tracker.tracked_values())
    # what is in the tracker queue?
    print(tracker.usage)
    # confirm that the API queue is empty
    print(f"Queue size: {m.api_queue.qsize()}")

    ## Next example - compute queue statistics
    all_done = Event()

    tracker_two = TrackerAPI(lock=lock, monitored_queue=m.api_queue)

    for i in range(10):
        raw = m.get_raw_response(
            prompt=f"What emotions are associated with {i}?",
            system_prompt=textwrap.dedent(
                """\
                                You are pretending to be a human taking a survey.
                                Do not break character. 
                                """
            ),
        )

    time.sleep(1)
    all_done.set()
    # have the tracker finish up
    tracker(all_done, interval=1)
    # print(tracker.usage)
    tracker.toJSON(filename="sample_data.json")

    # from .example_api_call_data import sample_data
    tracker = TrackerAPI.fromJSON("sample_data.json")
    print(tracker.usage)

    print(tracker.usage_rates(1000000))
