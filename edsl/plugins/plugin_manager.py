# edsl/plugins/plugin_manager.py
import os
import sys
import subprocess
import tempfile
import importlib
import importlib.util
import shutil
import re
import json
from typing import Optional, List, Dict, Any
import pluggy
import platformdirs
from urllib.parse import urlparse

from .hookspec import EDSLPluginSpec
from .exceptions import (
    PluginException, 
    PluginNotFoundError, 
    PluginInstallationError,
    GitHubRepoError,
    InvalidPluginError,
    PluginDependencyError,
    PluginMethodError
)
from .. import logger

class EDSLPluginManager:
    """Manage EDSL plugins using pluggy."""
    
    # Define paths for persistent data
    PLUGINS_DATA_DIR = platformdirs.user_data_dir("edsl")
    PLUGINS_DATA_FILE = os.path.join(PLUGINS_DATA_DIR, "installed_plugins.json")
    
    # Ensure the directory exists
    os.makedirs(PLUGINS_DATA_DIR, exist_ok=True)
    
    def __init__(self):
        # Create a plugin manager for the "edsl" project
        self.manager = pluggy.PluginManager("edsl")
        # Register the hook specifications
        self.manager.add_hookspecs(EDSLPluginSpec)
        # Load all plugins that are installed
        self.manager.load_setuptools_entrypoints("edsl_plugins")
        # Dictionary to store plugin methods
        self.methods = {}
        # Dictionary to track installed plugins
        self.installed_plugins = self._load_installed_plugins()
        # Dictionary to store objects exported to the global namespace
        self.exports = {}
        # Register built-in plugins
        self._register_builtin_plugins()
        # Discover and register methods
        self._discover_methods()
        # Gather exports from plugins
        self._gather_exports()
        
    def _load_installed_plugins(self) -> Dict[str, str]:
        """
        Load the list of installed plugins from the data file.
        
        Returns:
            Dictionary mapping plugin names to installation directories
        """
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(self.PLUGINS_DATA_FILE), exist_ok=True)
        
        # Load the plugins data if it exists
        if os.path.exists(self.PLUGINS_DATA_FILE):
            try:
                with open(self.PLUGINS_DATA_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load installed plugins data: {str(e)}")
        
        return {}
        
    def _save_installed_plugins(self):
        """
        Save the list of installed plugins to the data file.
        """
        try:
            with open(self.PLUGINS_DATA_FILE, 'w') as f:
                json.dump(self.installed_plugins, f)
        except IOError as e:
            logger.warning(f"Failed to save installed plugins data: {str(e)}")

    def install_plugin_from_github(self, github_url: str, branch: Optional[str] = None) -> List[str]:
        """
        Install a plugin from a GitHub repository.
        
        Args:
            github_url: URL to the GitHub repository
            branch: Optional branch to checkout (defaults to main/master)
            
        Returns:
            List of installed plugin names
            
        Raises:
            GitHubRepoError: If the URL is invalid or the repository cannot be accessed
            PluginInstallationError: If the installation fails
            InvalidPluginError: If the repository does not contain valid plugins
        """
        # Validate GitHub URL
        self._validate_github_url(github_url)
        
        # Extract plugin name from URL
        repo_name = github_url.split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]
        
        # Create a persistent directory for the plugin
        plugins_install_dir = os.path.join(self.PLUGINS_DATA_DIR, "plugins")
        os.makedirs(plugins_install_dir, exist_ok=True)
        plugin_dir = os.path.join(plugins_install_dir, repo_name)
        
        # Remove existing installation if it exists
        if os.path.exists(plugin_dir):
            shutil.rmtree(plugin_dir)
        
        try:
            # Clone the repository to the persistent directory
            self._clone_repository(github_url, plugin_dir, branch)
            
            # Check for setup.py or pyproject.toml
            if not self._has_package_files(plugin_dir):
                raise InvalidPluginError(
                    f"Repository at {github_url} does not contain required setup.py or pyproject.toml"
                )
            
            # Install the package in development mode
            installed_plugins = self._install_package(plugin_dir)
            
            # Reload plugins and discover methods
            self._reload_plugins()
            
            return installed_plugins
            
        except GitHubRepoError as e:
            # Re-raise with more context
            raise GitHubRepoError(f"Failed to access GitHub repository: {str(e)}")
        except subprocess.CalledProcessError as e:
            raise PluginInstallationError(f"Installation command failed: {e.output.decode() if hasattr(e, 'output') else str(e)}")
        except Exception as e:
            raise PluginInstallationError(f"Plugin installation failed: {str(e)}")
    
    def _validate_github_url(self, url: str) -> None:
        """
        Validate that a URL is a valid GitHub repository URL.
        
        Args:
            url: URL to validate
            
        Raises:
            GitHubRepoError: If the URL is invalid
        """
        parsed_url = urlparse(url)
        
        # Check that it's a valid URL with https scheme
        if not parsed_url.scheme or not parsed_url.netloc:
            raise GitHubRepoError(f"Invalid URL: {url}")
        
        # Check that it's a GitHub URL
        if not parsed_url.netloc.endswith('github.com'):
            raise GitHubRepoError(f"Not a GitHub URL: {url}")
        
        # Check that it has a path (username/repo)
        if not parsed_url.path or parsed_url.path.count('/') < 2:
            raise GitHubRepoError(f"Invalid GitHub repository path: {url}")
    
    def _clone_repository(self, url: str, target_dir: str, branch: Optional[str] = None) -> None:
        """
        Clone a GitHub repository to a local directory.
        
        Args:
            url: URL of the GitHub repository
            target_dir: Directory to clone into
            branch: Optional branch to checkout
            
        Raises:
            GitHubRepoError: If the clone fails
        """
        try:
            # Basic clone command
            cmd = ['git', 'clone', url, target_dir]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Checkout specific branch if requested
            if branch:
                subprocess.run(
                    ['git', 'checkout', branch], 
                    check=True, 
                    capture_output=True,
                    cwd=target_dir
                )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if hasattr(e, 'stderr') else str(e)
            raise GitHubRepoError(f"Failed to clone repository: {error_msg}")
    
    def _has_package_files(self, directory: str) -> bool:
        """
        Check if a directory contains Python package files.
        
        Args:
            directory: Directory to check
            
        Returns:
            True if setup.py or pyproject.toml exist
        """
        return (
            os.path.exists(os.path.join(directory, 'setup.py')) or
            os.path.exists(os.path.join(directory, 'pyproject.toml'))
        )
    
    def _install_package(self, package_dir: str) -> List[str]:
        """
        Install a Python package from a local directory.
        
        Args:
            package_dir: Directory containing the package
            
        Returns:
            List of installed plugin names
            
        Raises:
            PluginInstallationError: If installation fails
        """
        try:
            # Install in development mode
            cmd = [sys.executable, '-m', 'pip', 'install', '-e', package_dir]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Try to determine the package name from setup.py or pyproject.toml
            package_name = self._get_package_name(package_dir)
            
            # Record successful installation
            self.installed_plugins[package_name] = package_dir
            # Save the updated list of installed plugins
            self._save_installed_plugins()
            
            # Return names of plugins in this package
            # For now just return the package name as a placeholder
            return [package_name]
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if hasattr(e, 'stderr') else str(e)
            raise PluginInstallationError(f"Failed to install package: {error_msg}")
    
    def _get_package_name(self, package_dir: str) -> str:
        """
        Extract the package name from setup.py or pyproject.toml.
        
        Args:
            package_dir: Directory containing the package
            
        Returns:
            Package name (defaults to directory name if can't be determined)
        """
        # Try to extract from setup.py
        setup_py = os.path.join(package_dir, 'setup.py')
        if os.path.exists(setup_py):
            with open(setup_py, 'r') as f:
                content = f.read()
                # Look for name='...' pattern
                match = re.search(r"name=['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)
        
        # Try to extract from pyproject.toml
        pyproject_toml = os.path.join(package_dir, 'pyproject.toml')
        if os.path.exists(pyproject_toml):
            with open(pyproject_toml, 'r') as f:
                content = f.read()
                # Look for name = "..." pattern
                match = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", content)
                if match:
                    return match.group(1)
        
        # Look for name in plugins registry to normalize name
        try:
            # Get the GitHub URL from setup.py or repo directory
            git_config = os.path.join(package_dir, '.git', 'config')
            if os.path.exists(git_config):
                with open(git_config, 'r') as f:
                    content = f.read()
                    url_match = re.search(r"url\s*=\s*(.+)", content)
                    if url_match:
                        url = url_match.group(1).strip()
                        # Extract repo name
                        repo_name = url.split('/')[-1]
                        # Remove .git suffix if present
                        if repo_name.endswith('.git'):
                            repo_name = repo_name[:-4]
                            
                        # If repo name follows common patterns
                        if repo_name.startswith('edsl-'):
                            return repo_name[5:]  # Remove 'edsl-' prefix
                        if repo_name.startswith('plugin-'):
                            return repo_name[7:]  # Remove 'plugin-' prefix
                        if repo_name.endswith('-plugin'):
                            return repo_name[:-7]  # Remove '-plugin' suffix
        except Exception as e:
            logger.debug(f"Error extracting name from git config: {str(e)}")
        
        # Default to directory name
        dir_name = os.path.basename(os.path.normpath(package_dir))
        # Clean up common prefixes/suffixes in directory names too
        if dir_name.startswith('edsl-'):
            return dir_name[5:]
        if dir_name.startswith('plugin-'):
            return dir_name[7:]
        if dir_name.endswith('-plugin'):
            return dir_name[:-7]
            
        return dir_name
    
    def _gather_exports(self):
        """Gather objects from plugins that should be exported to the global namespace."""
        # Clear existing exports
        self.exports = {}
        
        # Get all plugins
        for plugin in self.manager.get_plugins():
            try:
                # Check if the plugin implements the exports_to_namespace hook
                if hasattr(plugin, "exports_to_namespace"):
                    exports = plugin.exports_to_namespace()
                    if exports:
                        # If plugin provides exports, add them to the exports dictionary
                        plugin_name = plugin.plugin_name()
                        for name, obj in exports.items():
                            # Log the export
                            logger.info(f"Plugin '{plugin_name}' exports '{name}' to global namespace")
                            self.exports[name] = obj
            except Exception as e:
                logger.warning(f"Error gathering exports from plugin: {str(e)}")
    
    def get_exports(self) -> Dict[str, Any]:
        """
        Get all objects that plugins export to the global namespace.
        
        Returns:
            Dictionary mapping names to exported objects
        """
        return self.exports

    def _reload_plugins(self) -> None:
        """Reload plugins and discover new methods."""
        # Reload setuptools entry points
        self.manager.load_setuptools_entrypoints("edsl_plugins")
        
        # Also check for directly installed plugins
        for plugin_name, plugin_dir in self.installed_plugins.items():
            try:
                if os.path.exists(plugin_dir):
                    # Try to find the main plugin module
                    plugin_module = os.path.join(plugin_dir, plugin_name.lower())
                    if os.path.exists(f"{plugin_module}.py"):
                        spec = importlib.util.spec_from_file_location(plugin_name, f"{plugin_module}.py")
                        if spec:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            # Try to register the plugin class
                            if hasattr(module, plugin_name):
                                plugin_class = getattr(module, plugin_name)
                                self.manager.register(plugin_class())
                                logger.info(f"Registered plugin {plugin_name} from {plugin_dir}")
            except Exception as e:
                logger.warning(f"Error loading plugin {plugin_name} from {plugin_dir}: {str(e)}")
                
        # Rediscover methods
        self._discover_methods()
        
        # Gather exports from plugins
        self._gather_exports()
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """
        Uninstall a plugin by name.
        
        Args:
            plugin_name: Name of the plugin to uninstall
            
        Returns:
            True if uninstallation was successful
            
        Raises:
            PluginNotFoundError: If the plugin is not installed
            PluginInstallationError: If uninstallation fails
        """
        # Check if plugin is installed directly
        if plugin_name in self.installed_plugins:
            actual_name = plugin_name
        else:
            # Try to find the plugin using case-insensitive matching and pattern recognition
            actual_name = None
            for installed_name in self.installed_plugins:
                # Check for exact match ignoring case
                if installed_name.lower() == plugin_name.lower():
                    actual_name = installed_name
                    break
                
                # Check for matches with common prefix/suffix variations
                normalized_installed = installed_name.lower()
                normalized_requested = plugin_name.lower()
                
                # Strip common prefixes/suffixes for comparison
                for prefix in ["edsl-", "plugin-"]:
                    if normalized_installed.startswith(prefix):
                        normalized_installed = normalized_installed[len(prefix):]
                    if normalized_requested.startswith(prefix):
                        normalized_requested = normalized_requested[len(prefix):]
                
                for suffix in ["-plugin"]:
                    if normalized_installed.endswith(suffix):
                        normalized_installed = normalized_installed[:-len(suffix)]
                    if normalized_requested.endswith(suffix):
                        normalized_requested = normalized_requested[:-len(suffix)]
                
                # Compare normalized names
                if normalized_installed == normalized_requested:
                    actual_name = installed_name
                    break
            
            if actual_name is None:
                raise PluginNotFoundError(f"Plugin '{plugin_name}' is not installed")
        
        try:
            package_dir = self.installed_plugins[actual_name]
            logger.debug(f"Uninstalling plugin '{actual_name}' from {package_dir}")
            
            # Determine pip package name
            pip_package_name = actual_name
            
            # Try to get the actual package name from setup.py or pyproject.toml
            setup_py = os.path.join(package_dir, 'setup.py')
            if os.path.exists(setup_py):
                with open(setup_py, 'r') as f:
                    content = f.read()
                    match = re.search(r"name=['\"]([^'\"]+)['\"]", content)
                    if match:
                        pip_package_name = match.group(1)
            
            pyproject_toml = os.path.join(package_dir, 'pyproject.toml')
            if os.path.exists(pyproject_toml):
                with open(pyproject_toml, 'r') as f:
                    content = f.read()
                    match = re.search(r"name\s*=\s*['\"]([^'\"]+)['\"]", content)
                    if match:
                        pip_package_name = match.group(1)
            
            # Uninstall the package using pip
            cmd = [sys.executable, '-m', 'pip', 'uninstall', '-y', pip_package_name]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Remove from installed plugins
            del self.installed_plugins[actual_name]
            # Save the updated list of installed plugins
            self._save_installed_plugins()
            
            # Reload plugins
            self._reload_plugins()
            
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if hasattr(e, 'stderr') else str(e)
            raise PluginInstallationError(f"Failed to uninstall plugin: {error_msg}")
    
    def _register_builtin_plugins(self):
        """Register built-in plugins."""
        # Import and register internal plugins
        from .built_in.pig_latin import PigLatin
        self.manager.register(PigLatin())
        
        # Register the export example plugin
        try:
            from .built_in.export_example import ExportExample
            self.manager.register(ExportExample())
        except ImportError:
            # In case the file isn't there or has issues
            logger.warning("Failed to load export_example plugin")
    
    def _discover_methods(self):
        """Discover and register all plugin methods."""
        # Clear existing methods
        self.methods = {}
        
        # Get all plugin names
        for plugin in self.manager.get_plugins():
            try:
                # Call the hook method directly on the plugin instance
                plugin_name = plugin.plugin_name()
                
                # Get methods from this plugin
                methods = plugin.get_plugin_methods()
    
                # Register methods with their full names and shortcuts
                if methods:
                    for method_name, method in methods.items():
                        # Create a bound method that takes the plugin instance as the first argument
                        bound_method = lambda *args, m=method, **kwargs: m(*args, **kwargs)
                        
                        # Full qualified name
                        full_name = f"{plugin_name}.{method_name}"
                        self.methods[full_name] = bound_method
                        
                        # Register shorthand if not already taken
                        if method_name not in self.methods:
                            self.methods[method_name] = bound_method
            except Exception as e:
                logger.warning(f"Error discovering methods for plugin: {str(e)}")
    
    def get_method(self, name: str) -> Optional[callable]:
        """
        Get a method by name.
        
        Args:
            name: Method name, can be shorthand or fully qualified
            
        Returns:
            Method function or None if not found
            
        Raises:
            PluginMethodError: If the method is not found but a plugin is
        """
        if name in self.methods:
            return self.methods[name]
            
        # If the name looks like a fully qualified name (plugin.method)
        # but the plugin exists and the method doesn't, give a more helpful error
        if '.' in name:
            plugin_name = name.split('.')[0]
            for plugin in self.manager.get_plugins():
                if plugin.plugin_name() == plugin_name:
                    method_name = name.split('.')[1]
                    raise PluginMethodError(
                        f"Plugin '{plugin_name}' exists but method '{method_name}' was not found"
                    )
        
        # Method not found
        return None
    
    def list_methods(self) -> List[str]:
        """
        List all available methods.
        
        Returns:
            Sorted list of method names
        """
        return sorted(self.methods.keys())
        
    def list_plugins(self) -> Dict[str, Dict[str, Any]]:
        """
        List all installed plugins with their details.
        
        Returns:
            Dictionary mapping plugin names to details
        """
        plugins_info = {}
        
        # Get plugins from the plugin manager
        for plugin in self.manager.get_plugins():
            try:
                name = plugin.plugin_name()
                
                # Gather details
                plugin_info = {
                    "name": name,
                    "description": plugin.plugin_description() if hasattr(plugin, "plugin_description") else None,
                    "methods": list(plugin.get_plugin_methods().keys()) if hasattr(plugin, "get_plugin_methods") else [],
                    "installed_from": self.installed_plugins.get(name, "built-in")
                }
                
                plugins_info[name] = plugin_info
                
            except Exception as e:
                logger.warning(f"Error getting info for plugin: {str(e)}")
        
        # Also include all plugins from installed_plugins.json even if they're not loaded
        for name, install_dir in self.installed_plugins.items():
            if name not in plugins_info:
                # Try to find description from standard paths
                description = None
                try:
                    # First check if we can find a description in setup.py or pyproject.toml
                    setup_py = os.path.join(install_dir, 'setup.py')
                    if os.path.exists(setup_py):
                        with open(setup_py, 'r') as f:
                            content = f.read()
                            # Look for description="..." pattern
                            match = re.search(r"description=['\"]([^'\"]+)['\"]", content)
                            if match:
                                description = match.group(1)
                    
                    pyproject_toml = os.path.join(install_dir, 'pyproject.toml')
                    if not description and os.path.exists(pyproject_toml):
                        with open(pyproject_toml, 'r') as f:
                            content = f.read()
                            # Look for description = "..." pattern
                            match = re.search(r"description\s*=\s*['\"]([^'\"]+)['\"]", content)
                            if match:
                                description = match.group(1)
                    
                    # If still no description, check for README files
                    if not description:
                        for readme_file in ["README.md", "README.rst", "README.txt"]:
                            readme_path = os.path.join(install_dir, readme_file)
                            if os.path.exists(readme_path):
                                with open(readme_path, 'r') as f:
                                    # Skip any markdown headers
                                    first_line = f.readline().strip()
                                    if first_line.startswith('#'):
                                        # Take the next line that's not empty
                                        for line in f:
                                            if line.strip():
                                                first_line = line.strip()
                                                break
                                    description = first_line[:100] + "..." if len(first_line) > 100 else first_line
                                    break
                except Exception as e:
                    logger.debug(f"Error extracting description for {name}: {e}")
                
                # Add basic info for installed but not loaded plugins
                plugins_info[name] = {
                    "name": name,
                    "description": description or f"Plugin installed at {install_dir}",
                    "methods": [],
                    "installed_from": install_dir,
                    "version": "unknown"
                }
                
        return plugins_info