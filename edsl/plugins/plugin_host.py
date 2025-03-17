# edsl/plugins/plugin_host.py
from typing import Optional, List, Dict, Any

from .plugin_manager import EDSLPluginManager
from .exceptions import (
    PluginException,
    PluginNotFoundError,
    PluginInstallationError,
    GitHubRepoError,
    InvalidPluginError,
    PluginMethodError
)

# Singleton instance of the plugin manager for global access
_plugin_manager = None

def get_plugin_manager() -> EDSLPluginManager:
    """
    Get or create the singleton plugin manager instance.
    
    Returns:
        The plugin manager instance
    """
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = EDSLPluginManager()
    return _plugin_manager

class PluginHost:
    """Host for plugins, providing method dispatch."""
    
    def __init__(self, obj):
        """Initialize with the object plugins will operate on."""
        self.obj = obj
        self.plugin_manager = get_plugin_manager()
    
    def __getattr__(self, name):
        """Route method calls to the appropriate plugin."""
        method = self.plugin_manager.get_method(name)
        
        if method:
            def wrapper(*args, **kwargs):
                # Pass the survey object as the first argument
                return method(self.obj, *args, **kwargs)
            
            return wrapper
        
        # Fall back to remote plugin if not found locally
        try:
            from edsl.coop import RemotePlugin
            
            def remote_wrapper(*args, **kwargs):
                method_call = {
                    "method": name,
                    "args": [self.obj] + list(args),
                    "kwargs": kwargs
                }
                remote_plugin = RemotePlugin()
                return remote_plugin(method_call)
                
            return remote_wrapper
        except (ImportError, AttributeError):
            # If RemotePlugin is not available, raise AttributeError for the missing method
            raise AttributeError(f"Method '{name}' not found in any plugin")
    
    def list_available_methods(self):
        """List all available methods."""
        return self.plugin_manager.list_methods()

    @staticmethod
    def install_from_github(github_url: str, branch: Optional[str] = None) -> List[str]:
        """
        Install a plugin from a GitHub repository.
        
        Args:
            github_url: URL to the GitHub repository
            branch: Optional branch to checkout (defaults to main/master)
            
        Returns:
            List of installed plugin names
            
        Raises:
            GitHubRepoError: If the URL is invalid or the repository cannot be accessed
            PluginInstallationError: If the installation fails
            InvalidPluginError: If the repository does not contain valid plugins
        """
        pm = get_plugin_manager()
        return pm.install_plugin_from_github(github_url, branch)
    
    @staticmethod
    def uninstall_plugin(plugin_name: str) -> bool:
        """
        Uninstall a plugin by name.
        
        Args:
            plugin_name: Name of the plugin to uninstall
            
        Returns:
            True if uninstallation was successful
            
        Raises:
            PluginNotFoundError: If the plugin is not installed
            PluginInstallationError: If uninstallation fails
        """
        pm = get_plugin_manager()
        return pm.uninstall_plugin(plugin_name)
    
    @staticmethod
    def list_plugins() -> Dict[str, Dict[str, Any]]:
        """
        List all installed plugins with their details.
        
        Returns:
            Dictionary mapping plugin names to details
        """
        pm = get_plugin_manager()
        return pm.list_plugins()
        
    @staticmethod
    def get_exports() -> Dict[str, Any]:
        """
        Get all objects that plugins export to the global namespace.
        
        Returns:
            Dictionary mapping names to exported objects
        """
        pm = get_plugin_manager()
        return pm.get_exports()