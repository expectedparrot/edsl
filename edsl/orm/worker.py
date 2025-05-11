"""
This is a task queue for taking serialized EDSL objects (files) and processing them.
A task is defined as a file location (path) and the type of the object. 
The task is to open the file, instaniate the object and then write it to the database.
"""

import json
import shutil
import os
import threading
import time
import random
from queue import Queue, Empty
from threading import Lock

from edsl import (Agent, QuestionMultipleChoice, QuestionLikertFive, QuestionLinearScale, 
                  QuestionFunctional, QuestionMultipleChoiceWithOther, Results, Survey, 
                  ScenarioList, AgentList)

class_names_to_classes = {
    'Agent': Agent,
    'QuestionMultipleChoice': QuestionMultipleChoice,
    'QuestionLikertFive': QuestionLikertFive,
    'QuestionLinearScale': QuestionLinearScale,
    'QuestionFunctional': QuestionFunctional,
    'QuestionMultipleChoiceWithOther': QuestionMultipleChoiceWithOther,
    'Results': Results,
    'Survey': Survey,
    'ScenarioList': ScenarioList,
    'AgentList': AgentList,
}


from .sql_base import create_test_session
from .agents_orm import AgentMappedObject

# Import mappers for EDSL objects - if these aren't available, it's a real problem
# that should be fixed, not quietly ignored
from .agents_orm import AgentListMappedObject
from .results_orm import ResultsMappedObject
from .surveys_orm import SurveyMappedObject
from .scenarios_orm import ScenarioListMappedObject

from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from sqlalchemy import create_engine
import tempfile
import sqlite3
import inspect

class Task:
    def __init__(self, path: str, obj_type: str):
        self.path = path
        self.obj_type = obj_type
        if obj_type not in class_names_to_classes:
            raise ValueError(f"Unknown object type: {obj_type}. Available types: {list(class_names_to_classes.keys())}")

class TaskQueue:
    def __init__(self):
        self.queue = []
        self.lock = Lock()  # Add lock for thread safety

    def add_task(self, task):
        with self.lock:
            self.queue.append(task)

    def get_task(self):
        with self.lock:
            if not self.is_empty():
                return self.queue.pop(0)
            return None

    def is_empty(self):
        with self.lock:
            return len(self.queue) == 0

    def __len__(self):
        with self.lock:
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
        
        print(f"Initializing WorkerPool with {num_workers} workers of type {worker_class.__name__}")
        self.workers = [worker_class() for _ in range(num_workers)]
        self.num_workers = num_workers
        self._current_worker_index = 0
        print(f"Worker pool initialized with {num_workers} workers")

    def process_until_empty(self):
        """
        Processes tasks from the queue until it's empty.
        Tasks are assigned to workers in a round-robin fashion.
        Note: This is a synchronous operation. If `worker_class.process_task` is blocking,
        this method will block, and tasks will be processed sequentially by the pool
        despite having multiple worker instances.
        """
        results = []
        print(f"Processing tasks until queue is empty (current size: {len(self.queue)})")
        while not self.queue.is_empty():
            task = self.queue.get_task()
            if task:
                # Simple round-robin for worker selection
                worker_instance = self.workers[self._current_worker_index]
                print(f"Assigning task to worker {self._current_worker_index}")
                try:
                    result = worker_instance.process_task(task)
                    results.append(result)
                    print(f"Worker {self._current_worker_index} completed task")
                except Exception as e:
                    print(f"Worker {self._current_worker_index} encountered error: {str(e)}")
                    import traceback
                    traceback.print_exc()
                finally:
                    self._current_worker_index = (self._current_worker_index + 1) % self.num_workers
            else:
                # This case should ideally not be reached if queue.is_empty() is false
                # and get_task() returns None only when empty.
                print("Warning: Queue reported not empty but get_task() returned None")
                break
        
        print(f"Finished processing tasks, processed {len(results)} items")
        return results

