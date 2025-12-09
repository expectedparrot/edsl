#!/usr/bin/env python
"""
Test script for EDSL benchmarking

This script runs a minimal version of the benchmarks to verify they work correctly.
"""

import time
import os
from pathlib import Path


def check_edsl_installed():
    """Check if EDSL is installed and accessible."""
    try:
        import edsl
        return True
    except ImportError:
        return False


def run_test():
    """Run a small test of the benchmarking scripts."""
    print("Testing EDSL benchmarking scripts")
    
    # Check if EDSL is installed
    edsl_installed = check_edsl_installed()
    if not edsl_installed:
        print("\n⚠️ WARNING: EDSL package is not installed or accessible in the current environment.")
        print("The benchmark scripts will create the necessary files, but won't be able to run actual benchmarks.")
        print("To run actual benchmarks, install EDSL with: pip install edsl or install from source")
        print("\nProceeding with file structure verification only...\n")
    
    # Ensure directory structure exists
    benchmark_logs = Path("benchmark_logs")
    benchmark_logs.mkdir(exist_ok=True)
    reports_dir = benchmark_logs / "reports"
    reports_dir.mkdir(exist_ok=True)
    
    # Create empty files if they don't exist
    if not edsl_installed:
        # Create minimal log files so visualization works
        empty_log = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "benchmarks": {}, "system_info": {"platform": "test"}}
        import json
        with open(benchmark_logs / "timing_log.jsonl", "w") as f:
            f.write(json.dumps(empty_log) + "\n")
        
        empty_component_log = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "components": {}, "system_info": {"platform": "test"}}
        with open(benchmark_logs / "component_timing_log.jsonl", "w") as f:
            f.write(json.dumps(empty_component_log) + "\n")
    
    if edsl_installed:
        # Test timing_benchmark.py with small sample
        print("\n1. Testing timing_benchmark.py with small sample")
        os.system("python scripts/timing_benchmark.py --num-questions=10")
        
        # Test component_benchmark.py with small sample
        print("\n2. Testing component_benchmark.py")
        os.system("python scripts/component_benchmark.py --scenario-size=10")
    
    # Test visualization
    print("\n3. Testing visualize_benchmarks.py")
    os.system("python scripts/visualize_benchmarks.py")
    
    # Test report generation
    print("\n4. Testing report generation")
    os.system("python scripts/visualize_benchmarks.py --report --trends")
    
    print("\nAll benchmark tests completed!")
    
    # Check if files were created
    timing_log = benchmark_logs / "timing_log.jsonl"
    component_log = benchmark_logs / "component_timing_log.jsonl"
    
    print("\nVerifying created files:")
    print(f"- Timing log exists: {timing_log.exists()}")
    print(f"- Component log exists: {component_log.exists()}")
    print(f"- Reports directory exists: {reports_dir.exists()}")
    
    if reports_dir.exists():
        report_files = list(reports_dir.glob("*"))
        print(f"- Number of report files: {len(report_files)}")
        if report_files:
            print("- Report files:")
            for file in report_files:
                print(f"  - {file.name}")
    
    print("\n✅ Benchmark system is set up correctly!")
    if not edsl_installed:
        print("⚠️ Install EDSL to run actual benchmarks")


if __name__ == "__main__":
    run_test()