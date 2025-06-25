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

__all__ = ["logger", "Config", "CONFIG", "__version__"]

# Define modules to import
modules_to_import = [
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
]

# Dynamically import modules and extend __all__
for module_name in modules_to_import:
    try:
        # Import the module
        module = importlib.import_module(f".{module_name}", package="edsl")

        # Get the module's __all__ attribute
        module_all = getattr(module, "__all__", [])

        # Import all names from the module
        exec(f"from .{module_name} import *")

        # Extend __all__ with the module's __all__
        if module_all:
            logger.debug(
                f"Adding {len(module_all)} items from {module_name} to __all__"
            )
            __all__.extend(module_all)
        else:
            logger.warning(f"Module {module_name} does not have __all__ defined")
    except ImportError as e:
        logger.warning(f"Failed to import module {module_name}: {e}")
    except Exception as e:
        logger.warning(f"Error importing from module {module_name}: {e}")


# Load plugins
try:
    from edsl.load_plugins import load_plugins
    from edsl.plugins import get_plugin_manager, get_exports

    # Load all plugins
    plugins = load_plugins()
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
            placeholder_class = type(
                placeholder_name,
                (),
                {
                    "__getattr__": lambda self, name: self._not_installed(name),
                    "_not_installed": lambda self, name: self._raise_import_error(),
                    "_raise_import_error": lambda self: exec(
                        f"""
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
"""
                    ),
                },
            )

            # Register the placeholder
            globals()[placeholder_name] = placeholder_class()
            __all__.append(placeholder_name)
            logger.info(
                f"Added placeholder for {placeholder_name} with installation instructions"
            )

except ImportError as e:
    # Modules not available
    logger.info("Plugin system not available, skipping plugin loading: %s", e)
    logger.debug("Plugin system not available, skipping plugin loading: %s", e)
except Exception as e:
    # Error loading plugins
    logger.error("Error loading plugins: %s", e)
    logger.debug("Error loading plugins: %s", e)

# Now that all modules are loaded, configure logging from the config
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
