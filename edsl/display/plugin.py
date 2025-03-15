"""
Plugin architecture for the display module.

This module defines the interface for display plugins and provides the mechanism
for registering and using them. Plugins enable replacing the default IPython-based
display functionality with alternative implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Type, List


class DisplayPlugin(ABC):
    """
    Abstract base class for display plugins.
    
    Any plugin for providing display functionality must implement this interface.
    """
    
    @abstractmethod
    def display(self, obj, *args, **kwargs) -> None:
        """
        Display an object in the frontend.
        
        Args:
            obj: The object to display
            *args: Additional objects to display
            **kwargs: Additional keyword arguments for display
        """
        pass
    
    @abstractmethod
    def html(self, data=None, metadata=None, **kwargs) -> Any:
        """
        Create an HTML display object.
        
        Args:
            data: The HTML data to display
            metadata: Any metadata for the display object
            **kwargs: Additional keyword arguments
            
        Returns:
            An object that can be displayed
        """
        pass
    
    @abstractmethod
    def file_link(self, path, url_prefix='', result_html_prefix='', 
                 result_html_suffix='', **kwargs) -> Any:
        """
        Create a FileLink display object.
        
        Args:
            path: The path to the file
            url_prefix: Prefix for the URL
            result_html_prefix: Prefix for the HTML result
            result_html_suffix: Suffix for the HTML result
            **kwargs: Additional keyword arguments
            
        Returns:
            An object that can be displayed
        """
        pass
    
    @abstractmethod
    def iframe(self, src, width, height, **kwargs) -> Any:
        """
        Create an IFrame display object.
        
        Args:
            src: The source URL for the iframe
            width: The width of the iframe
            height: The height of the iframe
            **kwargs: Additional keyword arguments
            
        Returns:
            An object that can be displayed
        """
        pass
    
    @abstractmethod
    def is_supported_environment(self) -> bool:
        """
        Check if the current environment supports this display plugin.
        
        Returns:
            bool: True if the environment is supported, False otherwise
        """
        pass


class DisplayPluginRegistry:
    """
    Registry for display plugins.
    
    This registry maintains a list of available display plugins and provides
    a mechanism for selecting the appropriate plugin for the current environment.
    """
    
    _plugins: List[Type[DisplayPlugin]] = []
    _active_plugin: Optional[DisplayPlugin] = None
    
    @classmethod
    def register_plugin(cls, plugin_class: Type[DisplayPlugin]) -> None:
        """
        Register a display plugin.
        
        Args:
            plugin_class: The plugin class to register
        """
        if plugin_class not in cls._plugins:
            cls._plugins.append(plugin_class)
    
    @classmethod
    def get_active_plugin(cls) -> Optional[DisplayPlugin]:
        """
        Get the currently active display plugin.
        
        If no plugin is active, this method will initialize the first supported plugin.
        
        Returns:
            The active display plugin, or None if no plugins are available
        """
        if cls._active_plugin is None:
            for plugin_class in cls._plugins:
                plugin = plugin_class()
                if plugin.is_supported_environment():
                    cls._active_plugin = plugin
                    break
        
        return cls._active_plugin
    
    @classmethod
    def set_active_plugin(cls, plugin: DisplayPlugin) -> None:
        """
        Set the active display plugin.
        
        Args:
            plugin: The plugin instance to set as active
        """
        cls._active_plugin = plugin


# Define a default IPython plugin that will be registered by default
class IPythonDisplayPlugin(DisplayPlugin):
    """
    Default display plugin that uses IPython.display.
    """
    
    def display(self, obj, *args, **kwargs) -> None:
        """
        Display an object using IPython.display.display.
        """
        from .core import display as core_display
        core_display(obj, *args, **kwargs)
    
    def html(self, data=None, metadata=None, **kwargs) -> Any:
        """
        Create an HTML display object using IPython.display.HTML.
        """
        from .core import HTML
        return HTML(data, metadata, **kwargs)
    
    def file_link(self, path, url_prefix='', result_html_prefix='', 
                 result_html_suffix='', **kwargs) -> Any:
        """
        Create a FileLink display object using IPython.display.FileLink.
        """
        from .core import FileLink
        return FileLink(path, url_prefix, result_html_prefix, 
                       result_html_suffix, **kwargs)
    
    def iframe(self, src, width, height, **kwargs) -> Any:
        """
        Create an IFrame display object using IPython.display.IFrame.
        """
        from .core import IFrame
        return IFrame(src, width, height, **kwargs)
    
    def is_supported_environment(self) -> bool:
        """
        Check if IPython display functionality is available.
        """
        from .core import _IPYTHON_AVAILABLE, is_notebook_environment
        return _IPYTHON_AVAILABLE and is_notebook_environment()


# Register the default IPython plugin
DisplayPluginRegistry.register_plugin(IPythonDisplayPlugin)