import pluggy

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
    def conjure_plugin(self):
        """Return the Conjure class for integration with edsl.
        
        This is kept for backward compatibility with the old plugin system.
        New plugins should use edsl_plugin instead.
        """
