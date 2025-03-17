# EDSL Plugin System Revision

This document explains the completed implementation of the EDSL plugin system and how to transition if you were using the Conjure plugin.

## Overview of Changes

The EDSL plugin system has been redesigned to be more modular, robust, and extensible using the pluggy package. The main changes include:

1. Centralized plugin management through the `edsl.plugins` module
2. Support for installing plugins directly from GitHub repositories
3. A command-line interface for managing plugins
4. External plugins like Conjure are now installed separately as needed

## Transition Guide for Conjure Users

If you were previously using the Conjure plugin that was bundled with EDSL, you'll need to install it separately now.

### Installing Conjure

You can install Conjure using either code or the command line:

#### Via Code

```python
from edsl.plugins import install_from_github

# Install Conjure from GitHub
install_from_github('https://github.com/expectedparrot/edsl-conjure')
```

#### Via Command Line

```bash
# Install Conjure from GitHub
edsl plugins install https://github.com/expectedparrot/edsl-conjure
```

### Using Conjure After Installation

Once installed, you can use Conjure as before:

```python
import edsl
from edsl import Conjure

# Create and deploy an app
app = Conjure.create_app(my_survey)
```

## Technical Details

### Plugin Discovery

Plugins are discovered through:
1. Python setuptools entry points in the "edsl_plugins" group
2. Direct registration through the plugin manager

### Plugin Structure

A valid EDSL plugin must:
1. Implement the required hook specifications
2. Register itself with the "edsl_plugins" entry point

### Available Hooks

- `plugin_name`: Returns the name of the plugin
- `plugin_description`: Returns a description of the plugin
- `get_plugin_methods`: Returns a dictionary of methods provided by the plugin
- `edsl_plugin`: Returns the plugin object itself for integration with EDSL

## Developing Plugins

To develop a plugin for EDSL, follow these guidelines:

1. Create a Python package with this structure:
   ```
   my-plugin/
   ├── setup.py (or pyproject.toml)
   ├── my_plugin/
   │   ├── __init__.py
   │   └── plugin.py
   ```

2. Implement the plugin interface:
   ```python
   # my_plugin/plugin.py
   import pluggy

   # Define a hook implementation marker
   hookimpl = pluggy.HookimplMarker("edsl")

   class MyPlugin:
       """My custom EDSL plugin."""
       
       @hookimpl
       def plugin_name(self):
           return "MyPlugin"
       
       @hookimpl
       def plugin_description(self):
           return "Description of my plugin."
           
       @hookimpl
       def edsl_plugin(self, plugin_name=None):
           if plugin_name is None or plugin_name == "MyPlugin":
               return self
           
       @hookimpl
       def get_plugin_methods(self):
           return {
               "my_method": self.my_method
           }
       
       def my_method(self, survey, *args, **kwargs):
           """Do something with a survey."""
           # Your implementation here
           return "Result"
   ```

3. Configure the package to register as an EDSL plugin:
   ```python
   # setup.py
   from setuptools import setup

   setup(
       name="my-plugin",
       version="0.1.0",
       packages=["my_plugin"],
       entry_points={
           "edsl_plugins": ["my_plugin = my_plugin.plugin:MyPlugin"]
       },
       install_requires=["edsl>=0.1.0", "pluggy>=1.0.0"]
   )
   ```

## Troubleshooting

If you encounter issues with plugins:

1. Verify the plugin is installed correctly:
   ```python
   from edsl.plugins import list_plugins
   print(list_plugins())
   ```

2. Check for any errors during plugin loading in the EDSL logs.

3. Try reinstalling the plugin:
   ```python
   from edsl.plugins import uninstall_plugin, install_from_github
   uninstall_plugin("plugin_name")
   install_from_github("https://github.com/owner/repo")
   ```