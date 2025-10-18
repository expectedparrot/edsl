#!/usr/bin/env python
"""
Visualize Performance Data from performance.yml

This script reads performance.yml and creates comprehensive visualizations
showing performance metrics over time.
"""

import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np


# Constants
ROOT_DIR = Path(__file__).parent.parent
PERFORMANCE_YAML = ROOT_DIR / "performance.yml"
REPORT_DIR = ROOT_DIR / "benchmark_logs" / "reports"


def load_performance_data() -> List[Dict[str, Any]]:
    """Load performance data from YAML file."""
    if not PERFORMANCE_YAML.exists():
        print(f"Performance file not found: {PERFORMANCE_YAML}")
        return []

    try:
        with open(PERFORMANCE_YAML, "r") as f:
            data = yaml.safe_load(f)
            if data is None:
                return []
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Error loading performance.yml: {e}")
        return []


def extract_metric_series(data: List[Dict[str, Any]]) -> Dict[str, List[tuple]]:
    """Extract time series data for each metric."""
    metric_series = {}

    for entry in data:
        timestamp = datetime.fromisoformat(entry.get("timestamp", ""))
        metrics = entry.get("metrics", {})

        for metric_name, value in metrics.items():
            if isinstance(value, (int, float)):
                if metric_name not in metric_series:
                    metric_series[metric_name] = []
                metric_series[metric_name].append((timestamp, value))

    # Sort each series by timestamp
    for metric_name in metric_series:
        metric_series[metric_name].sort(key=lambda x: x[0])

    return metric_series


def group_metrics(metric_names: List[str]) -> Dict[str, List[str]]:
    """Group metrics by prefix for organized visualization."""
    groups = {}

    for name in metric_names:
        # Extract prefix (e.g., "import" from "import_edsl")
        prefix = name.split('_')[0]
        if prefix not in groups:
            groups[prefix] = []
        groups[prefix].append(name)

    return groups


