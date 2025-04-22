#!/usr/bin/env python3
import concurrent.futures
import subprocess
import sys
from pathlib import Path

def run_doctest(module_path):
    """Run doctest on a single module and return the result."""
    try:
        result = subprocess.run(
            ["pytest", "--doctest-modules", str(module_path)],
            capture_output=True,
            text=True
        )
        return {
            "module": module_path,
            "success": result.returncode == 0,
            "output": result.stdout + result.stderr
        }
    except Exception as e:
        return {
            "module": module_path,
            "success": False,
            "output": str(e)
        }

def main():
    # List of modules to test
    modules = [
        "edsl/instructions",
        "edsl/key_management",
        "edsl/prompts",
        "edsl/tasks",
        "edsl/results",
        "edsl/dataset",
        "edsl/buckets",
        "edsl/interviews",
        "edsl/tokens",
        "edsl/jobs",
        "edsl/surveys",
        "edsl/agents",
        "edsl/scenarios",
        "edsl/questions",
        "edsl/utilities",
        "edsl/language_models",
        "edsl/caching",
        "edsl/inference_services"
    ]

    # Special case for buckets module
    modules.remove("edsl/buckets")
    modules.append("edsl/buckets/token_bucket.py")
    # Don't include token_bucket_client.py as it was ignored in the original

    # Convert to Path objects
    module_paths = [Path(module) for module in modules]

    # Run tests in parallel
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_to_module = {executor.submit(run_doctest, path): path for path in module_paths}
        
        all_success = True
        for future in concurrent.futures.as_completed(future_to_module):
            module = future_to_module[future]
            try:
                result = future.result()
                if not result["success"]:
                    all_success = False
                    print(f"\nFailed tests in {result['module']}:")
                    print(result["output"])
            except Exception as e:
                all_success = False
                print(f"\nError running tests for {module}:")
                print(str(e))

    if not all_success:
        sys.exit(1)

if __name__ == "__main__":
    main() 