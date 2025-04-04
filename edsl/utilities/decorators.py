import functools
import asyncio
import nest_asyncio
import os
import gc
import time
import json
import psutil
import tracemalloc
from datetime import datetime
from pathlib import Path
from edsl import __version__ as edsl_version

nest_asyncio.apply()


def add_edsl_version(func):
    """
    Decorator for EDSL objects' `to_dict` method.
    - Adds the EDSL version and class name to the dictionary.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        d = func(*args, **kwargs)
        d["edsl_version"] = edsl_version
        d["edsl_class_name"] = func.__qualname__.split(".")[0]
        return d

    return wrapper


def remove_edsl_version(func):
    """
    Decorator for the EDSL objects' `from_dict` method.
    - Removes the EDSL version and class name from the dictionary.
    - Ensures backwards compatibility with older versions of EDSL.
    """

    @functools.wraps(func)
    def wrapper(cls, data, *args, **kwargs):
        data_copy = dict(data)
        edsl_version = data_copy.pop("edsl_version", None)
        edsl_classname = data_copy.pop("edsl_class_name", None)

        # Version- and class-specific logic here
        if edsl_classname == "Survey":
            if edsl_version is None or edsl_version <= "0.1.20":
                data_copy["question_groups"] = {}

        return func(cls, data_copy, *args, **kwargs)

    return wrapper


def jupyter_nb_handler(func):
    """Decorator to run an async function in the event loop if it's running, or synchronously otherwise."""

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # This is an async wrapper to await the coroutine
        return await func(*args, **kwargs)

    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If the loop is running, schedule the coroutine and wait for the result
            future = asyncio.ensure_future(async_wrapper(*args, **kwargs))
            return loop.run_until_complete(future)
        else:
            # If the loop is not running, run the coroutine to completion
            return asyncio.run(async_wrapper(*args, **kwargs))

    return wrapper


def sync_wrapper(async_func):
    """Decorator to create a synchronous wrapper for an asynchronous function."""

    @functools.wraps(async_func)
    def wrapper(*args, **kwargs):
        return asyncio.run(async_func(*args, **kwargs))

    return wrapper


def memory_profile(func):
    """
    Decorator to profile memory usage of a function.
    
    Only activates if the EDSL_MEMORY_PROFILE environment variable is set to 'true'
    or if the function name is included in the EDSL_MEMORY_PROFILE_FUNCTIONS
    environment variable (comma-separated list of function names).
    
    Example:
        EDSL_MEMORY_PROFILE=true python your_script.py
        EDSL_MEMORY_PROFILE_FUNCTIONS=filter,duplicate python your_script.py
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Check if memory profiling is enabled
        profile_env = os.environ.get('EDSL_MEMORY_PROFILE', '').lower() == 'true'
        profile_functions = os.environ.get('EDSL_MEMORY_PROFILE_FUNCTIONS', '')
        profile_func_list = [f.strip() for f in profile_functions.split(',') if f.strip()]
        
        # Determine if this function should be profiled
        should_profile = profile_env or func.__name__ in profile_func_list
        
        if not should_profile:
            # Normal execution if profiling is disabled
            return func(*args, **kwargs)
        
        # Begin memory profiling
        # Force garbage collection before measuring
        gc.collect()
        gc.collect()
        
        # Get process for memory measurements
        process = psutil.Process(os.getpid())
        
        # Start memory tracking
        tracemalloc.start()
        
        # Record starting memory
        memory_before = process.memory_info().rss / (1024 * 1024)  # MB
        snapshot1 = tracemalloc.take_snapshot()
        start_time = time.time()
        
        # Execute the function
        result = func(*args, **kwargs)
        
        # Record ending stats
        end_time = time.time()
        snapshot2 = tracemalloc.take_snapshot()
        memory_after = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Calculate differences
        execution_time = end_time - start_time
        memory_diff = memory_after - memory_before
        
        # Get top memory differences
        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        
        # Prepare stats for report and JSON
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        stats = {
            "timestamp": timestamp,
            "function": func.__qualname__,
            "execution_time_seconds": execution_time,
            "memory_before_mb": memory_before,
            "memory_after_mb": memory_after,
            "memory_diff_mb": memory_diff,
            "top_allocations": [
                {
                    "file": stat.traceback.format()[0],
                    "size_kb": stat.size_diff / 1024
                } for stat in top_stats[:10]
            ]
        }
        
        # Generate console report
        print("\n" + "="*60)
        print(f"MEMORY PROFILE REPORT - {func.__name__}")
        print("="*60)
        print(f"Timestamp: {timestamp}")
        print(f"Function: {func.__qualname__}")
        print("-"*60)
        print(f"Execution time: {execution_time:.4f} seconds")
        print(f"Memory before: {memory_before:.2f} MB")
        print(f"Memory after: {memory_after:.2f} MB")
        print(f"Memory difference: {memory_diff:.2f} MB")
        print("-"*60)
        print("Top 10 memory allocations by line:")
        for stat in top_stats[:10]:
            print(f"{stat.traceback.format()[0]} - {stat.size_diff / 1024:.2f} KB")
        print("="*60)
        
        # Save report to file if EDSL_MEMORY_PROFILE_SAVE is true
        if os.environ.get('EDSL_MEMORY_PROFILE_SAVE', '').lower() == 'true':
            report_dir = Path("./benchmark_logs/memory_reports")
            report_dir.mkdir(parents=True, exist_ok=True)
            
            # Create filename with timestamp and function name
            timestamp_file = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = report_dir / f"{func.__name__}_{timestamp_file}.json"
            
            with open(report_path, 'w') as f:
                json.dump(stats, f, indent=2)
                
            print(f"Memory profile report saved to: {report_path}")
        
        # Stop memory tracking
        tracemalloc.stop()
        
        return result
    
    return wrapper