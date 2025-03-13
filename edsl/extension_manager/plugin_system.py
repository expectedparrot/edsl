import os
import importlib
import inspect
import pkgutil
from typing import Dict, List, Any, Callable, Tuple, Optional, Type, Union


class PluginInterface:
    """Base interface for plugins to inherit from."""
    
    @classmethod
    def plugin_name(cls) -> str:
        """Return the name of the plugin."""
        return cls.__name__
    
    @classmethod
    def plugin_methods(cls) -> Dict[str, Callable]:
        """Return a dictionary of methods provided by this plugin."""
        return {
            name: method for name, method in inspect.getmembers(cls, predicate=inspect.isfunction)
            if not name.startswith('_') and name not in ['plugin_name', 'plugin_methods']
        }


class PluginManager:
    """Discover and manage plugins."""
    
    def __init__(self, plugin_package: str):
        self.plugin_package = plugin_package
        self.plugins: Dict[str, Type[PluginInterface]] = {}
        self.plugin_instances: Dict[str, PluginInterface] = {}
    
    def discover_plugins(self) -> None:
        """Discover all available plugins in the plugin package."""
        # Import the package containing plugins
        try:
            package = importlib.import_module(self.plugin_package)
        except ImportError:
            print(f"Plugin package {self.plugin_package} not found.")
            return
        
        # Walk through all modules in the plugin package
        for _, name, is_pkg in pkgutil.iter_modules(package.__path__, package.__name__ + '.'):
            if not is_pkg:  # Only process modules, not packages
                try:
                    module = importlib.import_module(name)
                    
                    # Look for classes that implement PluginInterface
                    for item_name in dir(module):
                        item = getattr(module, item_name)
                        
                        if (isinstance(item, type) and 
                            issubclass(item, PluginInterface) and 
                            item is not PluginInterface):
                            # Register the plugin class
                            plugin_name = item.plugin_name()
                            self.plugins[plugin_name] = item
                            #print(f"Discovered plugin: {plugin_name}")
                except ImportError as e:
                    print(f"Error importing module {name}: {e}")
    
    def instantiate_plugins(self) -> None:
        """Create instances of all discovered plugins."""
        for name, plugin_class in self.plugins.items():
            try:
                self.plugin_instances[name] = plugin_class()
                #print(f"Instantiated plugin: {name}")
            except Exception as e:
                print(f"Error instantiating plugin {name}: {e}")


class PluginHost:
    """A class that dynamically routes method calls to registered plugins."""
    
    def __init__(self, plugin_manager: PluginManager, object: Any):
        self.plugin_manager = plugin_manager
        self.object = object
        # Format: {method_name: (plugin_instance, method_name)}
        self._method_registry: Dict[str, Tuple[Any, str]] = {}
        self._register_plugin_methods()
    
    def _register_plugin_methods(self) -> None:
        """Register all methods from all plugin instances."""
        for plugin_name, plugin_instance in self.plugin_manager.plugin_instances.items():
            methods = self.plugin_manager.plugins[plugin_name].plugin_methods()
            
            for method_name, _ in methods.items():
                # Create the full method name as plugin_name.method_name
                full_method_name = f"{plugin_name}.{method_name}"
                
                # Also register with just the method name if it doesn't exist yet
                # (first plugin that provides a method "owns" the shorthand name)
                if method_name not in self._method_registry:
                    self._method_registry[method_name] = (plugin_instance, method_name)
                    #print(f"Registered method shorthand: {method_name}")
                
                # Always register the fully qualified name
                self._method_registry[full_method_name] = (plugin_instance, method_name)
                #print(f"Registered method: {full_method_name}")
    
    def list_available_methods(self) -> List[str]:
        """Return a list of all available plugin methods."""
        return sorted(self._method_registry.keys())
    
    def __getattr__(self, name: str) -> Callable:
        """
        Intercept method calls and route them to the appropriate plugin.
        First tries local plugins, then falls back to remote plugins via Coop.
        
        Args:
            name: The name of the method being called.
            
        Returns:
            A wrapper function that calls the plugin method.
            
        Raises:
            AttributeError: If no plugin (local or remote) provides the requested method.
        """
        if name in self._method_registry:
            plugin_instance, method_name = self._method_registry[name]
            
            def method_wrapper(*args, **kwargs):
                try:
                    plugin_method = getattr(plugin_instance, method_name)
                    return plugin_method(self.object, *args, **kwargs)
                except Exception as e:
                    print(f"Error calling plugin method {name}: {e}")
                    raise
            
            return method_wrapper
        
        # If we get here, no local plugin provides this method
        # Create a wrapper that will serialize the call and use RemotePlugin
        from ..coop import RemotePlugin

        def remote_wrapper(*args, **kwargs):
            method_call = {
                "method": name,
                "args": [self.object] + list(args),  # Include self.object as first arg
                "kwargs": kwargs
            }
            remote_plugin = RemotePlugin()
            return remote_plugin(method_call)
        
        return remote_wrapper


# my_app/plugins/__init__.py
# This file can be empty - it just makes the directory a package

