"""EDSL Plugins module for extending functionality with custom plugins."""

# Import for public API
from .plugin_host import PluginHost, get_plugin_manager
from .exceptions import (
    PluginException,
    PluginNotFoundError,
    PluginInstallationError,
    GitHubRepoError,
    InvalidPluginError,
    PluginMethodError,
    PluginDependencyError
)
from .cli import PluginCLI
# Import the Typer CLI
from .cli_typer import app as typer_app

# Public API functions
def install_from_github(github_url, branch=None):
    """Install a plugin from a GitHub repository."""
    return PluginHost.install_from_github(github_url, branch)

def uninstall_plugin(plugin_name):
    """Uninstall a plugin by name."""
    return PluginHost.uninstall_plugin(plugin_name)

def list_plugins():
    """List all installed plugins."""
    return PluginHost.list_plugins()

def get_exports():
    """Get objects exported to the global namespace by plugins."""
    return PluginHost.get_exports()

def cli():
    """Run the plugin CLI (legacy version)."""
    from .cli import main
    main()

def cli_typer():
    """Run the Typer-based plugin CLI."""
    from .cli_typer import run
    run()

__all__ = [
    'PluginHost',
    'get_plugin_manager',
    'install_from_github',
    'uninstall_plugin',
    'list_plugins',
    'get_exports',
    'cli',
    'cli_typer',
    'PluginCLI',
    'typer_app',
    'PluginException',
    'PluginNotFoundError',
    'PluginInstallationError',
    'GitHubRepoError',
    'InvalidPluginError',
    'PluginMethodError',
    'PluginDependencyError'
]