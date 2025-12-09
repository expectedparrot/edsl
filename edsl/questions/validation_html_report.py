"""Generate an HTML report for validation failures.

This module provides functionality to create an HTML report of validation failures,
including statistics, suggestions for improvements, and examples of common failures.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..config import CONFIG
from .validation_analysis import get_validation_failure_stats, suggest_fix_improvements
from .validation_logger import get_validation_failure_logs

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EDSL Validation Failures Report</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        h1, h2, h3, h4 {
            color: #2c3e50;
        }
        .header {
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
        }
        .summary {
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
        }
        .stats-container, .suggestions-container, .examples-container {
            margin-bottom: 30px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }
        th, td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background-color: #f8f9fa;
            font-weight: 600;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .suggestion {
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 0 4px 4px 0;
        }
        .card {
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        .card-header {
            font-weight: 600;
            margin-bottom: 10px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }
        .example {
            background-color: #fff8e1;
            border-left: 4px solid #ffc107;
            padding: 10px 15px;
            margin-bottom: 10px;
            border-radius: 0 4px 4px 0;
            overflow-x: auto;
        }
        pre {
            background-color: #f5f5f5;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }
        code {
            font-family: SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            font-size: 0.9em;
        }
        .badge {
            display: inline-block;
            padding: 3px 7px;
            font-size: 0.75em;
            font-weight: 600;
            line-height: 1;
            text-align: center;
            white-space: nowrap;
            vertical-align: baseline;
            border-radius: 10px;
            background-color: #e9ecef;
            margin-right: 5px;
        }
        .badge-warning {
            background-color: #fff3cd;
            color: #856404;
        }
        .badge-primary {
            background-color: #cfe2ff;
            color: #084298;
        }
        .badge-success {
            background-color: #d1e7dd;
            color: #0f5132;
        }
        .fix-method {
            background-color: #e8f5e9;
            border-left: 4px solid #4caf50;
            padding: 10px 15px;
            margin: 10px 0;
            border-radius: 0 4px 4px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>EDSL Validation Failures Report</h1>
        <span class="timestamp">Generated on {{timestamp}}</span>
    </div>
    
    <div class="summary">
        <h2>Summary</h2>
        <p>This report analyzes validation failures that occurred when question answers didn't meet the expected format or constraints. 
        It provides statistics, improvement suggestions for fix methods, and examples of common failures.</p>
        <p><strong>Total validation failures:</strong> {{total_failures}}</p>
        <p><strong>Question types with failures:</strong> {{question_types_count}}</p>
    </div>
    
    <div class="stats-container">
        <h2>Validation Failure Statistics</h2>
        
        <div class="card">
            <div class="card-header">Failures by Question Type</div>
            <table>
                <thead>
                    <tr>
                        <th>Question Type</th>
                        <th>Failure Count</th>
                        <th>Percentage</th>
                    </tr>
                </thead>
                <tbody>
                    {{type_stats_rows}}
                </tbody>
            </table>
        </div>
        
        <div class="card">
            <div class="card-header">Top Error Messages</div>
            <table>
                <thead>
                    <tr>
                        <th>Error Message</th>
                        <th>Occurrence Count</th>
                    </tr>
                </thead>
                <tbody>
                    {{error_stats_rows}}
                </tbody>
            </table>
        </div>
    </div>
    
    <div class="suggestions-container">
        <h2>Fix Method Improvement Suggestions</h2>
        {{suggestions_content}}
    </div>
    
    <div class="examples-container">
        <h2>Example Validation Failures</h2>
        {{examples_content}}
    </div>
</body>
</html>
"""


def _generate_type_stats_rows(stats: Dict) -> str:
    """Generate HTML table rows for question type statistics."""
    type_stats = stats.get("by_question_type", {})
    total_failures = sum(type_stats.values())

    rows = []
    for question_type, count in sorted(
        type_stats.items(), key=lambda x: x[1], reverse=True
    ):
        percentage = (count / total_failures) * 100 if total_failures > 0 else 0
        row = (
            f"<tr>"
            f"<td>{question_type}</td>"
            f"<td>{count}</td>"
            f"<td>{percentage:.1f}%</td>"
            f"</tr>"
        )
        rows.append(row)

    return "\n".join(rows)


def _generate_error_stats_rows(stats: Dict) -> str:
    """Generate HTML table rows for error message statistics."""
    error_counts = {}

    # Aggregate error counts across all question types
    for question_type, errors in stats.get("by_error_message", {}).items():
        for error_msg, count in errors.items():
            error_counts[error_msg] = error_counts.get(error_msg, 0) + count

    # Sort by count (descending)
    sorted_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)

    rows = []
    for error_msg, count in sorted_errors[:10]:  # Show top 10 errors
        shortened_msg = error_msg[:100] + "..." if len(error_msg) > 100 else error_msg
        row = f"<tr>" f"<td>{shortened_msg}</td>" f"<td>{count}</td>" f"</tr>"
        rows.append(row)

    return "\n".join(rows)


