"""
EDSL Command Line Interface.

This module provides the main entry point for the EDSL command-line tool.
"""

import typer
import json
from pathlib import Path
from typing import Optional
from rich.console import Console
from importlib import metadata

# Create the main Typer app
app = typer.Typer(help="Expected Parrot EDSL Command Line Interface")
console = Console()

# Import the plugins app
from .plugins.cli_typer import app as plugins_app

# Add the plugins subcommand
app.add_typer(plugins_app, name="plugins")

# Create the validation app
validation_app = typer.Typer(help="Manage EDSL validation failures")
app.add_typer(validation_app, name="validation")


@validation_app.command("logs")
def list_validation_logs(
    count: int = typer.Option(10, "--count", "-n", help="Number of logs to show"),
    question_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Filter by question type"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """List validation failure logs."""
    from .questions.validation_logger import get_validation_failure_logs

    logs = get_validation_failure_logs(n=count)

    # Filter by question type if provided
    if question_type:
        logs = [log for log in logs if log.get("question_type") == question_type]

    if output:
        with open(output, "w") as f:
            json.dump(logs, f, indent=2)
        console.print(f"[green]Logs written to {output}[/green]")
    else:
        console.print_json(json.dumps(logs, indent=2))


@validation_app.command("clear")
def clear_validation_logs():
    """Clear validation failure logs."""
    from .questions.validation_logger import clear_validation_logs

    clear_validation_logs()
    console.print("[green]Validation logs cleared.[/green]")


@validation_app.command("stats")
def validation_stats(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Show validation failure statistics."""
    from .questions.validation_analysis import get_validation_failure_stats

    stats = get_validation_failure_stats()

    if output:
        with open(output, "w") as f:
            json.dump(stats, f, indent=2)
        console.print(f"[green]Stats written to {output}[/green]")
    else:
        console.print_json(json.dumps(stats, indent=2))


@validation_app.command("suggest")
def suggest_improvements(
    question_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Filter by question type"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Suggest improvements for fix methods."""
    from .questions.validation_analysis import suggest_fix_improvements

    suggestions = suggest_fix_improvements(question_type=question_type)

    if output:
        with open(output, "w") as f:
            json.dump(suggestions, f, indent=2)
        console.print(f"[green]Suggestions written to {output}[/green]")
    else:
        console.print_json(json.dumps(suggestions, indent=2))


@validation_app.command("report")
def generate_report(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
):
    """Generate a comprehensive validation report."""
    from .questions.validation_analysis import export_improvements_report

    report_path = export_improvements_report(output_path=output)
    console.print(f"[green]Report generated at: {report_path}[/green]")


@validation_app.command("html-report")
def generate_html_report(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file path"
    ),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Open the report in a browser"
    ),
):
    """Generate an HTML validation report and optionally open it in a browser."""
    from .questions.validation_html_report import generate_html_report
    import webbrowser

    report_path = generate_html_report(output_path=output)
    console.print(f"[green]HTML report generated at: {report_path}[/green]")

    if open_browser:
        try:
            webbrowser.open(f"file://{report_path}")
            console.print("[green]Opened report in browser[/green]")
        except Exception as e:
            console.print(f"[yellow]Could not open browser: {e}[/yellow]")
            console.print(f"[yellow]Report is available at: {report_path}[/yellow]")


@app.callback()
def callback():
    """
    Expected Parrot EDSL Command Line Interface.

    A toolkit for creating, managing, and running surveys with language models.
    """
    pass


@app.command()
def version():
    """Show the EDSL version."""
    try:
        version = metadata.version("edsl")
        console.print(f"[bold cyan]EDSL version:[/bold cyan] {version}")
    except metadata.PackageNotFoundError:
        console.print(
            "[yellow]EDSL package not installed or version not available.[/yellow]"
        )


@app.command()
def check_updates():
    """Check for available EDSL updates."""
    try:
        from edsl import check_for_updates

        console.print("[cyan]Checking for updates...[/cyan]")
        update_info = check_for_updates(silent=True)

        if update_info:
            console.print("\n[bold yellow]📦 Update Available![/bold yellow]")
            console.print(
                f"[cyan]Current version:[/cyan] {update_info['current_version']}"
            )
            console.print(
                f"[green]Latest version:[/green] {update_info['latest_version']}"
            )
            if update_info.get("update_info"):
                console.print(f"[cyan]Update info:[/cyan] {update_info['update_info']}")
            console.print(f"\n[bold]To update:[/bold] {update_info['update_command']}")
        else:
            console.print(
                "[green]✓ You are running the latest version of EDSL![/green]"
            )
    except Exception as e:
        console.print(f"[red]Error checking for updates: {str(e)}[/red]")


def main():
    """Main entry point for the EDSL CLI."""
    # Check for updates on startup if environment variable is set
    import os

    if os.getenv("EDSL_CHECK_UPDATES_ON_STARTUP", "").lower() in ["1", "true", "yes"]:
        try:
            from edsl import check_for_updates

            check_for_updates(silent=False)
        except Exception:
            pass  # Silently fail if update check fails

    app()
