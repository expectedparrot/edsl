"""
Command-line interface for managing EDSL plugins.

This module provides a text-based interface for listing, installing,
updating, and removing EDSL plugins.
"""

import sys
import argparse
import textwrap
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import asdict
import os
import re

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


class PluginCLI:
    """Command-line interface for managing EDSL plugins."""
    
    def __init__(self):
        """Initialize the CLI."""
        self.plugin_manager = get_plugin_manager()
        self.parser = self._create_parser()
        
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser for the CLI."""
        parser = argparse.ArgumentParser(
            description="EDSL Plugin Manager",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog=textwrap.dedent("""
                Examples:
                  edsl plugins list                 # List all installed plugins
                  edsl plugins available            # List available plugins from repository
                  edsl plugins search text          # Search for plugins related to text
                  edsl plugins info text_analysis   # Get detailed info about a plugin
                  edsl plugins install text_analysis # Install a plugin by name
                  edsl plugins install text_analysis --url https://github.com/example/repo # Install with explicit URL
                  edsl plugins uninstall text_analysis
            """)
        )
        
        subparsers = parser.add_subparsers(dest="command", help="Command to execute")
        
        # List command
        list_parser = subparsers.add_parser("list", help="List installed plugins")
        
        # Available command
        available_parser = subparsers.add_parser("available", help="List available plugins")
        
        # Search command
        search_parser = subparsers.add_parser("search", help="Search for plugins")
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument("--tags", nargs="+", help="Filter by tags")
        
        # Info command
        info_parser = subparsers.add_parser("info", help="Get detailed info about a plugin")
        info_parser.add_argument("name", help="Plugin name")
        
        # Install command
        install_parser = subparsers.add_parser("install", help="Install a plugin")
        install_parser.add_argument("name", help="Name of the plugin to install")
        install_parser.add_argument("--branch", help="Branch to install from")
        install_parser.add_argument("--url", help="Directly specify GitHub URL instead of using the registry")
        
        # Uninstall command
        uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall a plugin")
        uninstall_parser.add_argument("name", help="Plugin name")
        
        return parser
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """
        Run the CLI with the given arguments.
        
        Args:
            args: Command-line arguments (defaults to sys.argv[1:])
            
        Returns:
            Exit code (0 for success, non-zero for error)
        """
        if args is None:
            args = sys.argv[1:]
            
        # Parse arguments
        args = self.parser.parse_args(args)
        
        try:
            # Execute the requested command
            if args.command == "list":
                self._list_plugins()
            elif args.command == "available":
                self._list_available_plugins()
            elif args.command == "search":
                self._search_plugins(args.query, args.tags)
            elif args.command == "info":
                self._show_plugin_info(args.name)
            elif args.command == "install":
                self._install_plugin(args.name, args.branch, args.url)
            elif args.command == "uninstall":
                self._uninstall_plugin(args.name)
            else:
                self.parser.print_help()
                return 1
                
            return 0
            
        except PluginException as e:
            print(f"Error: {str(e)}")
            return 1
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return 1
    
    def _list_plugins(self) -> None:
        """List all installed plugins."""
        plugins_info = self.plugin_manager.list_plugins()
        
        if not plugins_info:
            print("No plugins installed.")
            return
            
        # Print a table of installed plugins
        print("\nInstalled Plugins:")
        print("-" * 80)
        print(f"{'Name':<20} {'Version':<10} {'Description':<50}")
        print("-" * 80)
        
        for name, info in plugins_info.items():
            # Truncate description if too long
            description = info.get('description', '')
            if description and len(description) > 47:
                description = description[:47] + "..."
                
            print(f"{name:<20} {'unknown':<10} {description:<50}")
            
        print("\nUse 'edsl plugins info <name>' for more details about a specific plugin.")
    
    def _list_available_plugins(self) -> None:
        """List all available plugins from the repository."""
        try:
            plugins = get_available_plugins()
            
            if not plugins:
                print("No plugins available.")
                return
                
            # Print a table of available plugins
            print("\nAvailable Plugins:")
            print("-" * 100)
            print(f"{'Name':<20} {'Version':<10} {'Rating':<8} {'Downloads':<10} {'Description':<50}")
            print("-" * 100)
            
            for plugin in plugins:
                # Truncate description if too long
                description = plugin.description
                if len(description) > 47:
                    description = description[:47] + "..."
                    
                print(f"{plugin.name:<20} {plugin.version:<10} {plugin.rating:<8.1f} {plugin.downloads:<10} {description:<50}")
                
            print("\nUse 'edsl plugins info <name>' for more details about a specific plugin.")
            print("Use 'edsl plugins install <name>' to install a plugin.")
            
        except Exception as e:
            print(f"Error fetching available plugins: {str(e)}")
    
    def _search_plugins(self, query: str, tags: Optional[List[str]] = None) -> None:
        """
        Search for plugins matching a query string or tags.
        
        Args:
            query: Search query string
            tags: Optional list of tags to filter by
        """
        try:
            results = search_plugins(query, tags)
            
            if not results:
                print(f"No plugins found matching '{query}'.")
                return
                
            # Print a table of search results
            print(f"\nSearch Results for '{query}':")
            if tags:
                print(f"Filtered by tags: {', '.join(tags)}")
                
            print("-" * 100)
            print(f"{'Name':<20} {'Version':<10} {'Rating':<8} {'Tags':<25} {'Description':<35}")
            print("-" * 100)
            
            for plugin in results:
                # Truncate description if too long
                description = plugin.description
                if len(description) > 32:
                    description = description[:32] + "..."
                    
                # Format tags
                tag_str = ", ".join(plugin.tags[:3])
                if len(plugin.tags) > 3:
                    tag_str += "..."
                if len(tag_str) > 22:
                    tag_str = tag_str[:22] + "..."
                    
                print(f"{plugin.name:<20} {plugin.version:<10} {plugin.rating:<8.1f} {tag_str:<25} {description:<35}")
                
            print("\nUse 'edsl plugins info <name>' for more details about a specific plugin.")
            
        except Exception as e:
            print(f"Error searching for plugins: {str(e)}")
    
    def _show_plugin_info(self, name: str) -> None:
        """
        Show detailed information about a specific plugin.
        
        Args:
            name: Name of the plugin to show info for
        """
        # First check if it's an installed plugin
        local_plugins = self.plugin_manager.list_plugins()
        
        if name in local_plugins:
            info = local_plugins[name]
            print(f"\nPlugin: {name} (Installed)")
            print("-" * 80)
            print(f"Description: {info.get('description', 'No description available')}")
            print(f"Methods: {', '.join(info.get('methods', []))}")
            print(f"Installed from: {info.get('installed_from', 'Unknown')}")
            print("\nUse 'edsl plugins uninstall {name}' to uninstall this plugin.")
            return
            
        # If not installed, check if it's available
        try:
            info = get_plugin_details(name)
            
            if not info:
                print(f"Plugin '{name}' not found.")
                return
                
            print(f"\nPlugin: {info['name']}")
            print("-" * 80)
            print(f"Description: {info['description']}")
            print(f"Version: {info['version']}")
            print(f"Author: {info['author']}")
            print(f"Tags: {', '.join(info['tags'])}")
            print(f"GitHub URL: {info['github_url']}")
            print(f"Created: {info['created_at']}")
            print(f"Last Updated: {info.get('last_update', 'Unknown')}")
            print(f"Downloads: {info['downloads']}")
            print(f"Rating: {info['rating']:.1f}/5.0")
            print(f"License: {info.get('license', 'Unknown')}")
            print(f"Dependencies: {', '.join(info.get('dependencies', ['None']))}")
            print(f"Compatible EDSL versions: {', '.join(info.get('compatible_edsl_versions', ['Unknown']))}")
            print("\nDocumentation:")
            print(f"  Homepage: {info.get('homepage', 'N/A')}")
            print(f"  Docs: {info.get('documentation', 'N/A')}")
            
            if 'examples' in info and info['examples']:
                print("\nExamples:")
                for example in info['examples']:
                    print(f"  - {example}")
                    
            print(f"\nUse 'edsl plugins install {info['github_url']}' to install this plugin.")
            
        except Exception as e:
            print(f"Error retrieving plugin information: {str(e)}")
    
    def _install_plugin(self, plugin_name: str, branch: Optional[str] = None, url: Optional[str] = None) -> None:
        """
        Install a plugin by name or URL.
        
        Args:
            plugin_name: Name of the plugin to install
            branch: Optional branch to checkout (defaults to main/master)
            url: Optional GitHub URL to use instead of registry lookup
        """
        try:
            github_url = url
            
            # If URL not provided, look up in registry by name
            if not github_url:
                github_url = get_github_url_by_name(plugin_name)
                if not github_url:
                    print(f"Plugin '{plugin_name}' not found in registry.")
                    print("Use 'edsl plugins available' to see available plugins.")
                    print("Or provide the GitHub URL with '--url' if you know it.")
                    return
            
            print(f"Installing plugin '{plugin_name}' from {github_url}...")
            if branch:
                print(f"Using branch: {branch}")
                
            # Install the plugin
            installed_plugins = PluginHost.install_from_github(github_url, branch)
            
            print(f"Successfully installed plugin(s): {', '.join(installed_plugins)}")
            print("\nUse 'edsl plugins list' to see all installed plugins.")
            
        except PluginException as e:
            print(f"Error installing plugin: {str(e)}")
            raise
        except Exception as e:
            print(f"Unexpected error during installation: {str(e)}")
            raise
    
    def _uninstall_plugin(self, name: str) -> None:
        """
        Uninstall a plugin by name.
        
        Args:
            name: Name of the plugin to uninstall
        """
        try:
            print(f"Uninstalling plugin '{name}'...")
            
            # Uninstall the plugin
            PluginHost.uninstall_plugin(name)
            
            print(f"Successfully uninstalled plugin '{name}'.")
            
        except PluginException as e:
            print(f"Error uninstalling plugin: {str(e)}")
            raise
        except Exception as e:
            print(f"Unexpected error during uninstallation: {str(e)}")
            raise
    
    def _get_plugin_name_from_url(self, url: str) -> str:
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


def main():
    """Main entry point for the CLI."""
    cli = PluginCLI()
    sys.exit(cli.run())