def create_database(db_name="edsl_worker_db", db_dir=None, create_tables=True):
    """
    Creates a SQLite database file in the specified directory or current directory.
    
    Args:
        db_name: Base name for the database file
        db_dir: Directory to create the database in (uses current directory if None)
        create_tables: Whether to create tables in the database
        
    Returns:
        session: SQLAlchemy session
        db_path: Path to the database file
        db_dir: Directory containing the database
    """
    import sqlite3
    
    # If no directory specified, use current directory
    if db_dir is None:
        db_dir = os.getcwd()
    
    # Create directory if it doesn't exist
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
        
    # Create the database file
    db_path = os.path.join(db_dir, f"{db_name}.sqlite")
    
    print(f"Creating database at: {db_path}")
    
    # Create the engine and session
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    session = Session()
    
    if create_tables:
        # Import the Base class from your ORM model
        from .sql_base import Base
        # Create all tables
        Base.metadata.create_all(engine)
        print(f"Created database tables in {db_path}")
        
        # Validate tables were created by checking if they exist
        try:
            # Run a query to get list of tables
            result = engine.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            table_names = [row[0] for row in result]
            print(f"Tables created in database: {', '.join(table_names)}")
            
            if not table_names:
                print("WARNING: No tables were created in the database!")
        except Exception as e:
            print(f"Error validating tables: {e}")
    
    return session, db_path, db_dir

def debug_edsl_object(obj, obj_type):
    """
    Debug helper to print detailed information about an EDSL object.
    """
    print(f"\n--- DEBUG: {obj_type} Object Structure ---")
    print(f"Type: {type(obj)}")
    
    # List all attributes of the object
    print("Attributes:")
    for attr_name in dir(obj):
        if not attr_name.startswith('_') and not callable(getattr(obj, attr_name)):
            try:
                attr_value = getattr(obj, attr_name)
                attr_type = type(attr_value).__name__
                
                # For collections, show length and sample
                if isinstance(attr_value, (list, tuple)):
                    if attr_value:
                        sample = str(attr_value[0])
                        if len(sample) > 50:
                            sample = sample[:50] + "..."
                        print(f"  {attr_name}: {attr_type}[{len(attr_value)}] - Sample: {sample}")
                    else:
                        print(f"  {attr_name}: {attr_type}[0] (empty)")
                elif isinstance(attr_value, dict):
                    if attr_value:
                        keys = list(attr_value.keys())
                        sample_key = keys[0]
                        sample_value = str(attr_value[sample_key])
                        if len(sample_value) > 50:
                            sample_value = sample_value[:50] + "..."
                        print(f"  {attr_name}: {attr_type}[{len(attr_value)}] - Sample: {sample_key}:{sample_value}")
                    else:
                        print(f"  {attr_name}: {attr_type}[0] (empty)")
                else:
                    value_str = str(attr_value)
                    if len(value_str) > 50:
                        value_str = value_str[:50] + "..."
                    print(f"  {attr_name}: {attr_type} - {value_str}")
            except Exception as e:
                print(f"  {attr_name}: Error accessing - {str(e)}")
    
    print(f"--- End DEBUG: {obj_type} ---\n")
    
    # If it's AgentList or ScenarioList, show more details about the contained items
    if obj_type == 'AgentList' and hasattr(obj, 'agents'):
        print(f"AgentList contains {len(obj.agents)} agents")
        if obj.agents:
            print(f"First agent type: {type(obj.agents[0])}")
    
    if obj_type == 'ScenarioList' and hasattr(obj, 'scenarios'):
        print(f"ScenarioList contains {len(obj.scenarios)} scenarios")
        if obj.scenarios:
            print(f"First scenario type: {type(obj.scenarios[0])}")

