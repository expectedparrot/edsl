"""
EDSL: Experimental Design Specification Language

EDSL is a Python library for conducting virtual social science experiments, surveys, 
and interviews with large language models.
"""
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

# Set up logger with configuration from environment/config
# (We'll configure the logger after CONFIG is initialized below)

__all__ = ['logger', 'Config', 'CONFIG', '__version__']

# Import the LazyModule class
from edsl.utilities.lazy_import import LazyModule, LazyCallable

# Define modules to lazy-load
_lazy_modules = [
    'dataset',
    'agents',
    'surveys',
    'questions',
    'scenarios',
    'language_models',
    'results',
    'caching',
    'notebooks',
    'coop',
    'instructions',
    'jobs',
    'base'
]

# Setup lazy imports
for module_name in _lazy_modules:
    # Create lazy module
    lazy_module = LazyModule(module_name, package='edsl')
    # Add to globals
    globals()[module_name] = lazy_module
    # Add to __all__
    __all__.append(module_name)

# Configure logging from the config
logger.configure_from_config()

# Flag to track if plugins have been loaded
_plugins_loaded = False

# Lazy loading for plugins
def load_plugins():
    """
    Lazily load plugins only when explicitly requested.
    Returns True if plugins were loaded, False otherwise.
    """
    global _plugins_loaded
    
    if _plugins_loaded:
        return True
        
    try:
        from edsl.load_plugins import load_plugins as _load_plugins
        from edsl.plugins import get_plugin_manager, get_exports
        
        # Load all plugins
        plugins = _load_plugins()
        logger.info(f"Loaded {len(plugins)} plugins")
        
        # Add plugins to globals and __all__
        for plugin_name, plugin in plugins.items():
            globals()[plugin_name] = plugin
            __all__.append(plugin_name)
            logger.info(f"Registered plugin {plugin_name} in global namespace")
        
        # Get exports from plugins and add them to globals
        exports = get_exports()
        logger.info(f"Found {len(exports)} exported objects from plugins")
        
        for name, obj in exports.items():
            globals()[name] = obj
            __all__.append(name)
            logger.info(f"Added plugin export: {name}")
        
        # Add placeholders for expected exports that are missing
        # This maintains backward compatibility for common plugins
        PLUGIN_PLACEHOLDERS = {
            # No placeholders - removed Conjure for cleaner namespace
        }
        
        for placeholder_name, github_url in PLUGIN_PLACEHOLDERS.items():
            if placeholder_name not in globals():
                # Create a placeholder class
                placeholder_class = type(placeholder_name, (), {
                    "__getattr__": lambda self, name: self._not_installed(name),
                    "_not_installed": lambda self, name: self._raise_import_error(),
                    "_raise_import_error": lambda self: exec(f"""
msg = (
    "The {placeholder_name} plugin is not installed. "
    "To use {placeholder_name} with EDSL, install it using:\\n"
    "  from edsl.plugins import install_from_github\\n"
    "  install_from_github('{github_url}')\\n"
    "\\nOr from the command line:\\n"
    "  edsl plugins install {github_url}"
)
logger.warning(msg)
raise ImportError(msg)
""")
                })
                
                # Register the placeholder
                globals()[placeholder_name] = placeholder_class()
                __all__.append(placeholder_name)
                logger.info(f"Added placeholder for {placeholder_name} with installation instructions")
        
        _plugins_loaded = True
        return True
    except ImportError as e:
        # Modules not available
        logger.info("Plugin system not available, skipping plugin loading: %s", e)
        logger.debug("Plugin system not available, skipping plugin loading: %s", e)
        return False
    except Exception as e:
        # Error loading plugins
        logger.error("Error loading plugins: %s", e)
        logger.debug("Error loading plugins: %s", e)
        return False

# Create lazy proxies for common classes instead of importing them directly
Model = LazyCallable('language_models', 'Model', package='edsl')
Agent = LazyCallable('agents', 'Agent', package='edsl')
Survey = LazyCallable('surveys', 'Survey', package='edsl')
QuestionFreeText = LazyCallable('questions', 'QuestionFreeText', package='edsl')
QuestionMultipleChoice = LazyCallable('questions', 'QuestionMultipleChoice', package='edsl')
QuestionYesNo = LazyCallable('questions', 'QuestionYesNo', package='edsl')
QuestionLinearScale = LazyCallable('questions', 'QuestionLinearScale', package='edsl')
Scenario = LazyCallable('scenarios', 'Scenario', package='edsl')
ScenarioList = LazyCallable('scenarios', 'ScenarioList', package='edsl')
FileStore = LazyCallable('scenarios', 'FileStore', package='edsl')
Cache = LazyCallable('caching', 'Cache', package='edsl')
AgentList = LazyCallable('agents', 'AgentList', package='edsl')
Notebook = LazyCallable('notebooks', 'Notebook', package='edsl')
Instruction = LazyCallable('instructions', 'Instruction', package='edsl')
ChangeInstruction = LazyCallable('instructions', 'ChangeInstruction', package='edsl')
Results = LazyCallable('results', 'Results', package='edsl')
Jobs = LazyCallable('jobs', 'Jobs', package='edsl')

# Add them to __all__
__all__.extend([
    'Model', 'Agent', 'Survey', 
    'QuestionFreeText', 'QuestionMultipleChoice', 'QuestionYesNo', 'QuestionLinearScale',
    'Scenario', 'ScenarioList', 'FileStore', 'Cache', 'AgentList', 'Notebook',
    'Instruction', 'ChangeInstruction', 'Results', 'Jobs'
])

# Lazily import base exception class (this was a bottleneck)
# Defer exception hook installation to reduce import time
_exception_hook_installed = False

def _install_exception_hook():
    """Lazily install the exception hook when needed."""
    global _exception_hook_installed
    if not _exception_hook_installed:
        # Import the module only when needed
        from edsl.base.base_exception import BaseException
        BaseException.install_exception_hook()
        _exception_hook_installed = True

# Don't install exception hook at import time
# It will be installed when an exception occurs
# or when someone explicitly accesses BaseException
# This significantly reduces import time

# Log the total number of items in __all__ for debugging
logger.debug(f"EDSL initialization complete with {len(__all__)} items in __all__")