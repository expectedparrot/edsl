import threading


class ReportErrors:
    def __init__(self, task_history):
        self.task_history = task_history
        self.email = None

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
        # The previous implementation was removed because it relied on the old Coop ErrorModel
        pass


def main():
    # Use the class directly since we're already in the module

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
