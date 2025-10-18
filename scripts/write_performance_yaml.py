#!/usr/bin/env python
"""
Write Performance Results to YAML

This script consolidates benchmark results from JSONL files into a unified
performance.yml file in the root directory for tracking over time.
"""

import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


# Constants
ROOT_DIR = Path(__file__).parent.parent
LOG_DIR = ROOT_DIR / "benchmark_logs"
TIMING_LOG_FILE = LOG_DIR / "timing_log.jsonl"
COMPONENT_LOG_FILE = LOG_DIR / "component_timing_log.jsonl"
PERFORMANCE_YAML = ROOT_DIR / "performance.yml"


def load_jsonl(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load the most recent entry from a JSONL file."""
    if not file_path.exists():
        return None

    last_entry = None
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                try:
                    last_entry = json.loads(line)
                except json.JSONDecodeError:
                    print(f"Error parsing line in {file_path}")

    return last_entry


def load_existing_performance_yaml() -> List[Dict[str, Any]]:
    """Load existing performance data from YAML file."""
    if not PERFORMANCE_YAML.exists():
        return []

    try:
        with open(PERFORMANCE_YAML, "r") as f:
            data = yaml.safe_load(f)
            if data is None:
                return []
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error loading existing performance.yml: {e}")
        return []


def consolidate_benchmark_results() -> Dict[str, Any]:
    """Consolidate results from timing and component benchmarks."""
    # Load latest results from JSONL files
    timing_data = load_jsonl(TIMING_LOG_FILE)
    component_data = load_jsonl(COMPONENT_LOG_FILE)

    # Create consolidated entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "metrics": {}
    }

    # Add system info and version
    if timing_data:
        if "system_info" in timing_data:
            entry["system_info"] = timing_data["system_info"]
        if "edsl_version" in timing_data:
            entry["edsl_version"] = timing_data["edsl_version"]

    # Add timing benchmarks
    if timing_data and "benchmarks" in timing_data:
        for key, value in timing_data["benchmarks"].items():
            if not isinstance(value, str):
                entry["metrics"][key] = float(value)

    # Add component benchmarks
    if component_data and "components" in component_data:
        for key, value in component_data["components"].items():
            if not isinstance(value, str):
                entry["metrics"][key] = float(value)

    return entry


def write_performance_yaml(append: bool = True):
    """Write consolidated benchmark results to performance.yml."""
    # Consolidate current results
    new_entry = consolidate_benchmark_results()

    if not new_entry["metrics"]:
        print("No benchmark metrics found to write.")
        return

    # Load existing data if appending
    if append:
        all_entries = load_existing_performance_yaml()
    else:
        all_entries = []

    # Append new entry
    all_entries.append(new_entry)

    # Write to YAML file
    with open(PERFORMANCE_YAML, "w") as f:
        yaml.dump(all_entries, f, default_flow_style=False, sort_keys=False)

    print(f"Performance data written to {PERFORMANCE_YAML}")
    print(f"Total benchmark runs recorded: {len(all_entries)}")
    print(f"Latest run metrics: {len(new_entry['metrics'])} measurements")


def main():
    """Main function."""
    import argparse
    parser = argparse.ArgumentParser(description="Write benchmark results to performance.yml")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing file instead of appending")
    args = parser.parse_args()

    write_performance_yaml(append=not args.overwrite)


if __name__ == "__main__":
    main()
