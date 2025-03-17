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