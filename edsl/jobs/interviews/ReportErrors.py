import os
import json
import requests

class ReportErrors:

    def __init__(self, task_history):
        self.task_history = task_history
        self.email = None
        self.url = os.getenv("EXPECTED_PARROT_ERROR_REPORTING_URL", None)
        if self.url is None:
            raise ValueError("""The URL for the error reporting service is not set.""")

    @property
    def data(self):
        return {
            "text": self.task_history.to_dict(),
            "email": self.email,
        }
  
    def get_email(self):
        self.email = input("Please enter your email address (if you want us to get in touch): ")

    def upload(self):
        json_data = json.dumps(self.data)
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(self.url, data=json_data, headers=headers)
        print("Status Code:", response.status_code)

