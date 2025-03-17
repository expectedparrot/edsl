import logging

def load_plugins():
    """
    Load plugins for EDSL.
    
    This function handles the discovery and loading of plugins via the pluggy library.
    It searches for entry points registered under the "edsl" namespace.
    """
    logger = logging.getLogger("edsl")
    
    try:
        logger.info("Loading plugins")
        import pluggy
        import pkg_resources
        
        logger.info("Available edsl entrypoints: %s", [ep for ep in pkg_resources.iter_entry_points("edsl")])
        
        # Import hook specs from the plugin system
        from edsl.plugins.hookspec import EDSLPluginSpec
        
        # Create plugin manager and register specs
        pm = pluggy.PluginManager("edsl")
        pm.add_hookspecs(EDSLPluginSpec)
        
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
            plugins = {}
            
            if results:
                for plugin in results:
                    if hasattr(plugin, "__name__"):
                        plugin_name = plugin.__name__
                    elif hasattr(plugin, "__class__"):
                        plugin_name = plugin.__class__.__name__
                    else:
                        plugin_name = f"Plugin_{len(plugins)}"
                    
                    logger.info(f"Loaded plugin: {plugin_name}")
                    plugins[plugin_name] = plugin
                
                return plugins
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
    
    return {}