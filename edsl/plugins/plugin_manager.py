# edsl/plugins/plugin_manager.py
import os
import sys
import subprocess
import tempfile
import importlib
import importlib.util
import shutil
import re
from typing import Optional, List, Dict, Any
import pluggy
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
        self.installed_plugins = {}
        # Register built-in plugins
        self._register_builtin_plugins()
        # Discover and register methods
        self._discover_methods()

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
        
        try:
            # Create temporary directory for cloning
            with tempfile.TemporaryDirectory() as temp_dir:
                # Clone the repository
                self._clone_repository(github_url, temp_dir, branch)
                
                # Check for setup.py or pyproject.toml
                if not self._has_package_files(temp_dir):
                    raise InvalidPluginError(
                        f"Repository at {github_url} does not contain required setup.py or pyproject.toml"
                    )
                
                # Install the package in development mode
                installed_plugins = self._install_package(temp_dir)
                
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
        
        # Default to directory name
        return os.path.basename(os.path.normpath(package_dir))
    
    def _reload_plugins(self) -> None:
        """Reload plugins and discover new methods."""
        # Reload setuptools entry points
        self.manager.load_setuptools_entrypoints("edsl_plugins")
        # Rediscover methods
        self._discover_methods()
    
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
        # Check if plugin is installed
        if plugin_name not in self.installed_plugins:
            raise PluginNotFoundError(f"Plugin '{plugin_name}' is not installed")
        
        try:
            # Uninstall the package
            cmd = [sys.executable, '-m', 'pip', 'uninstall', '-y', plugin_name]
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Remove from installed plugins
            del self.installed_plugins[plugin_name]
            
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
                
        return plugins_info