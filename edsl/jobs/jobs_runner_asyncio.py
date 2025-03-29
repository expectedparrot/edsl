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

from .jobs_runner_status import JobsRunnerStatus
from .async_interview_runner import AsyncInterviewRunner
from .data_structures import RunEnvironment, RunParameters, RunConfig

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

    async def run_async(self, parameters: RunParameters) -> 'Results':
        """
        Execute interviews asynchronously without progress tracking.
        
        This method provides a simplified version of the run method, primarily used
        by other modules that need direct access to asynchronous execution without
        the full feature set of the main run() method. This is a lower-level interface
        that doesn't include progress bars or advanced error handling.
        
        Parameters:
            parameters (RunParameters): Configuration parameters for the run
            
        Returns:
            Results: A Results object containing all responses and metadata
            
        Notes:
            - This method doesn't support progress bars or interactive cancellation
            - It doesn't handle keyboard interrupts specially
            - It's primarily meant for internal use by other EDSL components
            - For most use cases, the main run() method is preferred
        """
        # Initialize a simple status tracker (no progress bar)
        self.environment.jobs_runner_status = JobsRunnerStatus(self, n=parameters.n)
        data = []
        task_history = TaskHistory(include_traceback=False)

        run_config = RunConfig(parameters=parameters, environment=self.environment)
        result_generator = AsyncInterviewRunner(self.jobs, run_config)

        # Process results as they come in
        async for result, interview in result_generator.run():
            data.append(result)
            task_history.add_interview(interview)

        # Create the results object
        results = Results(survey=self.jobs.survey, task_history=task_history, data=data)

        # Extract only the relevant cache entries
        relevant_cache = results.relevant_cache(self.environment.cache)

        return Results(
            survey=self.jobs.survey,
            task_history=task_history,
            data=data,
            cache=relevant_cache,
        )

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

    @jupyter_nb_handler
    async def run(self, parameters: RunParameters) -> Results:
        """
        Execute interviews asynchronously with full feature support.
        
        This is the main method for running jobs with full feature support, including
        progress tracking, error handling, and graceful cancellation. It's decorated
        with @jupyter_nb_handler to ensure proper handling in notebook environments.
        
        Parameters:
            parameters (RunParameters): Configuration parameters for the run
            
        Returns:
            Results: A Results object containing all responses and metadata
            
        Raises:
            Exception: Any unhandled exception from interviews if stop_on_exception=True
            KeyboardInterrupt: If the user interrupts execution and it can't be handled gracefully
            
        Notes:
            - Supports progress bars with remote tracking via Coop
            - Handles keyboard interrupts gracefully
            - Manages concurrent execution of multiple interviews
            - Collects and consolidates results from all completed interviews
            - Can be used in both async and sync contexts due to the @jupyter_nb_handler decorator
        """

        run_config = RunConfig(parameters=parameters, environment=self.environment)

        self.start_time = time.monotonic()
        self.completed = False

        from ..coop import Coop

        coop = Coop()
        endpoint_url = coop.get_progress_bar_url()

        def set_up_jobs_runner_status(jobs_runner_status):
            if jobs_runner_status is not None:
                return jobs_runner_status(
                    self,
                    n=parameters.n,
                    endpoint_url=endpoint_url,
                    job_uuid=parameters.job_uuid,
                )
            else:
                return JobsRunnerStatus(
                    self,
                    n=parameters.n,
                    endpoint_url=endpoint_url,
                    job_uuid=parameters.job_uuid,
                )

        run_config.environment.jobs_runner_status = set_up_jobs_runner_status(
            self.environment.jobs_runner_status
        )

        async def get_results(results) -> None:
            """Conducted the interviews and append to the results list."""
            result_generator = AsyncInterviewRunner(self.jobs, run_config)
            async for result, interview in result_generator.run():
                results.append(result)
                results.task_history.add_interview(interview)

            self.completed = True

        def run_progress_bar(stop_event, jobs_runner_status) -> None:
            """Runs the progress bar in a separate thread."""
            jobs_runner_status.update_progress(stop_event)

        def set_up_progress_bar(progress_bar: bool, jobs_runner_status):
            progress_thread = None
            if progress_bar and jobs_runner_status.has_ep_api_key():
                jobs_runner_status.setup()
                progress_thread = threading.Thread(
                    target=run_progress_bar, args=(stop_event, jobs_runner_status)
                )
                progress_thread.start()
            elif progress_bar:
                warnings.warn(
                    "You need an Expected Parrot API key to view job progress bars."
                )
            return progress_thread

        results = Results(
            survey=self.jobs.survey,
            data=[],
            task_history=TaskHistory(),
            #           cache=self.environment.cache.new_entries_cache(),
        )

        stop_event = threading.Event()
        progress_thread = set_up_progress_bar(
            parameters.progress_bar, run_config.environment.jobs_runner_status
        )

        exception_to_raise = None
        try:
            await get_results(results)
        except KeyboardInterrupt:
            print("Keyboard interrupt received. Stopping gracefully...")
            stop_event.set()
        except Exception as e:
            if parameters.stop_on_exception:
                exception_to_raise = e
            stop_event.set()
        finally:
            stop_event.set()
            if progress_thread is not None:
                progress_thread.join()

            if exception_to_raise:
                raise exception_to_raise

            relevant_cache = results.relevant_cache(self.environment.cache)
            results.cache = relevant_cache
            # breakpoint()
            results.bucket_collection = self.environment.bucket_collection

            from .results_exceptions_handler import ResultsExceptionsHandler

            results_exceptions_handler = ResultsExceptionsHandler(results, parameters)

            results_exceptions_handler.handle_exceptions()
            return results
