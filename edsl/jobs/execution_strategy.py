"""
Execution strategies for EDSL jobs.

This module provides various execution strategy implementations for running EDSL jobs.
It follows the Strategy Pattern to abstract different execution modes (local, remote, async, sync)
and make them interchangeable.
"""
from abc import ABC, abstractmethod
from typing import Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from ..results import Results
    from .data_structures import RunConfig
    from ..jobs import Jobs
    from .jobs_runner_asyncio import JobsRunnerAsyncio
    from .remote_inference import JobsRemoteInferenceHandler


class ExecutionStrategy(ABC):
    """
    Abstract base class for job execution strategies.
    
    This class defines the interface for all execution strategies and provides
    common functionality. Concrete implementations handle specific execution
    modes (remote vs local, async vs sync).
    """
    
    def __init__(self, jobs: "Jobs", config: "RunConfig"):
        """
        Initialize an execution strategy.
        
        Parameters:
            jobs: The Jobs instance to execute
            config: Configuration parameters and environment for execution
        """
        self.jobs = jobs
        self.config = config
    
    @abstractmethod
    def execute(self) -> "Results":
        """
        Execute the job using this strategy.
        
        Returns:
            Results: The results of job execution
        """
        pass


class RemoteExecutionStrategy(ExecutionStrategy):
    """
    Strategy for executing jobs using remote inference.
    
    This strategy offloads execution to a remote server, which is useful
    for large jobs or when local resources are limited.
    """
    
    def execute(self) -> Union["Results", None]:
        """
        Execute the job using remote inference.
        
        This method tries to run the job on a remote server and returns
        the results if successful, or None if remote execution is not 
        available or disabled.
        
        Returns:
            Results or None: Results if remote execution succeeded, None otherwise
        """
        from .remote_inference import RemoteJobInfo, JobsRemoteInferenceHandler
        
        # Create remote inference handler
        job_handler = JobsRemoteInferenceHandler(
            self.jobs, verbose=self.config.parameters.verbose
        )
        
        # Check if remote inference should be used
        if not job_handler.use_remote_inference(self.config.parameters.disable_remote_inference):
            return None
            
        # Start remote job
        job_info: RemoteJobInfo = self._start_remote_inference_job(job_handler)
        
        # Handle background vs waiting mode
        if self.config.parameters.background:
            from edsl.results import Results
            results = Results.from_job_info(job_info)
            return results
        else:
            results = job_handler.poll_remote_inference_job(job_info)
            return results
    
    def _start_remote_inference_job(
        self, job_handler: "JobsRemoteInferenceHandler"
    ) -> "RemoteJobInfo":
        """
        Start a remote inference job.
        
        Parameters:
            job_handler: The handler for remote inference jobs
            
        Returns:
            RemoteJobInfo: Information about the created remote job
        """
        job_info = job_handler.create_remote_inference_job(
            iterations=self.config.parameters.n,
            remote_inference_description=self.config.parameters.remote_inference_description,
            remote_inference_results_visibility=self.config.parameters.remote_inference_results_visibility,
            fresh=self.config.parameters.fresh,
        )
        return job_info


class LocalExecutionStrategy(ExecutionStrategy):
    """
    Strategy for executing jobs locally.
    
    This strategy runs jobs on the local machine using available resources.
    It's the fallback strategy when remote execution is not available.
    """
    
    def execute(self) -> "Results":
        """
        Execute the job locally.
        
        This method runs the job on the local machine using the configured
        resources and parameters.
        
        Returns:
            Results: The results of job execution
        """
        import asyncio
        from .jobs_runner_asyncio import JobsRunnerAsyncio
        
        # Initialize the runner with the current environment
        runner = JobsRunnerAsyncio(self.jobs, environment=self.config.environment)
        
        # For doctests and regular sync execution, use runner.run directly
        # This avoids async/await complications
        return runner.run(self.config.parameters)
    
    def is_async_context(self) -> bool:
        """
        Check if this code is running in an async context.
        
        Returns:
            bool: True if in an async context, False otherwise
        """
        import asyncio
        try:
            # If this doesn't raise, we're in an async context
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            # No running event loop
            return False


class ExecutionStrategyFactory:
    """
    Factory for creating appropriate execution strategies.
    
    This factory determines which execution strategy to use based on
    job configuration and available resources.
    """
    
    @staticmethod
    def create_strategy(jobs: "Jobs", config: "RunConfig") -> ExecutionStrategy:
        """
        Create the appropriate execution strategy for the given job and config.
        
        This method first tries to create a remote execution strategy if remote
        execution is enabled and available. If not, it falls back to local execution.
        
        Parameters:
            jobs: The Jobs instance to execute
            config: Configuration parameters and environment
            
        Returns:
            ExecutionStrategy: The appropriate strategy for executing the job
        """
        # Prepare common prerequisites
        jobs._prepare_to_run()
        jobs._check_if_remote_keys_ok()
        
        # Set up cache if needed
        if config.environment.cache is None or config.environment.cache is True:
            from ..caching import CacheHandler
            config.environment.cache = CacheHandler().get_cache()
        elif config.environment.cache is False:
            from ..caching import Cache
            config.environment.cache = Cache(immediate_write=False)
        
        # Try remote strategy first
        remote_strategy = RemoteExecutionStrategy(jobs, config)
        results = remote_strategy.execute()
        
        if results is not None:
            return remote_strategy
        
        # Fall back to local execution
        jobs._check_if_local_keys_ok()
        
        # Set up bucket collection if needed
        if config.environment.bucket_collection is None:
            config.environment.bucket_collection = jobs.create_bucket_collection()
        
        # Update bucket collection from key lookup if available
        if (
            config.environment.key_lookup is not None
            and config.environment.bucket_collection is not None
        ):
            config.environment.bucket_collection.update_from_key_lookup(
                config.environment.key_lookup
            )
        
        return LocalExecutionStrategy(jobs, config)