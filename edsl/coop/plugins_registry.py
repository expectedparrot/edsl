"""
Plugin registry module for accessing available plugins from the Expected Parrot cloud.

This module provides functionality to discover and retrieve information about
available plugins from the Expected Parrot cloud service. It defines data structures
for plugin metadata and provides methods to access the plugin registry.
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import json
import random
from datetime import datetime

from ..base import BaseException
from .exceptions import CoopErrors


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
        downloads: Number of downloads/installations
        rating: Average user rating (0-5)
        is_installed: Whether the plugin is currently installed locally
    """
    name: str
    description: str
    github_url: str
    version: str = "0.1.0"
    author: str = "Expected Parrot"
    tags: List[str] = None
    created_at: str = None
    downloads: int = 0
    rating: float = 0.0
    is_installed: bool = False
    
    def __post_init__(self):
        """Initialize default values for optional fields."""
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now().strftime("%Y-%m-%d")


class PluginRegistryError(CoopErrors):
    """
    Exception raised when there's an issue with the plugin registry.
    
    This exception is raised when the plugin registry cannot be accessed
    or when there's an issue with the plugin data format.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/plugins.html"


def get_available_plugins(refresh: bool = False) -> List[AvailablePlugin]:
    """
    Get a list of available plugins from the Expected Parrot cloud service.
    
    In future versions, this will retrieve the data from the actual cloud service.
    Currently, it returns mock data for development purposes.
    
    Args:
        refresh: Whether to refresh the cache and fetch the latest data
        
    Returns:
        List of AvailablePlugin objects representing available plugins
        
    Raises:
        PluginRegistryError: If the registry cannot be accessed or data is invalid
    """
    # In a future version, this would make an API call to the Expected Parrot service
    # For now, return mock data
    
    # Mock data
    mock_plugins = [
        AvailablePlugin(
            name="text_analysis",
            description="Advanced text analysis tools for EDSL surveys",
            github_url="https://github.com/expectedparrot/plugin-text-analysis",
            version="1.2.0",
            author="Expected Parrot",
            tags=["text", "analysis", "nlp"],
            downloads=1245,
            rating=4.8
        ),
        AvailablePlugin(
            name="visualization",
            description="Data visualization tools for survey results",
            github_url="https://github.com/expectedparrot/plugin-visualization",
            version="0.9.5",
            author="Data Viz Team",
            tags=["visualization", "charts", "graphs"],
            downloads=982,
            rating=4.5
        ),
        AvailablePlugin(
            name="export_tools",
            description="Advanced export functionality for EDSL data",
            github_url="https://github.com/expectedparrot/plugin-export-tools",
            version="2.1.3",
            author="John Smith",
            tags=["export", "csv", "excel", "pdf"],
            downloads=726,
            rating=4.2
        ),
        AvailablePlugin(
            name="survey_templates",
            description="Pre-built survey templates for common research scenarios",
            github_url="https://github.com/expectedparrot/plugin-survey-templates",
            version="1.0.2",
            author="Research Team",
            tags=["templates", "surveys", "research"],
            downloads=543,
            rating=4.7
        ),
        AvailablePlugin(
            name="statistical_analysis",
            description="Statistical analysis tools for survey data",
            github_url="https://github.com/expectedparrot/plugin-statistical-analysis",
            version="1.3.1",
            author="Stats Group",
            tags=["statistics", "analysis", "correlation"],
            downloads=418,
            rating=4.6
        )
    ]
    
    return mock_plugins


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
                "downloads": plugin.downloads,
                "rating": plugin.rating,
                # Add additional mock details
                "last_update": (datetime.now().replace(
                    day=random.randint(1, 28),
                    month=random.randint(1, 12) if random.random() > 0.7 else datetime.now().month
                )).strftime("%Y-%m-%d"),
                "license": "MIT",
                "dependencies": ["pluggy>=1.0.0"],
                "compatible_edsl_versions": [">=0.1.0"],
                "homepage": f"https://expectedparrot.com/plugins/{plugin.name}",
                "documentation": f"https://docs.expectedparrot.com/plugins/{plugin.name}",
                "examples": [
                    f"Example 1: Using {plugin.name} to analyze data",
                    f"Example 2: Advanced {plugin.name} usage"
                ]
            }
            return plugin_dict
    
    return None