"""
Display module for edsl providing IPython display functionality with plugin capabilities.

This module provides abstractions over IPython.display functionality to facilitate
greater modularity and potentially make the IPython dependency optional via a plugin system.
"""

from .core import display, HTML, FileLink, IFrame, is_notebook_environment
from .utils import file_notice, display_html
from .plugin import DisplayPlugin, DisplayPluginRegistry

__all__ = [
    # Core display functionality
    "display",
    "HTML",
    "FileLink",
    "IFrame",
    "is_notebook_environment",
    
    # Utility functions
    "file_notice",
    "display_html",
    
    # Plugin architecture
    "DisplayPlugin",
    "DisplayPluginRegistry"
]