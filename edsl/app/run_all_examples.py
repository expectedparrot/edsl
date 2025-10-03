#!/usr/bin/env python3
"""
Script to run all Python examples in the current directory.
Stops execution on the first exception encountered.
"""

import os
import subprocess
import sys
from pathlib import Path

def run_all_examples():
    """Run all Python examples, stopping on first exception."""
    current_dir = Path.cwd()
    python_files = sorted(current_dir.glob("*.py"))

    # Exclude this script itself
    script_name = Path(__file__).name
    python_files = [f for f in python_files if f.name != script_name]

    if not python_files:
        print("No Python examples found in current directory.")
        return

    print(f"Found {len(python_files)} Python examples to run:")
    for file in python_files:
        print(f"  - {file.name}")
    print()

    for i, example_file in enumerate(python_files, 1):
        print(f"[{i}/{len(python_files)}] Running {example_file.name}...")

        try:
            result = subprocess.run(
                [sys.executable, str(example_file)],
                capture_output=True,
                text=True,
                check=True,
                timeout=300  # 5 minute timeout per example
            )
            print(f"✓ {example_file.name} completed successfully")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
            print()

        except subprocess.CalledProcessError as e:
            print(f"✗ {example_file.name} failed with exit code {e.returncode}")
            if e.stdout:
                print(f"STDOUT:\n{e.stdout}")
            if e.stderr:
                print(f"STDERR:\n{e.stderr}")
            print(f"\nStopping execution due to failure in {example_file.name}")
            sys.exit(1)

        except subprocess.TimeoutExpired:
            print(f"✗ {example_file.name} timed out after 5 minutes")
            print(f"Stopping execution due to timeout in {example_file.name}")
            sys.exit(1)

        except Exception as e:
            print(f"✗ Unexpected error running {example_file.name}: {e}")
            print(f"Stopping execution due to error in {example_file.name}")
            sys.exit(1)

    print(f"All {len(python_files)} examples completed successfully! ✓")

if __name__ == "__main__":
    run_all_examples()