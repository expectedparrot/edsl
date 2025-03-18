"""
Command-line interface for managing EDSL plugins using Typer.

This module provides a Typer-based CLI for listing, installing,
updating, and removing EDSL plugins.
"""

import sys
from typing import Optional, List, Dict, Any
import re
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich import box

from .plugin_host import PluginHost, get_plugin_manager
from .exceptions import (
    PluginException, 
    PluginNotFoundError, 
    PluginInstallationError,
    GitHubRepoError,
    InvalidPluginError
)
from .plugins_registry import (
    AvailablePlugin,
    get_available_plugins,
    search_plugins, 
    get_plugin_details,
    get_github_url_by_name
)

# Create the Typer app
app = typer.Typer(help="Manage EDSL plugins")
console = Console()

@app.command("list")
def list_plugins():
    """List all installed plugins."""
    plugin_manager = get_plugin_manager()
    plugins_info = plugin_manager.list_plugins()
    
    if not plugins_info:
        console.print("[yellow]No plugins installed.[/yellow]")
        return
        
    # Create a rich table
    table = Table(title="Installed Plugins", box=box.ROUNDED)
    table.add_column("Name", style="cyan")
    table.add_column("Version", style="green")
    table.add_column("Description")
    
    for name, info in plugins_info.items():
        description = info.get('description', '')
        table.add_row(
            name, 
            info.get('version', 'unknown'), 
            description
        )
    
    console.print(table)
    console.print("\nUse [bold cyan]edsl plugins info <name>[/bold cyan] for more details about a specific plugin.")

