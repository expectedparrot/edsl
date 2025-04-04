# EDSL Benchmarking

This directory contains performance benchmark logs for the EDSL library. These benchmarks track performance over time to identify optimization opportunities and regressions.

## Available Benchmarks

The benchmarking suite measures various aspects of EDSL performance:

1. **General Benchmarks** (`timing_benchmark.py`):
   - Import time - How long it takes to import the EDSL library
   - Survey creation - How long it takes to create surveys with many questions
   - Prompt rendering - How long it takes to render prompts for all questions
   - Model execution - How long it takes to run a survey with a test model

2. **Component Benchmarks** (`component_benchmark.py`):
   - Individual module import times
   - Question type creation performance
   - Survey DAG construction
   - Language model setup
   - Scenario list creation

## Running Benchmarks

Use the following make commands to run benchmarks:

```bash
# General benchmarks
make benchmark-timing            # Run standard timing benchmarks
make benchmark-small             # Run benchmarks with fewer questions (faster)
make benchmark-timing-profile    # Run benchmarks with pyinstrument profiling

# Component benchmarks
make benchmark-components        # Run detailed component-level benchmarks

# Visualization
make benchmark-plot              # Basic plot of historical benchmark data
make benchmark-visualize         # Create comprehensive benchmark visualizations
make benchmark-report            # Generate HTML report with trend analysis

# Run everything
make benchmark-all               # Run all benchmarks and generate reports
```

## Benchmark Logs

Benchmark results are stored in these files:

- `timing_log.jsonl` - Historical log of general benchmark runs
- `component_timing_log.jsonl` - Historical log of component benchmark runs
- `latest_results.json` - Results from the most recent benchmark run

## Reports and Visualization

The benchmarking tools can generate several visualizations:

1. **Time Series Charts**:
   - Track performance metrics over time
   - Group related operations for easier comparison

2. **Comparison Charts**:
   - Compare the time taken by different operations
   - Identify the most expensive operations

3. **Trend Analysis**:
   - Analyze performance improvements or regressions 
   - Percentage changes in metrics over time

4. **HTML Reports**:
   - Comprehensive HTML report with all metrics
   - System information and benchmark details

All visualizations are saved in the `reports/` subdirectory.

## Profiling

For deeper performance analysis, you can run benchmarks with Python profiling:

```bash
# Run benchmarks with pyinstrument profiling
make benchmark-timing-profile
```

This produces an HTML report showing which functions consume the most time, helping identify optimization targets. These reports are saved in the benchmark_logs directory with timestamps.

## Memory Profiling

The codebase includes tools for memory profiling specific components:

1. **ScenarioList Memory Testing**:
   - The `ScenarioList` module includes memory profiling capabilities for tracking memory usage of key operations
   - Separate memory profiling scripts are available for comprehensive memory analysis

### Method 1: Using environment variables for on-demand profiling

EDSL provides environment variables to enable memory profiling for any function decorated with `@memory_profile`:

```bash
# Enable memory profiling for all decorated functions
EDSL_MEMORY_PROFILE=true python your_script.py

# Enable memory profiling for specific functions only
EDSL_MEMORY_PROFILE_FUNCTIONS=filter,duplicate python your_script.py

# Save memory profiling reports to JSON files
EDSL_MEMORY_PROFILE=true EDSL_MEMORY_PROFILE_SAVE=true python your_script.py
```

The ScenarioList.filter method is already decorated with `@memory_profile`, so it can be profiled using these environment variables.

### Method 2: Using the dedicated profiling script

For more comprehensive memory profiling of ScenarioList operations:

```bash
# Run memory profiling with make command
make benchmark-memory

# Run memory profiling with larger dataset
make benchmark-memory-large

# Run directly with custom options
python scripts/memory_profiler.py --size 2000 --expression "id > 500"
```

### Report generation

Memory profiling reports are saved in the `benchmark_logs/memory_reports/` directory in JSON format. These reports track:

- Memory usage before and after operations
- Memory difference (allocation during operation)
- Execution time
- Top memory allocations by source code line
- Detailed memory usage statistics

You can generate visual reports from collected data:

```bash
# Generate and open visualization from JSON reports
python scripts/visualize_memory.py
```

### Method 3: Line-by-line memory profiling

For detailed line-by-line memory profiling that shows the memory consumption of each line of code:

```bash
# Run line-by-line memory profiling on ScenarioList.filter
make benchmark-memory-line

# Run with custom parameters
python scripts/memory_line_profiler.py --size 500 --expression "category == 'A'"

# Profile a different function
python scripts/memory_line_profiler.py --function edsl.scenarios.scenario_list.ScenarioList.duplicate
```

This line-by-line profiling generates both a text report showing the memory usage of each line of code and an HTML report with execution timing information.

### Method 4: Memory scaling tests

EDSL includes comprehensive tests for analyzing how memory usage scales with dataset size:

```bash
# Run memory scaling tests (analysis of memory usage with different dataset sizes)
make test-memory-scaling

# Run all memory tests for ScenarioList
make test-memory
```

The memory scaling tests:
- Measure memory usage during ScenarioList creation and filtering operations
- Test with different dataset sizes (100, 500, 1000, 2000, 5000 scenarios)
- Calculate memory per scenario to demonstrate efficiency improvements at scale
- Verify that memory usage plateaus rather than growing linearly with dataset size
- Calculate efficiency gains as dataset size increases

These tests help identify and validate optimizations that improve memory efficiency, particularly important for large-scale data processing.

### Memory investigation findings

Our investigation of ScenarioList memory usage has revealed important patterns:

1. **Memory usage plateaus**: As dataset size increases, memory usage doesn't grow linearly
   - Creation: ~9 MB for 10,000 scenarios
   - Filtering: ~8.6 MB for 10,000 scenarios
   
2. **Memory efficiency improves with scale**: Memory per scenario decreases as total scenarios increase
   - Small datasets: ~0.014 MB per scenario
   - Large datasets: ~0.0009 MB per scenario
   
3. **Primary memory usage sources**:
   - SQLite operations (database creation, querying)
   - Pickle serialization/deserialization
   - Python object overhead

4. **Garbage collection behavior**:
   - Pickling objects are properly garbage collected
   - SQLite maintains a memory cache that doesn't immediately release
   
5. **Memory usage during operations**:
   - Filter operation: Temporary spike during filtering due to query execution
   - Duplicate operation: More memory efficient than filter, better query optimization

This information helps identify memory-intensive operations and potential memory leaks, particularly important for operations with large datasets.