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
from typing import TYPE_CHECKING, List, Generator, Tuple, Optional, Any

if TYPE_CHECKING:
    from ..results import Results

from ..results import Results
from ..tasks import TaskHistory
from ..utilities.decorators import jupyter_nb_handler

from .jobs_runner_status import JobsRunnerStatus
from .async_interview_runner import AsyncInterviewRunner
from .data_structures import RunEnvironment, RunParameters, RunConfig
from .progress_tracking import ProgressTracker
from .error_handling import ErrorHandler
from .cache_manager import CacheManager

if TYPE_CHECKING:
    from ..jobs import Jobs
    from ..interviews import Interview


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
        relevant_cache = CacheManager.extract_relevant_cache(results, self.environment.cache)

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

        # Set up jobs runner status and progress tracking
        if self.environment.jobs_runner_status is None:
            from edsl.coop import Coop
            coop = Coop()
            endpoint_url = coop.get_progress_bar_url()
            
            self.environment.jobs_runner_status = JobsRunnerStatus(
                self,
                n=parameters.n,
                endpoint_url=endpoint_url,
                job_uuid=parameters.job_uuid,
            )
        
        # Set up progress tracking
        progress_tracker = ProgressTracker(self.jobs, run_config)
        progress_tracker.setup()

        # Initialize empty results
        results = Results(
            survey=self.jobs.survey,
            data=[],
            task_history=TaskHistory(),
        )

        # Run the interviews and collect results
        exception_to_raise = None
        try:
            # Run interviews and collect results
            await self._collect_results(results, run_config)
            self.completed = True
            
        except KeyboardInterrupt:
            # Handle keyboard interrupts gracefully
            print("Keyboard interrupt received. Stopping gracefully...")
            
        except Exception as e:
            # Handle other exceptions based on configuration
            if parameters.stop_on_exception:
                exception_to_raise = e
                
        finally:
            # Clean up progress tracking
            progress_tracker.cleanup()

            if exception_to_raise:
                raise exception_to_raise

            # Process results and handle exceptions
            self._process_results(results, run_config)
            
            return results
            
    async def _collect_results(self, results: Results, run_config: RunConfig) -> None:
        """
        Collect results from interviews.
        
        Parameters:
            results: The Results object to populate
            run_config: Configuration for running interviews
        """
        result_generator = AsyncInterviewRunner(self.jobs, run_config)
        async for result, interview in result_generator.run():
            results.append(result)
            results.task_history.add_interview(interview)
    
    def _process_results(self, results: Results, run_config: RunConfig) -> None:
        """
        Process the collected results.
        
        This method extracts relevant cache entries, adds bucket collection info,
        and handles any exceptions that occurred during execution.
        
        Parameters:
            results: The Results object to process
            run_config: Configuration used for running interviews
        """
        # Extract relevant cache entries
        relevant_cache = CacheManager.extract_relevant_cache(results, self.environment.cache)
        results.cache = relevant_cache
        
        # Add bucket collection info
        results.bucket_collection = self.environment.bucket_collection
        
        # Handle any exceptions that occurred
        error_handler = ErrorHandler(results, run_config.parameters)
        error_handler.handle_exceptions()