def debug_mapper_class(mapper_class):
    """Debug helper to print information about a mapper class."""
    print(f"\n--- DEBUG: Mapper Class {mapper_class.__name__} ---")
    print(f"Module: {mapper_class.__module__}")
    
    # Check if from_edsl_object is a class or instance method
    from_edsl_object = getattr(mapper_class, 'from_edsl_object', None)
    if from_edsl_object:
        import inspect
        print(f"from_edsl_object is: {type(from_edsl_object)}")
        
        # Try to get the source code
        try:
            source = inspect.getsource(from_edsl_object)
            print(f"Method source code:\n{source}")
        except Exception as e:
            print(f"Could not get source code: {e}")
        
        # Check if it's a classmethod
        is_classmethod = inspect.ismethod(from_edsl_object) and from_edsl_object.__self__ is mapper_class
        print(f"Is classmethod: {is_classmethod}")
        
        # Check if it accepts the right parameter
        try:
            sig = inspect.signature(from_edsl_object)
            print(f"Method signature: {sig}")
            param_names = list(sig.parameters.keys())
            if is_classmethod:
                # For a classmethod, first param is cls, second is EDSL object
                if len(param_names) >= 2:
                    print(f"Second parameter name (should be EDSL object): {param_names[1]}")
                else:
                    print("Method does not have enough parameters")
            else:
                # For a static or instance method, first param should be EDSL object
                if param_names:
                    print(f"First parameter name (should be EDSL object): {param_names[0]}")
                else:
                    print("Method does not have parameters")
        except Exception as e:
            print(f"Error analyzing method signature: {e}")
    else:
        print("from_edsl_object method not found!")
    
    print(f"--- End DEBUG: Mapper Class ---\n")

class EdslObjectWorker:
    """
    Worker that processes EDSL object files according to the module docstring:
    1. Opens the file at the specified path
    2. Instantiates the correct object type based on the task's obj_type
    3. Writes the object to the database
    """
    def __init__(self, session_factory=None, db_name=None, db_dir=None):
        print("Initializing EdslObjectWorker...")
        self.db_path = None
        self.db_dir = None
        
        if session_factory is None:
            # Create a database in the specified location
            db_name = db_name or f"edsl_worker_{int(time.time())}"
            session, db_path, db_dir = create_database(db_name=db_name, db_dir=db_dir)
            
            print(f"Created new database session")
            print(f"Database name: {db_name}")
            print(f"Database path: {db_path}")
            print(f"Absolute database path: {os.path.abspath(db_path)}")
            print(f"Database directory: {db_dir}")
            
            # Store paths for later reference
            self.db_path = db_path
            self.db_dir = db_dir
            
            # Create a sessionmaker from the existing engine
            self.session_factory = sessionmaker(bind=session.bind)
            # Close the initial session
            session.close()
        else:
            print("Using provided session factory")
            self.session_factory = session_factory
        
        # Map EDSL object types to their corresponding ORM mapper classes
        self.mapper_classes = {
            'Agent': AgentMappedObject,
            'AgentList': AgentListMappedObject,
            'Results': ResultsMappedObject,
            'Survey': SurveyMappedObject,
            'ScenarioList': ScenarioListMappedObject
            # Add other mappers as needed
        }
        
        print(f"EdslObjectWorker initialized with mappers for: {', '.join(self.mapper_classes.keys())}")
        if self.db_path:
            print(f"Worker database located at: {self.db_path}")
    
    @contextmanager
    def get_session(self):
        """Context manager for database sessions"""
        print("Opening new database session...")
        session = self.session_factory()
        
        # Get database path info from the engine connection
        engine = session.get_bind()
        db_url = str(engine.url)
        if 'sqlite' in db_url:
            if 'sqlite:///' in db_url:
                path = db_url.replace('sqlite:///', '')
                print(f"Connected to SQLite database at: {path}")
                print(f"Absolute path: {os.path.abspath(path)}")
            
        try:
            yield session
            print("Committing session...")
            session.commit()
        except:
            print("Error in session, rolling back...")
            session.rollback()
            raise
        finally:
            print("Closing session...")
            session.close()
    
    def process_task(self, task):
        """Process a task by instantiating the object and writing to database if possible."""
        print(f"Processing task: {task.obj_type} from {task.path}")
        
        # Open the file and load JSON data
        with open(task.path, "r") as f:
            data = json.load(f)
        
        print(f"Loaded JSON data, creating {task.obj_type} object...")
        
        # Get the appropriate class for instantiation
        obj_class = class_names_to_classes[task.obj_type]
        
        # Instantiate the object
        edsl_obj = obj_class.from_dict(data)
        print(f"Successfully created {task.obj_type} object")
        
        # Special debugging for problematic object types
        if task.obj_type in ['ScenarioList', 'AgentList']:
            debug_edsl_object(edsl_obj, task.obj_type)
        
        # Write to database if we have a mapper for this object type
        if task.obj_type in self.mapper_classes:
            mapper_class = self.mapper_classes[task.obj_type]
            print(f"{task.obj_type} mapper found: {mapper_class.__name__}, attempting to write to database...")
            
            with self.get_session() as session:
                print(f"Creating mapped object from {task.obj_type}...")
                
                # Extra debugging for problematic types
                if task.obj_type in ['ScenarioList', 'AgentList']:
                    print(f"About to call {mapper_class.__name__}.from_edsl_object()")
                    debug_mapper_class(mapper_class)
                
                # Map the object - will throw exception if it fails
                mapped_obj = mapper_class.from_edsl_object(edsl_obj)
                print(f"Successfully created mapped object: {type(mapped_obj).__name__}")
                
                session.add(mapped_obj)
                print(f"Added mapped object to session, about to flush...")
                
                # Flush changes to get IDs/check constraints
                session.flush()
                print(f"Successfully flushed {task.obj_type} to database")
        else:
            print(f"ERROR: No database mapper for {task.obj_type}")
            raise ValueError(f"No database mapper available for {task.obj_type}")
        
        return edsl_obj

