import pluggy
from typing import Dict, Any, Optional

# Define a hook specification namespace
hookspec = pluggy.HookspecMarker("edsl")

class EDSLPluginSpec:
    """Hook specifications for EDSL plugins."""
    
    @hookspec
    def plugin_name(self):
        """Return the name of the plugin."""
        
    @hookspec
    def get_plugin_methods(self):
        """Return a dictionary of methods provided by this plugin."""

    @hookspec
    def plugin_description(self):
        """Return a description of the plugin."""

    @hookspec
    def plugin_return_type(self):
        """Return the return type of the plugin."""

    @hookspec
    def plugin_args(self):
        """Return the arguments of the plugin."""
        
    @hookspec
    def edsl_plugin(self, plugin_name=None):
        """Return a plugin class for integration with edsl.
        
        Args:
            plugin_name: Optional name of the specific plugin to return.
        """
    
    @hookspec
    def exports_to_namespace(self) -> Optional[Dict[str, Any]]:
        """
        Define objects that should be exported to the global namespace.
        
        Plugins can use this hook to specify objects (classes, functions, etc.)
        that should be available for direct import from the edsl package.
        
        Returns:
            A dictionary mapping names to objects, or None if nothing to export.
            Example: {'MyClass': MyClass, 'my_function': my_function}
        """
        
    # Legacy conjure_plugin hook removed - all plugins should use edsl_plugin