def create_metric_group_plot(metric_series: Dict[str, List[tuple]], group_name: str,
                             metric_names: List[str], output_path: Path):
    """Create a plot for a group of related metrics."""
    fig, ax = plt.subplots(figsize=(12, 6))

    for metric_name in sorted(metric_names):
        if metric_name not in metric_series:
            continue

        data = metric_series[metric_name]
        if not data:
            continue

        timestamps, values = zip(*data)
        label = metric_name.replace('_', ' ').title()
        ax.plot(timestamps, values, 'o-', label=label, linewidth=2, markersize=6)

    ax.set_title(f"{group_name.capitalize()} Performance Over Time", fontsize=14, fontweight='bold')
    ax.set_ylabel("Time (seconds)", fontsize=12)
    ax.set_xlabel("Date", fontsize=12)
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=10)
    ax.grid(True, alpha=0.3)

    # Format date ticks
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gcf().autofmt_xdate()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def create_latest_comparison_plot(data: List[Dict[str, Any]], output_path: Path):
    """Create a bar chart comparing the latest benchmark results."""
    if not data:
        return

    latest = data[-1]
    metrics = latest.get("metrics", {})

    if not metrics:
        return

    # Sort metrics by value (descending)
    sorted_metrics = sorted(metrics.items(), key=lambda x: x[1], reverse=True)

    # Take top 15 metrics
    top_metrics = sorted_metrics[:15]
    names = [name.replace('_', ' ').title() for name, _ in top_metrics]
    values = [value for _, value in top_metrics]

    # Create horizontal bar chart
    fig, ax = plt.subplots(figsize=(12, 8))
    y_pos = np.arange(len(names))
    bars = ax.barh(y_pos, values, color='steelblue')

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=10)
    ax.set_xlabel('Time (seconds)', fontsize=12)
    ax.set_title('Top 15 Most Time-Consuming Operations (Latest Run)',
                 fontsize=14, fontweight='bold')

    # Add value labels on bars
    for i, (bar, value) in enumerate(zip(bars, values)):
        ax.text(value + max(values) * 0.01, i, f"{value:.3f}s",
                va='center', fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def create_trend_analysis_plot(metric_series: Dict[str, List[tuple]], output_path: Path):
    """Create a plot showing performance trends (% change over time)."""
    trend_data = []

    for metric_name, data in metric_series.items():
        if len(data) < 2:
            continue

        earliest_value = data[0][1]
        latest_value = data[-1][1]

        if earliest_value > 0:
            pct_change = ((latest_value - earliest_value) / earliest_value) * 100
            trend_data.append((metric_name, pct_change))

    if not trend_data:
        return

    # Sort by percent change
    trend_data.sort(key=lambda x: x[1], reverse=True)

    # Take top 20 changes (both positive and negative)
    if len(trend_data) > 20:
        # Get top 10 increases and top 10 decreases
        top_increases = trend_data[:10]
        top_decreases = trend_data[-10:]
        trend_data = top_increases + top_decreases

    names = [name.replace('_', ' ').title() for name, _ in trend_data]
    changes = [change for _, change in trend_data]

    # Create horizontal bar chart with color coding
    fig, ax = plt.subplots(figsize=(12, 10))
    y_pos = np.arange(len(names))
    colors = ['red' if c > 0 else 'green' for c in changes]
    bars = ax.barh(y_pos, changes, color=colors, alpha=0.7)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=9)
    ax.set_xlabel('Percent Change (%)', fontsize=12)
    ax.set_title('Performance Trend Analysis\n(Green = Faster, Red = Slower)',
                 fontsize=14, fontweight='bold')
    ax.axvline(x=0, color='black', linestyle='-', linewidth=0.8)

    # Add value labels
    for i, (bar, value) in enumerate(zip(bars, changes)):
        x_pos = value + (2 if value >= 0 else -2)
        alignment = 'left' if value >= 0 else 'right'
        ax.text(x_pos, i, f"{value:.1f}%", va='center', ha=alignment, fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def create_summary_statistics(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create summary statistics from performance data."""
    if not data:
        return {}

    latest = data[-1]
    metrics = latest.get("metrics", {})

    summary = {
        "total_runs": len(data),
        "latest_timestamp": latest.get("timestamp"),
        "edsl_version": latest.get("edsl_version", "unknown"),
        "total_metrics": len(metrics),
        "slowest_operation": None,
        "fastest_operation": None,
    }

    if metrics:
        sorted_metrics = sorted(metrics.items(), key=lambda x: x[1])
        summary["fastest_operation"] = {
            "name": sorted_metrics[0][0],
            "time": sorted_metrics[0][1]
        }
        summary["slowest_operation"] = {
            "name": sorted_metrics[-1][0],
            "time": sorted_metrics[-1][1]
        }

    return summary


def create_html_report(data: List[Dict[str, Any]], output_path: Path):
    """Create comprehensive HTML report."""
    summary = create_summary_statistics(data)

    html = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "    <meta charset='UTF-8'>",
        "    <title>EDSL Performance Report</title>",
        "    <style>",
        "        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #f5f5f5; }",
        "        .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        "        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }",
        "        h2 { color: #34495e; margin-top: 30px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }",
        "        .summary { background-color: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }",
        "        .summary-item { margin: 10px 0; font-size: 16px; }",
        "        .summary-item strong { color: #2c3e50; }",
        "        .chart-container { margin: 30px 0; text-align: center; }",
        "        .chart-container img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }",
        "        .timestamp { color: #7f8c8d; font-size: 14px; }",
        "    </style>",
        "</head>",
        "<body>",
        "    <div class='container'>",
        "        <h1>EDSL Performance Benchmark Report</h1>",
        f"        <p class='timestamp'>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
    ]

    # Add summary section
    html.append("        <div class='summary'>")
    html.append("            <h2>Summary</h2>")
    html.append(f"            <div class='summary-item'><strong>Total Benchmark Runs:</strong> {summary.get('total_runs', 0)}</div>")
    html.append(f"            <div class='summary-item'><strong>EDSL Version:</strong> {summary.get('edsl_version', 'unknown')}</div>")
    html.append(f"            <div class='summary-item'><strong>Total Metrics Tracked:</strong> {summary.get('total_metrics', 0)}</div>")
    html.append(f"            <div class='summary-item'><strong>Latest Run:</strong> {summary.get('latest_timestamp', 'N/A')}</div>")

    if summary.get('slowest_operation'):
        op = summary['slowest_operation']
        html.append(f"            <div class='summary-item'><strong>Slowest Operation:</strong> {op['name'].replace('_', ' ')} ({op['time']:.3f}s)</div>")

    if summary.get('fastest_operation'):
        op = summary['fastest_operation']
        html.append(f"            <div class='summary-item'><strong>Fastest Operation:</strong> {op['name'].replace('_', ' ')} ({op['time']:.3f}s)</div>")

    html.append("        </div>")

    # Add charts
    html.append("        <h2>Performance Visualizations</h2>")

    chart_files = [
        ("latest_comparison.png", "Latest Benchmark Results"),
        ("trend_analysis.png", "Performance Trends Over Time"),
    ]

    for filename, title in chart_files:
        if (REPORT_DIR / filename).exists():
            html.append("        <div class='chart-container'>")
            html.append(f"            <h3>{title}</h3>")
            html.append(f"            <img src='{filename}' alt='{title}' />")
            html.append("        </div>")

    # Add metric group charts
    html.append("        <h2>Metric Group Performance</h2>")
    for chart_file in sorted(REPORT_DIR.glob("group_*.png")):
        group_name = chart_file.stem.replace('group_', '').replace('_', ' ').title()
        html.append("        <div class='chart-container'>")
        html.append(f"            <h3>{group_name}</h3>")
        html.append(f"            <img src='{chart_file.name}' alt='{group_name}' />")
        html.append("        </div>")

    html.append("    </div>")
    html.append("</body>")
    html.append("</html>")

    with open(output_path, "w") as f:
        f.write("\n".join(html))


def main():
    """Main function to generate performance visualizations."""
    parser = argparse.ArgumentParser(description="Visualize performance data from performance.yml")
    parser.add_argument("--report", action="store_true",
                        help="Generate HTML report")
    parser.add_argument("--open", action="store_true",
                        help="Open HTML report in browser after generation")
    args = parser.parse_args()

    # Load performance data
    data = load_performance_data()

    if not data:
        print("No performance data found in performance.yml")
        return

    print(f"Loaded {len(data)} benchmark runs from {PERFORMANCE_YAML}")

    # Create output directory
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Extract metric series
    metric_series = extract_metric_series(data)
    print(f"Found {len(metric_series)} unique metrics")

    # Create latest comparison plot
    print("Creating latest comparison plot...")
    create_latest_comparison_plot(data, REPORT_DIR / "latest_comparison.png")

    # Create trend analysis plot
    if len(data) >= 2:
        print("Creating trend analysis plot...")
        create_trend_analysis_plot(metric_series, REPORT_DIR / "trend_analysis.png")
    else:
        print("Skipping trend analysis (need at least 2 benchmark runs)")

    # Group metrics and create plots for each group
    metric_groups = group_metrics(list(metric_series.keys()))
    print(f"Creating plots for {len(metric_groups)} metric groups...")

    for group_name, metric_names in metric_groups.items():
        # Only create plots for groups with time series data
        if any(len(metric_series.get(name, [])) >= 2 for name in metric_names):
            output_path = REPORT_DIR / f"group_{group_name}.png"
            create_metric_group_plot(metric_series, group_name, metric_names, output_path)
            print(f"  - Created {group_name} plot")

    # Generate HTML report
    if args.report or args.open:
        print("Generating HTML report...")
        report_path = REPORT_DIR / "performance_report.html"
        create_html_report(data, report_path)
        print(f"HTML report saved to {report_path}")

        if args.open:
            import webbrowser
            webbrowser.open(f"file://{report_path.resolve()}")

    print(f"\nAll visualizations saved to {REPORT_DIR}")


if __name__ == "__main__":
    main()
