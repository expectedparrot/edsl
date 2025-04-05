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
        <p>Function profiled: {reports[0].get('function', reports[0].get('file', 'Unknown')) if reports else 'Unknown'}</p>
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
    <style>
        .copy-button {
            background-color: #f1f1f1;
            border: none;
            color: #333;
            padding: 4px 8px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 12px;
            margin: 2px 2px;
            cursor: pointer;
            border-radius: 4px;
        }
        .copy-button:hover {
            background-color: #ddd;
        }
        .tooltip {
            position: relative;
            display: inline-block;
        }
        .tooltip .tooltiptext {
            visibility: hidden;
            width: 140px;
            background-color: #555;
            color: #fff;
            text-align: center;
            border-radius: 6px;
            padding: 5px;
            position: absolute;
            z-index: 1;
            bottom: 150%;
            left: 50%;
            margin-left: -75px;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .tooltip .tooltiptext::after {
            content: "";
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -5px;
            border-width: 5px;
            border-style: solid;
            border-color: #555 transparent transparent transparent;
        }
        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
    </style>
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                // Show tooltip
                var tooltip = event.currentTarget.querySelector('.tooltiptext');
                tooltip.innerHTML = "Copied!";
                setTimeout(function() {
                    tooltip.innerHTML = "Copy to clipboard";
                }, 1500);
            }, function(err) {
                console.error('Could not copy text: ', err);
            });
        }
    </script>
    <table>
        <tr>
            <th>File</th>
            <th>Frequency</th>
            <th>Average Size (KB)</th>
            <th>Actions</th>
        </tr>
"""

    # Analyze top allocations across all reports
    allocation_files = {}
    allocation_sizes = {}
    allocation_lines = {}
    
    for report in reports:
        for allocation in report.get('top_allocations', []):
            file_info = allocation.get('file', '')
            file = file_info.split(':')[0].strip()
            
            # Extract line number if available
            line_num = None
            if "line" in file_info:
                try:
                    line_num = int(file_info.split("line")[1].strip())
                except:
                    pass
                
            if file:
                allocation_files[file] = allocation_files.get(file, 0) + 1
                if file not in allocation_sizes:
                    allocation_sizes[file] = []
                allocation_sizes[file].append(allocation.get('size_kb', 0))
                
                # Store line numbers
                if line_num and file not in allocation_lines:
                    allocation_lines[file] = line_num
    
    # Sort by frequency
    sorted_files = sorted(allocation_files.items(), key=lambda x: x[1], reverse=True)
    
    # Add to HTML
    for file, frequency in sorted_files[:10]:  # Show top 10
        if file in allocation_sizes and allocation_sizes[file]:
            avg_size = sum(allocation_sizes[file]) / len(allocation_sizes[file])
            
            # Get line number for display
            line_info = ""
            if file in allocation_lines:
                line_info = f" line {allocation_lines[file]}"
                
            # Clean file path for display
            display_path = file.replace("  File \"", "").replace("\"", "")
            
            # Full path for copy button
            copy_path = display_path
            if file in allocation_lines:
                copy_path = f"{display_path}:{allocation_lines[file]}"
                
            html += f"""
        <tr>
            <td>{display_path}{line_info}</td>
            <td>{frequency} / {len(reports)} reports</td>
            <td>{avg_size:.2f}</td>
            <td>
                <div class="tooltip">
                    <button class="copy-button" onclick="copyToClipboard('{copy_path}')">
                        Copy Path
                        <span class="tooltiptext">Copy to clipboard</span>
                    </button>
                </div>
            </td>
        </tr>"""
    
    # Finish HTML
    html += """
    </table>
    
    <h2>Line-by-Line Memory Allocation Details</h2>
    <p>The following table shows detailed memory allocations by line from the most recent report:</p>
    <table id="line-details">
        <tr>
            <th>Rank</th>
            <th>File & Line</th>
            <th>Size (KB)</th>
            <th>Actions</th>
        </tr>
    """
    
    # Add detailed line-by-line information from the most recent report
    if reports:
        latest_report = reports[-1]
        for i, allocation in enumerate(latest_report.get('top_allocations', []), 1):
            file_info = allocation.get('file', '')
            size_kb = allocation.get('size_kb', 0)
            
            # Clean up the file path for display
            display_path = file_info.replace("  File \"", "").replace("\"", "")
            
            # Extract path and line for the copy button
            path_for_copy = display_path
            if "line" in display_path:
                parts = display_path.split("line")
                file_path = parts[0].strip()
                line_num = parts[1].strip() if len(parts) > 1 else ""
                path_for_copy = f"{file_path.strip()}:{line_num}"
            
            html += f"""
        <tr class="allocation-row">
            <td>{i}</td>
            <td>{display_path}</td>
            <td>{size_kb:.2f}</td>
            <td>
                <div class="tooltip">
                    <button class="copy-button" onclick="copyToClipboard('{path_for_copy}')">
                        Copy Path
                        <span class="tooltiptext">Copy to clipboard</span>
                    </button>
                </div>
            </td>
        </tr>"""
    
    html += """
    </table>
    
    <h3>Detailed Source View</h3>
    <p>For the top memory allocation points, here's the surrounding code context:</p>
    <div id="source-display">
    """
    
    # Add line content for the top allocations if available
    if reports:
        latest_report = reports[-1]
        top_allocations = latest_report.get('top_allocations', [])
        
        # Only process the first 3 (most significant) allocations
        for i, allocation in enumerate(top_allocations[:3], 1):
            file_info = allocation.get('file', '')
            size_kb = allocation.get('size_kb', 0)
            
            # Extract file path and line number
            if "line" in file_info:
                try:
                    file_path = file_info.split("line")[0].replace("  File \"", "").replace("\"", "").strip()
                    line_num = int(file_info.split("line")[1].strip())
                    
                    # Try to read source file if it exists
                    try:
                        import linecache
                        
                        html += f"""
        <div class="source-section">
            <h4>{i}. {file_path} line {line_num} ({size_kb:.2f} KB)</h4>
            <pre class="source-code">"""
                        
                        # Show 5 lines before and after
                        start_line = max(1, line_num - 5)
                        end_line = line_num + 5
                        
                        for l in range(start_line, end_line + 1):
                            line = linecache.getline(file_path, l).rstrip()
                            # Highlight the specific line
                            if l == line_num:
                                html += f'<span class="highlight-line">{l}: {line}</span>\n'
                            else:
                                html += f'{l}: {line}\n'
                        
                        html += """</pre>
            <div class="tooltip">
                <button class="copy-button" onclick="copyToClipboard('{file_path}:{line_num}')">
                    Copy Path
                    <span class="tooltiptext">Copy to clipboard</span>
                </button>
            </div>
        </div>"""
                    except Exception as e:
                        html += f"<p>Could not read source: {e}</p>"
                except Exception:
                    # If we can't parse the line number, just show the file info
                    html += f"<p>{file_info} - {size_kb:.2f} KB</p>"
            else:
                html += f"<p>{file_info} - {size_kb:.2f} KB</p>"
    
    html += """
    </div>

    <style>
    .source-section {
        margin: 20px 0;
        padding: 15px;
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 5px;
    }
    .source-code {
        background-color: #f5f5f5;
        padding: 10px;
        border-radius: 4px;
        font-family: monospace;
        white-space: pre;
        overflow-x: auto;
    }
    .highlight-line {
        background-color: #ffeb3b;
        font-weight: bold;
        display: block;
    }
    .allocation-row:nth-child(-n+3) {
        background-color: rgba(255, 235, 59, 0.2);
    }
    </style>

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