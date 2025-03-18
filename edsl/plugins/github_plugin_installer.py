"""
Module for installing plugins from GitHub repositories, with support for private repositories using deploy keys.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path

from ..logger import logger
from ..config import CONFIG
from .exceptions import PluginInstallationError, GitHubRepoError

def setup_ssh_with_deploy_key(deploy_key):
    """
    Create a temporary SSH key file and set up the environment for SSH.
    
    Args:
        deploy_key (str): The deploy key content
        
    Returns:
        dict: Environment variables including GIT_SSH_COMMAND
        str: Path to the temporary directory containing the key file
    """
    temp_dir = tempfile.mkdtemp()
    logger.info(f"Creating temporary SSH key file in {temp_dir}")
    
    # Create deploy key file
    key_file = os.path.join(temp_dir, "deploy_key")
    with open(key_file, "w") as f:
        f.write(deploy_key)
    
    # Set correct permissions
    os.chmod(key_file, 0o600)
    
    # Set the SSH command
    ssh_cmd = f'ssh -i "{key_file}" -o StrictHostKeyChecking=no'
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = ssh_cmd
    
    logger.debug("SSH environment configured successfully")
    
    return env, temp_dir

def install_plugin_from_github(repo_url, branch="main", install_args=None, debug=False):
    """
    Install a plugin directly from a GitHub repository using git clone and pip.
    
    Args:
        repo_url (str): The URL of the GitHub repository (HTTPS or SSH)
        branch (str, optional): The branch to install from. Defaults to "main".
        install_args (list, optional): Additional arguments to pass to pip install. 
        debug (bool, optional): Whether to enable debug output. Defaults to False.
        
    Returns:
        bool: True if installation was successful
        
    Raises:
        PluginInstallationError: If there is an error installing the plugin
        GitHubRepoError: If there is an error with the repository URL or access
    """
    logger.info(f"Installing plugin from GitHub repository: {repo_url}")
    
    try:
        # Check if this is a private repository
        is_private = "private" in repo_url or repo_url.startswith("git@github.com")
        
        # Try to get deploy key from config
        deploy_key = CONFIG.get("EDSL_PRIVATE_PLUGIN_DEPLOY_KEY")
        if deploy_key == "None":
            deploy_key = None
            
        # For private repos, verify we have a deploy key
        if is_private and not deploy_key:
            raise PluginInstallationError(
                "Attempting to install from a private repository but EDSL_PRIVATE_PLUGIN_DEPLOY_KEY is not set."
            )
        
        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            logger.info(f"Using temporary directory for installation: {temp_dir}")
            
            # Set up environment variables and temporary path for SSH
            env = os.environ.copy()
            ssh_temp_dir = None
            
            if is_private and deploy_key:
                logger.info("Using deploy key for private repository")
                env, ssh_temp_dir = setup_ssh_with_deploy_key(deploy_key)
            
            try:
                # Clone the repository
                git_clone_cmd = ["git", "clone"]
                if branch and branch != "main":
                    git_clone_cmd.extend(["-b", branch])
                git_clone_cmd.extend([repo_url, temp_dir])
                
                logger.debug(f"Running git clone: {' '.join(git_clone_cmd)}")
                clone_result = subprocess.run(
                    git_clone_cmd,
                    env=env,
                    stdout=subprocess.PIPE if not debug else None,
                    stderr=subprocess.PIPE if not debug else None,
                    text=True
                )
                
                if clone_result.returncode != 0:
                    error_msg = clone_result.stderr if hasattr(clone_result, 'stderr') else "Unknown error"
                    raise GitHubRepoError(f"Failed to clone repository: {error_msg}")
                
                # Install the package with pip
                pip_install_cmd = [sys.executable, "-m", "pip", "install", "-e", temp_dir]
                if install_args:
                    pip_install_cmd.extend(install_args)
                
                logger.debug(f"Running pip install: {' '.join(pip_install_cmd)}")
                install_result = subprocess.run(
                    pip_install_cmd,
                    stdout=subprocess.PIPE if not debug else None,
                    stderr=subprocess.PIPE if not debug else None,
                    text=True
                )
                
                if install_result.returncode != 0:
                    error_msg = install_result.stderr if hasattr(install_result, 'stderr') else "Unknown error"
                    raise PluginInstallationError(f"Failed to install package: {error_msg}")
                
                logger.info(f"Successfully installed plugin from {repo_url}")
                return True
                
            finally:
                # Clean up SSH key directory
                if ssh_temp_dir and os.path.exists(ssh_temp_dir):
                    logger.debug(f"Cleaning up SSH temporary directory: {ssh_temp_dir}")
                    try:
                        for file in os.listdir(ssh_temp_dir):
                            os.remove(os.path.join(ssh_temp_dir, file))
                        os.rmdir(ssh_temp_dir)
                    except Exception as e:
                        logger.warning(f"Error cleaning up SSH directory: {e}")
        
    except Exception as e:
        logger.error(f"Error installing plugin from GitHub: {str(e)}")
        if isinstance(e, (PluginInstallationError, GitHubRepoError)):
            raise
        raise PluginInstallationError(f"Error installing plugin from GitHub: {str(e)}")

def install_plugin_from_local_path(path, install_args=None):
    """
    Install a plugin from a local path.
    
    Args:
        path (str): The path to the plugin directory.
        install_args (list, optional): Additional arguments to pass to pip install.
        
    Returns:
        bool: True if installation was successful
        
    Raises:
        PluginInstallationError: If there is an error installing the plugin
    """
    logger.info(f"Installing plugin from local path: {path}")
    
    try:
        # Ensure the path exists
        if not os.path.exists(path):
            raise PluginInstallationError(f"Plugin path does not exist: {path}")
        
        # Check if it has setup.py or pyproject.toml
        if not (os.path.exists(os.path.join(path, 'setup.py')) or 
                os.path.exists(os.path.join(path, 'pyproject.toml'))):
            raise PluginInstallationError(
                f"Path does not contain a valid Python package (setup.py or pyproject.toml not found): {path}"
            )
        
        # Install the package
        install_cmd = [sys.executable, "-m", "pip", "install", "-e", path]
        if install_args:
            install_cmd.extend(install_args)
            
        install_result = subprocess.run(
            install_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if install_result.returncode != 0:
            raise PluginInstallationError(
                f"Failed to install plugin: {install_result.stderr}"
            )
        
        logger.info(f"Successfully installed plugin from {path}")
        return True
        
    except Exception as e:
        logger.error(f"Error installing plugin from local path: {str(e)}")
        if isinstance(e, PluginInstallationError):
            raise
        raise PluginInstallationError(f"Error installing plugin from local path: {str(e)}")