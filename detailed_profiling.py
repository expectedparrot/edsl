"""
Detailed profiling script for investigating performance issues in Jobs.run() (Issue #1841).

This script adds detailed profiling to key methods in the Jobs and Interview classes
to identify exactly where time is being spent during execution. It focuses particularly
on measuring how performance scales with increasing numbers of responses.
"""

import time
import csv
import gc
import os
import tracemalloc
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
import matplotlib.pyplot as plt

from edsl import Jobs, Agent, Model, Survey, Results
from edsl.questions import QuestionDict
from edsl.jobs.async_interview_runner import AsyncInterviewRunner
from edsl.interviews.interview import Interview

# Configuration
OUTPUT_CSV = "detailed_profiling_results.csv"
RESPONSE_SIZES = [10, 20, 50, 100, 200, 400]
ITERATIONS = 1  # Number of times to run each test for averaging
MEASURE_MEMORY = True  # Whether to measure memory usage

@dataclass
class ProfilingPoint:
    """Class for tracking profiling data for a specific operation."""
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration: float = 0.0
    call_count: int = 0
    memory_before: int = 0
    memory_after: int = 0
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)
    
    def start(self):
        """Start timing this profiling point."""
        self.start_time = time.time()
        if MEASURE_MEMORY:
            tracemalloc.start()
            self.memory_before = tracemalloc.get_traced_memory()[0]
    
    def end(self):
        """End timing this profiling point."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.call_count += 1
        if MEASURE_MEMORY:
            self.memory_after = tracemalloc.get_traced_memory()[0]
            tracemalloc.stop()

@dataclass
class ProfilingResult:
    """Class for storing all profiling results for a single test run."""
    response_size: int
    total_time: float = 0.0
    time_per_response: float = 0.0
    points: Dict[str, ProfilingPoint] = field(default_factory=dict)
    total_memory: int = 0
    
    def add_point(self, name: str, parent: Optional[str] = None) -> ProfilingPoint:
        """Add a new profiling point."""
        point = ProfilingPoint(name=name, parent=parent)
        self.points[name] = point
        if parent and parent in self.points:
            self.points[parent].children.append(name)
        return point

class ProfilingTracker:
    """Class for tracking and managing profiling data across multiple runs."""
    
    def __init__(self):
        self.current_result = None
        self.all_results = []
        self.active_points = {}
    
    def start_run(self, response_size: int):
        """Start a new profiling run."""
        self.current_result = ProfilingResult(response_size=response_size)
        self.all_results.append(self.current_result)
        return self.current_result
    
    def start_point(self, name: str, parent: Optional[str] = None) -> ProfilingPoint:
        """Start timing a specific operation."""
        if self.current_result is None:
            raise ValueError("Must start a run before starting a profiling point")
        
        if name not in self.current_result.points:
            point = self.current_result.add_point(name, parent)
        else:
            point = self.current_result.points[name]
        
        point.start()
        self.active_points[name] = point
        return point
    
    def end_point(self, name: str):
        """End timing a specific operation."""
        if name not in self.active_points:
            return
        
        point = self.active_points[name]
        point.end()
        del self.active_points[name]
    
    def save_results(self, filename: str):
        """Save all profiling results to a CSV file."""
        with open(filename, 'w', newline='') as csvfile:
            fieldnames = ['response_size', 'operation', 'duration', 'call_count', 
                         'avg_duration', 'parent', 'memory_change']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.all_results:
                for name, point in result.points.items():
                    memory_change = point.memory_after - point.memory_before if MEASURE_MEMORY else 0
                    avg_duration = point.duration / point.call_count if point.call_count > 0 else 0
                    
                    writer.writerow({
                        'response_size': result.response_size,
                        'operation': name,
                        'duration': point.duration,
                        'call_count': point.call_count,
                        'avg_duration': avg_duration,
                        'parent': point.parent or '',
                        'memory_change': memory_change
                    })
        
        print(f"Detailed profiling results saved to {filename}")
    
    def plot_results(self):
        """Plot the profiling results."""
        # Extract key operations to track across different response sizes
        key_operations = set()
        for result in self.all_results:
            for name in result.points.keys():
                if name != "total":
                    key_operations.add(name)
        
        key_operations = sorted(list(key_operations))
        response_sizes = [r.response_size for r in self.all_results]
        
        # Create a plot for each key operation
        fig, axes = plt.subplots(2, 1, figsize=(12, 10))
        
        # Plot 1: Total time by response size
        total_times = [r.total_time for r in self.all_results]
        axes[0].plot(response_sizes, total_times, 'o-', linewidth=2)
        axes[0].set_xlabel('Number of Responses')
        axes[0].set_ylabel('Total Execution Time (seconds)')
        axes[0].set_title('Total Execution Time vs. Number of Responses')
        axes[0].grid(True)
        
        # Plot 2: Breakdown of time by operation
        operation_times = {}
        for op in key_operations:
            operation_times[op] = []
            
        for result in self.all_results:
            for op in key_operations:
                if op in result.points:
                    operation_times[op].append(result.points[op].duration)
                else:
                    operation_times[op].append(0)
        
        # Filter to only operations that take significant time
        significant_ops = [op for op in key_operations 
                         if any(t > 0.1 for t in operation_times[op])]
        
        # Plot each significant operation
        for op in significant_ops:
            axes[1].plot(response_sizes, operation_times[op], 'o-', linewidth=2, label=op)
        
        axes[1].set_xlabel('Number of Responses')
        axes[1].set_ylabel('Duration (seconds)')
        axes[1].set_title('Time Breakdown by Operation')
        axes[1].legend()
        axes[1].grid(True)
        
        plt.tight_layout()
        plt.savefig('performance_breakdown.png')
        print("Performance breakdown plot saved to performance_breakdown.png")

# Create global profiling tracker
profiler = ProfilingTracker()

# Patched versions of key methods to add profiling
original_jobs_run = Jobs.run
original_interview_conduct = Interview.async_conduct_interview
original_async_interview_runner_run = AsyncInterviewRunner.run

async def patched_interview_conduct(self, run_config=None):
    """Patched version of Interview.async_conduct_interview with profiling."""
    point_name = f"interview_conduct_{id(self)}"
    profiler.start_point(point_name, "jobs_run")
    result = await original_interview_conduct(self, run_config)
    profiler.end_point(point_name)
    return result

def patched_jobs_run(self, *args, **kwargs):
    """Patched version of Jobs.run with profiling."""
    profiler.start_point("jobs_run", "total")
    result = original_jobs_run(self, *args, **kwargs)
    profiler.end_point("jobs_run")
    return result

async def patched_async_interview_runner_run(self):
    """Patched version of AsyncInterviewRunner.run with profiling."""
    point_name = "interview_runner_run"
    profiler.start_point(point_name, "jobs_run")
    
    # Create a generator that profiles each interview execution
    async for result, interview, idx in original_async_interview_runner_run(self):
        item_point = f"interview_item_{idx}"
        profiler.start_point(item_point, point_name)
        profiler.end_point(item_point)
        yield result, interview, idx
    
    profiler.end_point(point_name)

def create_test_job(num_responses: int) -> Jobs:
    """Create a test job with a specified number of responses."""
    # Create a question
    q = QuestionDict(
        question_name="pros_cons",
        question_text="What are the pros and cons of driverless cars?",
        answer_keys=["pros", "cons"]
    )
    
    # Create a survey
    survey = Survey(questions=[q])
    
    # Create a test model
    model = Model('test')
    
    # Create agents
    agents = [Agent(traits={"id": i}) for i in range(num_responses)]
    
    # Create the job
    job = Jobs(survey=survey)
    job.by(agents)
    job.by(model)
    
    return job

def run_benchmark(response_sizes: List[int], iterations: int = 1) -> List[Dict[str, Any]]:
    """Run the benchmark with different response sizes."""
    results = []
    
    for size in response_sizes:
        print(f"Running test with {size} responses...")
        total_time = 0
        
        for i in range(iterations):
            # Start profiling for this run
            current_result = profiler.start_run(size)
            profiler.start_point("total")
            
            # Create a fresh job for each iteration
            job = create_test_job(size)
            
            # Force garbage collection
            gc.collect()
            
            # Run the job
            start_time = time.time()
            response = job.run(cache=False, disable_remote_inference=True, skip_retry=True)
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Record total time
            total_time += execution_time
            current_result.total_time = execution_time
            current_result.time_per_response = execution_time / size
            
            profiler.end_point("total")
            
            print(f"  Iteration {i+1}/{iterations}: {execution_time:.2f} seconds")
            
            # Clean up
            del job
            del response
            gc.collect()
        
        # Calculate average time
        avg_time = total_time / iterations
        time_per_question = avg_time / size
        
        # Record results
        result = {
            "response_size": size,
            "total_time": avg_time,
            "time_per_question": time_per_question
        }
        results.append(result)
        
        print(f"  Average: {avg_time:.2f} seconds, {time_per_question*1000:.2f} ms per question")
    
    return results

def apply_patches():
    """Apply the performance profiling patches to key methods."""
    print("Applying performance profiling patches...")
    Jobs.run = patched_jobs_run
    Interview.async_conduct_interview = patched_interview_conduct
    AsyncInterviewRunner.run = patched_async_interview_runner_run

def restore_originals():
    """Restore the original methods."""
    print("Restoring original methods...")
    Jobs.run = original_jobs_run
    Interview.async_conduct_interview = original_interview_conduct
    AsyncInterviewRunner.run = original_async_interview_runner_run

def save_summary(results: List[Dict[str, Any]], filename: str):
    """Save summary benchmark results to a CSV file."""
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['response_size', 'total_time', 'time_per_question']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            writer.writerow(result)
    
    print(f"Summary results saved to {filename}")

def main():
    """Main function to run the benchmark."""
    print(f"Running detailed profiling with {len(RESPONSE_SIZES)} different response sizes")
    print(f"Response sizes: {RESPONSE_SIZES}")
    print(f"Iterations per size: {ITERATIONS}")
    
    try:
        apply_patches()
        
        # Run the benchmarks
        results = run_benchmark(RESPONSE_SIZES, ITERATIONS)
        
        # Save and plot results
        summary_file = "summary_" + OUTPUT_CSV
        save_summary(results, summary_file)
        profiler.save_results(OUTPUT_CSV)
        profiler.plot_results()
        
        # Print a summary
        print("\nSummary:")
        for result in results:
            print(f"  {result['response_size']} responses: {result['total_time']:.2f}s total, "
                 f"{result['time_per_question']*1000:.2f}ms per question")
    
    finally:
        # Make sure we restore the original methods even if an error occurs
        restore_originals()

if __name__ == "__main__":
    main()