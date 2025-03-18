"""
Plugin registry module for accessing available plugins.

This module provides functionality to discover and retrieve information about
available plugins from the Expected Parrot cloud service. It defines data structures
for plugin metadata and provides methods to access the plugin registry.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json
import random
from datetime import datetime

from ..base.base_exception import BaseException
from .exceptions import PluginException


@dataclass
class AvailablePlugin:
    """
    Data class representing an available plugin in the registry.
    
    Attributes:
        name: The name of the plugin
        description: A description of the plugin's functionality
        github_url: URL to the plugin's GitHub repository
        version: Version of the plugin
        author: Author of the plugin
        tags: List of tags associated with the plugin
        created_at: Date when the plugin was created
        is_installed: Whether the plugin is currently installed locally
    """
    name: str
    description: str
    github_url: str
    version: str = "0.1.0"
    author: str = "Expected Parrot"
    tags: List[str] = None
    created_at: str = None
    is_installed: bool = False
    
    def __post_init__(self):
        """Initialize default values for optional fields."""
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now().strftime("%Y-%m-%d")


class PluginRegistryError(PluginException):
    """
    Exception raised when there's an issue with the plugin registry.
    
    This exception is raised when the plugin registry cannot be accessed
    or when there's an issue with the plugin data format.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/plugins.html"


def get_available_plugins(refresh: bool = False) -> List[AvailablePlugin]:
    """
    Get a list of available plugins from the Expected Parrot.
    
    This retrieves the official list of plugins available for EDSL.
    
    Args:
        refresh: Whether to refresh the cache and fetch the latest data
        
    Returns:
        List of AvailablePlugin objects representing available plugins
        
    Raises:
        PluginRegistryError: If the registry cannot be accessed or data is invalid
    """
    # Official plugins list
    plugins = [
        AvailablePlugin(
            name="conjure",
            description="Create EDSL objects from Qualtrics, SPSS, Stata, and other survey/statistical files",
            github_url="https://github.com/expectedparrot/edsl-conjure",
            version="1.0.0",
            author="Expected Parrot",
            tags=["qualtrics", "stata", "spss", "survey", "web", "import", "convert"],
        )
    ]
    
    return plugins


def search_plugins(query: str, tags: Optional[List[str]] = None) -> List[AvailablePlugin]:
    """
    Search for plugins matching a query string or tags.
    
    Args:
        query: Search query string
        tags: Optional list of tags to filter by
        
    Returns:
        List of matching AvailablePlugin objects
    """
    all_plugins = get_available_plugins()
    
    # Filter by search query
    if query:
        query = query.lower()
        filtered_plugins = [
            plugin for plugin in all_plugins 
            if query in plugin.name.lower() or query in plugin.description.lower()
        ]
    else:
        filtered_plugins = all_plugins
    
    # Filter by tags if provided
    if tags:
        tags = [tag.lower() for tag in tags]
        filtered_plugins = [
            plugin for plugin in filtered_plugins
            if any(tag in [t.lower() for t in plugin.tags] for tag in tags)
        ]
    
    return filtered_plugins


def get_plugin_details(plugin_name: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a specific plugin.
    
    Args:
        plugin_name: Name of the plugin to get details for
        
    Returns:
        Dictionary of detailed plugin information or None if not found
    """
    all_plugins = get_available_plugins()
    
    # Find the plugin by name
    for plugin in all_plugins:
        if plugin.name.lower() == plugin_name.lower():
            # Convert dataclass to dict and add additional details
            plugin_dict = {
                "name": plugin.name,
                "description": plugin.description,
                "github_url": plugin.github_url,
                "version": plugin.version,
                "author": plugin.author,
                "tags": plugin.tags,
                "created_at": plugin.created_at,
            }
            return plugin_dict
    
    return None


def get_github_url_by_name(plugin_name: str) -> Optional[str]:
    """
    Get a plugin's GitHub URL by its name.
    
    Args:
        plugin_name: Name of the plugin
        
    Returns:
        GitHub URL of the plugin or None if not found
    """
    plugin_details = get_plugin_details(plugin_name)
    if plugin_details:
        return plugin_details.get("github_url")
    return None