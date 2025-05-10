import json
import shutil

from .sql_base import create_test_session
from .agent_orm import AgentMappedObject

from edsl import Agent

class Task:
    def __init__(self, path: str):
        self.path = path

class TaskQueue:
    def __init__(self):
        self.queue = []

    def add_task(self, task):
        self.queue.append(task)

    def get_task(self):
        if not self.is_empty():
            return self.queue.pop(0)
        return None

    def is_empty(self):
        return len(self.queue) == 0

    def __len__(self):
        return len(self.queue)



class Worker:
    def __init__(self):
        pass

    def process_task(self, task):
        with open(task.path, "r") as f:
            data = json.load(f)

        return Agent.from_dict(data)

session, db_path, db_tmpdir = create_test_session()

class WorkerAddToDB:
    def __init__(self):
        pass

    def process_task(self, task):
        with open(task.path, "r") as f:
            data = json.load(f)

        agent = Agent.from_dict(data)
        agent_mapped = AgentMappedObject.from_edsl_object(agent)
        session.add(agent_mapped)
        session.commit()

class WorkerPool:
    def __init__(self, queue: TaskQueue, num_workers: int, worker_class=Worker):
        self.queue = queue
        if num_workers <= 0:
            raise ValueError("Number of workers must be positive.")
        
        self.workers = [worker_class() for _ in range(num_workers)]
        self.num_workers = num_workers
        self._current_worker_index = 0

    def process_until_empty(self):
        """
        Processes tasks from the queue until it's empty.
        Tasks are assigned to workers in a round-robin fashion.
        Note: This is a synchronous operation. If `worker_class.process_task` is blocking,
        this method will block, and tasks will be processed sequentially by the pool
        despite having multiple worker instances.
        """
        results = []
        while not self.queue.is_empty():
            task = self.queue.get_task()
            if task:
                # Simple round-robin for worker selection
                worker_instance = self.workers[self._current_worker_index]
                result = worker_instance.process_task(task)
                results.append(result)
                self._current_worker_index = (self._current_worker_index + 1) % self.num_workers
            else:
                # This case should ideally not be reached if queue.is_empty() is false
                # and get_task() returns None only when empty.
                break
        return results

if __name__ == "__main__":
    from edsl import Agent
    import os # For file operations

    # Prepare a test task file
    test_agent_filename = "test_agent_main.json"
    # Ensure the Agent.example().to_dict() structure is compatible with json.dump
    # It should be if it returns a dictionary of JSON-serializable types.
    agent_example_data = Agent.example().to_dict() 
    with open(test_agent_filename, "w") as f:
        json.dump(agent_example_data, f)

    # Create a queue and populate it with tasks for the default Worker
    num_tasks_for_worker = 10000
    worker_task_queue = TaskQueue()
    for _ in range(num_tasks_for_worker):
        task_instance = Task(path=test_agent_filename)
        worker_task_queue.add_task(task_instance)

    print(f"Queue for Worker populated with {len(worker_task_queue)} tasks.")

    # Initialize and run the WorkerPool with Worker
    num_pool_workers = 2 # Using 2 workers for this pool
    # worker_pool_default = WorkerPool(queue=worker_task_queue, num_workers=num_pool_workers, worker_class=Worker)
    # Make sure self.worker_class is not used if worker_class is the parameter name
    worker_pool_default = WorkerPool(queue=worker_task_queue, num_workers=num_pool_workers, worker_class=Worker)


    print(f"Starting WorkerPool with {num_pool_workers} generic Workers...")
    processed_agents = worker_pool_default.process_until_empty()
    
    print(f"WorkerPool (generic Worker) finished. Processed {len(processed_agents)} tasks.")
    if processed_agents:
        print("Example result from generic Worker (first processed agent):")
        # Assuming Agent objects have a __str__ or __repr__ for printing
        print(processed_agents[0])

    # Create another queue and populate it for WorkerAddToDB
    num_tasks_for_db_worker = 10000
    db_task_queue = TaskQueue()
    for _ in range(num_tasks_for_db_worker):
        task_instance = Task(path=test_agent_filename)
        db_task_queue.add_task(task_instance)

    print(f"\nQueue for WorkerAddToDB populated with {len(db_task_queue)} tasks.")

    # Initialize and run the WorkerPool with WorkerAddToDB
    # Using 1 worker for the DB pool for simplicity, can be increased
    db_worker_pool = WorkerPool(queue=db_task_queue, num_workers=1, worker_class=WorkerAddToDB)
    
    print(f"Starting WorkerPool with 1 WorkerAddToDB...")
    # WorkerAddToDB.process_task typically doesn't return a value to collect in 'results'
    # as its main job is a side effect (adding to DB).
    db_worker_pool.process_until_empty() 
    
    print("WorkerPool (WorkerAddToDB) finished.")
    # Verification for DB worker would involve checking the database content,
    # which is outside the scope of this print.

    # Report database size
    if os.path.exists(db_path):
        db_size_bytes = os.path.getsize(db_path)
        db_size_kb = db_size_bytes / 1024
        db_size_mb = db_size_kb / 1024
        print(f"\nDatabase file size: {db_size_bytes} bytes ({db_size_kb:.2f} KB / {db_size_mb:.2f} MB)")
    else:
        print(f"\nDatabase file at {db_path} not found.")

    # Clean up the test file and the temporary database directory
    if os.path.exists(test_agent_filename):
        try:
            os.remove(test_agent_filename)
            print(f"\nCleaned up {test_agent_filename}")
        except OSError as e:
            print(f"Error removing {test_agent_filename}: {e}")
    
    if os.path.exists(db_tmpdir):
        try:
            shutil.rmtree(db_tmpdir)
            print(f"Cleaned up temporary database directory: {db_tmpdir}")
        except OSError as e:
            print(f"Error removing temporary database directory {db_tmpdir}: {e}")
