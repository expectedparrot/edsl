#!/usr/bin/env python
"""
Memory Profiling Visualization Tool

This script visualizes memory profiling results from the ScenarioList.filter operation
to help identify memory usage patterns and optimization opportunities.
"""

import os
import json
import glob
import argparse
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from pathlib import Path

def load_memory_reports(directory="./benchmark_logs/memory_reports", function_name=None):
    """Load all memory report JSON files from the specified directory."""
    report_files = glob.glob(f"{directory}/*.json")
    
    # Filter by function name if specified
    if function_name:
        report_files = [f for f in report_files if function_name in f]
    
    reports = []
    for file_path in report_files:
        try:
            with open(file_path, 'r') as f:
                report = json.load(f)
                # Add the filename for reference
                report['file'] = os.path.basename(file_path)
                reports.append(report)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    # Sort by timestamp
    if reports:
        reports.sort(key=lambda x: x.get('timestamp', ''))
    
    return reports

def create_memory_report(reports, output_dir="./benchmark_logs/reports"):
    """Create visualizations of memory usage over time."""
    if not reports:
        print("No memory reports found.")
        return
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Convert reports to a DataFrame for easier analysis
    df = pd.DataFrame(reports)
    
    # Convert timestamp to datetime
    df['datetime'] = pd.to_datetime(df['timestamp'])
    
    # Create a figure with multiple subplots
    fig, axs = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('Memory Profiling Results', fontsize=16)
    
    # 1. Memory Usage Over Time
    ax1 = axs[0, 0]
    ax1.plot(df['datetime'], df['memory_before_mb'], 'b-', label='Before')
    ax1.plot(df['datetime'], df['memory_after_mb'], 'r-', label='After')
    ax1.fill_between(df['datetime'], df['memory_before_mb'], df['memory_after_mb'], color='r', alpha=0.3)
    ax1.set_title('Memory Usage Over Time')
    ax1.set_xlabel('Time')
    ax1.set_ylabel('Memory (MB)')
    ax1.legend()
    ax1.grid(True)
    
    # 2. Memory Difference
    ax2 = axs[0, 1]
    ax2.bar(df['datetime'], df['memory_diff_mb'], color='orange')
    ax2.set_title('Memory Difference (MB)')
    ax2.set_xlabel('Time')
    ax2.set_ylabel('Memory Difference (MB)')
    ax2.grid(True)
    
    # 3. Memory Difference vs Execution Time
    ax3 = axs[1, 0]
    scatter = ax3.scatter(df['execution_time_seconds'], df['memory_diff_mb'], 
                          c=range(len(df)), cmap='viridis', alpha=0.7, s=100)
    ax3.set_title('Memory Difference vs Execution Time')
    ax3.set_xlabel('Execution Time (seconds)')
    ax3.set_ylabel('Memory Difference (MB)')
    ax3.grid(True)
    
    # Add colorbar to show chronological order
    cbar = fig.colorbar(scatter, ax=ax3)
    cbar.set_label('Chronological Order')
    
    # 4. Memory Efficiency (ratio of memory diff to before memory)
    ax4 = axs[1, 1]
    memory_ratio = df['memory_diff_mb'] / df['memory_before_mb'] * 100
    ax4.bar(df['datetime'], memory_ratio, color='green')
    ax4.set_title('Memory Efficiency (% increase)')
    ax4.set_xlabel('Time')
    ax4.set_ylabel('Memory Increase (%)')
    ax4.grid(True)
    
    # Adjust layout and save figure
    plt.tight_layout(rect=[0, 0, 1, 0.95])
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = Path(output_dir) / f"memory_report_{timestamp}.png"
    plt.savefig(report_path)
    
    # Create a detailed HTML report
    html_report = create_html_report(df, reports)
    html_path = Path(output_dir) / f"memory_report_{timestamp}.html"
    with open(html_path, 'w') as f:
        f.write(html_report)
    
    print(f"Memory visualization saved to: {report_path}")
    print(f"Detailed HTML report saved to: {html_path}")
    
    return report_path, html_path

