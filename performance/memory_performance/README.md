# Memory Performance Tests

This directory contains tests that verify the memory efficiency of EDSL components, particularly focusing on memory scaling as workload increases.

## Purpose

These tests are designed to:

1. Confirm memory optimizations and improvements in the codebase
2. Act as regression tests to catch memory-related regressions
3. Provide quantitative measurements of memory efficiency
4. Verify that memory usage scales efficiently with increased workload

## Current Tests

- `test_job_memory_scaling.py`: Verifies that memory usage per interview decreases as the number of interviews increases, demonstrating efficient memory usage in the Jobs implementation.

## Running Tests

You can run these tests with:

```bash
# Run all memory performance tests
python -m pytest -xv tests/memory_performance/

# Run a specific test file
python -m pytest -xv tests/memory_performance/test_job_memory_scaling.py
```

## Typical Results

A successful test will show that memory per interview decreases substantially as the job size increases. Typical improvements range from 25-80% memory reduction per interview when comparing small jobs to large jobs.

## Implementation Notes

- These tests may take longer to run than other unit tests due to the need to run with larger datasets
- Memory measurements can vary between environments, so the tests use relative comparisons rather than fixed thresholds
- Multiple garbage collection passes are performed to ensure consistent measurements