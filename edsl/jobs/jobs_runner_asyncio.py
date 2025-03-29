"""
Asynchronous execution engine for EDSL jobs.

This module provides the core functionality for running interviews asynchronously,
which is essential for efficient execution of large jobs. It handles the complex
process of coordinating multiple concurrent interviews, managing progress tracking,
and gracefully handling cancellations and errors.

Key components:
- JobsRunnerAsyncio: The main class that orchestrates async execution
- Progress bar integration with remote status tracking
- Error handling and graceful cancellation
- Result collection and organization

This module is primarily used internally by the Jobs class and is typically not
accessed directly by end users, though advanced users may need to understand its
behavior when customizing job execution.
"""
from __future__ import annotations
import time
import asyncio
import threading
import warnings
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..results import Results

from ..results import Results
from ..tasks import TaskHistory
from ..utilities.decorators import jupyter_nb_handler
from ..utilities.memory_debugger import MemoryDebugger


from .jobs_runner_status import JobsRunnerStatus
from .async_interview_runner import AsyncInterviewRunner
from .data_structures import RunEnvironment, RunParameters, RunConfig
from .results_exceptions_handler import ResultsExceptionsHandler
        


if TYPE_CHECKING:
    from ..jobs import Jobs


class JobsRunnerAsyncio:
    """
    Executes a collection of interviews asynchronously with progress tracking.
    
    This class is the main execution engine for EDSL jobs. It manages the asynchronous
    running of interviews, handles progress tracking, and organizes results. It is
    instantiated by a Jobs object and handles the complex execution logic that makes
    parallel interview processing efficient.
    
    Key responsibilities:
    1. Coordinating asynchronous execution of interviews
    2. Tracking and reporting progress
    3. Handling errors and cancellations
    4. Collecting and organizing results
    
    This class supports two main execution modes:
    - run(): For synchronous contexts (returns after completion)
    - run_async(): For asynchronous contexts (can be awaited)
    """

    def __init__(self, jobs: "Jobs", environment: RunEnvironment):
        """
        Initialize a JobsRunnerAsyncio instance.
        
        Parameters:
            jobs (Jobs): The Jobs instance containing the interviews to run
            environment (RunEnvironment): The environment configuration containing
                resources like cache, key_lookup, and bucket_collection
                
        Notes:
            - The Jobs instance provides the interviews to be executed
            - The environment contains resources like caches and API keys
            - Additional runtime state like completion status is initialized when run() is called
        """
        self.jobs = jobs
        self.environment = environment
        # These will be set when run() is called
        self.start_time = None
        self.completed = None

    def __len__(self):
        return len(self.jobs)

    async def _execute_interviews(self, parameters: RunParameters, run_config: RunConfig) -> Results:
        """Core interview execution logic shared between run() and run_async()."""
        results = Results(
            survey=self.jobs.survey,
            data=[],
            task_history=TaskHistory(include_traceback=not parameters.progress_bar),
        )

        result_generator = AsyncInterviewRunner(self.jobs, run_config)
        async for result, interview in result_generator.run():
            results.data.append(result)
            results.task_history.add_interview(interview)
        
        results.cache = results.relevant_cache(self.environment.cache)
        results.bucket_collection = self.environment.bucket_collection
        
        return results

    async def run_async(self, parameters: RunParameters) -> Results:
        """Execute interviews asynchronously without progress tracking."""
        run_config = RunConfig(parameters=parameters, environment=self.environment)
        self.environment.jobs_runner_status = JobsRunnerStatus(self, n=parameters.n)
        
        return await self._execute_interviews(parameters, run_config)

    def simple_run(self, parameters: Optional[RunParameters] = None) -> Results:
        """
        Run interviews synchronously with minimal configuration.
        
        This is a convenience method that provides a very simple synchronous interface
        for running jobs. It's primarily used for quick tests or debugging, not for 
        production use.
        
        Parameters:
            parameters (RunParameters, optional): Configuration parameters for the run.
                If not provided, default parameters will be used.
                
        Returns:
            Results: A Results object containing all responses and metadata
            
        Notes:
            - This method is synchronous (blocks until completion)
            - It doesn't include progress tracking or advanced error handling
            - For production use, use the main run() method instead
        """
        if parameters is None:
            parameters = RunParameters()
            
        data = asyncio.run(self.run_async(parameters))
        return Results(survey=self.jobs.survey, data=data)

    class ProgressBarManager:
        """Context manager for handling progress bar setup and thread management."""
        
        def __init__(self, jobs_runner, run_config, parameters):
            self.parameters = parameters
            
            # Set up progress tracking
            from ..coop import Coop
            coop = Coop()
            endpoint_url = coop.get_progress_bar_url()
            
            # Set up jobs runner status
            params = {
                "jobs_runner": jobs_runner,
                "n": parameters.n,
                "endpoint_url": endpoint_url,
                "job_uuid": parameters.job_uuid,
            }
            jobs_runner_status_cls = (JobsRunnerStatus if run_config.environment.jobs_runner_status is None 
                                    else run_config.environment.jobs_runner_status)
            self.jobs_runner_status = jobs_runner_status_cls(**params)
            
            # Store on run_config for use by other components
            run_config.environment.jobs_runner_status = self.jobs_runner_status
            
            self.progress_thread = None
            self.stop_event = threading.Event()

        def __enter__(self):
            if self.parameters.progress_bar and self.jobs_runner_status.has_ep_api_key():
                self.jobs_runner_status.setup()
                self.progress_thread = threading.Thread(
                    target=self._run_progress_bar,
                    args=(self.stop_event, self.jobs_runner_status)
                )
                self.progress_thread.start()
            elif self.parameters.progress_bar:
                warnings.warn(
                    "You need an Expected Parrot API key to view job progress bars."
                )
            return self.stop_event

        def __exit__(self, exc_type, exc_val, exc_tb):
            self.stop_event.set()
            if self.progress_thread is not None:
                self.progress_thread.join()

        @staticmethod
        def _run_progress_bar(stop_event, jobs_runner_status):
            """Runs the progress bar in a separate thread."""
            jobs_runner_status.update_progress(stop_event)

    @jupyter_nb_handler
    async def run(self, parameters: RunParameters) -> Results:
        """Execute interviews asynchronously with full feature support."""
        run_config = RunConfig(parameters=parameters, environment=self.environment)
        self.start_time = time.monotonic()
        self.completed = False

        exception_to_raise = None
        with self.ProgressBarManager(self, run_config, parameters) as stop_event:
            try:
                results = await self._execute_interviews(parameters, run_config)
                self.completed = True
            except KeyboardInterrupt:
                print("Keyboard interrupt received. Stopping gracefully...")
                results = Results(survey=self.jobs.survey, data=[], task_history=TaskHistory())
            except Exception as e:
                if parameters.stop_on_exception:
                    exception_to_raise = e
                results = Results(survey=self.jobs.survey, data=[], task_history=TaskHistory())

        if exception_to_raise:
            raise exception_to_raise

        ResultsExceptionsHandler(results, parameters).handle_exceptions()
        return results
