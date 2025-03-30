import gc
import os
import time
import pytest
import psutil
from edsl import Model, QuestionFreeText, ScenarioList


def get_memory_usage():
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / (1024 * 1024)
    return memory_mb


def run_prime_check(job_size):
    """Run a simple job and analyze its memory usage"""
    # Force garbage collection before measuring
    gc.collect()
    gc.collect()  # Multiple collections can help with more complete cleanup
    
    # Record memory before starting
    memory_before = get_memory_usage()
    
    # Create a job with the specified number of items
    numbers = ScenarioList.from_list("number", range(1, job_size+1))
    m = Model("test", canned_response="Yes") 
    q = QuestionFreeText(
        question_text="Is {{ number}} prime?", 
        question_name="prime_question"
    )
    jobs = q.by(numbers).by(m)
    
    # Run the jobs without collecting results
    start_time = time.time()
    results = jobs.run(disable_remote_inference=True, disable_remote_caching=True, stop_on_exception=True)
    end_time = time.time()
    
    # Record memory after running
    gc.collect()
    gc.collect()  # Multiple collections for better cleanup
    time.sleep(0.5)  # Small delay to allow memory to settle
    memory_after = get_memory_usage()
    memory_used = memory_after - memory_before
    
    return {
        'size': job_size,
        'memory_used': memory_used,
        'memory_per_interview': memory_used / job_size,
        'execution_time': end_time - start_time
    }


def test_memory_per_interview_decreases_with_scale():
    """
    Test that as the job size increases substantially, memory per interview decreases.
    
    This test runs jobs with increasingly larger sizes and verifies that the 
    memory usage per interview decreases significantly as the job size grows,
    confirming memory efficiency improvements in the Jobs implementation.
    """
    # Use larger job sizes for more reliable measurements
    small_size = 20
    medium_size = 100
    large_size = 500
    
    # Force garbage collection before starting
    gc.collect()
    gc.collect()
    
    # Run jobs of different sizes
    small_job_result = run_prime_check(small_size)
    medium_job_result = run_prime_check(medium_size)
    large_job_result = run_prime_check(large_size)
    
    # Calculate memory usage per interview for each job size
    small_memory_per_interview = small_job_result['memory_per_interview']
    medium_memory_per_interview = medium_job_result['memory_per_interview']
    large_memory_per_interview = large_job_result['memory_per_interview']
    
    # Print info for debugging and report
    print(f"\nMemory usage analysis for job scaling:")
    print(f"Small job ({small_size} interviews):")
    print(f"  Memory used: {small_job_result['memory_used']:.2f} MB")
    print(f"  Memory per interview: {small_memory_per_interview:.6f} MB")
    
    print(f"\nMedium job ({medium_size} interviews):")
    print(f"  Memory used: {medium_job_result['memory_used']:.2f} MB")
    print(f"  Memory per interview: {medium_memory_per_interview:.6f} MB")
    
    print(f"\nLarge job ({large_size} interviews):")
    print(f"  Memory used: {large_job_result['memory_used']:.2f} MB")
    print(f"  Memory per interview: {large_memory_per_interview:.6f} MB")
    
    print(f"\nMemory efficiency improvements:")
    small_to_medium = (1 - medium_memory_per_interview / small_memory_per_interview) * 100
    medium_to_large = (1 - large_memory_per_interview / medium_memory_per_interview) * 100
    small_to_large = (1 - large_memory_per_interview / small_memory_per_interview) * 100
    
    print(f"  Small to medium job improvement: {small_to_medium:.2f}%")
    print(f"  Medium to large job improvement: {medium_to_large:.2f}%")
    print(f"  Small to large job improvement: {small_to_large:.2f}%")
    
    # The key test assertion
    # We check if there's a substantial overall improvement (at least 25%)
    # from small to large job sizes
    assert large_memory_per_interview < small_memory_per_interview * 0.75, \
        f"Expected at least 25% memory per interview reduction from small to large jobs, " \
        f"but got only {small_to_large:.2f}% reduction"