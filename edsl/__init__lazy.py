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
from edsl.utilities.lazy_import import LazyModule

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
    'jobs'
]

# Setup lazy imports
for module_name in _lazy_modules:
    # Create lazy module
    lazy_module = LazyModule(module_name, package='edsl')
    # Add to globals
    globals()[module_name] = lazy_module
    # Add to __all__
    __all__.append(module_name)

# Now that all modules are loaded, configure logging from the config
logger.configure_from_config()

# Lazy loading for plugins
def load_plugins():
    """
    Lazily load plugins only when explicitly requested.
    """
    from edsl.load_plugins import load_plugins as _load_plugins
    from edsl.plugins import get_plugin_manager, get_exports
    
    # Load all plugins
    plugins = _load_plugins()
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

# These are used frequently, so import them directly
from edsl.language_models import Model
from edsl.agents import Agent
from edsl.surveys import Survey
from edsl.questions import (
    QuestionFreeText, 
    QuestionMultipleChoice,
    QuestionYesNo
)
from edsl.scenarios import Scenario, ScenarioList

# Add them to __all__
__all__.extend([
    'Model', 'Agent', 'Survey', 
    'QuestionFreeText', 'QuestionMultipleChoice', 'QuestionYesNo',
    'Scenario', 'ScenarioList'
])

# Install exception handling
from .base.base_exception import BaseException
BaseException.install_exception_hook()

# Log the total number of items in __all__ for debugging
logger.debug(f"EDSL initialization complete with {len(__all__)} items in __all__")