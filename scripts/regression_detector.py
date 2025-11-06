#!/usr/bin/env python
"""
Performance Regression Detector

This script analyzes performance.yml to detect performance regressions.
It creates a visualization showing all metrics across runs, with the current
run highlighted to make regressions immediately visible.
"""

import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
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


def calculate_performance_changes(data: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    Calculate performance changes from historical average for all metrics.
    Returns dict mapping metric names to dict with pct_change and abs_change.
    """
    if len(data) < 2:
        return {}

    changes = {}
    latest = data[-1]
    latest_metrics = latest.get("metrics", {})

    # Calculate historical averages (excluding latest run)
    metric_history = {}
    for entry in data[:-1]:
        for metric_name, value in entry.get("metrics", {}).items():
            if isinstance(value, (int, float)):
                if metric_name not in metric_history:
                    metric_history[metric_name] = []
                metric_history[metric_name].append(value)

    # Calculate percentage and absolute change for each metric
    for metric_name, latest_value in latest_metrics.items():
        if not isinstance(latest_value, (int, float)):
            continue

        if metric_name in metric_history and len(metric_history[metric_name]) > 0:
            historical_avg = np.mean(metric_history[metric_name])
            abs_change = latest_value - historical_avg
            pct_change = (abs_change / historical_avg) * 100 if historical_avg > 0 else 0

            changes[metric_name] = {
                'pct_change': pct_change,
                'abs_change': abs_change,
                'latest_value': latest_value,
                'historical_avg': historical_avg
            }

    return changes


def create_regression_heatmap(data: List[Dict[str, Any]], output_path: Path):
    """
    Create a heatmap showing all metrics across all runs.
    Current run is highlighted to make regressions visible.
    """
    if not data:
        return

    # Extract all metrics and their values across runs
    all_metrics = set()
    for entry in data:
        all_metrics.update(entry.get("metrics", {}).keys())

    # Filter to only numeric metrics
    numeric_metrics = []
    for metric in sorted(all_metrics):
        if any(isinstance(entry.get("metrics", {}).get(metric), (int, float)) for entry in data):
            numeric_metrics.append(metric)

    if not numeric_metrics:
        return

    # Limit to top N most variable metrics to keep plot readable
    max_metrics = 30
    if len(numeric_metrics) > max_metrics:
        # Calculate variance for each metric
        metric_variances = {}
        for metric in numeric_metrics:
            values = []
            for entry in data:
                val = entry.get("metrics", {}).get(metric)
                if isinstance(val, (int, float)):
                    values.append(val)
            if len(values) > 1:
                metric_variances[metric] = np.var(values)

        # Take metrics with highest variance
        top_metrics = sorted(metric_variances.items(), key=lambda x: x[1], reverse=True)[:max_metrics]
        numeric_metrics = [m for m, _ in top_metrics]

    # Create matrix of values
    matrix = []
    run_labels = []

    for i, entry in enumerate(data):
        timestamp = entry.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(timestamp)
            label = dt.strftime("%m/%d %H:%M")
        except:
            label = f"Run {i+1}"

        run_labels.append(label)

        row = []
        for metric in numeric_metrics:
            val = entry.get("metrics", {}).get(metric)
            if isinstance(val, (int, float)):
                row.append(val)
            else:
                row.append(np.nan)
        matrix.append(row)

    matrix = np.array(matrix).T  # Transpose so metrics are rows

    # Normalize each metric row to show relative performance (0-1 scale)
    normalized_matrix = np.zeros_like(matrix)
    for i in range(matrix.shape[0]):
        row = matrix[i, :]
        valid_vals = row[~np.isnan(row)]
        if len(valid_vals) > 0:
            min_val = np.min(valid_vals)
            max_val = np.max(valid_vals)
            if max_val > min_val:
                normalized_matrix[i, :] = (row - min_val) / (max_val - min_val)
            else:
                normalized_matrix[i, :] = 0.5

    # Create figure
    fig, ax = plt.subplots(figsize=(max(12, len(run_labels) * 0.8), max(10, len(numeric_metrics) * 0.4)))

    # Create heatmap with green (fast) to red (slow) colormap
    im = ax.imshow(normalized_matrix, aspect='auto', cmap='RdYlGn_r', interpolation='nearest')

    # Set ticks and labels
    ax.set_xticks(np.arange(len(run_labels)))
    ax.set_yticks(np.arange(len(numeric_metrics)))
    ax.set_xticklabels(run_labels, rotation=45, ha='right')
    ax.set_yticklabels([m.replace('_', ' ') for m in numeric_metrics], fontsize=9)

    # Highlight the current (latest) run
    current_run_idx = len(run_labels) - 1
    for i in range(len(numeric_metrics)):
        rect = mpatches.Rectangle((current_run_idx - 0.5, i - 0.5), 1, 1,
                                   fill=False, edgecolor='blue', linewidth=3)
        ax.add_patch(rect)

    # Add actual values as text (only for current run)
    for i, metric in enumerate(numeric_metrics):
        val = matrix[i, current_run_idx]
        if not np.isnan(val):
            # Use white or black text depending on background
            text_color = 'white' if normalized_matrix[i, current_run_idx] > 0.5 else 'black'
            ax.text(current_run_idx, i, f'{val:.3f}', ha='center', va='center',
                   color=text_color, fontweight='bold', fontsize=8)

    ax.set_title('Performance Regression Heatmap\n(Blue border = Current Run, Green = Fast, Red = Slow)',
                fontsize=14, fontweight='bold', pad=20)
    ax.set_xlabel('Benchmark Runs', fontsize=12)
    ax.set_ylabel('Metrics', fontsize=12)

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label('Relative Performance (0=best, 1=worst)', rotation=270, labelpad=20)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()


def create_metric_line_graphs(data: List[Dict[str, Any]], output_dir: Path):
    """Create individual line graphs for each metric showing trend over time."""
    if not data:
        return []

    # Extract all metrics
    all_metrics = set()
    for entry in data:
        all_metrics.update(entry.get("metrics", {}).keys())

    # Filter to numeric metrics
    numeric_metrics = []
    for metric in sorted(all_metrics):
        if any(isinstance(entry.get("metrics", {}).get(metric), (int, float)) for entry in data):
            numeric_metrics.append(metric)

    if not numeric_metrics:
        return []

    created_charts = []

    # Create a line graph for each metric
    for metric in numeric_metrics:
        run_numbers = []
        values = []

        for idx, entry in enumerate(data, start=1):
            val = entry.get("metrics", {}).get(metric)
            if isinstance(val, (int, float)):
                run_numbers.append(idx)
                values.append(val)

        if len(values) < 2:
            continue

        # Create figure
        fig, ax = plt.subplots(figsize=(10, 4))

        # Plot line
        ax.plot(run_numbers, values, 'o-', linewidth=2, markersize=8,
                color='steelblue', markeredgecolor='darkblue', markeredgewidth=1.5)

        # Highlight the latest point
        if len(run_numbers) > 0:
            ax.plot(run_numbers[-1], values[-1], 'o', markersize=12,
                   color='red', markeredgecolor='darkred', markeredgewidth=2,
                   label='Current Run', zorder=5)

        # Add horizontal line for mean (excluding current run)
        if len(values) > 1:
            historical_mean = np.mean(values[:-1])
            ax.axhline(y=historical_mean, color='gray', linestyle='--',
                      linewidth=1, alpha=0.7, label=f'Historical Avg: {historical_mean:.3f}s')

        # Styling
        metric_display = metric.replace('_', ' ').title()
        ax.set_title(f'{metric_display}', fontsize=12, fontweight='bold')
        ax.set_ylabel('Time (seconds)', fontsize=10)
        ax.set_xlabel('Run Number', fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=9)

        # Set x-axis to show integer run numbers
        ax.set_xticks(run_numbers)
        ax.set_xticklabels([str(r) for r in run_numbers])

        # Add value annotations
        for i, (run_num, val) in enumerate(zip(run_numbers, values)):
            # Only annotate first, last, and any outliers
            is_outlier = len(values) > 1 and (val > np.mean(values) + np.std(values) or
                                              val < np.mean(values) - np.std(values))
            if i == 0 or i == len(values) - 1 or is_outlier:
                offset = 10 if i == len(values) - 1 else 5
                ax.annotate(f'{val:.3f}s', (run_num, val),
                           textcoords="offset points", xytext=(0, offset),
                           ha='center', fontsize=8,
                           fontweight='bold' if i == len(values) - 1 else 'normal',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow' if i == len(values) - 1 else 'white',
                                   alpha=0.8, edgecolor='red' if i == len(values) - 1 else 'gray'))

        plt.tight_layout()

        # Save the figure
        chart_filename = f'metric_{metric}.png'
        chart_path = output_dir / chart_filename
        plt.savefig(chart_path, dpi=100, bbox_inches='tight')
        plt.close()

        created_charts.append({
            'metric': metric,
            'filename': chart_filename,
            'display_name': metric_display
        })

    return created_charts


def create_regression_table_html(data: List[Dict[str, Any]], perf_changes: Dict[str, Dict]) -> str:
    """Create HTML table showing metrics across runs with current run highlighted."""
    if not data:
        return ""

    # Get all metrics that appear in at least one run
    all_metrics = set()
    for entry in data:
        all_metrics.update(entry.get("metrics", {}).keys())

    # Filter to numeric metrics only
    numeric_metrics = sorted([m for m in all_metrics
                             if any(isinstance(entry.get("metrics", {}).get(m), (int, float))
                                   for entry in data)])

    if not numeric_metrics:
        return "<p>No numeric metrics found.</p>"

    # Limit to top 20 metrics for readability (prioritize by latest value)
    if len(numeric_metrics) > 20:
        priority_metrics = []
        for m in numeric_metrics:
            latest_val = data[-1].get("metrics", {}).get(m, 0)
            priority_metrics.append((m, latest_val))

        priority_metrics.sort(key=lambda x: x[1], reverse=True)
        numeric_metrics = [m for m, _ in priority_metrics[:20]]

    html = []
    html.append("<table class='regression-table'>")

    # Header row
    html.append("  <thead>")
    html.append("    <tr>")
    html.append("      <th>Metric</th>")

    for i, entry in enumerate(data):
        timestamp = entry.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(timestamp)
            label = dt.strftime("%m/%d<br/>%H:%M")
        except:
            label = f"Run<br/>{i+1}"

        is_current = (i == len(data) - 1)
        cell_class = "current-run" if is_current else ""
        html.append(f"      <th class='{cell_class}'>{label}</th>")

    html.append("    </tr>")
    html.append("  </thead>")

    # Data rows
    html.append("  <tbody>")
    for metric in numeric_metrics:
        change_info = perf_changes.get(metric, {})
        pct_change = change_info.get('pct_change', 0)
        abs_change = change_info.get('abs_change', 0)

        row_class = "regression-row" if pct_change > 10 else ""
        html.append(f"    <tr class='{row_class}'>")

        # Metric name with change indicator
        metric_display = metric.replace('_', ' ')
        if pct_change > 10:
            metric_display = f"⚠️ {metric_display} (+{pct_change:.1f}%, +{abs_change:.3f}s)"
        elif pct_change < -10:
            metric_display = f"✓ {metric_display} ({pct_change:.1f}%, {abs_change:.3f}s)"

        html.append(f"      <td class='metric-name'>{metric_display}</td>")

        # Values for each run
        values = []
        for entry in data:
            val = entry.get("metrics", {}).get(metric)
            if isinstance(val, (int, float)):
                values.append(val)
            else:
                values.append(None)

        # Calculate average of historical runs (exclude current)
        historical_values = [v for v in values[:-1] if v is not None]
        avg = np.mean(historical_values) if historical_values else None

        for i, val in enumerate(values):
            is_current = (i == len(values) - 1)
            cell_class = "current-run"

            if val is not None:
                # Color code based on performance vs average
                if avg and val > avg * 1.1:
                    cell_class += " slow"
                elif avg and val < avg * 0.9:
                    cell_class += " fast"

                if is_current and perf_changes.get(metric, {}).get('pct_change', 0) > 10:
                    cell_class += " regression"

                display_val = f"{val:.4f}" if val < 0.01 else f"{val:.3f}"
                html.append(f"      <td class='{cell_class}'>{display_val}</td>")
            else:
                html.append(f"      <td class='{cell_class}'>-</td>")

        html.append("    </tr>")

    html.append("  </tbody>")
    html.append("</table>")

    return "\n".join(html)


def create_regression_report(data: List[Dict[str, Any]], perf_changes: Dict[str, Dict],
                            line_charts: List[Dict], output_path: Path):
    """Create comprehensive HTML report focused on regression detection."""
    latest = data[-1] if data else {}

    html = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        "    <meta charset='UTF-8'>",
        "    <title>EDSL Performance Regression Report</title>",
        "    <style>",
        "        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; background-color: #f5f5f5; }",
        "        .container { max-width: 1400px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        "        h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }",
        "        h2 { color: #34495e; margin-top: 30px; border-bottom: 2px solid #ecf0f1; padding-bottom: 8px; }",
        "        .alert { background-color: #fff3cd; border: 2px solid #ffc107; border-radius: 5px; padding: 15px; margin: 20px 0; }",
        "        .alert.success { background-color: #d4edda; border-color: #28a745; }",
        "        .alert h3 { margin-top: 0; color: #856404; }",
        "        .alert.success h3 { color: #155724; }",
        "        .regression-table { width: 100%; border-collapse: collapse; font-size: 13px; margin: 20px 0; }",
        "        .regression-table th, .regression-table td { border: 1px solid #ddd; padding: 8px; text-align: right; }",
        "        .regression-table th { background-color: #f2f2f2; position: sticky; top: 0; }",
        "        .regression-table td.metric-name { text-align: left; font-weight: 500; }",
        "        .regression-table .current-run { background-color: #e3f2fd; font-weight: bold; }",
        "        .regression-table .regression { background-color: #ffebee; color: #c62828; }",
        "        .regression-table .fast { color: #2e7d32; }",
        "        .regression-table .slow { color: #d84315; }",
        "        .regression-table tr.regression-row { background-color: #fff3e0; }",
        "        .chart-container { margin: 30px 0; text-align: center; }",
        "        .chart-container img { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }",
        "        .summary { background-color: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }",
        "        .summary-item { margin: 10px 0; font-size: 16px; }",
        "        .summary-item strong { color: #2c3e50; }",
        "        .legend { margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }",
        "        .legend-item { display: inline-block; margin-right: 20px; }",
        "        .legend-box { display: inline-block; width: 20px; height: 20px; margin-right: 5px; vertical-align: middle; border: 1px solid #999; }",
        "    </style>",
        "</head>",
        "<body>",
        "    <div class='container'>",
        "        <h1>🔍 Performance Regression Report</h1>",
        f"        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>",
    ]

    # Performance changes summary
    increases = {m: info for m, info in perf_changes.items() if info.get('pct_change', 0) > 10}
    decreases = {m: info for m, info in perf_changes.items() if info.get('pct_change', 0) < -10}

    if increases:
        html.append("        <div class='alert'>")
        html.append(f"            <h3>📈 {len(increases)} Metric(s) Increased Significantly</h3>")
        html.append("            <ul>")
        for metric, info in sorted(increases.items(), key=lambda x: x[1]['pct_change'], reverse=True):
            pct = info['pct_change']
            abs_val = info['abs_change']
            html.append(f"                <li><strong>{metric.replace('_', ' ')}</strong>: "
                       f"↑{pct:.1f}% (+{abs_val:.3f}s)</li>")
        html.append("            </ul>")
        html.append("        </div>")

    if decreases:
        html.append("        <div class='alert success'>")
        html.append(f"            <h3>✅ {len(decreases)} Metric(s) Improved Significantly</h3>")
        html.append("            <ul>")
        for metric, info in sorted(decreases.items(), key=lambda x: x[1]['pct_change']):
            pct = info['pct_change']
            abs_val = info['abs_change']
            html.append(f"                <li><strong>{metric.replace('_', ' ')}</strong>: "
                       f"{pct:.1f}% ({abs_val:.3f}s)</li>")
        html.append("            </ul>")
        html.append("        </div>")

    if not increases and not decreases:
        html.append("        <div class='alert success'>")
        html.append("            <h3>✅ Performance Stable</h3>")
        html.append("            <p>All metrics are within expected ranges compared to historical performance.</p>")
        html.append("        </div>")

    # Summary statistics
    html.append("        <div class='summary'>")
    html.append("            <h2>Run Summary</h2>")
    html.append(f"            <div class='summary-item'><strong>Total Runs in History:</strong> {len(data)}</div>")
    html.append(f"            <div class='summary-item'><strong>Current Run:</strong> {latest.get('timestamp', 'N/A')}</div>")
    html.append(f"            <div class='summary-item'><strong>EDSL Version:</strong> {latest.get('edsl_version', 'unknown')}</div>")
    html.append(f"            <div class='summary-item'><strong>Metrics Tracked:</strong> {len(latest.get('metrics', {}))}</div>")
    html.append("        </div>")

    # Legend
    html.append("        <div class='legend'>")
    html.append("            <strong>Legend:</strong> ")
    html.append("            <span class='legend-item'><span class='legend-box' style='background-color: #e3f2fd;'></span>Current Run</span>")
    html.append("            <span class='legend-item'><span class='legend-box' style='background-color: #ffebee;'></span>Regression</span>")
    html.append("            <span class='legend-item'><span style='color: #d84315;'>●</span> Slower than avg</span>")
    html.append("            <span class='legend-item'><span style='color: #2e7d32;'>●</span> Faster than avg</span>")
    html.append("        </div>")

    # Performance table
    html.append("        <h2>Performance Metrics Across Runs</h2>")
    html.append("        <p>Current run is highlighted in blue. Scroll right to see all runs.</p>")
    html.append("        <div style='overflow-x: auto;'>")
    html.append(create_regression_table_html(data, perf_changes))
    html.append("        </div>")

    # Heatmap
    html.append("        <h2>Visual Analysis - Heatmap</h2>")
    html.append("        <div class='chart-container'>")
    html.append("            <img src='regression_heatmap.png' alt='Regression Heatmap' />")
    html.append("        </div>")

    # Line graphs for each metric
    if line_charts:
        html.append("        <h2>Metric Trends Over Time</h2>")
        html.append("        <p>Each graph shows the trend for a specific metric. "
                   "The current run is highlighted in red, and the gray dashed line shows the historical average.</p>")

        for chart_info in line_charts:
            html.append("        <div class='chart-container'>")
            html.append(f"            <h3>{chart_info['display_name']}</h3>")
            html.append(f"            <img src='{chart_info['filename']}' alt='{chart_info['display_name']}' />")
            html.append("        </div>")

    html.append("    </div>")
    html.append("</body>")
    html.append("</html>")

    with open(output_path, "w") as f:
        f.write("\n".join(html))


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Visualize performance across runs from performance.yml")
    parser.add_argument("--open", action="store_true",
                       help="Open HTML report in browser after generation")
    args = parser.parse_args()

    # Load performance data
    data = load_performance_data()

    if not data:
        print("No performance data found in performance.yml")
        return 0

    print(f"Loaded {len(data)} benchmark runs from {PERFORMANCE_YAML}")

    # Create output directory
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Calculate performance changes (with both percentage and absolute values)
    perf_changes = calculate_performance_changes(data)

    # Show summary
    increases = {m: info for m, info in perf_changes.items() if info.get('pct_change', 0) > 10}
    decreases = {m: info for m, info in perf_changes.items() if info.get('pct_change', 0) < -10}

    if increases:
        print(f"\n📈 {len(increases)} metric(s) increased >10%:")
        for metric, info in sorted(increases.items(), key=lambda x: x[1]['pct_change'], reverse=True)[:5]:
            pct = info['pct_change']
            abs_val = info['abs_change']
            print(f"  - {metric}: ↑{pct:.1f}% (+{abs_val:.3f}s)")

    if decreases:
        print(f"\n✅ {len(decreases)} metric(s) improved >10%:")
        for metric, info in sorted(decreases.items(), key=lambda x: x[1]['pct_change'])[:5]:
            pct = info['pct_change']
            abs_val = info['abs_change']
            print(f"  - {metric}: {pct:.1f}% ({abs_val:.3f}s)")

    # Create visualizations
    print("\nGenerating performance heatmap...")
    heatmap_path = REPORT_DIR / "regression_heatmap.png"
    create_regression_heatmap(data, heatmap_path)
    print(f"Heatmap saved to {heatmap_path}")

    # Create line graphs for each metric
    print("Generating line graphs for each metric...")
    line_charts = create_metric_line_graphs(data, REPORT_DIR)
    print(f"Created {len(line_charts)} line graphs")

    # Create HTML report
    print("Generating HTML report...")
    report_path = REPORT_DIR / "regression_report.html"
    create_regression_report(data, perf_changes, line_charts, report_path)
    print(f"Report saved to {report_path}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{report_path.resolve()}")

    return 0


if __name__ == "__main__":
    exit(main())
