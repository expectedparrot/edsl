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