def _generate_suggestions_content(suggestions: Dict) -> str:
    """Generate HTML content for fix method suggestions."""
    if not suggestions:
        return "<p>No suggestions available. Log more validation failures to generate improvement suggestions.</p>"

    content = []

    for question_type, question_suggestions in suggestions.items():
        content.append("<div class='card'>")
        content.append(f"<div class='card-header'>{question_type}</div>")

        for suggestion in question_suggestions:
            error_msg = suggestion.get("error_message", "")
            occurrence_count = suggestion.get("occurrence_count", 0)
            suggestion_text = suggestion.get("suggestion", "")

            content.append(
                f"<div class='suggestion'>"
                f"<p><strong>Error:</strong> {error_msg}</p>"
                f"<p><strong>Occurrences:</strong> {occurrence_count}</p>"
                f"<div class='fix-method'>"
                f"<p><strong>Suggested improvement:</strong></p>"
                f"<p>{suggestion_text}</p>"
                f"</div>"
                f"</div>"
            )

        content.append("</div>")

    return "\n".join(content)


def _generate_examples_content(logs: List[Dict]) -> str:
    """Generate HTML content for example validation failures."""
    if not logs:
        return "<p>No validation failure examples available.</p>"

    content = []

    # Group logs by question type
    logs_by_type = {}
    for log in logs:
        question_type = log.get("question_type", "unknown")
        if question_type not in logs_by_type:
            logs_by_type[question_type] = []
        logs_by_type[question_type].append(log)

    # For each question type, show the most recent example
    for question_type, type_logs in logs_by_type.items():
        # Sort by timestamp (newest first)
        sorted_logs = sorted(
            type_logs, key=lambda x: x.get("timestamp", ""), reverse=True
        )
        example_log = sorted_logs[0]

        error_message = example_log.get("error_message", "")
        invalid_data = example_log.get("invalid_data", {})
        model_schema = example_log.get("model_schema", {})

        content.append("<div class='card'>")
        content.append(f"<div class='card-header'>{question_type}</div>")

        content.append(
            f"<div class='example'>"
            f"<p><strong>Error:</strong> {error_message}</p>"
            f"<p><strong>Invalid Data:</strong></p>"
            f"<pre><code>{json.dumps(invalid_data, indent=2)}</code></pre>"
            f"<p><strong>Expected Schema:</strong></p>"
            f"<pre><code>{json.dumps(model_schema, indent=2)}</code></pre>"
            f"</div>"
        )

        content.append("</div>")

    return "\n".join(content)


def generate_html_report(output_path: Optional[Path] = None) -> Path:
    """
    Generate an HTML report of validation failures.

    Args:
        output_path: Optional custom path for the report

    Returns:
        Path to the generated HTML report
    """
    # Determine output path
    if output_path is None:
        default_log_dir = Path.home() / ".edsl" / "logs"
        try:
            report_dir = Path(CONFIG.get("EDSL_LOG_DIR"))
        except Exception:
            # If EDSL_LOG_DIR is not defined, use default
            report_dir = default_log_dir
        os.makedirs(report_dir, exist_ok=True)
        output_path = report_dir / "validation_report.html"

    # Get validation data
    logs = get_validation_failure_logs(n=100)  # Get up to 100 recent logs
    stats = get_validation_failure_stats()
    suggestions = suggest_fix_improvements()

    # Calculate summary statistics
    total_failures = sum(stats.get("by_question_type", {}).values())
    question_types_count = len(stats.get("by_question_type", {}))

    # Generate report content
    type_stats_rows = _generate_type_stats_rows(stats)
    error_stats_rows = _generate_error_stats_rows(stats)
    suggestions_content = _generate_suggestions_content(suggestions)
    examples_content = _generate_examples_content(logs)

    # Format timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Fill the template
    html_content = HTML_TEMPLATE.replace("{{timestamp}}", timestamp)
    html_content = html_content.replace("{{total_failures}}", str(total_failures))
    html_content = html_content.replace(
        "{{question_types_count}}", str(question_types_count)
    )
    html_content = html_content.replace("{{type_stats_rows}}", type_stats_rows)
    html_content = html_content.replace("{{error_stats_rows}}", error_stats_rows)
    html_content = html_content.replace("{{suggestions_content}}", suggestions_content)
    html_content = html_content.replace("{{examples_content}}", examples_content)

    # Write the report
    with open(output_path, "w") as f:
        f.write(html_content)

    return output_path


def generate_and_open_report() -> None:
    """Generate a validation report and open it in the default browser."""
    report_path = generate_html_report()
    print(f"Report generated at: {report_path}")

    # Try to open the report in a browser
    try:
        import webbrowser

        webbrowser.open(f"file://{report_path}")
    except Exception as e:
        print(f"Could not open browser: {e}")
        print(f"Report is available at: {report_path}")


if __name__ == "__main__":
    generate_and_open_report()
