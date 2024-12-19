import os
import glob
from pydocstyle import check
from datetime import datetime


def create_html_report(filename, violations):
    """Create an HTML report for a single file's pydocstyle violations."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>PyDocStyle Report - {filename}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .violation {{ 
                background-color: #f8f8f8;
                border-left: 4px solid #e74c3c;
                margin: 10px 0;
                padding: 10px;
            }}
            .violation-code {{ 
                font-weight: bold;
                color: #c0392b;
            }}
            .file-info {{
                background-color: #eee;
                padding: 10px;
                margin-bottom: 20px;
            }}
            .timestamp {{
                color: #666;
                font-size: 0.9em;
            }}
        </style>
    </head>
    <body>
        <div class="file-info">
            <h2>PyDocStyle Report</h2>
            <p>File: {filename}</p>
            <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><a href="index.html">Back to Index</a></p>
        </div>
    """

    if not violations:
        html_content += "<p>✅ No documentation style violations found!</p>"
    else:
        html_content += f"<h3>Found {len(violations)} violation(s):</h3>"
        for violation in violations:
            html_content += f"""
            <div class="violation">
                <p><span class="violation-code">{violation.code}</span> at line {violation.line}</p>
                <p>{violation.message}</p>
                <pre><code>{violation.source}</code></pre>
            </div>
            """

    html_content += """
    </body>
    </html>
    """
    return html_content


def create_index_html(file_reports, output_dir):
    """Create an index.html with a summary table of all reports."""
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>PyDocStyle Reports Index</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            th, td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f5f5f5;
            }}
            tr:hover {{
                background-color: #f8f8f8;
            }}
            .error-count {{
                font-weight: bold;
                color: #e74c3c;
            }}
            .no-errors {{
                color: #27ae60;
            }}
            .summary {{
                background-color: #eee;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 4px;
            }}
        </style>
    </head>
    <body>
        <h1>PyDocStyle Reports Index</h1>
        <div class="summary">
            <p>Generated: {}</p>
            <p>Total files analyzed: {}</p>
            <p>Total violations found: {}</p>
        </div>
        <table>
            <thead>
                <tr>
                    <th>File Path</th>
                    <th>Violations</th>
                </tr>
            </thead>
            <tbody>
    """
    html_content = template.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        len(file_reports),
        sum(count for _, count in file_reports.values()),
    )

    # Sort files by violation count (descending) and then by path
    sorted_files = sorted(file_reports.items(), key=lambda x: (-x[1][1], x[0]))

    for file_path, (report_path, violation_count) in sorted_files:
        # Make the report path relative to the output directory
        relative_report_path = os.path.relpath(report_path, output_dir)

        error_class = "no-errors" if violation_count == 0 else "error-count"
        html_content += f"""
            <tr>
                <td><a href="{relative_report_path}">{file_path}</a></td>
                <td class="{error_class}">{violation_count}</td>
            </tr>
        """

    html_content += """
            </tbody>
        </table>
    </body>
    </html>
    """

    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return index_path


def process_files(source_dir=".", output_dir="pydocstyle_reports"):
    """Process all Python files and generate HTML reports."""
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Dictionary to store file reports info: {file_path: (report_path, violation_count)}
    file_reports = {}

    # Find all Python files
    python_files = glob.glob(os.path.join(source_dir, "**/*.py"), recursive=True)

    for py_file in python_files:
        # Get violations for the file
        violations = list(check([py_file]))

        # Create HTML report
        html_content = create_html_report(py_file, violations)

        # Generate output filename
        relative_path = os.path.relpath(py_file, source_dir)
        output_file = os.path.join(output_dir, f"{relative_path}.html")

        # Create necessary subdirectories
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Write the report
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Store report info
        file_reports[relative_path] = (output_file, len(violations))

        print(f"Generated report for {py_file} -> {output_file}")

    # Create index.html
    index_path = create_index_html(file_reports, output_dir)
    print(f"\nGenerated index at {index_path}")
    print(f"Total files analyzed: {len(file_reports)}")
    print(f"Total violations found: {sum(count for _, count in file_reports.values())}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate HTML reports for PyDocStyle violations"
    )
    parser.add_argument(
        "--source", default=".", help="Source directory containing Python files"
    )
    parser.add_argument(
        "--output",
        default="pydocstyle_reports",
        help="Output directory for HTML reports",
    )

    args = parser.parse_args()
    process_files(args.source, args.output)
