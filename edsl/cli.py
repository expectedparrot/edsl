"""
EDSL Command Line Interface.

This module provides the main entry point for the EDSL command-line tool.
"""

import sys
import typer
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
        console.print("[yellow]EDSL package not installed or version not available.[/yellow]")

def main():
    """Main entry point for the EDSL CLI."""
    app()