"""
Final solution for Issue #1841: Non-linear scaling of job running time.

This implementation addresses the memory management issues in Jobs.run()
with a hybrid approach that adapts the batch size based on workload.
"""

import asyncio
import gc
import time
from typing import Union

from edsl.jobs.jobs import Jobs
from edsl.results import Results
from edsl.tasks import TaskHistory
from edsl.jobs.async_interview_runner import AsyncInterviewRunner
from edsl.jobs.progress_bar_manager import ProgressBarManager
from edsl.jobs.results_exceptions_handler import ResultsExceptionsHandler
from edsl.jobs.data_structures import RunConfig

async def optimized_execute_with_remote_cache(self, run_job_async: bool) -> Results:
    """Optimized implementation of _execute_with_remote_cache for better scaling.
    
    This implementation uses a hybrid approach:
    1. Dynamic batch sizing based on the total number of interviews
    2. Efficient cleanup of interview references
    3. Strategic garbage collection
    4. Optimized result insertion
    
    The batch size is determined dynamically - small for small workloads for maximum
    memory efficiency, and larger for larger workloads to reduce GC overhead.
    """
    from edsl.caching import Cache
    
    assert isinstance(self.run_config.environment.cache, Cache)
    
    # Create the RunConfig for the job
    run_config = RunConfig(parameters=self.run_config.parameters, environment=self.run_config.environment)
    
    # Setup JobsRunnerStatus if needed
    if self.run_config.environment.jobs_runner_status is None:
        from edsl.jobs.jobs_runner_status import JobsRunnerStatus
        self.run_config.environment.jobs_runner_status = JobsRunnerStatus(
            self, n=self.run_config.parameters.n
        )
    
    # Create interview runner
    interview_runner = AsyncInterviewRunner(self, run_config)
    
    # Create an initial Results object with appropriate settings
    results = Results(
        survey=self.survey,
        data=[],
        task_history=TaskHistory(include_traceback=not self.run_config.parameters.progress_bar)
    )
    
    # Calculate appropriate batch size based on workload
    num_interviews = self.num_interviews
    
    # Determine optimal batch size:
    # - Small batch for small workloads (better memory efficiency)
    # - Larger batch for larger workloads (fewer GC calls)
    if num_interviews < 25:
        batch_size = 5  # Very small batch for small workloads
    elif num_interviews < 100:
        batch_size = 20  # Medium batch for medium workloads
    else:
        batch_size = 50  # Larger batch for large workloads
    
    # Core execution logic with adaptive batched processing
    async def process_interviews(runner, results_obj):
        cleanup_list = []
        
        # Process each interview as it completes
        async for result, interview, idx in runner.run():
            # Set the order attribute for correct ordering
            result.order = idx
            
            # Add task history and insert result
            results_obj.add_task_history_entry(interview)
            results_obj.insert_sorted(result)
            
            # Add interview to cleanup list
            cleanup_list.append(interview)
            
            # When batch is full, perform cleanup
            if len(cleanup_list) >= batch_size:
                # Clear references to help garbage collection
                for itv in cleanup_list:
                    if hasattr(itv, 'clear_references'):
                        itv.clear_references()
                
                # Clear cleanup list and force garbage collection
                cleanup_list.clear()
                gc.collect()
        
        # Clean up any remaining interviews
        for itv in cleanup_list:
            if hasattr(itv, 'clear_references'):
                itv.clear_references()
        cleanup_list.clear()
        
        # Force final garbage collection
        gc.collect()
        
        # Finalize results object
        results_obj.cache = results_obj.relevant_cache(self.run_config.environment.cache)
        if hasattr(self.run_config.environment, 'bucket_collection'):
            results_obj.bucket_collection = self.run_config.environment.bucket_collection
        
        return results_obj
    
    if run_job_async:
        # For async execution mode (simplified path without progress bar)
        return await process_interviews(interview_runner, results)
    else:
        # For synchronous execution mode (with progress bar)
        with ProgressBarManager(self, run_config, self.run_config.parameters) as stop_event:
            try:
                return await process_interviews(interview_runner, results)
            except KeyboardInterrupt:
                print("Keyboard interrupt received. Stopping gracefully...")
                results = Results(survey=self.survey, data=[], task_history=TaskHistory())
            except Exception as e:
                if self.run_config.parameters.stop_on_exception:
                    raise
                results = Results(survey=self.survey, data=[], task_history=TaskHistory())
        
        # Process any exceptions in the results
        if results:
            ResultsExceptionsHandler(results, self.run_config.parameters).handle_exceptions()
        
        return results

def apply_optimization():
    """Apply the optimization by patching the Jobs._execute_with_remote_cache method."""
    original_method = Jobs._execute_with_remote_cache
    Jobs._execute_with_remote_cache = optimized_execute_with_remote_cache
    return original_method

def restore_original(original_method):
    """Restore the original Jobs._execute_with_remote_cache method."""
    Jobs._execute_with_remote_cache = original_method

# Usage example
if __name__ == "__main__":
    from edsl import Jobs, Model, Agent, Survey
    from edsl.questions import QuestionDict
    
    # Create a test job
    q = QuestionDict(
        question_name="pros_cons",
        question_text="What are the pros and cons of driverless cars?",
        answer_keys=["pros", "cons"]
    )
    survey = Survey(questions=[q])
    model = Model('test')
    agents = [Agent(traits={"id": i}) for i in range(50)]
    
    job = Jobs(survey=survey)
    job.by(agents)
    job.by(model)
    
    # Apply the optimization
    original = apply_optimization()
    
    # Run the job with the optimization
    print("Running with optimization...")
    start_time = time.time()
    results = job.run(cache=False, disable_remote_inference=True, skip_retry=True)
    end_time = time.time()
    
    print(f"Completed in {end_time - start_time:.2f} seconds with {len(results)} results")
    
    # Restore original method
    restore_original(original)