import os
import json
import requests
import threading

class ReportErrors:

    def __init__(self, task_history):
        self.task_history = task_history
        self.email = None
        self.url = os.getenv("EXPECTED_PARROT_ERROR_REPORTING_URL", None)
        if self.url is None:
            raise ValueError("The URL for the error reporting service is not set.")

    @property
    def data(self):
        return {
            "text": self.task_history.to_dict(),
            "email": self.email,
        }

    def get_email(self, timeout=10):
        """ Helper method to get user input with a timeout. """
        input_queue = []

        def input_thread_method():
            email_input = input("Please enter your email address (if you want us to get in touch): ")
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
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(self.url, data=json_data, headers=headers)
        print("Status Code:", response.status_code)

