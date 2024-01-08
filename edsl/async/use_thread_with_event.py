import asyncio
import threading
import random


class TaskResults:
    def __init__(self, total_tasks):
        self.data = []
        self.lock = threading.Lock()
        self.total_tasks = total_tasks
        self.tasks_completed = asyncio.Event()  # Event to signal task completion

    def add_result(self, result):
        with self.lock:
            self.data.append(result)
            if len(self.data) == self.total_tasks:
                self.tasks_completed.set()  # Set the event when all tasks are complete

    @property
    def is_complete(self):
        return len(self.data) == self.total_tasks

    @property
    def status(self):
        pct_complete = round(100 * len(self.data) / self.total_tasks, 0)
        return f"Percent completed: {pct_complete}%"


async def async_task(task_id, results_obj):
    time_delay = random.randint(1, 10)
    await asyncio.sleep(time_delay)
    result = f"Result of task {task_id}"
    results_obj.add_result(result)


async def main_async(results_obj):
    tasks = [async_task(i, results_obj) for i in range(10)]
    await asyncio.gather(*tasks)


def run_async_code_in_thread(results_obj):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_async(results_obj))
    loop.close()


if __name__ == "__main__":
    results_obj = TaskResults(10)
    t = threading.Thread(target=run_async_code_in_thread, args=(results_obj,))
    t.start()

    # Wait for the asynchronous operations to complete
    results_obj.tasks_completed.wait()

    # Now that all tasks are completed, join the thread
    t.join()

    # Access the results
    print("All tasks completed. Results:", results_obj.data)