def create_html_report(df, reports):
    """Create a detailed HTML report from the memory profiling data."""
    # Generate timestamp for the report
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Start HTML content
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EDSL Memory Profiling Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        h1 {{
            border-bottom: 2px solid #eaecef;
            padding-bottom: 10px;
        }}
        .report-header {{
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .memory-change-positive {{
            color: #e74c3c;
        }}
        .memory-change-neutral {{
            color: #3498db;
        }}
        .chart-container {{
            width: 100%;
            max-width: 800px;
            margin: 20px auto;
        }}
        .footer {{
            margin-top: 40px;
            padding-top: 10px;
            border-top: 1px solid #eaecef;
            font-size: 0.9em;
            color: #6c757d;
        }}
    </style>
</head>
<body>
    <div class="report-header">
        <h1>EDSL Memory Profiling Report</h1>
        <p>Generated: {timestamp}</p>
        <p>Total reports analyzed: {len(reports)}</p>
        <p>Function profiled: {reports[0]['function'] if reports else 'Unknown'}</p>
    </div>

    <h2>Summary Statistics</h2>
    <table>
        <tr>
            <th>Metric</th>
            <th>Average</th>
            <th>Minimum</th>
            <th>Maximum</th>
            <th>Latest</th>
        </tr>
        <tr>
            <td>Execution Time (seconds)</td>
            <td>{df['execution_time_seconds'].mean():.4f}</td>
            <td>{df['execution_time_seconds'].min():.4f}</td>
            <td>{df['execution_time_seconds'].max():.4f}</td>
            <td>{df['execution_time_seconds'].iloc[-1]:.4f}</td>
        </tr>
        <tr>
            <td>Memory Before (MB)</td>
            <td>{df['memory_before_mb'].mean():.2f}</td>
            <td>{df['memory_before_mb'].min():.2f}</td>
            <td>{df['memory_before_mb'].max():.2f}</td>
            <td>{df['memory_before_mb'].iloc[-1]:.2f}</td>
        </tr>
        <tr>
            <td>Memory After (MB)</td>
            <td>{df['memory_after_mb'].mean():.2f}</td>
            <td>{df['memory_after_mb'].min():.2f}</td>
            <td>{df['memory_after_mb'].max():.2f}</td>
            <td>{df['memory_after_mb'].iloc[-1]:.2f}</td>
        </tr>
        <tr>
            <td>Memory Difference (MB)</td>
            <td>{df['memory_diff_mb'].mean():.2f}</td>
            <td>{df['memory_diff_mb'].min():.2f}</td>
            <td>{df['memory_diff_mb'].max():.2f}</td>
            <td>{df['memory_diff_mb'].iloc[-1]:.2f}</td>
        </tr>
        <tr>
            <td>Memory Increase (%)</td>
            <td>{(df['memory_diff_mb'] / df['memory_before_mb'] * 100).mean():.2f}%</td>
            <td>{(df['memory_diff_mb'] / df['memory_before_mb'] * 100).min():.2f}%</td>
            <td>{(df['memory_diff_mb'] / df['memory_before_mb'] * 100).max():.2f}%</td>
            <td>{(df['memory_diff_mb'].iloc[-1] / df['memory_before_mb'].iloc[-1] * 100):.2f}%</td>
        </tr>
    </table>

    <h2>All Reports (Chronological Order)</h2>
    <table>
        <tr>
            <th>Timestamp</th>
            <th>Memory Before (MB)</th>
            <th>Memory After (MB)</th>
            <th>Memory Diff (MB)</th>
            <th>Execution Time (s)</th>
        </tr>
"""

    # Add rows for each report
    for _, row in df.iterrows():
        memory_class = "memory-change-positive" if row['memory_diff_mb'] > 0 else "memory-change-neutral"
        html += f"""
        <tr>
            <td>{row['timestamp']}</td>
            <td>{row['memory_before_mb']:.2f}</td>
            <td>{row['memory_after_mb']:.2f}</td>
            <td class="{memory_class}">{row['memory_diff_mb']:.2f}</td>
            <td>{row['execution_time_seconds']:.4f}</td>
        </tr>"""

    # Add information about memory allocations
    html += """
    </table>

    <h2>Memory Allocation Hotspots</h2>
    <p>The following table shows the files that consistently appear in the top memory allocations:</p>
    <table>
        <tr>
            <th>File</th>
            <th>Frequency</th>
            <th>Average Size (KB)</th>
        </tr>
"""

    # Analyze top allocations across all reports
    allocation_files = {}
    allocation_sizes = {}
    
    for report in reports:
        for allocation in report.get('top_allocations', []):
            file = allocation.get('file', '').split(':')[0].strip()
            if file:
                allocation_files[file] = allocation_files.get(file, 0) + 1
                if file not in allocation_sizes:
                    allocation_sizes[file] = []
                allocation_sizes[file].append(allocation.get('size_kb', 0))
    
    # Sort by frequency
    sorted_files = sorted(allocation_files.items(), key=lambda x: x[1], reverse=True)
    
    # Add to HTML
    for file, frequency in sorted_files[:10]:  # Show top 10
        if file in allocation_sizes and allocation_sizes[file]:
            avg_size = sum(allocation_sizes[file]) / len(allocation_sizes[file])
            html += f"""
        <tr>
            <td>{file}</td>
            <td>{frequency} / {len(reports)} reports</td>
            <td>{avg_size:.2f}</td>
        </tr>"""
    
    # Finish HTML
    html += """
    </table>

    <h2>Recommendations</h2>
    <ul>
        <li>Focus optimizations on the files that consistently appear in top memory allocations</li>
        <li>Consider the memory-to-execution-time ratio when evaluating optimizations</li>
        <li>Watch for memory leaks (consistent increases in baseline memory usage)</li>
    </ul>

    <div class="footer">
        <p>EDSL Memory Profiling Tool</p>
    </div>
</body>
</html>
"""
    
    return html

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Memory Profiling Visualization Tool")
    parser.add_argument("--directory", "-d", default="./benchmark_logs/memory_reports",
                        help="Directory containing memory profiling JSON reports")
    parser.add_argument("--output", "-o", default="./benchmark_logs/reports",
                        help="Directory to save visualizations and reports")
    parser.add_argument("--function", "-f", default=None,
                        help="Filter reports by function name")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    reports = load_memory_reports(args.directory, args.function)
    create_memory_report(reports, args.output)