#!/usr/bin/env python
"""
Memory Profiling Tool for EDSL

This module provides memory profiling utilities for EDSL components,
particularly focused on memory-intensive operations like ScenarioList filtering.
"""

import gc
import os
import time
import json
import psutil
import argparse
import tracemalloc
import functools
import importlib
import webbrowser
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

# Type variable for generic function
F = TypeVar('F', bound=Callable[..., Any])

def profile_memory(func: F) -> F:
    """
    Decorator to profile memory usage of a function.
    
    Args:
        func: The function to profile
        
    Returns:
        Wrapped function that profiles memory usage
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
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
        
        # Save report to file
        report_dir = Path("./benchmark_logs/memory_reports")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        # Create filename with timestamp and function name
        timestamp_file = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = report_dir / f"{func.__name__}_{timestamp_file}.json"
        
        with open(report_path, 'w') as f:
            json.dump(stats, f, indent=2)
            
        print(f"Memory profile report saved to: {report_path}")
        
        # If detailed report is requested, show full source for top offenders
        if getattr(func, 'detailed_report', False):
            print("\n==== DETAILED LINE-BY-LINE ANALYSIS ====")
            print(f"Debug: Detailed report requested: {getattr(func, 'detailed_report', False)}")
            for i, stat in enumerate(top_stats[:5]):  # Show top 5 only
                print(f"\n{i+1}. {stat.traceback.format()[0]} - {stat.size_diff / 1024:.2f} KB")
                if stat.traceback and len(stat.traceback) > 0:
                    frame = stat.traceback[0]
                    try:
                        import linecache
                        # Show 5 lines before and after the line in question
                        line_no = frame.lineno
                        start_line = max(1, line_no - 5)
                        end_line = line_no + 5
                        filename = frame.filename
                        print(f"From {filename}:")
                        for l in range(start_line, end_line + 1):
                            line = linecache.getline(filename, l).rstrip()
                            prefix = ">>> " if l == line_no else "    "
                            print(f"{prefix}{l}: {line}")
                    except Exception as e:
                        print(f"Could not get source: {e}")
            print("\n==== END DETAILED ANALYSIS ====")
                
        # Stop memory tracking
        tracemalloc.stop()
        
        return result
    
    return wrapper


def test_scenariolist_memory(size=10000, filter_expression="id % 2 == 0", profile_filter=True):
    """
    Test memory usage when creating and filtering a large ScenarioList.
    
    Args:
        size: Number of scenarios to create (default: 10000)
        filter_expression: Expression to filter the scenarios (default: "id % 2 == 0")
        profile_filter: Whether to apply the memory profiling decorator to the filter method
        
    Returns:
        Tuple of (original ScenarioList, filtered ScenarioList)
    """
    import gc
    import os
    import time
    import psutil
    import numpy as np
    from datetime import datetime
    from edsl.scenarios import Scenario, ScenarioList
    
    # Apply memory profiling to ScenarioList.filter if requested
    if profile_filter:
        # Get the original filter method
        original_filter = ScenarioList.filter
        
        # Create a decorated function with detailed reporting
        decorated_filter = profile_memory(original_filter)
        decorated_filter.detailed_report = True
        
        # Apply the decorator
        ScenarioList.filter = decorated_filter
    
    process = psutil.Process(os.getpid())
    
    # Force garbage collection before starting
    gc.collect()
    gc.collect()
    
    # Record start time and memory
    start_time = time.time()
    start_memory = process.memory_info().rss / (1024 * 1024)  # MB
    
    print(f"\n==== MEMORY TEST: Creating and filtering a ScenarioList with {size} scenarios ====")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Starting memory usage: {start_memory:.2f} MB")
    
    # Create large text data (100 KB per scenario)
    text_size = 100 * 1024  # 100 KB
    large_text = "x" * text_size
    
    # Create scenarios with increasing memory requirements
    print(f"\nCreating {size} scenarios with 100 KB of text data each...")
    scenarios = []
    for i in range(size):
        scenarios.append({
            "id": i,
            "text": large_text,
            "category": "A" if i % 2 == 0 else "B",
            "value": i * 10
        })
    
    # Record memory after creating scenarios
    after_scenarios_memory = process.memory_info().rss / (1024 * 1024)
    print(f"Memory after creating raw dictionaries: {after_scenarios_memory:.2f} MB")
    print(f"Increase: {after_scenarios_memory - start_memory:.2f} MB")
    
    # Create ScenarioList
    print(f"\nCreating ScenarioList...")
    scenario_list = ScenarioList(scenarios)
    
    # Record memory after creating ScenarioList
    after_sl_memory = process.memory_info().rss / (1024 * 1024)
    print(f"Memory after creating ScenarioList: {after_sl_memory:.2f} MB")
    print(f"Increase: {after_sl_memory - after_scenarios_memory:.2f} MB")
    
    # The filter operation is now decorated with @profile_memory if profile_filter=True
    print(f"\nFiltering ScenarioList with expression: {filter_expression}")
    filtered_list = scenario_list.filter(filter_expression)
    
    # Record memory after filtering
    after_filter_memory = process.memory_info().rss / (1024 * 1024)
    
    # Calculate data size
    total_data_size_mb = (text_size * size) / (1024 * 1024)
    filtered_size = len(filtered_list)
    
    # Print summary
    print(f"\n==== TEST SUMMARY ====")
    print(f"Total scenarios: {size}")
    print(f"Filtered scenarios: {filtered_size}")
    print(f"Total test runtime: {time.time() - start_time:.2f} seconds")
    print(f"Total raw data size: {total_data_size_mb:.2f} MB")
    print(f"Final memory usage: {after_filter_memory:.2f} MB")
    print(f"Memory usage ratio: {after_filter_memory / total_data_size_mb:.2f}x the raw data size")
    
    if after_filter_memory < total_data_size_mb:
        efficiency = (1 - after_filter_memory / total_data_size_mb) * 100
        print(f"Memory efficiency: {efficiency:.2f}% less than storing everything in memory")
    else:
        print(f"Memory overhead: {(after_filter_memory / total_data_size_mb - 1) * 100:.2f}% more than raw data")
    
    # Restore the original filter method if we replaced it
    if profile_filter:
        ScenarioList.filter = original_filter
    
    # Force garbage collection at the end for clean state
    gc.collect()
    
    return scenario_list, filtered_list


def run_memory_profiling(
    test_name: str = "filter", size: int = 1000, 
    expression: str = "id % 2 == 0", generate_report: bool = True,
    open_report: bool = True, detailed: bool = False
) -> Optional[Tuple[Path, Path]]:
    """
    Run memory profiling tests and generate reports.
    
    Args:
        test_name: The test to run (currently only "filter" is supported)
        size: Number of scenarios to create for the test
        expression: Expression to use for filtering tests
        generate_report: Whether to generate visualization reports
        open_report: Whether to open the HTML report in a browser
        detailed: Whether to show detailed line-by-line analysis
        
    Returns:
        Optional tuple of (image_path, html_path) if generate_report=True
    """
    if test_name == "filter":
        # If detailed analysis is requested, perform manual trace of the top memory files
        if detailed:
            print("\n==== DETAILED FILE ANALYSIS ====")
            print("Analyzing top memory usage files...")
            
            # Analyze the scenario_list.py file where most memory is allocated
            scenario_list_path = "/Users/johnhorton/tools/ep/edsl/edsl/scenarios/scenario_list.py"
            sqlite_list_path = "/Users/johnhorton/tools/ep/edsl/edsl/db_list/sqlite_list.py"
            
            # Show the contents of the key functions
            print("\n1. ScenarioList.filter - contains the main memory allocation point at line 109")
            with open(scenario_list_path, 'r') as f:
                for i, line in enumerate(f, 1):
                    if 104 <= i <= 114:  # Show lines around the key allocation point
                        prefix = ">>> " if i == 109 else "    "
                        print(f"{prefix}{i}: {line.rstrip()}")
            
            print("\n2. SQLiteList.__len__ - significant memory allocation at line 70")
            with open(sqlite_list_path, 'r') as f:
                for i, line in enumerate(f, 1):
                    if 65 <= i <= 75:
                        prefix = ">>> " if i == 70 else "    "
                        print(f"{prefix}{i}: {line.rstrip()}")
                        
            print("\n3. SQLiteList.__insert - significant memory allocation at line 148")  
            with open(sqlite_list_path, 'r') as f:
                for i, line in enumerate(f, 1):
                    if 143 <= i <= 153:
                        prefix = ">>> " if i == 148 else "    "
                        print(f"{prefix}{i}: {line.rstrip()}")
                        
            print("\n4. ScenarioList.filter - allocation at lines 918-926 (scenario copying)")
            with open(scenario_list_path, 'r') as f:
                for i, line in enumerate(f, 1):
                    if 913 <= i <= 931:
                        prefix = ">>> " if i in (918, 926) else "    "
                        print(f"{prefix}{i}: {line.rstrip()}")
                        
            print("\n==== END DETAILED ANALYSIS ====")
        
        # Run the actual memory test
        test_scenariolist_memory(size, expression)
    else:
        print(f"Unknown test name: {test_name}")
        return None
    
    if generate_report:
        # Import the visualization module
        from scripts.visualize_memory import load_memory_reports, create_memory_report
        
        # Load memory reports
        reports = load_memory_reports()
        
        # Create memory report
        image_path, html_path = create_memory_report(reports)
        
        # Open the HTML report if requested
        if open_report and html_path:
            webbrowser.open(f"file://{html_path.resolve()}")
            
        return image_path, html_path
    
    return None


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="EDSL Memory Profiling Tool")
    parser.add_argument("--test", "-t", default="filter",
                      help="Test to run (currently only 'filter' is supported)")
    parser.add_argument("--size", "-s", type=int, default=1000,
                      help="Number of scenarios to create for the test")
    parser.add_argument("--expression", "-e", default="id % 2 == 0",
                      help="Expression to use for filtering tests")
    parser.add_argument("--no-report", "-n", action="store_true",
                      help="Don't generate visualization reports")
    parser.add_argument("--no-open", "-o", action="store_true",
                      help="Don't automatically open the HTML report")
    parser.add_argument("--detailed", "-d", action="store_true",
                      help="Show detailed line-by-line analysis")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_memory_profiling(
        test_name=args.test,
        size=args.size,
        expression=args.expression,
        generate_report=not args.no_report,
        open_report=not args.no_open,
        detailed=args.detailed
    )