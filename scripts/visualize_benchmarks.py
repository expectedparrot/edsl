#!/usr/bin/env python
"""
EDSL Benchmark Visualization

This script provides visualization tools for the benchmark data collected
by the timing_benchmark.py and component_benchmark.py scripts.
"""

import json
import datetime
import argparse
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# Constants
LOG_DIR = Path(".") / "benchmark_logs"
TIMING_LOG_FILE = LOG_DIR / "timing_log.jsonl"
COMPONENT_LOG_FILE = LOG_DIR / "component_timing_log.jsonl"
REPORT_DIR = LOG_DIR / "reports"


def load_benchmark_data(file_path):
    """Load benchmark data from a JSONL file."""
    if not file_path.exists():
        return []
    
    data = []
    with open(file_path, "r") as f:
        for line in f:
            if line.strip():
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    print(f"Error parsing line in {file_path}")
    
    return data


def create_time_series_plots(data, metric_type):
    """Create time series plots for benchmark metrics."""
    if not data:
        print(f"No {metric_type} benchmark data found.")
        return
    
    # Get all benchmark keys
    benchmark_keys = set()
    for entry in data:
        if metric_type == "timing":
            benchmark_keys.update(entry.get("benchmarks", {}).keys())
        else:
            benchmark_keys.update(entry.get("components", {}).keys())
    
    # Sort keys for consistent ordering
    benchmark_keys = sorted(benchmark_keys)
    
    # Group similar metrics
    metric_groups = {}
    for key in benchmark_keys:
        # Group by prefix (e.g., import_, create_, render_)
        prefix = key.split('_')[0]
        if prefix not in metric_groups:
            metric_groups[prefix] = []
        metric_groups[prefix].append(key)
    
    # Create a figure for each group
    for group_name, group_keys in metric_groups.items():
        if not group_keys:
            continue
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        for key in sorted(group_keys):
            times = []
            dates = []
            for entry in data:
                if metric_type == "timing":
                    metrics = entry.get("benchmarks", {})
                else:
                    metrics = entry.get("components", {})
                
                if key in metrics and not isinstance(metrics[key], str):
                    times.append(metrics[key])
                    dates.append(datetime.datetime.fromisoformat(entry["timestamp"]))
            
            if times:
                ax.plot(dates, times, 'o-', label=key)
        
        ax.set_title(f"{group_name.capitalize()} Operations")
        ax.set_ylabel("Time (s)")
        ax.set_xlabel("Date")
        ax.legend()
        ax.grid(True)
        
        # Format date ticks
        plt.gcf().autofmt_xdate()
        
        # Save the figure
        REPORT_DIR.mkdir(exist_ok=True, parents=True)
        plt.tight_layout()
        plt.savefig(REPORT_DIR / f"{metric_type}_{group_name}_metrics.png")
        plt.close()


def create_comparison_plot(timing_data, component_data):
    """Create a comparison plot of the latest benchmark results."""
    if not timing_data or not component_data:
        print("Not enough data for comparison plot.")
        return
    
    # Get latest data
    latest_timing = timing_data[-1]
    latest_component = component_data[-1]
    
    # Combine data for plotting
    all_metrics = {}
    all_metrics.update(latest_timing.get("benchmarks", {}))
    all_metrics.update(latest_component.get("components", {}))
    
    # Remove any string values
    all_metrics = {k: v for k, v in all_metrics.items() if not isinstance(v, str)}
    
    # Sort by time (descending)
    sorted_metrics = sorted(all_metrics.items(), key=lambda x: x[1], reverse=True)
    
    # Plot horizontal bar chart of top 15 metrics
    plt.figure(figsize=(12, 10))
    metrics = [k for k, v in sorted_metrics[:15]]
    times = [v for k, v in sorted_metrics[:15]]
    
    # Create horizontal bar chart
    y_pos = np.arange(len(metrics))
    plt.barh(y_pos, times)
    plt.yticks(y_pos, [m.replace('_', ' ') for m in metrics])
    plt.xlabel('Time (s)')
    plt.title('Top 15 Most Time-Consuming Operations')
    
    # Add values at the end of each bar
    for i, v in enumerate(times):
        plt.text(v + 0.01, i, f"{v:.3f}s", va='center')
    
    REPORT_DIR.mkdir(exist_ok=True, parents=True)
    plt.tight_layout()
    plt.savefig(REPORT_DIR / "top_metrics_comparison.png")
    plt.close()


