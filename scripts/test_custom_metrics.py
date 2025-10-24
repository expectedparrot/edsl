#!/usr/bin/env python
"""
Test Custom Metrics Integration

This script demonstrates how to add custom performance metrics to the
performance tracking system. It shows that the system automatically picks up
any new metrics added to the benchmark JSONL files.
"""

import json
import time
from pathlib import Path
from datetime import datetime


# Constants
ROOT_DIR = Path(__file__).parent.parent
LOG_DIR = ROOT_DIR / "benchmark_logs"
TIMING_LOG_FILE = LOG_DIR / "timing_log.jsonl"
COMPONENT_LOG_FILE = LOG_DIR / "component_timing_log.jsonl"


def timed_operation(func):
    """Decorator to time a function."""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        return end - start, result
    return wrapper


@timed_operation
def custom_metric_example_1():
    """Example custom metric: simulate some computation."""
    total = 0
    for i in range(1000):
        total += i ** 2
    return total


@timed_operation
def custom_metric_example_2():
    """Example custom metric: simulate I/O operation."""
    time.sleep(0.01)  # Simulate I/O
    return "done"


@timed_operation
def custom_database_query():
    """Example custom metric: simulate database query."""
    # Simulate some database work
    data = [{"id": i, "value": i * 10} for i in range(100)]
    return len(data)


def add_custom_metrics_to_timing_log():
    """
    Demonstrate adding custom metrics to the timing benchmark log.

    The system will automatically:
    1. Pick up these metrics from the JSONL file
    2. Include them in performance.yml
    3. Visualize them in the appropriate group (based on prefix)
    """

    # Run custom benchmarks
    print("Running custom benchmarks...")

    custom_1_time, _ = custom_metric_example_1()
    custom_2_time, _ = custom_metric_example_2()
    db_time, _ = custom_database_query()

    print(f"  custom_computation: {custom_1_time:.4f}s")
    print(f"  custom_io_operation: {custom_2_time:.4f}s")
    print(f"  database_query_simulation: {db_time:.4f}s")

    # Create benchmark entry with custom metrics
    entry = {
        "timestamp": datetime.now().isoformat(),
        "benchmarks": {
            # These custom metrics will be automatically picked up!
            "custom_computation": custom_1_time,
            "custom_io_operation": custom_2_time,
            "database_query_simulation": db_time,

            # You can add any metrics here with any naming convention
            "my_special_benchmark": 0.123,
            "api_response_time_average": 0.456,
            "cache_hit_ratio_check": 0.001,
        },
        "system_info": {
            "platform": "test",
            "custom_test": "demo"
        },
        "edsl_version": "test"
    }

    # Append to timing log
    LOG_DIR.mkdir(exist_ok=True)
    with open(TIMING_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"\nCustom metrics written to {TIMING_LOG_FILE}")
    print("\nThese metrics will automatically:")
    print("  1. Be included in performance.yml when you run: python scripts/write_performance_yaml.py")
    print("  2. Be grouped by prefix (custom, database, my, api, cache)")
    print("  3. Be visualized in group plots: group_custom.png, group_database.png, etc.")
    print("  4. Appear in trend analysis if you run benchmarks multiple times")
    print("  5. Show up in the HTML report")


def demonstrate_component_metrics():
    """
    Demonstrate adding custom metrics to component benchmarks.
    """

    print("\n" + "="*70)
    print("You can also add metrics to component_timing_log.jsonl")
    print("="*70)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "components": {
            # Component-specific custom metrics
            "load_custom_plugin": 0.234,
            "initialize_custom_module": 0.567,
            "setup_custom_environment": 0.089,
        },
        "system_info": {
            "platform": "test"
        }
    }

    with open(COMPONENT_LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"Custom component metrics written to {COMPONENT_LOG_FILE}")


def show_metric_naming_conventions():
    """Show recommended naming conventions for metrics."""
    print("\n" + "="*70)
    print("METRIC NAMING CONVENTIONS")
    print("="*70)
    print("""
The system groups metrics by the prefix (first word before underscore).
Use this to organize your metrics:

Good naming patterns:
  - import_<module>       → Groups all imports together
  - create_<object>       → Groups all creation operations
  - render_<component>    → Groups all rendering operations
  - query_<database>      → Groups all query operations
  - process_<data>        → Groups all processing operations
  - benchmark_<feature>   → Groups all feature benchmarks

Examples:
  - import_custom_plugin
  - create_user_object
  - render_dashboard_widget
  - query_user_database
  - process_large_dataset
  - benchmark_new_feature

The visualization system will automatically:
  1. Group these into plots (group_import.png, group_create.png, etc.)
  2. Show trends over time for each group
  3. Include them in comparison charts
  4. Display them in the HTML report
    """)


def main():
    """Main function to demonstrate custom metrics."""
    print("="*70)
    print("CUSTOM METRICS INTEGRATION TEST")
    print("="*70)
    print("\nThis demonstrates that the performance tracking system")
    print("automatically handles ANY new metrics you add.\n")

    # Add custom metrics
    add_custom_metrics_to_timing_log()

    # Add component metrics
    demonstrate_component_metrics()

    # Show naming conventions
    show_metric_naming_conventions()

    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
To see your custom metrics in action:

1. Run the consolidation:
   python scripts/write_performance_yaml.py

2. Generate visualizations:
   python scripts/visualize_performance.py --report --open

3. Or just run:
   make benchmark-all

Your custom metrics will automatically appear in:
  - performance.yml (under metrics section)
  - Group plots (e.g., group_custom.png)
  - Trend analysis (if you have 2+ runs)
  - HTML report summary tables
    """)


if __name__ == "__main__":
    main()