class ClientSimulator(threading.Thread):
    """
    Simulates a client that adds random tasks to the queue in a separate thread.
    """
    def __init__(self, task_queue, task_files, num_tasks=20, interval=0.5):
        """
        Args:
            task_queue: The TaskQueue to add tasks to
            task_files: Dict mapping object types to their json file paths
            num_tasks: Number of tasks to add before stopping
            interval: Seconds to wait between adding tasks
        """
        super().__init__()
        self.task_queue = task_queue
        self.task_files = task_files
        self.num_tasks = num_tasks
        self.interval = interval
        self.daemon = True  # Thread will exit when main program exits
        self.tasks_added = 0
        self.running = True
        self._stop_event = threading.Event()
    
    def run(self):
        """Run the client simulation thread."""
        print(f"Client simulator started. Will add {self.num_tasks} random tasks.")
        while self.running and self.tasks_added < self.num_tasks:
            # Randomly select an object type
            obj_type = random.choice(list(self.task_files.keys()))
            file_path = self.task_files[obj_type]
            
            # Create and add the task
            task = Task(path=file_path, obj_type=obj_type)
            self.task_queue.add_task(task)
            self.tasks_added += 1
            
            print(f"Client added task #{self.tasks_added}: {obj_type} from {file_path}")
            
            # Sleep for the specified interval
            time.sleep(self.interval)
        
        print(f"Client simulator finished. Added {self.tasks_added} tasks.")
    
    def stop(self):
        """Stop the client simulator."""
        self.running = False
        self._stop_event.set()

