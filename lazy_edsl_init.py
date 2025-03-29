
import os
import time
import importlib
import pkgutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

from edsl.__version__ import __version__
from edsl.config import Config, CONFIG

# Initialize and expose logger
from edsl import logger

__all__ = ['logger', 'Config', 'CONFIG']

# Define modules to lazy-load
_lazy_modules = {
    'dataset': None,
    'agents': None,
    'surveys': None,
    'questions': None,
    'scenarios': None,
    'language_models': None,
    'results': None,
    'caching': None,
    'notebooks': None,
    'coop': None,
    'instructions': None,
    'jobs': None
}

# Setup lazy imports
for module_name in _lazy_modules:
    # Create lazy module
    lazy_module = LazyModule(module_name, package='edsl')
    # Add to globals
    globals()[module_name] = lazy_module
    # Add to __all__
    __all__.append(module_name)

# Configure logging
logger.configure_from_config()

# Install exception hook (lazily)
def _load_exception_hook():
    from edsl.base.base_exception import BaseException
    BaseException.install_exception_hook()
    
# Only load plugins when explicitly requested
def load_all_plugins():
    from edsl.load_plugins import load_plugins
    from edsl.plugins import get_plugin_manager, get_exports
    
    # Load all plugins
    plugins = load_plugins()
    logger.info(f"Loaded {len(plugins)} plugins")
    
    # Add plugins to globals and __all__
    for plugin_name, plugin in plugins.items():
        globals()[plugin_name] = plugin
        __all__.append(plugin_name)
    
    # Get exports from plugins and add them to globals
    exports = get_exports()
    for name, obj in exports.items():
        globals()[name] = obj
        __all__.append(name)
    
    return plugins

# Lazily load the exception hook at first usage
_load_exception_hook()

# Helper class for lazy importing
class LazyModule:
    def __init__(self, name, package=None):
        self._name = name
        self._package = package
        self._module = None
    
    def __getattr__(self, attr):
        if self._module is None:
            if self._package:
                self._module = importlib.import_module(f".{self._name}", package=self._package)
            else:
                self._module = importlib.import_module(self._name)
        
        return getattr(self._module, attr)
