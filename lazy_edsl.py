"""
Prototype implementation of lazy loading for the edsl package.
This demonstrates how the edsl module could be restructured to reduce import memory usage.
"""

# Lazy loading prototype
class LazyEdslModule:
    """A lazy-loading implementation of the edsl module."""
    
    def __init__(self):
        # These are the core components we'd still load on import
        import os
        import time
        from edsl.__version__ import __version__
        from edsl.config import Config, CONFIG
        from edsl import logger
        
        # Basic module attributes
        self.__version__ = __version__
        self.Config = Config
        self.CONFIG = CONFIG
        self.logger = logger
        
        # Define which modules can be lazy loaded
        self._lazy_modules = {
            'dataset': '.dataset',
            'agents': '.agents',
            'surveys': '.surveys',
            'questions': '.questions', 
            'scenarios': '.scenarios',
            'language_models': '.language_models',
            'results': '.results',
            'caching': '.caching',
            'notebooks': '.notebooks',
            'coop': '.coop',
            'instructions': '.instructions',
            'jobs': '.jobs',
        }
        
        # Dictionary to hold loaded modules
        self._loaded_modules = {}
        
        # Dictionary to hold loaded module attributes
        self._module_attrs = {}
    
    def __getattr__(self, name):
        """Lazy load modules and their attributes on demand."""
        # Case 1: It's a module we can lazy load
        if name in self._lazy_modules:
            if name not in self._loaded_modules:
                import importlib
                self.logger.info(f"Lazy loading module: {name}")
                module_path = self._lazy_modules[name]
                self._loaded_modules[name] = importlib.import_module(module_path, package='edsl')
                
                # Import module's attributes
                self._import_module_attrs(name)
            
            return self._loaded_modules[name]
        
        # Case 2: It might be an attribute from a module
        for module_name, module in self._loaded_modules.items():
            if hasattr(module, name):
                return getattr(module, name)
        
        # Case 3: It might be in the module's __all__ attributes we've imported
        if name in self._module_attrs:
            return self._module_attrs[name]
        
        # Case 4: We need to load all modules and check
        self._load_all_modules()
        
        if name in self._module_attrs:
            return self._module_attrs[name]
            
        # Not found anywhere
        raise AttributeError(f"Module 'edsl' has no attribute '{name}'")
    
    def _import_module_attrs(self, module_name):
        """Import attributes from a module's __all__ list."""
        module = self._loaded_modules[module_name]
        module_all = getattr(module, '__all__', [])
        
        for attr_name in module_all:
            if hasattr(module, attr_name):
                self._module_attrs[attr_name] = getattr(module, attr_name)
                self.logger.debug(f"Imported {attr_name} from {module_name}")
    
    def _load_all_modules(self):
        """Load all modules if needed."""
        for module_name in self._lazy_modules:
            if module_name not in self._loaded_modules:
                self.__getattr__(module_name)  # Will trigger lazy loading

# Create a sample usage function
def demonstrate_lazy_loading():
    """Shows how to use the lazy-loaded implementation."""
    # This would be part of the edsl package's initialization
    edsl = LazyEdslModule()
    
    # Print basic information without loading everything
    print(f"EDSL version: {edsl.__version__}")
    print(f"Logger initialized: {edsl.logger is not None}")
    
    # Memory usage before accessing lazy-loaded modules
    import os
    print(f"Memory usage before lazy loading: {os.popen('ps -o rss -p %d | tail -n1' % os.getpid()).read().strip()} KB")
    
    # Now access a module, triggering lazy loading
    print("\nAccessing 'Model' class (should trigger lazy loading)...")
    Model = edsl.Model  # This will trigger lazy loading of the language_models module
    print(f"Model class loaded: {Model is not None}")
    
    # Memory usage after accessing one module
    print(f"Memory usage after loading language_models: {os.popen('ps -o rss -p %d | tail -n1' % os.getpid()).read().strip()} KB")
    
    # Access another module
    print("\nAccessing 'Agent' class (should trigger lazy loading)...")
    Agent = edsl.Agent  # This will trigger lazy loading of the agents module 
    print(f"Agent class loaded: {Agent is not None}")
    
    # Final memory usage
    print(f"Final memory usage: {os.popen('ps -o rss -p %d | tail -n1' % os.getpid()).read().strip()} KB")

if __name__ == "__main__":
    demonstrate_lazy_loading()