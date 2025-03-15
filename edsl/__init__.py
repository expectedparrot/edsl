import os
import time
import importlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

from edsl.__version__ import __version__
from edsl.config import Config, CONFIG

# Initialize and expose logger
from edsl import logger

# Set up logger with configuration from environment/config
# (We'll configure the logger after CONFIG is initialized below)

__all__ = ['logger']

# List of modules to import
MODULES = [
    "dataset",
    "agents",
    "surveys",
    "questions",
    "scenarios",
    "language_models",
    "results",
    "caching",
    "notebooks",
    "coop",
    "instructions",
    "jobs"
]

# Import all modules and extend __all__
for module_name in MODULES:
    module = importlib.import_module(f".{module_name}", package="edsl")
    module_all = getattr(module, "__edsl_all__")
    globals().update({name: getattr(module, name) for name in module_all})
    __all__.extend(module_all)

# Load plugins
from .load_plugins import load_plugins
plugin_objects = load_plugins()

# Add plugin objects to globals and __all__
for name, obj in plugin_objects.items():
    globals()[name] = obj
    __all__.append(name)

# Now that all modules are loaded, configure logging from the config
logger.configure_from_config()