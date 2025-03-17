# edsl/extension_manager/plugin_manager.py
import pluggy
from .hookspec import EDSLPluginSpec

class EDSLPluginManager:
    """Manage EDSL plugins using pluggy."""
    
    def __init__(self):
        # Create a plugin manager for the "edsl" project
        self.manager = pluggy.PluginManager("edsl")
        # Register the hook specifications
        self.manager.add_hookspecs(EDSLPluginSpec)
        # Load all plugins that are installed
        self.manager.load_setuptools_entrypoints("edsl_plugins")
        # Dictionary to store plugin methods
        self.methods = {}
        # Register built-in plugins
        self._register_builtin_plugins()
        # Discover and register methods
        self._discover_methods()
    
    def _register_builtin_plugins(self):
        """Register built-in plugins."""
        # Import and register internal plugins
        from .built_in.pig_latin import PigLatin
        self.manager.register(PigLatin())
    
    def _discover_methods(self):
        """Discover and register all plugin methods."""
        # Get all plugin names
        for plugin in self.manager.get_plugins():
            # Call the hook method directly on the plugin instance
            plugin_name = plugin.plugin_name()
            #print("Plugin name:", plugin_name)
            # Get methods from this plugin
            methods = plugin.get_plugin_methods()

            # Register methods with their full names and shortcuts
            if methods:
                for method_name, method in methods.items():
                    # Create a bound method that takes the plugin instance as the first argument
                    bound_method = lambda *args, m=method, **kwargs: m(*args, **kwargs)
                    
                    # Full qualified name
                    full_name = f"{plugin_name}.{method_name}"
                    self.methods[full_name] = bound_method
                    
                    # Register shorthand if not already taken
                    if method_name not in self.methods:
                        self.methods[method_name] = bound_method
    
    def get_method(self, name):
        """Get a method by name."""
        if name in self.methods:
            return self.methods[name]
        return None
    
    def list_methods(self):
        """List all available methods."""
        return sorted(self.methods.keys())