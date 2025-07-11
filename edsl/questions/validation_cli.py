"""Command-line interface for validation logging and analysis.

This module provides a command-line interface for managing validation logs,
generating reports, and suggesting improvements to fix methods.
"""

import argparse
import json
import sys
from pathlib import Path

from .validation_analysis import (
    export_improvements_report,
    get_validation_failure_stats,
    suggest_fix_improvements,
)
from .validation_logger import clear_validation_logs, get_validation_failure_logs


def main():
    """Run the validation CLI."""
    parser = argparse.ArgumentParser(
        description="Manage and analyze question validation failures"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # List logs command
    list_parser = subparsers.add_parser("list", help="List validation failure logs")
    list_parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=10,
        help="Number of logs to show (default: 10)",
    )
    list_parser.add_argument("-t", "--type", type=str, help="Filter by question type")
    list_parser.add_argument(
        "-o", "--output", type=str, help="Output file path (default: stdout)"
    )

    # Clear logs command
    subparsers.add_parser("clear", help="Clear validation failure logs")

    # Stats command
    stats_parser = subparsers.add_parser(
        "stats", help="Show validation failure statistics"
    )
    stats_parser.add_argument(
        "-o", "--output", type=str, help="Output file path (default: stdout)"
    )

    # Suggest improvements command
    suggest_parser = subparsers.add_parser(
        "suggest", help="Suggest improvements for fix methods"
    )
    suggest_parser.add_argument(
        "-t", "--type", type=str, help="Filter by question type"
    )
    suggest_parser.add_argument(
        "-o", "--output", type=str, help="Output file path (default: stdout)"
    )

    # Generate report command
    report_parser = subparsers.add_parser(
        "report", help="Generate a comprehensive report"
    )
    report_parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output file path (default: ~/.edsl/logs/fix_methods_improvements.json)",
    )

    args = parser.parse_args()

    if args.command == "list":
        logs = get_validation_failure_logs(n=args.count)

        # Filter by question type if provided
        if args.type:
            logs = [log for log in logs if log.get("question_type") == args.type]

        output = json.dumps(logs, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)

    elif args.command == "clear":
        clear_validation_logs()
        print("Validation logs cleared.")

    elif args.command == "stats":
        stats = get_validation_failure_stats()
        output = json.dumps(stats, indent=2)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)

    elif args.command == "suggest":
        suggestions = suggest_fix_improvements(question_type=args.type)
        output = json.dumps(suggestions, indent=2)

        if args.output:
            with open(args.output, "w") as f:
                f.write(output)
        else:
            print(output)

    elif args.command == "report":
        output_path = None
        if args.output:
            output_path = Path(args.output)

        report_path = export_improvements_report(output_path=output_path)
        print(f"Report generated at: {report_path}")

    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
