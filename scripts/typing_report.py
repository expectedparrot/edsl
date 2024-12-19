import os
import glob
import json
from datetime import datetime
import subprocess
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional


@dataclass
class MypyError:
    """Representation of a mypy error."""

    file: str
    line: int
    column: Optional[int]
    severity: str
    message: str
    error_type: Optional[str]


def check_mypy_installation() -> bool:
    """Check if mypy is installed and supports JSON output."""
    try:
        # Check mypy version
        version_result = subprocess.run(
            ["mypy", "--version"], capture_output=True, text=True
        )
        if version_result.returncode != 0:
            print("Error: mypy is not properly installed.")
            print("Please install mypy with: pip install mypy")
            return False

        print(f"Found mypy version: {version_result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("Error: mypy is not installed.")
        print("Please install mypy with: pip install mypy")
        return False


def run_mypy(file_path: str) -> List[MypyError]:
    """Run mypy on a single file and return the errors."""
    # First check if mypy is properly installed
    if not check_mypy_installation():
        return []
    try:
        print(f"Running mypy on {file_path}")
        # Run mypy with --json output format
        # Run mypy with show-error-codes to get more detailed output
        result = subprocess.run(
            [
                "mypy",
                "--show-error-codes",
                "--no-error-summary",
                "--no-color-output",
                file_path,
            ],
            capture_output=True,
            text=True,
        )

        # Parse the text output instead of JSON
        errors = []
        if result.stdout:
            for line in result.stdout.splitlines():
                if ": error:" in line or ": note:" in line:
                    try:
                        # Parse lines like: file.py:10: error: Message [error-code]
                        file_info, message = line.split(": ", 1)
                        file_path, line_no = file_info.rsplit(":", 1)
                        severity, message = message.split(": ", 1)

                        # Extract error code if present
                        error_type = None
                        if "[" in message and message.endswith("]"):
                            message, error_type = message.rsplit(" [", 1)
                            error_type = error_type[:-1]  # Remove closing bracket

                        errors.append(
                            MypyError(
                                file=file_path,
                                line=int(line_no),
                                column=None,  # Column information not available in text output
                                severity=severity,
                                message=message,
                                error_type=error_type,
                            )
                        )
                    except (ValueError, IndexError) as e:
                        print(f"Error parsing line: {line}")
                        print(f"Error details: {e}")
                        continue

        return errors

        errors = []
        for error in output:
            errors.append(
                MypyError(
                    file=error["path"],
                    line=error["line"],
                    column=error.get("column"),
                    severity=error["severity"],
                    message=error["message"],
                    error_type=error.get("type"),
                )
            )

        return errors
    except (subprocess.SubprocessError, json.JSONDecodeError) as e:
        print(f"Error analyzing {file_path}: {e}")
        print(f"stderr: {result.stderr}")
        print(f"stdout: {result.stdout}")
        return []


def create_html_report(filename: str, errors: List[MypyError]) -> str:
    """Create an HTML report for a single file's mypy errors."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mypy Report - {filename}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .error {{ 
                background-color: #f8f8f8;
                border-left: 4px solid #e74c3c;
                margin: 10px 0;
                padding: 10px;
            }}
            .warning {{
                background-color: #f8f8f8;
                border-left: 4px solid #f39c12;
                margin: 10px 0;
                padding: 10px;
            }}
            .error-type {{ 
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
            .location {{
                color: #666;
                font-family: monospace;
            }}
        </style>
    </head>
    <body>
        <div class="file-info">
            <h2>Mypy Type Check Report</h2>
            <p>File: {filename}</p>
            <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><a href="index.html">Back to Index</a></p>
        </div>
    """

    if not errors:
        html_content += "<p>✅ No type checking errors found!</p>"
    else:
        html_content += f"<h3>Found {len(errors)} error(s):</h3>"
        for error in errors:
            severity_class = "error" if error.severity == "error" else "warning"
            location = f"line {error.line}"
            if error.column is not None:
                location += f", column {error.column}"

            html_content += f"""
            <div class="{severity_class}">
                <p><span class="error-type">{error.error_type or error.severity.upper()}</span></p>
                <p>{error.message}</p>
                <p class="location">{location}</p>
            </div>
            """

    html_content += """
    </body>
    </html>
    """
    return html_content


def create_index_html(file_reports: Dict[str, Tuple[str, int]], output_dir: str) -> str:
    """Create an index.html with a summary table of all reports."""
    template = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mypy Reports Index</title>
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
        <h1>Mypy Type Check Reports</h1>
        <div class="summary">
            <p>Generated: {}</p>
            <p>Total files analyzed: {}</p>
            <p>Total type errors found: {}</p>
        </div>
        <table>
            <thead>
                <tr>
                    <th>File Path</th>
                    <th>Type Errors</th>
                </tr>
            </thead>
            <tbody>
    """

    html_content = template.format(
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        len(file_reports),
        sum(count for _, count in file_reports.values()),
    )

    # Sort files by error count (descending) and then by path
    sorted_files = sorted(file_reports.items(), key=lambda x: (-x[1][1], x[0]))

    for file_path, (report_path, error_count) in sorted_files:
        # Make the report path relative to the output directory
        relative_report_path = os.path.relpath(report_path, output_dir)

        error_class = "no-errors" if error_count == 0 else "error-count"
        html_content += f"""
            <tr>
                <td><a href="{relative_report_path}">{file_path}</a></td>
                <td class="{error_class}">{error_count}</td>
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


def process_files(source_dir: str = ".", output_dir: str = "mypy_reports") -> None:
    """Process all Python files and generate HTML reports."""
    # Check mypy installation first
    if not check_mypy_installation():
        print("Aborting due to mypy installation issues.")
        return
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Dictionary to store file reports info: {file_path: (report_path, error_count)}
    file_reports = {}

    # Find all Python files
    python_files = glob.glob(os.path.join(source_dir, "**/*.py"), recursive=True)

    for py_file in python_files:
        # Run mypy and get errors
        errors = run_mypy(py_file)

        # Create HTML report
        html_content = create_html_report(py_file, errors)

        # Generate output filename
        relative_path = os.path.relpath(py_file, source_dir)
        output_file = os.path.join(output_dir, f"{relative_path}.html")

        # Create necessary subdirectories
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Write the report
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Store report info
        file_reports[relative_path] = (output_file, len(errors))

        print(f"Generated report for {py_file} -> {output_file}")

    # Create index.html
    index_path = create_index_html(file_reports, output_dir)
    print(f"\nGenerated index at {index_path}")
    print(f"Total files analyzed: {len(file_reports)}")
    print(
        f"Total type errors found: {sum(count for _, count in file_reports.values())}"
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate HTML reports for Mypy type checking results"
    )
    parser.add_argument(
        "--source", default=".", help="Source directory containing Python files"
    )
    parser.add_argument(
        "--output",
        default="mypy_reports",
        help="Output directory for HTML reports",
    )

    args = parser.parse_args()
    process_files(args.source, args.output)