class WorkerThread(threading.Thread):
    """
    Thread for continuously processing tasks from the queue.
    """
    def __init__(self, worker_pool):
        super().__init__()
        self.worker_pool = worker_pool
        self.daemon = True
        self.processed_count = 0
        self.failed_count = 0
        self.running = True
        self._stop_event = threading.Event()
        print(f"WorkerThread initialized with {len(worker_pool.workers)} workers")
    
    def run(self):
        print("Worker thread started")
        while self.running:
            try:
                if not self.worker_pool.queue.is_empty():
                    # Process a single task at a time
                    task = self.worker_pool.queue.get_task()
                    if task:
                        print(f"WorkerThread got task: {task.obj_type} from {task.path}")
                        try:
                            # Process individual task with the first worker
                            worker = self.worker_pool.workers[0]
                            print(f"Delegating task to worker of type {type(worker).__name__}")
                            result = worker.process_task(task)
                            if result is not None:
                                self.processed_count += 1
                                print(f"Worker processed task: {task.obj_type} - total {self.processed_count} tasks processed")
                            else:
                                self.failed_count += 1
                                print(f"Worker failed to process task: {task.obj_type} - total failures: {self.failed_count}")
                        except Exception as e:
                            self.failed_count += 1
                            print(f"Error in worker processing task: {str(e)}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print("Warning: Queue reported not empty but get_task() returned None")
                else:
                    # Sleep briefly if no tasks are available
                    time.sleep(0.1)
            except Exception as e:
                print(f"Unexpected error in worker thread: {str(e)}")
                import traceback
                traceback.print_exc()
                time.sleep(0.5)  # Add delay to prevent high CPU usage on repeated errors
        
        print(f"Worker thread stopped. Processed {self.processed_count} tasks, failed {self.failed_count}")
    
    def stop(self):
        print("Stopping worker thread...")
        self.running = False
        self._stop_event.set()

if __name__ == "__main__":
    from edsl import (Agent, QuestionMultipleChoice, QuestionLikertFive, 
                      Results, Survey, ScenarioList, AgentList)
    import os
    import signal
    import time
    import concurrent.futures
    import argparse
    import sqlite3
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='EDSL Worker Task Processing Demo')
    parser.add_argument('--db-name', type=str, default="edsl_worker_test", help='Name for the database file')
    parser.add_argument('--db-dir', type=str, default=None, help='Directory to store the database (default: current directory)')
    parser.add_argument('--num-tasks', type=int, default=5000, help='Number of tasks to process')
    parser.add_argument('--num-workers', type=int, default=4, help='Number of worker threads')
    parser.add_argument('--sequential', action='store_true', help='Use sequential processing instead of threaded')
    args = parser.parse_args()
    
    try:
        from tqdm import tqdm  # for progress bar (install with pip if needed)
    except ImportError:
        print("tqdm not available. Installing simple progress bar.")
        # Simple tqdm replacement
        class tqdm:
            def __init__(self, total, desc):
                self.total = total
                self.desc = desc
                self.n = 0
                print(f"{desc}: 0/{total} (0%)")
            
            def update(self, n):
                self.n += n
                percentage = int(self.n / self.total * 100)
                if self.n % (self.total // 20) == 0 or self.n == self.total:  # Show 5% increments
                    print(f"{self.desc}: {self.n}/{self.total} ({percentage}%)")
            
            def __enter__(self):
                return self
            
            def __exit__(self, *args):
                print(f"{self.desc}: {self.n}/{self.total} (100%) [Complete]")
    
    # Set up timeout handler to avoid hanging
    def timeout_handler(signum, frame):
        print("\n!!! TIMEOUT - Process taking too long !!!")
        import sys
        sys.exit(1)
    
    # Set 120 second timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(120)

    print("\n--- EDSL Worker Mass Task Processing Demo ---\n")
    
    # Create a permanent database
    db_name = args.db_name
    db_dir = args.db_dir or os.getcwd()
    print(f"Creating database: {db_name} in directory: {db_dir}")
    
    # Initialize worker with a permanent database
    print("\nInitializing EdslObjectWorker with permanent database...")
    worker = EdslObjectWorker(db_name=db_name, db_dir=db_dir)
    
    # Store database info
    db_path = worker.db_path
    db_dir = worker.db_dir
    
    # Get and print the full absolute path to the database
    abs_db_path = os.path.abspath(db_path)
    print(f"\n===== DATABASE INFORMATION =====")
    print(f"Database name: {db_name}")
    print(f"Database file: {db_path}")
    print(f"Absolute database path: {abs_db_path}")
    print(f"Database directory: {db_dir}")
    print(f"Database directory exists: {os.path.exists(db_dir)}")
    print(f"Database file exists: {os.path.exists(db_path)}")
    print(f"==================================\n")
    
    # Create test files for all supported EDSL types
    print("\nCreating example files for all EDSL object types...")
    test_files = {}
    
    # Create an Agent example
    test_files['Agent'] = "test_agent_mass.json"
    agent_example_data = Agent.example().to_dict() 
    with open(test_files['Agent'], "w") as f:
        json.dump(agent_example_data, f)
    print(f"Created Agent example file")
    
    # Create a QuestionMultipleChoice example
    test_files['QuestionMultipleChoice'] = "test_question_mc_mass.json"
    question_mc_example_data = QuestionMultipleChoice.example().to_dict()
    with open(test_files['QuestionMultipleChoice'], "w") as f:
        json.dump(question_mc_example_data, f)
    print(f"Created QuestionMultipleChoice example file")
    
    # Create a QuestionLikertFive example
    test_files['QuestionLikertFive'] = "test_question_likert_mass.json"
    question_likert_example_data = QuestionLikertFive.example().to_dict()
    with open(test_files['QuestionLikertFive'], "w") as f:
        json.dump(question_likert_example_data, f)
    print(f"Created QuestionLikertFive example file")
    
    # Create a Results example
    test_files['Results'] = "test_results_mass.json"
    results_example_data = Results.example().to_dict()
    with open(test_files['Results'], "w") as f:
        json.dump(results_example_data, f)
    print(f"Created Results example file")
    
    # Create a Survey example
    test_files['Survey'] = "test_survey_mass.json"
    survey_example_data = Survey.example().to_dict()
    with open(test_files['Survey'], "w") as f:
        json.dump(survey_example_data, f)
    print(f"Created Survey example file")
    
    # Create a ScenarioList example
    test_files['ScenarioList'] = "test_scenariolist_mass.json"
    scenariolist_example_data = ScenarioList.example().to_dict()
    with open(test_files['ScenarioList'], "w") as f:
        json.dump(scenariolist_example_data, f)
    print(f"Created ScenarioList example file")
    
    # Create an AgentList example
    test_files['AgentList'] = "test_agentlist_mass.json"
    agentlist_example_data = AgentList.example().to_dict()
    with open(test_files['AgentList'], "w") as f:
        json.dump(agentlist_example_data, f)
    print(f"Created AgentList example file")
    
    print(f"Created test files for {len(test_files)} EDSL object types")
    
    # Add database schema inspection
    def inspect_table_schema(db_path, table_name):
        """Inspect the schema of a specific table in the database."""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check if table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            if not cursor.fetchone():
                print(f"Table '{table_name}' does not exist in the database.")
                return
            
            # Get schema
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            print(f"\n--- Schema for table '{table_name}' ---")
            print("| ID | Name | Type | NotNull | DefaultValue | PK |")
            print("|----|----|----|----|----|----|")
            for col in columns:
                print(f"| {col[0]} | {col[1]} | {col[2]} | {col[3]} | {col[4]} | {col[5]} |")
            
            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list({table_name});")
            fks = cursor.fetchall()
            
            if fks:
                print("\nForeign Keys:")
                print("| ID | Seq | Table | From | To | OnUpdate | OnDelete | Match |")
                print("|----|----|----|----|----|----|----|----|")
                for fk in fks:
                    print(f"| {fk[0]} | {fk[1]} | {fk[2]} | {fk[3]} | {fk[4]} | {fk[5]} | {fk[6]} | {fk[7] if len(fk) > 7 else ''} |")
            
            # Get indexes
            cursor.execute(f"PRAGMA index_list({table_name});")
            indexes = cursor.fetchall()
            
            if indexes:
                print("\nIndexes:")
                for idx in indexes:
                    idx_name = idx[1]
                    print(f"- {idx_name}")
                    # Get index columns
                    cursor.execute(f"PRAGMA index_info({idx_name});")
                    idx_cols = cursor.fetchall()
                    for ic in idx_cols:
                        print(f"  - Column {ic[1]}: {ic[2]} (position {ic[0]})")
            
            conn.close()
        except Exception as e:
            print(f"Error inspecting schema for table '{table_name}': {e}")
    
    # Add schema inspection for problematic tables after validation
    print("\n===== DATABASE SCHEMA INSPECTION =====")
    inspect_table_schema(db_path, "agent_list")
    inspect_table_schema(db_path, "scenario_list")
    print("=====================================\n")
    
    # Add mapper class inspection
    print("\n===== MAPPER CLASS INSPECTION =====")
    print("Inspecting ScenarioListMappedObject:")
    debug_mapper_class(ScenarioListMappedObject)
    
    print("Inspecting AgentListMappedObject:")
    debug_mapper_class(AgentListMappedObject)
    print("===================================\n")
    
    # Add a test run of the problematic mapper classes
    print("\n===== TESTING MAPPER IMPLEMENTATIONS =====")
    # Create a sample ScenarioList
    print("Creating test ScenarioList...")
    scenario_list = ScenarioList.example()
    print(f"Created ScenarioList with {len(scenario_list.scenarios) if hasattr(scenario_list, 'scenarios') else 'unknown'} scenarios")
    
    # Test the mapping directly
    print("Testing ScenarioListMappedObject.from_edsl_object()...")
    # This will throw an exception if it fails
    mapped_scenario_list = ScenarioListMappedObject.from_edsl_object(scenario_list)
    print(f"Successfully mapped ScenarioList to {type(mapped_scenario_list).__name__}")
    
    # Create a sample AgentList
    print("\nCreating test AgentList...")
    agent_list = AgentList.example()
    print(f"Created AgentList with {len(agent_list.agents) if hasattr(agent_list, 'agents') else 'unknown'} agents")
    
    # Test the mapping directly
    print("Testing AgentListMappedObject.from_edsl_object()...")
    # This will throw an exception if it fails
    mapped_agent_list = AgentListMappedObject.from_edsl_object(agent_list)
    print(f"Successfully mapped AgentList to {type(mapped_agent_list).__name__}")
    
    print("========================================\n")
    
    # Settings for mass processing
    num_tasks = args.num_tasks
    batch_size = 100  # Tasks to process in each report
    use_threading = not args.sequential
    num_workers = args.num_workers if use_threading else 1  # Number of worker threads
    
    # Add database table validation before starting processing
    def validate_database(db_path):
        """Validate that the database exists and contains tables"""
        if not os.path.exists(db_path):
            print(f"ERROR: Database file {db_path} does not exist!")
            return False
            
        try:
            # Connect directly to the database and check tables
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]
            print(f"Database contains tables: {', '.join(table_names)}")
            conn.close()
            return len(table_names) > 0
        except Exception as e:
            print(f"Error validating database: {e}")
            return False
    
    # Validate the database was properly created
    print("\nValidating database...")
    if validate_database(db_path):
        print("Database validation successful!")
    else:
        print("WARNING: Database validation failed!")
    
    try:
        # Create tasks in memory (mix of different types)
        print(f"\nGenerating {num_tasks} tasks...")
        all_tasks = []
        obj_types = list(test_files.keys())
        
        for i in range(num_tasks):
            # Select task type in round-robin fashion
            obj_type = obj_types[i % len(obj_types)]
            task = Task(path=test_files[obj_type], obj_type=obj_type)
            all_tasks.append(task)
        
        print(f"Generated {num_tasks} tasks")
        
        # Process all tasks with progress tracking
        print(f"\nProcessing {num_tasks} tasks...")
        start_time = time.time()
        
        results = []
        success_count = 0
        failure_count = 0
        
        if use_threading:
            print(f"Using ThreadPoolExecutor with {num_workers} workers")
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit all tasks to the executor
                future_to_task = {executor.submit(worker.process_task, task): task for task in all_tasks}
                
                # Process results as they complete with progress bar
                with tqdm(total=num_tasks, desc="Processing") as progress:
                    for future in concurrent.futures.as_completed(future_to_task):
                        task = future_to_task[future]
                        try:
                            result = future.result()
                            if result is not None:
                                success_count += 1
                            else:
                                failure_count += 1
                            results.append(result)
                        except Exception as e:
                            print(f"Task processing error: {e}")
                            failure_count += 1
                        finally:
                            progress.update(1)
                            
                            # Periodically show stats
                            if (success_count + failure_count) % batch_size == 0:
                                elapsed = time.time() - start_time
                                rate = (success_count + failure_count) / elapsed
                                print(f"\nProcessed {success_count + failure_count} tasks "
                                      f"({success_count} succeeded, {failure_count} failed) "
                                      f"in {elapsed:.2f}s ({rate:.2f} tasks/sec)")
        else:
            print("Using sequential processing")
            # Process tasks sequentially with progress bar
            with tqdm(total=num_tasks, desc="Processing") as progress:
                for i, task in enumerate(all_tasks):
                    try:
                        result = worker.process_task(task)
                        if result is not None:
                            success_count += 1
                        else:
                            failure_count += 1
                        results.append(result)
                    except Exception as e:
                        print(f"Task processing error: {e}")
                        failure_count += 1
                    finally:
                        progress.update(1)
                        
                        # Periodically show stats
                        if (i + 1) % batch_size == 0:
                            elapsed = time.time() - start_time
                            rate = (i + 1) / elapsed
                            print(f"\nProcessed {i + 1} tasks "
                                  f"({success_count} succeeded, {failure_count} failed) "
                                  f"in {elapsed:.2f}s ({rate:.2f} tasks/sec)")
        
        # Final stats
        elapsed = time.time() - start_time
        rate = num_tasks / elapsed
        
        print("\n--- Final Results ---")
        print(f"Total tasks: {num_tasks}")
        print(f"Succeeded: {success_count}")
        print(f"Failed: {failure_count}")
        print(f"Time elapsed: {elapsed:.2f} seconds")
        print(f"Processing rate: {rate:.2f} tasks/second")
        
        # Collect metrics by type
        type_metrics = {}
        for task, result in zip(all_tasks, results):
            if task.obj_type not in type_metrics:
                type_metrics[task.obj_type] = {'total': 0, 'success': 0, 'failure': 0}
            
            type_metrics[task.obj_type]['total'] += 1
            if result is not None:
                type_metrics[task.obj_type]['success'] += 1
            else:
                type_metrics[task.obj_type]['failure'] += 1
        
        print("\n--- Results by Type ---")
        for obj_type, metrics in type_metrics.items():
            print(f"{obj_type}: {metrics['success']}/{metrics['total']} succeeded "
                  f"({metrics['success']/metrics['total']*100:.1f}%)")
            
    except Exception as e:
        print(f"\n!!! Error during processing: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        # Cancel the alarm
        signal.alarm(0)
        
        # Close the database connections
        print("\nClosing database connections...")
        
        # Print final database information
        print("\n===== FINAL DATABASE INFORMATION =====")
        print(f"Database name: {db_name}")
        print(f"Database file: {db_path}")
        print(f"Absolute database path: {abs_db_path}")
        print(f"Database directory: {db_dir}")
        print(f"Database directory exists: {os.path.exists(db_dir)}")
        print(f"Database file exists: {os.path.exists(db_path)}")
        if os.path.exists(db_path):
            db_size_bytes = os.path.getsize(db_path)
            print(f"Database file size: {db_size_bytes} bytes ({db_size_bytes/1024:.2f} KB)")
        print(f"======================================\n")
        
        # Inspect database tables and counts
        print("\n===== DATABASE TABLE COUNTS =====")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                    count = cursor.fetchone()[0]
                    print(f"Table '{table_name}': {count} rows")
                except Exception as e:
                    print(f"Error counting rows in table '{table_name}': {e}")
            
            # Specifically check the agent table
            try:
                cursor.execute("SELECT COUNT(*) FROM agent;")
                agent_count = cursor.fetchone()[0]
                print(f"\nAgent table details: {agent_count} total rows")
                
                # Check if any agents came from AgentList objects
                if 'AgentList' in class_names_to_classes:
                    # Check for agents that might have been part of an AgentList
                    cursor.execute("SELECT COUNT(DISTINCT id) FROM agent;")
                    unique_agents = cursor.fetchone()[0]
                    print(f"Unique agents: {unique_agents}")
            except Exception as e:
                print(f"Error getting agent table details: {e}")
            
            conn.close()
        except Exception as e:
            print(f"Error inspecting database: {e}")
        print(f"================================\n")
        
        # Clean up test files
        print("Cleaning up test files...")
        for filename in test_files.values():
            if os.path.exists(filename):
                try:
                    os.remove(filename)
                    print(f"Removed {filename}")
                except OSError as e:
                    print(f"Error removing {filename}: {e}")
        
        # Database is permanent, we don't need to clean it up
        print(f"\n===== DATABASE INFORMATION =====")
        print(f"Database is located at: {abs_db_path}")
        print(f"You can access it with: sqlite3 {abs_db_path}")
        print(f"=================================\n")
        
        print("\n--- Demo Completed ---")
