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
    logger.info("Loading plugins")
    import pluggy
    import pkg_resources
    
    logger.info("Available edsl entrypoints: %s", [ep for ep in pkg_resources.iter_entry_points("edsl")])
    
    # Define the plugin hooks specification
    hookspec = pluggy.HookspecMarker("edsl")
    
    class EDSLHookSpecs:
        """Hook specifications for edsl plugins."""
        
        @hookspec
        def conjure_plugin(self):
            """Return the Conjure class for integration with edsl."""
    
    # Create plugin manager and register specs
    pm = pluggy.PluginManager("edsl")
    pm.add_hookspecs(EDSLHookSpecs)
    
    # Load all plugins
    logger.info("Loading setuptools entrypoints...")
    pm.load_setuptools_entrypoints("edsl")
    
    # Get registered plugins 
    registered_plugins = [
        plugin_name 
        for plugin_name, _ in pm.list_name_plugin()
        if plugin_name != "EDSLHookSpecs"
    ]
    logger.info("Registered plugins: %s", registered_plugins)
    
    # Get plugins and add to __all__
    logger.info("Calling edsl_plugin hook...")
    try:
        results = pm.hook.edsl_plugin()
        logger.info("Results: %s", results)
        if results:
            plugins = {}
            
            # Process each plugin
            for plugin in results:
                if hasattr(plugin, "__name__"):
                    plugin_name = plugin.__name__
                elif hasattr(plugin, "__class__"):
                    plugin_name = plugin.__class__.__name__
                else:
                    plugin_name = f"Plugin_{len(plugins)}"
                
                # Register plugin in globals and __all__
                globals()[plugin_name] = plugin
                __all__.append(plugin_name)
                logger.info(f"Loaded plugin: {plugin_name}")
    except Exception as e:
        logger.error("Error calling edsl_plugin hook: %s", e)
except ImportError as e:
    # pluggy not available
    logger.info("pluggy not available, skipping plugin loading: %s", e)
    logger.debug("pluggy not available, skipping plugin loading: %s", e)
except Exception as e:
    # Error loading plugins
    logger.error("Error loading plugins: %s", e)
    logger.debug("Error loading plugins: %s", e)

# Now that all modules are loaded, configure logging from the config
logger.configure_from_config()

# Log the total number of items in __all__ for debugging
logger.debug(f"EDSL initialization complete with {len(__all__)} items in __all__")