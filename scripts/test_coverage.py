#!/usr/bin/env python
"""
Script to run tests with coverage and generate a report by module.
"""
import os
import subprocess
import json
from pathlib import Path
import pandas as pd
from rich.console import Console
from rich.table import Table

def run_coverage(module_path=None):
    """Run pytest with coverage and generate a JSON report."""
    print("Running tests with coverage...")
    
    # Set default test path
    test_path = "tests/"
    
    # If a specific module is provided, target tests for that module
    if module_path:
        module_name = module_path.split('/')[-1]
        test_path = f"tests/{module_name}/"
        print(f"Running coverage for module: {module_name}")
    
    # Create the .coverage file
    subprocess.run(
        ["coverage", "run", "--source", module_path or "edsl", "-m", "pytest", test_path], 
        check=False
    )
    
    # Convert to JSON for easier parsing
    subprocess.run(
        ["coverage", "json"], 
        check=False
    )

def parse_coverage_data():
    """Parse the coverage JSON data and return module stats."""
    # Load the JSON data
    with open("coverage.json", "r") as f:
        data = json.load(f)
    
    # Extract files data
    files_data = data.get("files", {})
    
    # Prepare results
    results = []
    
    # Get the base path to determine relative paths
    base_path = Path(os.getcwd()) / "edsl"
    
    for file_path, file_data in files_data.items():
        path = Path(file_path)
        
        # Only include files in the edsl package
        if "edsl" not in str(path):
            continue
            
        # Get relative path from the edsl directory
        try:
            rel_path = path.relative_to(base_path)
            module_path = str(rel_path).replace("/", ".").replace("\\", ".").replace(".py", "")
            if module_path.startswith("."):
                module_path = module_path[1:]
                
            # For __init__.py files, use the directory name
            if module_path.endswith("__init__"):
                module_path = module_path[:-9]
                if module_path.endswith("."):
                    module_path = module_path[:-1]
        except ValueError:
            # If we can't get a relative path, use the filename
            module_path = path.stem
        
        # Get coverage stats
        coverage = file_data.get("summary", {}).get("percent_covered", 0)
        statements = file_data.get("summary", {}).get("num_statements", 0)
        missing = file_data.get("summary", {}).get("missing_lines", 0)
        
        # Add to results
        results.append({
            "module": module_path,
            "statements": statements,
            "coverage": coverage,
            "missing": missing,
        })
    
    return results

def aggregate_by_module(results):
    """Aggregate results by top-level module."""
    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(results)
    
    # Extract top-level module
    df["top_module"] = df["module"].apply(lambda x: x.split(".")[0] if "." in x else x)
    
    # Group by top-level module
    grouped = df.groupby("top_module").agg({
        "statements": "sum", 
        "missing": "sum"
    }).reset_index()
    
    # Calculate coverage percentage
    grouped["coverage"] = 100 * (grouped["statements"] - grouped["missing"]) / grouped["statements"]
    
    # Sort by coverage
    grouped = grouped.sort_values("coverage", ascending=False)
    
    return grouped

def display_results(results_df, overall_data):
    """Display the results in a nicely formatted table."""
    console = Console()
    
    table = Table(title="Test Coverage by Module")
    
    table.add_column("Module", style="cyan")
    table.add_column("Statements", justify="right", style="green")
    table.add_column("Coverage %", justify="right", style="magenta")
    
    # Add module rows
    for _, row in results_df.iterrows():
        table.add_row(
            row["top_module"],
            str(int(row["statements"])),
            f"{row['coverage']:.1f}%"
        )
    
    # Add a separator
    table.add_row("----------", "----------", "----------")
    
    # Add overall row
    total_statements = results_df["statements"].sum()
    overall_coverage = 100 * (total_statements - results_df["missing"].sum()) / total_statements
    table.add_row(
        "OVERALL",
        str(int(total_statements)),
        f"{overall_coverage:.1f}%",
        style="bold"
    )
    
    console.print(table)

def main():
    """Main function to run the coverage report."""
    import sys
    
    # Check if a specific module was provided
    module_path = None
    if len(sys.argv) > 1:
        module_path = sys.argv[1]
    
    run_coverage(module_path)
    
    results = parse_coverage_data()
    
    if not results:
        print("No coverage data found. Make sure tests are running correctly.")
        return
    
    # Aggregate by module
    module_results = aggregate_by_module(results)
    
    # Calculate overall stats
    total_statements = sum(r["statements"] for r in results)
    total_missing = sum(r["missing"] for r in results)
    overall_coverage = 100 * (total_statements - total_missing) / total_statements if total_statements > 0 else 0
    
    overall_data = {
        "statements": total_statements,
        "missing": total_missing,
        "coverage": overall_coverage
    }
    
    # Display results
    display_results(module_results, overall_data)

if __name__ == "__main__":
    main()