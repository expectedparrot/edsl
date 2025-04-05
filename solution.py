"""
Solution for Issue #1841: Non-linear scaling of job running time.

Based on detailed profiling, the main cause of the non-linear scaling is:
1. Inefficient memory management during result collection
2. Lack of batched processing for interview results
3. Growing memory usage leading to more frequent garbage collection
4. Reference cycles between Interview objects and their tasks

This solution modifies the Jobs._execute_with_remote_cache method to:
1. Process results in batches for better memory efficiency
2. Immediately clear references to completed interviews
3. Explicitly force garbage collection at strategic points
4. Optimize result insertion to avoid building large data structures in memory
"""

import asyncio
import gc
import weakref
import time
import matplotlib.pyplot as plt
from typing import List, Dict, Any, Generator

from edsl import Jobs, Model, Agent, Survey, Results
from edsl.questions import QuestionDict
from edsl.results import Result
from edsl.tasks import TaskHistory
from edsl.jobs.async_interview_runner import AsyncInterviewRunner
from edsl.jobs.data_structures import RunConfig
from edsl.caching import Cache
from edsl.jobs.jobs_runner_status import JobsRunnerStatus
from edsl.jobs.progress_bar_manager import ProgressBarManager
from edsl.jobs.results_exceptions_handler import ResultsExceptionsHandler

# The core optimization: process interviews in batches and clean up references
async def optimized_execute_with_remote_cache(self, run_job_async: bool) -> Results:
    """Optimized implementation of _execute_with_remote_cache for better scaling.
    
    Key improvements:
    1. Processes results in batches to limit memory growth
    2. Immediately clears references to completed interviews
    3. Performs strategic garbage collection
    4. Uses insert_sorted for more efficient result collection
    """
    assert isinstance(self.run_config.environment.cache, Cache)
    
    # Create the RunConfig for the job
    run_config = RunConfig(parameters=self.run_config.parameters, environment=self.run_config.environment)
    
    # Setup JobsRunnerStatus if needed
    if self.run_config.environment.jobs_runner_status is None:
        self.run_config.environment.jobs_runner_status = JobsRunnerStatus(self, n=self.run_config.parameters.n)
    
    # Create interview runner
    interview_runner = AsyncInterviewRunner(self, run_config)
    
    # Create an initial Results object with appropriate settings
    results = Results(
        survey=self.survey,
        data=[],
        task_history=TaskHistory(include_traceback=not self.run_config.parameters.progress_bar)
    )
    
    # Core execution logic with batched processing
    async def process_interviews(runner, results_obj):
        batch_size = 20  # Process interviews in batches of 20
        batch = []
        
        # Reuse the list for interview cleanup to reduce allocations
        cleanup_list = []
        
        async for result, interview, idx in runner.run():
            # Set the order attribute for correct ordering
            result.order = idx
            
            # Add task history and set result
            results_obj.add_task_history_entry(interview)
            results_obj.insert_sorted(result)
            
            # Add interview to cleanup list
            cleanup_list.append(interview)
            
            # When enough interviews have been processed, perform cleanup
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
        
        # Ensure no strong references to batch items
        batch.clear()
        
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
    # Store the original method for later restoration
    original_method = Jobs._execute_with_remote_cache
    
    # Apply the optimized method
    setattr(Jobs, '_execute_with_remote_cache', optimized_execute_with_remote_cache)
    
    return original_method

def restore_original(original_method):
    """Restore the original Jobs._execute_with_remote_cache method."""
    setattr(Jobs, '_execute_with_remote_cache', original_method)

def run_benchmark(size, optimized=False):
    """Run a benchmark with the specified number of responses."""
    # Create test job
    q = QuestionDict(
        question_name="pros_cons",
        question_text="What are the pros and cons of driverless cars?",
        answer_keys=["pros", "cons"]
    )
    survey = Survey(questions=[q])
    model = Model('test')
    agents = [Agent(traits={"id": i}) for i in range(size)]
    
    job = Jobs(survey=survey)
    job.by(agents)
    job.by(model)
    
    # Apply optimization if requested
    original = None
    if optimized:
        original = apply_optimization()
    
    # Run and time the job
    start_time = time.time()
    try:
        job_results = job.run(cache=False, disable_remote_inference=True, skip_retry=True)
        execution_time = time.time() - start_time
    except Exception as e:
        print(f"Error running benchmark: {e}")
        execution_time = float('nan')  # Use NaN to indicate error
    
    # Restore original if needed
    if optimized and original:
        restore_original(original)
    
    # Clean up
    if 'job_results' in locals():
        del job_results
    del job
    gc.collect()
    
    return execution_time

def benchmark_comparison():
    """Run a benchmark comparing original and optimized implementations."""
    # Test parameters - include larger sizes to better observe scaling
    response_sizes = [10, 25, 50, 100]
    results = {"original": [], "optimized": []}
    
    # Run benchmarks
    for size in response_sizes:
        print(f"Testing with {size} responses...")
        
        # Original implementation
        print("  Running original implementation...")
        original_time = run_benchmark(size, optimized=False)
        results["original"].append(original_time)
        
        # Give system time to recover
        time.sleep(2)
        gc.collect()
        
        # Optimized implementation
        print("  Running optimized implementation...")
        optimized_time = run_benchmark(size, optimized=True)
        results["optimized"].append(optimized_time)
        
        print(f"  Original: {original_time:.2f}s, Optimized: {optimized_time:.2f}s, "
              f"Improvement: {(1 - optimized_time/original_time)*100:.1f}%")
        
        # Give system time to recover before next test
        time.sleep(2)
        gc.collect()
    
    # Plot results
    plt.figure(figsize=(12, 6))
    plt.plot(response_sizes, results["original"], 'o-', label="Original", linewidth=2)
    plt.plot(response_sizes, results["optimized"], 'o-', label="Optimized", linewidth=2)
    plt.xlabel("Number of Responses")
    plt.ylabel("Execution Time (seconds)")
    plt.title("Performance Comparison: Original vs. Optimized Implementation")
    plt.legend()
    plt.grid(True)
    plt.savefig("performance_comparison.png")
    print("Performance comparison plot saved to performance_comparison.png")
    
    # Calculate improvement
    improvements = [(1 - opt/orig)*100 for orig, opt in 
                   zip(results["original"], results["optimized"])]
    valid_improvements = [i for i in improvements if not float('nan') in (i,)]
    avg_improvement = sum(valid_improvements) / len(valid_improvements) if valid_improvements else float('nan')
    print(f"\nAverage performance improvement: {avg_improvement:.1f}%")
    
    # Print detailed results
    print("\nDetailed Results:")
    print(f"{'Responses':<10} {'Original (s)':<15} {'Optimized (s)':<15} {'Improvement':<15}")
    print("-" * 55)
    for i, size in enumerate(response_sizes):
        improvement = improvements[i]
        improvement_str = f"{improvement:.1f}%" if not float('nan') in (improvement,) else "N/A"
        print(f"{size:<10} {results['original'][i]:<15.2f} {results['optimized'][i]:<15.2f} {improvement_str:<15}")

if __name__ == "__main__":
    print("Running performance benchmark comparison...")
    benchmark_comparison()