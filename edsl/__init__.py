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

__all__ = ['logger']

# Define modules to import
modules_to_import = [
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

# Dynamically import modules and extend __all__
for module_name in modules_to_import:
    try:
        # Import the module
        module = importlib.import_module(f'.{module_name}', package='edsl')
        
        # Get the module's __all__ attribute
        module_all = getattr(module, '__all__', [])
        
        # Import all names from the module
        exec(f"from .{module_name} import *")
        
        # Extend __all__ with the module's __all__
        if module_all:
            logger.debug(f"Adding {len(module_all)} items from {module_name} to __all__")
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
    from edsl.plugins import get_plugin_manager
    
    # Load all plugins
    plugins = load_plugins()
    logger.info(f"Loaded {len(plugins)} plugins")
    
    # Add plugins to globals and __all__
    for plugin_name, plugin in plugins.items():
        globals()[plugin_name] = plugin
        __all__.append(plugin_name)
        logger.info(f"Registered plugin {plugin_name} in global namespace")
    
    # Check for Conjure plugin (for backward compatibility)
    if "Conjure" not in plugins:
        # Conjure not found, add a placeholder that recommends installation
        class ConjurePlaceholder:
            """Placeholder for the Conjure plugin that recommends installation."""
            
            def __getattr__(self, name):
                msg = (
                    "The Conjure plugin is not installed. "
                    "To use Conjure with EDSL, install it using:\n"
                    "  from edsl.plugins import install_from_github\n"
                    "  install_from_github('https://github.com/expectedparrot/edsl-conjure')\n"
                    "\nOr from the command line:\n"
                    "  edsl plugins install https://github.com/expectedparrot/edsl-conjure"
                )
                logger.warning(msg)
                raise ImportError(msg)
        
        # Register the placeholder
        Conjure = ConjurePlaceholder()
        globals()["Conjure"] = Conjure
        __all__.append("Conjure")
        logger.info("Added Conjure placeholder with installation instructions")

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

# Log the total number of items in __all__ for debugging
logger.debug(f"EDSL initialization complete with {len(__all__)} items in __all__")