def create_html_report(timing_data, component_data):
    """Create an HTML report of benchmark results."""
    if not timing_data and not component_data:
        print("No data found for HTML report.")
        return
    
    REPORT_DIR.mkdir(exist_ok=True, parents=True)
    report_path = REPORT_DIR / "benchmark_report.html"
    
    # Get the latest results if available
    latest_timing = timing_data[-1] if timing_data else None
    latest_component = component_data[-1] if component_data else None
    
    # Start HTML content
    html = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "    <title>EDSL Performance Benchmark Report</title>",
        "    <style>",
        "        body { font-family: Arial, sans-serif; margin: 20px; }",
        "        h1, h2, h3 { color: #333; }",
        "        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }",
        "        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
        "        th { background-color: #f2f2f2; }",
        "        tr:nth-child(even) { background-color: #f9f9f9; }",
        "        .chart-container { margin: 20px 0; text-align: center; }",
        "        .chart-container img { max-width: 100%; border: 1px solid #ddd; }",
        "    </style>",
        "</head>",
        "<body>",
        "    <h1>EDSL Performance Benchmark Report</h1>"
    ]
    
    # Add timestamp
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html.append(f"    <p>Generated: {current_time}</p>")
    
    # Add system information
    if latest_timing and "system_info" in latest_timing:
        system_info = latest_timing["system_info"]
        html.append("    <h2>System Information</h2>")
        html.append("    <table>")
        for key, value in system_info.items():
            html.append(f"        <tr><th>{key}</th><td>{value}</td></tr>")
        html.append("    </table>")
    
    # Add EDSL version
    if latest_timing and "edsl_version" in latest_timing:
        html.append(f"    <p>EDSL Version: {latest_timing['edsl_version']}</p>")
    
    # Add timing benchmark results
    if latest_timing and "benchmarks" in latest_timing:
        html.append("    <h2>Timing Benchmark Results</h2>")
        html.append("    <table>")
        html.append("        <tr><th>Benchmark</th><th>Time (s)</th></tr>")
        
        for key, value in sorted(latest_timing["benchmarks"].items()):
            if not isinstance(value, str):
                html.append(f"        <tr><td>{key.replace('_', ' ')}</td><td>{value:.4f}</td></tr>")
        
        html.append("    </table>")
    
    # Add component benchmark results
    if latest_component and "components" in latest_component:
        html.append("    <h2>Component Benchmark Results</h2>")
        html.append("    <table>")
        html.append("        <tr><th>Component</th><th>Time (s)</th></tr>")
        
        for key, value in sorted(latest_component["components"].items()):
            if not isinstance(value, str):
                html.append(f"        <tr><td>{key.replace('_', ' ')}</td><td>{value:.4f}</td></tr>")
        
        html.append("    </table>")
    
    # Add chart images
    html.append("    <h2>Benchmark Charts</h2>")
    html.append("    <div class='chart-container'>")
    html.append("        <h3>Top Time-Consuming Operations</h3>")
    html.append("        <img src='top_metrics_comparison.png' alt='Top Metrics' />")
    html.append("    </div>")
    
    # Close HTML tags
    html.append("</body>")
    html.append("</html>")
    
    # Write HTML file
    with open(report_path, "w") as f:
        f.write("\n".join(html))
    
    print(f"HTML report generated at {report_path}")


def create_trend_analysis(timing_data, component_data):
    """Analyze trends in benchmark data over time."""
    if len(timing_data) < 2 and len(component_data) < 2:
        print("Not enough historical data for trend analysis.")
        return
    
    # Combine all benchmark data
    all_metrics = {}
    
    # Process timing data
    for entry in timing_data:
        timestamp = datetime.datetime.fromisoformat(entry["timestamp"])
        for key, value in entry.get("benchmarks", {}).items():
            if isinstance(value, (int, float)):
                if key not in all_metrics:
                    all_metrics[key] = []
                all_metrics[key].append((timestamp, value))
    
    # Process component data
    for entry in component_data:
        timestamp = datetime.datetime.fromisoformat(entry["timestamp"])
        for key, value in entry.get("components", {}).items():
            if isinstance(value, (int, float)):
                if key not in all_metrics:
                    all_metrics[key] = []
                all_metrics[key].append((timestamp, value))
    
    # Create a trend report for metrics with enough data points
    trend_data = {}
    for key, values in all_metrics.items():
        if len(values) >= 2:
            # Sort by timestamp
            values.sort(key=lambda x: x[0])
            
            # Calculate simple trend (latest vs earliest)
            earliest = values[0][1]
            latest = values[-1][1]
            if earliest > 0:
                pct_change = ((latest - earliest) / earliest) * 100
                trend_data[key] = {
                    "earliest": earliest,
                    "latest": latest,
                    "pct_change": pct_change
                }
    
    # Create a DataFrame for trend visualization
    if trend_data:
        df = pd.DataFrame({
            "Metric": [k.replace("_", " ") for k in trend_data.keys()],
            "Percent Change": [v["pct_change"] for v in trend_data.values()]
        })
        
        # Sort by percent change
        df = df.sort_values("Percent Change", ascending=False)
        
        # Plot
        plt.figure(figsize=(12, 10))
        colors = ['green' if x < 0 else 'red' for x in df["Percent Change"]]
        plt.barh(df["Metric"], df["Percent Change"], color=colors)
        plt.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
        plt.xlabel('Percent Change (%)')
        plt.title('Performance Trend Analysis\n(negative is better - operation got faster)')
        
        # Add values at the end of each bar
        for i, v in enumerate(df["Percent Change"]):
            plt.text(v + 1 if v >= 0 else v - 5, i, f"{v:.1f}%", va='center')
        
        REPORT_DIR.mkdir(exist_ok=True, parents=True)
        plt.tight_layout()
        plt.savefig(REPORT_DIR / "trend_analysis.png")
        plt.close()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="EDSL Benchmark Visualization")
    parser.add_argument("--report", action="store_true",
                        help="Generate an HTML report of benchmark results")
    parser.add_argument("--trends", action="store_true",
                        help="Generate trend analysis of benchmark results")
    return parser.parse_args()


def main():
    """Main function to run the visualization."""
    args = parse_args()
    
    # Load benchmark data
    timing_data = load_benchmark_data(TIMING_LOG_FILE)
    component_data = load_benchmark_data(COMPONENT_LOG_FILE)
    
    # Create time series plots
    create_time_series_plots(timing_data, "timing")
    create_time_series_plots(component_data, "component")
    
    # Create comparison plot
    create_comparison_plot(timing_data, component_data)
    
    # Generate HTML report if requested
    if args.report:
        create_html_report(timing_data, component_data)
    
    # Generate trend analysis if requested
    if args.trends:
        create_trend_analysis(timing_data, component_data)


if __name__ == "__main__":
    main()