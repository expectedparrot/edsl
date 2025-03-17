"""
EDSL Plugins module for extending functionality with custom plugins.

# EDSL Plugin System

The EDSL Plugin System allows you to extend EDSL's functionality with custom plugins. 
This documentation explains how to install, use, and manage plugins through both code 
and the command-line interface.

## Plugin Concepts

EDSL plugins are Python packages that add specialized functionality to EDSL. Plugins follow 
a standard structure and integration pattern, allowing them to be dynamically discovered 
and used within your EDSL code.

Key concepts include:

- **Plugin Registry**: A central repository of available plugins
- **Plugin Methods**: Functions provided by plugins that you can call
- **Plugin Host**: A component that manages plugin discovery and method execution

## Installing Plugins

### Through Code

You can install plugins programmatically:

```python
from edsl.plugins import install_from_github

# Install a plugin from a GitHub repository
install_from_github('https://github.com/expectedparrot/plugin-text-analysis')

# Install from a specific branch
install_from_github('https://github.com/expectedparrot/plugin-text-analysis', branch='develop')
```

### Through Command-Line

The plugin system provides a command-line interface for easy management:

```bash
# Install a plugin from GitHub
edsl plugins install https://github.com/expectedparrot/plugin-text-analysis

# Install from a specific branch
edsl plugins install https://github.com/expectedparrot/plugin-text-analysis --branch develop
```

## Using Plugins

Once installed, you can use plugin methods with your EDSL objects:

```python
import edsl
from edsl import Survey

# Create a survey
survey = Survey()
# ... add questions ...

# Use a plugin method directly on the survey
survey.plugins.text_analysis()

# Or use the fully qualified method name
survey.plugins.TextAnalysis.analyze_text()
```

The `plugins` attribute is automatically added to EDSL objects, providing access to all available plugin methods.

## Managing Plugins

### Listing Installed Plugins

```python
from edsl.plugins import list_plugins

# Get all installed plugins
plugins = list_plugins()
for name, info in plugins.items():
    print(f"Plugin: {name}")
    print(f"Description: {info.get('description')}")
    print(f"Methods: {', '.join(info.get('methods', []))}")
```

### Uninstalling Plugins

```python
from edsl.plugins import uninstall_plugin

# Uninstall a plugin by name
uninstall_plugin('text_analysis')
```

### Finding Available Plugins

```python
from edsl.coop import get_available_plugins, search_plugins, get_plugin_details

# Get all available plugins
available_plugins = get_available_plugins()
for plugin in available_plugins:
    print(f"{plugin.name}: {plugin.description}")

# Search for plugins matching a query
results = search_plugins('visualization')
for plugin in results:
    print(f"{plugin.name} (Rating: {plugin.rating}): {plugin.description}")

# Get detailed information about a specific plugin
details = get_plugin_details('text_analysis')
print(f"Version: {details['version']}")
print(f"GitHub URL: {details['github_url']}")
```

## Command-Line Interface

The plugin system includes a command-line interface for managing plugins:

```bash
# Show help information
edsl plugins --help

# List installed plugins
edsl plugins list

# Show available plugins from the registry
edsl plugins available

# Search for plugins
edsl plugins search visualization

# Search with tag filtering
edsl plugins search analysis --tags nlp text

# Get detailed information about a plugin
edsl plugins info text_analysis

# Install a plugin
edsl plugins install https://github.com/expectedparrot/plugin-text-analysis

# Uninstall a plugin
edsl plugins uninstall text_analysis
```

## Creating Your Own Plugins

You can create your own EDSL plugins by following these steps:

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
       \"\"\"My custom EDSL plugin.\"\"\"
       
       @hookimpl
       def plugin_name(self):
           return "MyPlugin"
       
       @hookimpl
       def plugin_description(self):
           return "Description of my plugin."
           
       @hookimpl
       def get_plugin_methods(self):
           return {
               "my_method": self.my_method
           }
       
       def my_method(self, survey, *args, **kwargs):
           \"\"\"Do something with a survey.\"\"\"
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

4. Install your plugin:
   ```bash
   pip install -e /path/to/my-plugin
   ```

## API Reference

### Plugin Management

- `edsl.plugins.install_from_github(github_url: str, branch: Optional[str] = None) -> List[str]`
  Installs a plugin from a GitHub repository.

- `edsl.plugins.uninstall_plugin(plugin_name: str) -> bool`
  Uninstalls a plugin by name.

- `edsl.plugins.list_plugins() -> Dict[str, Dict[str, Any]]`
  Returns a dictionary of installed plugins with their metadata.

- `edsl.plugins.cli()`
  Runs the plugin command-line interface.

### Plugin Registry

- `edsl.coop.get_available_plugins(refresh: bool = False) -> List[AvailablePlugin]`
  Returns a list of available plugins from the registry.

- `edsl.coop.search_plugins(query: str, tags: Optional[List[str]] = None) -> List[AvailablePlugin]`
  Searches for plugins matching a query string or tags.

- `edsl.coop.get_plugin_details(plugin_name: str) -> Optional[Dict[str, Any]]`
  Returns detailed information about a specific plugin.

### Plugin Host

- `edsl.plugins.PluginHost`
  The class that provides access to plugin methods for EDSL objects.

- `edsl.plugins.get_plugin_manager() -> EDSLPluginManager`
  Returns the plugin manager instance.

### Exceptions

- `edsl.plugins.PluginException`
  Base class for all plugin-related exceptions.

- `edsl.plugins.PluginNotFoundError`
  Raised when a requested plugin is not found.

- `edsl.plugins.PluginInstallationError`
  Raised when a plugin installation fails.

- `edsl.plugins.GitHubRepoError`
  Raised when there's an error with a GitHub repository.

- `edsl.plugins.InvalidPluginError`
  Raised when a plugin is invalid or does not implement required hooks.
"""

# Import for public API
from .plugin_host import PluginHost, get_plugin_manager
from .exceptions import (
    PluginException,
    PluginNotFoundError,
    PluginInstallationError,
    GitHubRepoError,
    InvalidPluginError,
    PluginMethodError,
    PluginDependencyError
)
from .cli import PluginCLI
# Import the Typer CLI
from .cli_typer import app as typer_app

# Public API functions
def install_from_github(github_url, branch=None):
    """Install a plugin from a GitHub repository."""
    return PluginHost.install_from_github(github_url, branch)

def uninstall_plugin(plugin_name):
    """Uninstall a plugin by name."""
    return PluginHost.uninstall_plugin(plugin_name)

def list_plugins():
    """List all installed plugins."""
    return PluginHost.list_plugins()

def cli():
    """Run the plugin CLI (legacy version)."""
    from .cli import main
    main()

def cli_typer():
    """Run the Typer-based plugin CLI."""
    from .cli_typer import run
    run()

__all__ = [
    'PluginHost',
    'get_plugin_manager',
    'install_from_github',
    'uninstall_plugin',
    'list_plugins',
    'cli',
    'cli_typer',
    'PluginCLI',
    'typer_app',
    'PluginException',
    'PluginNotFoundError',
    'PluginInstallationError',
    'GitHubRepoError',
    'InvalidPluginError',
    'PluginMethodError',
    'PluginDependencyError'
]