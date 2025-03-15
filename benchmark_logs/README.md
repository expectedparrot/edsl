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