@app.command("available")
def list_available_plugins():
    """List all available plugins from the repository."""
    try:
        plugins = get_available_plugins()
        
        if not plugins:
            console.print("[yellow]No plugins available.[/yellow]")
            return
            
        # Create a rich table
        table = Table(title="Available Plugins", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Description")
        
        for plugin in plugins:
            table.add_row(
                plugin.name,
                plugin.version,
                plugin.description
            )
        
        console.print(table)
        console.print("\nUse [bold cyan]edsl plugins info <name>[/bold cyan] for more details about a specific plugin.")
        console.print("Use [bold cyan]edsl plugins install <name>[/bold cyan] to install a plugin.")
        
    except Exception as e:
        console.print(f"[red]Error fetching available plugins: {str(e)}[/red]")

@app.command("search")
def search_for_plugins(
    query: str = typer.Argument(..., help="Search query string"),
    tags: Optional[List[str]] = typer.Option(None, help="Filter by tags")
):
    """Search for plugins matching a query string or tags."""
    try:
        results = search_plugins(query, tags)
        
        if not results:
            console.print(f"[yellow]No plugins found matching '{query}'.[/yellow]")
            return
            
        # Create a rich table
        title = f"Search Results for '{query}'"
        if tags:
            title += f" (Tags: {', '.join(tags)})"
            
        table = Table(title=title, box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Tags")
        table.add_column("Description")
        
        for plugin in results:
            # Format tags
            tag_str = ", ".join(plugin.tags[:3])
            if len(plugin.tags) > 3:
                tag_str += "..."
                
            table.add_row(
                plugin.name,
                plugin.version,
                tag_str,
                plugin.description
            )
        
        console.print(table)
        console.print("\nUse [bold cyan]edsl plugins info <name>[/bold cyan] for more details about a specific plugin.")
        
    except Exception as e:
        console.print(f"[red]Error searching for plugins: {str(e)}[/red]")

@app.command("info")
def show_plugin_info(name: str = typer.Argument(..., help="Plugin name")):
    """Get detailed information about a specific plugin."""
    plugin_manager = get_plugin_manager()
    local_plugins = plugin_manager.list_plugins()
    
    if name in local_plugins:
        info = local_plugins[name]
        
        panel_content = []
        panel_content.append(f"[bold cyan]Description:[/bold cyan] {info.get('description', 'No description available')}")
        panel_content.append(f"[bold cyan]Methods:[/bold cyan] {', '.join(info.get('methods', []))}")
        panel_content.append(f"[bold cyan]Installed from:[/bold cyan] {info.get('installed_from', 'Unknown')}")
        
        panel = Panel(
            "\n".join(panel_content),
            title=f"[bold]Plugin: {name} (Installed)[/bold]",
            expand=False
        )
        console.print(panel)
        console.print(f"\nUse [bold cyan]edsl plugins uninstall {name}[/bold cyan] to uninstall this plugin.")
        return
        
    # If not installed, check if it's available
    try:
        info = get_plugin_details(name)
        
        if not info:
            console.print(f"[yellow]Plugin '{name}' not found.[/yellow]")
            return
            
        # Create a rich panel with detailed information
        panel_content = []
        panel_content.append(f"[bold cyan]Description:[/bold cyan] {info['description']}")
        panel_content.append(f"[bold cyan]Version:[/bold cyan] {info['version']}")
        panel_content.append(f"[bold cyan]Author:[/bold cyan] {info['author']}")
        panel_content.append(f"[bold cyan]Tags:[/bold cyan] {', '.join(info['tags'])}")
        panel_content.append(f"[bold cyan]GitHub URL:[/bold cyan] {info['github_url']}")
        panel_content.append(f"[bold cyan]Created:[/bold cyan] {info['created_at']}")
        panel_content.append(f"[bold cyan]Last Updated:[/bold cyan] {info.get('last_update', 'Unknown')}")
        panel_content.append(f"[bold cyan]License:[/bold cyan] {info.get('license', 'Unknown')}")
        panel_content.append(f"[bold cyan]Dependencies:[/bold cyan] {', '.join(info.get('dependencies', ['None']))}")
        panel_content.append(f"[bold cyan]Compatible EDSL versions:[/bold cyan] {', '.join(info.get('compatible_edsl_versions', ['Unknown']))}")
        
        panel_content.append("\n[bold cyan]Documentation:[/bold cyan]")
        panel_content.append(f"  Homepage: {info.get('homepage', 'N/A')}")
        panel_content.append(f"  Docs: {info.get('documentation', 'N/A')}")
        
        if 'examples' in info and info['examples']:
            panel_content.append("\n[bold cyan]Examples:[/bold cyan]")
            for example in info['examples']:
                panel_content.append(f"  • {example}")
                
        panel = Panel(
            "\n".join(panel_content),
            title=f"[bold]Plugin: {info['name']}[/bold]",
            expand=False
        )
        console.print(panel)
        console.print(f"\nUse [bold cyan]edsl plugins install {info['name']}[/bold cyan] to install this plugin.")
        
    except Exception as e:
        console.print(f"[red]Error retrieving plugin information: {str(e)}[/red]")

@app.command("install")
def install_plugin(
    name: str = typer.Argument(..., help="Name of the plugin to install"),
    branch: Optional[str] = typer.Option(None, help="Branch to install from"),
    url: Optional[str] = typer.Option(None, help="Directly specify GitHub URL instead of using the registry")
):
    """Install a plugin by name or URL."""
    try:
        github_url = url
        
        # If URL not provided, look up in registry by name
        if not github_url:
            github_url = get_github_url_by_name(name)
            if not github_url:
                console.print(f"[yellow]Plugin '{name}' not found in registry.[/yellow]")
                console.print("Use [bold cyan]edsl plugins available[/bold cyan] to see available plugins.")
                console.print("Or provide the GitHub URL with '--url' if you know it.")
                raise typer.Exit(code=1)
        
        with console.status(f"Installing plugin '{name}' from {github_url}...", spinner="dots"):
            # Install the plugin
            installed_plugins = PluginHost.install_from_github(github_url, branch)
        
        console.print(f"[green]Successfully installed plugin(s): {', '.join(installed_plugins)}[/green]")
        console.print("\nUse [bold cyan]edsl plugins list[/bold cyan] to see all installed plugins.")
        
    except PluginException as e:
        console.print(f"[red]Error installing plugin: {str(e)}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Unexpected error during installation: {str(e)}[/red]")
        raise typer.Exit(code=1)

@app.command("uninstall")
def uninstall_plugin(
    name: str = typer.Argument(..., help="Plugin name")
):
    """Uninstall a plugin by name."""
    try:
        with console.status(f"Uninstalling plugin '{name}'...", spinner="dots"):
            # Uninstall the plugin
            PluginHost.uninstall_plugin(name)
        
        console.print(f"[green]Successfully uninstalled plugin '{name}'.[/green]")
        
    except PluginException as e:
        console.print(f"[red]Error uninstalling plugin: {str(e)}[/red]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Unexpected error during uninstallation: {str(e)}[/red]")
        raise typer.Exit(code=1)

def _get_plugin_name_from_url(url: str) -> str:
    """
    Extract a plugin name from a GitHub URL.
    
    Args:
        url: GitHub URL
        
    Returns:
        Extracted plugin name or a placeholder
    """
    # Try to extract the repository name from the URL
    match = re.search(r"github\.com/[^/]+/([^/]+)", url)
    if match:
        repo_name = match.group(1)
        # Convert repo name to plugin name
        if repo_name.startswith("plugin-"):
            return repo_name[7:]  # Remove "plugin-" prefix
        elif repo_name.startswith("edsl-plugin-"):
            return repo_name[12:]  # Remove "edsl-plugin-" prefix
        else:
            return repo_name
            
    # If we can't extract a name, return a placeholder
    return "plugin"

def run():
    """Run the plugin CLI."""
    app()