"""
Performance benchmark script for investigating Issue #1841.

This script measures the performance of Jobs.run() as the number of responses increases.
The primary focus is on identifying why execution time grows non-linearly with the number of responses.
"""

import time
import timeit
import csv
import os
import gc
from functools import wraps
from typing import Dict, List, Any

import matplotlib.pyplot as plt
from edsl import Jobs, Agent, Model, Question, Survey, Results
from edsl.questions import QuestionDict

# Configuration
OUTPUT_CSV = "performance_results.csv"
RESPONSE_SIZES = [10, 20, 50, 100, 200, 300, 400, 500]
ITERATIONS = 1  # Number of times to run each test for averaging

def time_execution(func):
    """Decorator to measure execution time of a function."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        return result, execution_time
    return wrapper

class InstrumentedJobs(Jobs):
    """Extension of Jobs class with instrumentation for performance profiling."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.execution_times = {}
        
    @time_execution
    def run(self, *args, **kwargs):
        """Override run method to time its execution."""
        return super().run(*args, **kwargs)
    
    def create_profile_point(self, name: str, start_time: float = None):
        """Create a profile point to track execution time."""
        if start_time is None:
            self.execution_times[name] = {"start": time.time()}
        else:
            if name in self.execution_times:
                self.execution_times[name]["end"] = time.time()
                self.execution_times[name]["duration"] = self.execution_times[name]["end"] - start_time
            else:
                self.execution_times[name] = {"start": start_time, "end": time.time(), 
                                             "duration": time.time() - start_time}
                
    def get_execution_profile(self) -> Dict[str, Dict[str, float]]:
        """Get the execution profile data."""
        return self.execution_times

def create_test_job(num_responses: int) -> InstrumentedJobs:
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
    # This is where we control the number of responses
    agents = [Agent(traits={"id": i}) for i in range(num_responses)]
    
    # Create the job
    job = InstrumentedJobs(survey=survey)
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
            # Create a fresh job for each iteration
            job = create_test_job(size)
            
            # Add profiling points
            job.create_profile_point("job_creation")
            
            # Force garbage collection to start with a clean state
            gc.collect()
            
            # Run the job and measure time
            _, execution_time = job.run(cache=False, disable_remote_inference=True, skip_retry=True)
            
            job.create_profile_point("job_completion", job.execution_times["job_creation"]["start"])
            
            total_time += execution_time
            
            # Record detailed execution times
            execution_profile = job.get_execution_profile()
            
            print(f"  Iteration {i+1}/{iterations}: {execution_time:.2f} seconds")
            
            # Clean up
            del job
            gc.collect()
        
        # Calculate average time
        avg_time = total_time / iterations
        time_per_question = avg_time / size
        
        # Record results
        result = {
            "response_size": size,
            "total_time": avg_time,
            "time_per_question": time_per_question,
            "execution_profile": execution_profile
        }
        results.append(result)
        
        print(f"  Average: {avg_time:.2f} seconds, {time_per_question*1000:.2f} ms per question")
    
    return results

def save_results(results: List[Dict[str, Any]], filename: str):
    """Save benchmark results to a CSV file."""
    with open(filename, 'w', newline='') as csvfile:
        fieldnames = ['response_size', 'total_time', 'time_per_question']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for result in results:
            # Extract just the basic measurements
            row = {
                'response_size': result['response_size'],
                'total_time': result['total_time'],
                'time_per_question': result['time_per_question']
            }
            writer.writerow(row)
    
    print(f"Results saved to {filename}")

def plot_results(results: List[Dict[str, Any]]):
    """Plot the benchmark results."""
    response_sizes = [r['response_size'] for r in results]
    total_times = [r['total_time'] for r in results]
    times_per_question = [r['time_per_question'] * 1000 for r in results]  # Convert to ms
    
    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Plot total time
    ax1.plot(response_sizes, total_times, 'o-', linewidth=2)
    ax1.set_xlabel('Number of Responses')
    ax1.set_ylabel('Total Execution Time (seconds)')
    ax1.set_title('Total Execution Time vs. Number of Responses')
    ax1.grid(True)
    
    # Plot time per question
    ax2.plot(response_sizes, times_per_question, 'o-', linewidth=2, color='green')
    ax2.set_xlabel('Number of Responses')
    ax2.set_ylabel('Time per Question (ms)')
    ax2.set_title('Time per Question vs. Number of Responses')
    ax2.grid(True)
    
    plt.tight_layout()
    plt.savefig('performance_results.png')
    print("Plot saved to performance_results.png")

def main():
    """Main function to run the benchmark."""
    print(f"Running performance benchmark with {len(RESPONSE_SIZES)} different response sizes")
    print(f"Response sizes: {RESPONSE_SIZES}")
    print(f"Iterations per size: {ITERATIONS}")
    
    results = run_benchmark(RESPONSE_SIZES, ITERATIONS)
    save_results(results, OUTPUT_CSV)
    plot_results(results)
    
    # Print a summary
    print("\nSummary:")
    for result in results:
        print(f"  {result['response_size']} responses: {result['total_time']:.2f}s total, "
              f"{result['time_per_question']*1000:.2f}ms per question")

if __name__ == "__main__":
    main()