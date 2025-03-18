"""
Module for installing plugins from GitHub repositories, with support for private repositories using deploy keys.
"""

import os
import sys
import time
import signal
import tempfile
import subprocess
import threading
from pathlib import Path
from contextlib import contextmanager

from ..logger import logger
from ..config import CONFIG
from .exceptions import PluginInstallationError, GitHubRepoError

class TimeoutError(Exception):
    """Exception raised when a command times out."""
    pass

@contextmanager
def timeout_context(seconds, message="Operation timed out"):
    """
    Context manager to timeout operations.
    
    Args:
        seconds (int): Number of seconds before timing out
        message (str): Message to include in the TimeoutError
        
    Raises:
        TimeoutError: If the operation times out
    """
    def timeout_handler(signum, frame):
        raise TimeoutError(message)
        
    # Set handler for SIGALRM
    original_handler = signal.getsignal(signal.SIGALRM)
    try:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)  # Cancel the alarm
        signal.signal(signal.SIGALRM, original_handler)

def run_with_timeout(cmd, timeout_seconds=300, env=None, cwd=None, debug=False):
    """
    Run a command with timeout and detailed debugging.
    
    Args:
        cmd (list): Command to run as a list of strings
        timeout_seconds (int): Timeout in seconds
        env (dict): Environment variables
        cwd (str): Working directory
        debug (bool): Whether to print debug output
        
    Returns:
        subprocess.CompletedProcess: Result of the command
        
    Raises:
        TimeoutError: If the command times out
        subprocess.CalledProcessError: If the command fails
    """
    # For debugging
    print(f"DEBUG: Running command: {' '.join(cmd)}")
    print(f"DEBUG: Timeout: {timeout_seconds} seconds")
    print(f"DEBUG: Working directory: {cwd or 'current'}")
    
    # Start process
    process = subprocess.Popen(
        cmd,
        env=env,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Create output collectors
    stdout_parts = []
    stderr_parts = []
    
    def read_stream(stream, parts):
        """Read from stream and append to parts."""
        for line in stream:
            parts.append(line)
            if debug:
                print(f"DEBUG: {line.strip()}")
    
    # Create threads to read stdout and stderr
    stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, stdout_parts))
    stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, stderr_parts))
    
    # Start reading threads
    stdout_thread.daemon = True
    stderr_thread.daemon = True
    stdout_thread.start()
    stderr_thread.start()
    
    # Wait for process with timeout
    start_time = time.time()
    try:
        returncode = process.wait(timeout=timeout_seconds)
        
        # Wait for threads to finish reading
        stdout_thread.join(1)
        stderr_thread.join(1)
        
        print(f"DEBUG: Command completed in {time.time() - start_time:.2f} seconds")
        
        # Prepare the result
        result = subprocess.CompletedProcess(
            cmd, returncode, 
            stdout=''.join(stdout_parts),
            stderr=''.join(stderr_parts)
        )
        
        if result.returncode != 0:
            print(f"DEBUG: Command failed with code {result.returncode}")
            print(f"DEBUG: stderr: {result.stderr}")
            raise subprocess.CalledProcessError(
                result.returncode, cmd, output=result.stdout, stderr=result.stderr
            )
            
        return result
        
    except subprocess.TimeoutExpired:
        # Terminate the process if it times out
        print(f"DEBUG: Command timed out after {timeout_seconds} seconds")
        process.terminate()
        try:
            process.wait(3)
        except subprocess.TimeoutExpired:
            process.kill()
            print("DEBUG: Had to forcefully kill the process")
            
        raise TimeoutError(f"Command timed out after {timeout_seconds} seconds: {' '.join(cmd)}")

def setup_ssh_with_deploy_key(deploy_key):
    """
    Create a temporary SSH key file and set up the environment for SSH.
    
    Args:
        deploy_key (str): The deploy key content
        
    Returns:
        dict: Environment variables including GIT_SSH_COMMAND
        str: Path to the temporary directory containing the key file
    """
    print("DEBUG: Setting up SSH with deploy key")
    temp_dir = tempfile.mkdtemp()
    print(f"DEBUG: Created temporary directory for SSH key: {temp_dir}")
    
    # Create deploy key file
    key_file = os.path.join(temp_dir, "deploy_key")
    with open(key_file, "w") as f:
        f.write(deploy_key)
    
    # Set correct permissions
    os.chmod(key_file, 0o600)
    print(f"DEBUG: Created SSH key file with 0600 permissions: {key_file}")
    
    # Set the SSH command with verbose logging
    ssh_cmd = f'ssh -vvv -i "{key_file}" -o StrictHostKeyChecking=no'
    env = os.environ.copy()
    env["GIT_SSH_COMMAND"] = ssh_cmd
    
    print(f"DEBUG: SSH command set to: {ssh_cmd}")
    print("DEBUG: SSH environment configured successfully")
    
    return env, temp_dir

