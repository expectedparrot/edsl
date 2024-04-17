import json
import requests
import threading
from edsl.config import CONFIG


class ReportErrors:
    def __init__(self, task_history):
        self.task_history = task_history
        self.email = None
        self.url = CONFIG.EXPECTED_PARROT_URL
        if self.url is None:
            raise ValueError("The URL for the error reporting service is not set.")

    @property
    def data(self):
        return {
            "text": self.task_history.to_dict(),
            "email": self.email,
        }

    def get_email(self, timeout=10):
        """Helper method to get user input with a timeout."""
        input_queue = []

        def input_thread_method():
            email_input = input(
                "Please enter your email address (if you want us to get in touch): "
            )
            input_queue.append(email_input)

        input_thread = threading.Thread(target=input_thread_method)
        input_thread.start()
        input_thread.join(timeout=timeout)

        if input_queue:
            self.email = input_queue[0]
        else:
            print("No input received within the timeout period.")

    def upload(self):
        json_data = json.dumps(self.data)
        headers = {"Content-Type": "application/json"}
        response = requests.post(
            f"{self.url}/api/v0/errors",
            json={"json_string": json_data},
            headers=headers,
        )
        print("Status Code:", response.status_code)


def main():
    from edsl.jobs.interviews.ReportErrors import ReportErrors

    class TaskHistory:
        def __init__(self, data):
            self.data = data

        def to_dict(self):
            """Converts the internal data of the task history to a dictionary format."""
            return self.data

    task_history_data = {
        "task": "Example Task",
        "status": "Completed",
        "details": "This is an example of a task history.",
    }
    task_history = TaskHistory(task_history_data)

    reporter = ReportErrors(task_history)
    # one without email
    reporter.upload()
    # one with email
    reporter.email = "fake@gmail.com"
    reporter.upload()
