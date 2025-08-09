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

# NOTE: `ext` is lazily imported below via __getattr__ to avoid circular-import issues.

# Initialize and expose logger
from edsl import logger

# Set up logger with configuration from environment/config
# (We'll configure the logger after CONFIG is initialized below)

__all__ = ["logger", "Config", "CONFIG", "__version__"]

# Define modules for lazy loading
_LAZY_MODULES = {
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
    "jobs",
    "base",
    "conversation",
    "extensions",
}

# Cache for lazy-loaded modules
_module_cache = {}

def __getattr__(name):
    """Lazy loading of EDSL modules and their exports."""
    # Check if it's a module we should lazy-load
    for module_name in _LAZY_MODULES:
        try:
            module = _module_cache.get(module_name)
            if module is None:
                module = importlib.import_module(f".{module_name}", package="edsl")
                _module_cache[module_name] = module
            
            # Check if the requested name is in this module
            if hasattr(module, name):
                return getattr(module, name)
        except ImportError:
            continue
    
    # Special handling for 'ext'
    if name == "ext":
        try:
            from edsl.extensions import ext
            return ext
        except Exception as e:
            logger.warning("Failed to import edsl.extensions.ext: %s", e)
            raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Configure logging from the config
logger.configure_from_config()

# Installs a custom exception handling routine for edsl exceptions
from .base.base_exception import BaseException

BaseException.install_exception_hook()

# Log the total number of items in __all__ for debugging
logger.debug(f"EDSL initialization complete with {len(__all__)} items in __all__")


def check_for_updates(silent: bool = False) -> dict:
    """
    Check if there's a newer version of EDSL available.

    Args:
        silent: If True, don't print any messages to console

    Returns:
        dict with version info if update is available, None otherwise
    """
    from edsl.coop import Coop

    coop = Coop()
    return coop.check_for_updates(silent=silent)


# Add check_for_updates to exports
__all__.append("check_for_updates")


# Perform version check on import (non-blocking)
def _check_version_on_import():
    """Check for updates on package import in a non-blocking way."""
    import threading
    import os

    # Check if version check is disabled
    if os.getenv("EDSL_DISABLE_VERSION_CHECK", "").lower() in ["1", "true", "yes"]:
        return

    # Check if we've already checked recently (within 24 hours)
    cache_file = os.path.join(os.path.expanduser("~"), ".edsl_version_check")
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                last_check = float(f.read().strip())
                if time.time() - last_check < 86400:  # 24 hours
                    return
    except Exception:
        pass

    def check_in_background():
        try:
            # Update cache file
            with open(cache_file, "w") as f:
                f.write(str(time.time()))

            # Perform the check
            from edsl.coop import Coop

            coop = Coop()
            coop.check_for_updates(silent=False)
        except Exception:
            # Silently fail
            pass

    # Run in a separate thread to avoid blocking imports
    thread = threading.Thread(target=check_in_background, daemon=True)
    thread.start()


# Run version check on import
_check_version_on_import()
