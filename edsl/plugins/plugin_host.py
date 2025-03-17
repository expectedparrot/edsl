# edsl/extension_manager/plugin_host.py
from .plugin_manager import EDSLPluginManager

class PluginHost:
    """Host for plugins, providing method dispatch."""
    
    def __init__(self, obj):
        """Initialize with the object plugins will operate on."""
        self.obj = obj
        self.plugin_manager = EDSLPluginManager()
    
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