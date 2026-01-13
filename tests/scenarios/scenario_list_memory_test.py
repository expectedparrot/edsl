"""
Memory usage test for ScenarioList with different data sizes.
"""

import gc
import os
import time
import json
from typing import Dict, List

import pytest

# Skip all tests in this module if optional dependencies aren't installed
psutil = pytest.importorskip("psutil", reason="psutil not installed")
plt = pytest.importorskip("matplotlib.pyplot", reason="matplotlib not installed")


def get_memory_usage() -> float:
    """Get current memory usage in MB"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    memory_mb = memory_info.rss / (1024 * 1024)
    return memory_mb


def log_memory(label: str) -> float:
    """Log and return current memory usage."""
    mem = get_memory_usage()
    print(f"{label}: {mem:.2f} MB")
    return mem


def run_memory_test(
    sizes: List[int], item_size_kb: int = 10
) -> Dict[str, Dict[int, float]]:
    """
    Test memory usage for ScenarioList with different dataset sizes.

    Args:
        sizes: List of dataset sizes to test
        item_size_kb: Size of text data in each scenario (in KB)

    Returns:
        Dictionary with memory usage metrics for each size
    """
    from edsl.scenarios import ScenarioList

    results = {"creation": {}, "filter": {}, "baseline": {}, "total": {}}

    for size in sizes:
        print(f"\n{'='*50}")
        print(f"Testing with {size} scenarios (each with {item_size_kb}KB text)")
        print(f"{'='*50}")

        # Force garbage collection before starting
        gc.collect()
        gc.collect()
        time.sleep(1)  # Give system time to stabilize

        baseline_mem = log_memory("Baseline memory")
        results["baseline"][size] = baseline_mem

        # Create test data
        text_size = item_size_kb * 1024  # Convert KB to bytes
        text = "x" * text_size

        # Create scenarios
        print(f"Creating {size} scenarios...")
        scenarios = []
        for i in range(size):
            scenarios.append(
                {
                    "id": i,
                    "text": text,
                    "category": "A" if i % 2 == 0 else "B",
                    "value": i * 10,
                }
            )

        # Measure memory after creating raw data
        after_raw_mem = log_memory("Memory after creating raw data")

        # Create ScenarioList
        print("Creating ScenarioList...")
        start_time = time.time()
        sl = ScenarioList(scenarios)
        creation_time = time.time() - start_time

        # Measure memory after creating ScenarioList
        after_creation_mem = log_memory("Memory after creating ScenarioList")
        creation_mem_diff = after_creation_mem - after_raw_mem
        results["creation"][size] = creation_mem_diff
        print(f"Creation memory increase: {creation_mem_diff:.2f} MB")
        print(f"Creation time: {creation_time:.2f} seconds")

        # Filter ScenarioList
        print("Filtering ScenarioList...")
        start_time = time.time()
        filtered = sl.filter("id % 2 == 0")
        filter_time = time.time() - start_time

        # Measure memory after filtering
        after_filter_mem = log_memory("Memory after filtering")
        filter_mem_diff = after_filter_mem - after_creation_mem
        results["filter"][size] = filter_mem_diff
        results["total"][size] = after_filter_mem - baseline_mem
        print(f"Filter memory increase: {filter_mem_diff:.2f} MB")
        print(f"Filter time: {filter_time:.2f} seconds")
        print(f"Total memory increase: {after_filter_mem - baseline_mem:.2f} MB")

        # Clean up to prepare for next iteration
        del scenarios
        del sl
        del filtered
        gc.collect()
        gc.collect()
        time.sleep(1)  # Give system time to stabilize

    return results


def plot_results(
    results: Dict[str, Dict[int, float]], output_path: str = "memory_usage_plot.png"
) -> None:
    """
    Plot memory usage results.

    Args:
        results: Dictionary with memory usage metrics
        output_path: Path to save the plot
    """
    sizes = sorted(results["creation"].keys())

    # Extract data for plotting
    creation_memory = [results["creation"][size] for size in sizes]
    filter_memory = [results["filter"][size] for size in sizes]
    total_memory = [results["total"][size] for size in sizes]

    # Create figure and axis
    plt.figure(figsize=(12, 8))

    # Plot memory usage
    plt.subplot(2, 1, 1)
    plt.plot(sizes, creation_memory, "o-", label="ScenarioList Creation")
    plt.plot(sizes, filter_memory, "s-", label="Filter Operation")
    plt.plot(sizes, total_memory, "^-", label="Total Memory Usage")
    plt.xlabel("Number of Scenarios")
    plt.ylabel("Memory Usage (MB)")
    plt.title("Memory Usage vs. Dataset Size")
    plt.grid(True)
    plt.legend()

    # Plot memory usage per scenario
    plt.subplot(2, 1, 2)
    mem_per_scenario_creation = [
        mem / size for mem, size in zip(creation_memory, sizes)
    ]
    mem_per_scenario_filter = [mem / size for mem, size in zip(filter_memory, sizes)]
    mem_per_scenario_total = [mem / size for mem, size in zip(total_memory, sizes)]

    plt.plot(sizes, mem_per_scenario_creation, "o-", label="Creation (per scenario)")
    plt.plot(sizes, mem_per_scenario_filter, "s-", label="Filter (per scenario)")
    plt.plot(sizes, mem_per_scenario_total, "^-", label="Total (per scenario)")
    plt.xlabel("Number of Scenarios")
    plt.ylabel("Memory Usage per Scenario (MB)")
    plt.title("Memory Efficiency vs. Dataset Size")
    plt.grid(True)
    plt.legend()

    # Set log scale for x-axis to better visualize the trend
    plt.xscale("log")

    plt.tight_layout()
    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")


def main():
    """Run memory tests and plot results."""
    # Test with increasing dataset sizes
    sizes = [100, 500, 1000, 2000, 5000, 10000]

    # Each scenario will have a 10KB text field
    item_size_kb = 10

    # Create output directory if it doesn't exist
    os.makedirs("benchmark_logs/memory_reports", exist_ok=True)

    # Run tests
    results = run_memory_test(sizes, item_size_kb)

    # Save results as JSON
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_path = f"benchmark_logs/memory_reports/memory_test_results_{timestamp}.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")

    # Plot results
    plot_path = f"benchmark_logs/memory_reports/memory_usage_plot_{timestamp}.png"
    plot_results(results, plot_path)


def test_scenario_list_memory():
    """
    Simple test function for pytest to run a small memory test.
    This is a simplified version of the main benchmarking function.
    """
    # Use very small sample size for pytest
    sizes = [10, 20]
    item_size_kb = 1

    # Run a minimal test
    results = run_memory_test(sizes, item_size_kb)

    # Verify we got results
    assert isinstance(results, dict)
    assert "creation" in results
    assert "filter" in results
    assert "total" in results

    # No need to return anything for pytest


if __name__ == "__main__":
    main()
