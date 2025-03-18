"""
Utility for installing plugins from GitHub repositories, with support for private repositories using deploy keys.
"""

import os
import tempfile
import subprocess
from pathlib import Path

from edsl.logger import logger
from edsl.config import CONFIG

class GitHubPluginInstallError(Exception):
    """Raised when there is an error installing a plugin from GitHub."""
    pass

def install_plugin_from_github(repo_url, branch="main", install_args=None):
    """
    Install a plugin directly from a GitHub repository using pip.
    
    Args:
        repo_url (str): The URL of the GitHub repository.
        branch (str, optional): The branch to install from. Defaults to "main".
        install_args (list, optional): Additional arguments to pass to pip install. Defaults to None.
    
    Returns:
        bool: True if installation was successful, False otherwise.
        
    Raises:
        GitHubPluginInstallError: If there is an error installing the plugin.
    """
    logger.info(f"Installing plugin from GitHub repository: {repo_url}")
    
    try:
        # Check if this is a private repository and we need to use deploy key
        is_private = "private" in repo_url or repo_url.startswith("git@github.com")
        deploy_key = CONFIG.get("EDSL_PRIVATE_PLUGIN_DEPLOY_KEY") if hasattr(CONFIG, "EDSL_PRIVATE_PLUGIN_DEPLOY_KEY") else None
        
        if is_private and not deploy_key:
            raise GitHubPluginInstallError(
                "Attempting to install from a private repository but EDSL_PRIVATE_PLUGIN_DEPLOY_KEY is not set."
            )
        
        # For HTTP URLs, convert to git+https format
        if repo_url.startswith("https://"):
            pip_url = f"git+{repo_url}@{branch}"
        # For SSH URLs, convert to git+ssh format
        elif repo_url.startswith("git@"):
            if "@" in repo_url and ":" in repo_url.split("@")[1]:
                # Convert from git@github.com:owner/repo.git to git+ssh://git@github.com/owner/repo.git
                parts = repo_url.split(":")
                host = parts[0]  # git@github.com
                path = parts[1]  # owner/repo.git
                pip_url = f"git+ssh://{host}/{path}@{branch}"
            else:
                raise GitHubPluginInstallError(
                    f"Invalid SSH URL format: {repo_url}. Expected format: git@github.com:owner/repo.git"
                )
        else:
            raise GitHubPluginInstallError(
                f"Unsupported repository URL format: {repo_url}. Use HTTPS or SSH format."
            )
        
        # For private repositories with deploy key, use SSH
        if is_private and deploy_key:
            with tempfile.TemporaryDirectory() as temp_dir:
                logger.info("Using deploy key for private repository")
                # Create a temporary SSH key file
                key_file = os.path.join(temp_dir, "deploy_key")
                with open(key_file, "w") as f:
                    f.write(deploy_key)
                os.chmod(key_file, 0o600)  # Set appropriate permissions
                
                # Set up SSH command with the key
                ssh_cmd = f'ssh -i "{key_file}" -o StrictHostKeyChecking=no'
                env = os.environ.copy()
                env["GIT_SSH_COMMAND"] = ssh_cmd
                
                # Install using pip
                install_cmd = ["pip", "install", pip_url]
                if install_args:
                    install_cmd.extend(install_args)
                    
                install_result = subprocess.run(
                    install_cmd,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Remove key file immediately after installation
                if os.path.exists(key_file):
                    os.remove(key_file)
                
                if install_result.returncode != 0:
                    raise GitHubPluginInstallError(
                        f"Failed to install plugin: {install_result.stderr}"
                    )
        else:
            # For public repositories, simply use pip install
            install_cmd = ["pip", "install", pip_url]
            if install_args:
                install_cmd.extend(install_args)
                
            install_result = subprocess.run(
                install_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if install_result.returncode != 0:
                raise GitHubPluginInstallError(
                    f"Failed to install plugin: {install_result.stderr}"
                )
        
        logger.info(f"Successfully installed plugin from {repo_url}")
        return True
        
    except Exception as e:
        logger.error(f"Error installing plugin from GitHub: {str(e)}")
        raise GitHubPluginInstallError(f"Error installing plugin from GitHub: {str(e)}")


def install_plugin_from_local_path(path, install_args=None):
    """
    Install a plugin from a local path.
    
    Args:
        path (str): The path to the plugin directory.
        install_args (list, optional): Additional arguments to pass to pip install. Defaults to None.
    
    Returns:
        bool: True if installation was successful, False otherwise.
        
    Raises:
        GitHubPluginInstallError: If there is an error installing the plugin.
    """
    logger.info(f"Installing plugin from local path: {path}")
    
    try:
        # Ensure the path exists
        if not os.path.exists(path):
            raise GitHubPluginInstallError(f"Plugin path does not exist: {path}")
        
        # Install the package
        install_cmd = ["pip", "install", "-e", path]
        if install_args:
            install_cmd.extend(install_args)
            
        install_result = subprocess.run(
            install_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if install_result.returncode != 0:
            raise GitHubPluginInstallError(
                f"Failed to install plugin: {install_result.stderr}"
            )
        
        logger.info(f"Successfully installed plugin from {path}")
        return True
        
    except Exception as e:
        logger.error(f"Error installing plugin from local path: {str(e)}")
        raise GitHubPluginInstallError(f"Error installing plugin from local path: {str(e)}")