def install_plugin_from_github(repo_url, branch="main", install_args=None, debug=True, timeout=300):
    """
    Install a plugin directly from a GitHub repository using git clone and pip.
    
    Args:
        repo_url (str): The URL of the GitHub repository (HTTPS or SSH)
        branch (str, optional): The branch to install from. Defaults to "main".
        install_args (list, optional): Additional arguments to pass to pip install.
        debug (bool, optional): Whether to enable debug output. Defaults to True.
        timeout (int, optional): Timeout in seconds for operations. Defaults to 300.
        
    Returns:
        bool: True if installation was successful
        
    Raises:
        PluginInstallationError: If there is an error installing the plugin
        GitHubRepoError: If there is an error with the repository URL or access
        TimeoutError: If the installation times out
    """
    print(f"DEBUG: Starting installation of plugin from: {repo_url}")
    logger.info(f"Installing plugin from GitHub repository: {repo_url}")
    
    try:
        # Check if this is a private repository
        is_private = "private" in repo_url or repo_url.startswith("git@github.com")
        print(f"DEBUG: Repository is {'private' if is_private else 'public'}")
        
        # Try to get deploy key from config
        deploy_key = CONFIG.get("EDSL_PRIVATE_PLUGIN_DEPLOY_KEY")
        if deploy_key == "None":
            deploy_key = None
        
        print(f"DEBUG: Deploy key {'found' if deploy_key else 'not found'}")
            
        # For private repos, verify we have a deploy key
        if is_private and not deploy_key:
            print("DEBUG: ERROR - Private repository without deploy key")
            raise PluginInstallationError(
                "Attempting to install from a private repository but EDSL_PRIVATE_PLUGIN_DEPLOY_KEY is not set."
            )
        
        # Create a temporary directory for cloning
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"DEBUG: Using temporary directory for installation: {temp_dir}")
            logger.info(f"Using temporary directory for installation: {temp_dir}")
            
            # Set up environment variables and temporary path for SSH
            env = os.environ.copy()
            ssh_temp_dir = None
            
            if is_private and deploy_key:
                print("DEBUG: Using deploy key for private repository")
                logger.info("Using deploy key for private repository")
                env, ssh_temp_dir = setup_ssh_with_deploy_key(deploy_key)
            
            try:
                # Clone the repository
                git_clone_cmd = ["git", "clone"]
                if branch and branch != "main":
                    git_clone_cmd.extend(["-b", branch])
                git_clone_cmd.extend([repo_url, temp_dir])
                
                print(f"DEBUG: Running git clone: {' '.join(git_clone_cmd)}")
                logger.debug(f"Running git clone: {' '.join(git_clone_cmd)}")
                
                try:
                    # Run git clone with timeout
                    clone_result = run_with_timeout(
                        git_clone_cmd,
                        timeout_seconds=timeout,
                        env=env,
                        debug=debug
                    )
                    print("DEBUG: Repository cloned successfully")
                except TimeoutError as e:
                    print(f"DEBUG: Git clone operation timed out after {timeout} seconds")
                    logger.error(f"Git clone operation timed out: {str(e)}")
                    raise PluginInstallationError(f"Git clone operation timed out after {timeout} seconds")
                except subprocess.CalledProcessError as e:
                    print(f"DEBUG: Git clone failed: {e.stderr}")
                    error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
                    raise GitHubRepoError(f"Failed to clone repository: {error_msg}")
                
                # Install the package with pip
                pip_install_cmd = [sys.executable, "-m", "pip", "install", "-e", temp_dir]
                if install_args:
                    pip_install_cmd.extend(install_args)
                
                print(f"DEBUG: Running pip install: {' '.join(pip_install_cmd)}")
                logger.debug(f"Running pip install: {' '.join(pip_install_cmd)}")
                
                try:
                    # Run pip install with timeout
                    install_result = run_with_timeout(
                        pip_install_cmd,
                        timeout_seconds=timeout,
                        debug=debug
                    )
                    print("DEBUG: Package installed successfully")
                except TimeoutError as e:
                    print(f"DEBUG: Pip install operation timed out after {timeout} seconds")
                    logger.error(f"Pip install operation timed out: {str(e)}")
                    raise PluginInstallationError(f"Pip install operation timed out after {timeout} seconds")
                except subprocess.CalledProcessError as e:
                    print(f"DEBUG: Pip install failed: {e.stderr}")
                    error_msg = e.stderr if hasattr(e, 'stderr') else str(e)
                    raise PluginInstallationError(f"Failed to install package: {error_msg}")
                
                print(f"DEBUG: Successfully installed plugin from {repo_url}")
                logger.info(f"Successfully installed plugin from {repo_url}")
                return True
                
            finally:
                # Clean up SSH key directory
                if ssh_temp_dir and os.path.exists(ssh_temp_dir):
                    print(f"DEBUG: Cleaning up SSH temporary directory: {ssh_temp_dir}")
                    logger.debug(f"Cleaning up SSH temporary directory: {ssh_temp_dir}")
                    try:
                        for file in os.listdir(ssh_temp_dir):
                            file_path = os.path.join(ssh_temp_dir, file)
                            print(f"DEBUG: Removing file: {file_path}")
                            os.remove(file_path)
                        print(f"DEBUG: Removing directory: {ssh_temp_dir}")
                        os.rmdir(ssh_temp_dir)
                    except Exception as e:
                        print(f"DEBUG: Error cleaning up SSH directory: {e}")
                        logger.warning(f"Error cleaning up SSH directory: {e}")
        
    except Exception as e:
        print(f"DEBUG: Error installing plugin from GitHub: {str(e)}")
        logger.error(f"Error installing plugin from GitHub: {str(e)}")
        if isinstance(e, (PluginInstallationError, GitHubRepoError, TimeoutError)):
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