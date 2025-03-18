#!/usr/bin/env python3
"""Script to install the edsl-autostudy plugin using the deploy key."""

import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path
import platformdirs
from dotenv import load_dotenv

# Import the plugin installer
from edsl.plugins.github_plugin_installer import install_plugin_from_github

def manually_register_plugin(name, install_dir):
    """Manually register the plugin in the platformdirs data file."""
    # Get the plugins data directory
    plugins_data_dir = platformdirs.user_data_dir("edsl")
    plugins_data_file = os.path.join(plugins_data_dir, "installed_plugins.json")
    os.makedirs(plugins_data_dir, exist_ok=True)
    
    # Load existing plugins data
    plugins_data = {}
    if os.path.exists(plugins_data_file):
        try:
            with open(plugins_data_file, 'r') as f:
                plugins_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not decode {plugins_data_file}, creating new file")
    
    # Update with new plugin
    plugins_data[name] = install_dir
    
    # Save updated data
    with open(plugins_data_file, 'w') as f:
        json.dump(plugins_data, f)
    
    print(f"Plugin {name} registered in {plugins_data_file}")
    return True

def main():
    """Install the edsl-autostudy plugin."""
    # Load environment variables from .env file if present
    dotenv_path = Path(".env")
    if dotenv_path.exists():
        load_dotenv(dotenv_path)
        print("Loaded environment from .env file")
    else:
        load_dotenv()
    
    # Verify the deploy key is loaded
    deploy_key = os.getenv("EDSL_PRIVATE_PLUGIN_DEPLOY_KEY")
    if not deploy_key:
        print("Error: EDSL_PRIVATE_PLUGIN_DEPLOY_KEY environment variable not found")
        print("Please set this environment variable to your GitHub deploy key")
        print("You can do this by:")
        print("  1. Creating a .env file with EDSL_PRIVATE_PLUGIN_DEPLOY_KEY=your_key_here")
        print("  2. Or setting the environment variable directly: export EDSL_PRIVATE_PLUGIN_DEPLOY_KEY=your_key_here")
        return 1
    
    # Ensure the key is set in environment for the installer to find
    os.environ["EDSL_PRIVATE_PLUGIN_DEPLOY_KEY"] = deploy_key
    
    print(f"Deploy key loaded ({len(deploy_key)} characters)")
    print("Installing edsl-autostudy plugin...")
    
    # Create plugins directory in the platform-specific user data dir
    plugin_name = "autostudy"
    plugins_dir = os.path.join(platformdirs.user_data_dir("edsl"), "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    install_dir = os.path.join(plugins_dir, f"edsl-{plugin_name}")
    
    # Remove existing installation if it exists
    if os.path.exists(install_dir):
        print(f"Removing existing installation at {install_dir}")
        import shutil
        shutil.rmtree(install_dir)
    
    try:
        # Using SSH URL format for GitHub
        repo_url = "git@github.com:expectedparrot/edsl-autostudy.git"
        
        # Clone the repo to a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set up SSH with deploy key
            env = os.environ.copy()
            
            # Create temporary SSH key file
            key_file = os.path.join(temp_dir, "deploy_key")
            with open(key_file, "w") as f:
                f.write(deploy_key)
            os.chmod(key_file, 0o600)
            
            # Set SSH command
            ssh_cmd = f'ssh -i "{key_file}" -o StrictHostKeyChecking=no'
            env["GIT_SSH_COMMAND"] = ssh_cmd
            
            # Clone the repository
            print(f"Cloning repository to {install_dir}...")
            clone_cmd = ["git", "clone", repo_url, install_dir]
            clone_result = subprocess.run(
                clone_cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if clone_result.returncode != 0:
                print(f"Error cloning repository: {clone_result.stderr}")
                return 1
            
            print("Repository cloned successfully")
        
        # Verify the directory exists
        if not os.path.exists(install_dir):
            print(f"Error: Installation directory {install_dir} not found after cloning")
            return 1
        
        # Install the package
        install_cmd = [sys.executable, "-m", "pip", "install", "-e", install_dir]
        print(f"Installing package: {' '.join(install_cmd)}")
        
        install_result = subprocess.run(
            install_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if install_result.returncode != 0:
            print(f"Error installing package: {install_result.stderr}")
            return 1
        
        # Manually register the plugin
        manually_register_plugin(plugin_name, install_dir)
        
        print("Successfully installed the plugin!")
        
        # List installed plugins
        try:
            print("\nVerifying plugin data file:")
            plugins_data_file = os.path.join(platformdirs.user_data_dir("edsl"), "installed_plugins.json")
            if os.path.exists(plugins_data_file):
                with open(plugins_data_file, 'r') as f:
                    data = json.load(f)
                    print(f"Installed plugins: {json.dumps(data, indent=2)}")
            else:
                print(f"Warning: Plugin data file {plugins_data_file} not found")
        except Exception as e:
            print(f"Warning: Could not read plugin data file: {e}")
            
        return 0
    except Exception as e:
        print(f"Error installing plugin: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())