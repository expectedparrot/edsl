import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

from edsl.__version__ import __version__
from edsl.config import Config, CONFIG

# Initialize and expose logger
from edsl import logger

# Set up logger with configuration from environment/config
# (We'll configure the logger after CONFIG is initialized below)

__all__ = ['logger']

from .dataset import __all__ as dataset_all
from .dataset import *
__all__.extend(dataset_all)

from .agents import __all__ as agents_all
from .agents import *
__all__.extend(agents_all)

from .surveys import __all__ as surveys_all
from .surveys import *
__all__.extend(surveys_all)

# Questions
from .questions import __all__ as questions_all
from .questions import *
__all__.extend(questions_all)

from .scenarios import __all__ as scenarios_all
from .scenarios import *
__all__.extend(scenarios_all)

from .language_models import __all__ as language_models_all
from .language_models import *
__all__.extend(language_models_all)

from .results import __all__ as results_all
from .results import *
__all__.extend(results_all)

from .caching import __all__ as caching_all
from .caching import *
__all__.extend(caching_all)

from .notebooks import __all__ as notebooks_all
from .notebooks import *
__all__.extend(notebooks_all)

from .coop import __all__ as coop_all
from .coop import *
__all__.extend(coop_all)

from .instructions import __all__ as instructions_all
from .instructions import *
__all__.extend(instructions_all)

from .jobs import __all__ as jobs_all
from .jobs import *
__all__.extend(jobs_all)


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
    logger.info("Calling conjure_plugin hook...")
    try:
        results = pm.hook.conjure_plugin()
        logger.info("Results: %s", results)
        if results:
            # Get the Conjure class from the plugin
            Conjure = results[0]
            globals()["Conjure"] = Conjure
            __all__.append("Conjure")
            logger.info("Loaded Conjure plugin")
    except Exception as e:
        logger.error("Error calling conjure_plugin hook: %s", e)
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


from edsl.base.base_exception import BaseException
BaseException.install_exception_hook()