#!/usr/bin/env python3
"""Script to install the edsl-autostudy plugin using the deploy key."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Import the plugin installer
from edsl.plugins.github_plugin_installer import install_plugin_from_github

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
    
    # Ensure the key is set in config for the installer to find
    from edsl.config import CONFIG
    # Set environment variable which will be picked up by CONFIG
    os.environ["EDSL_PRIVATE_PLUGIN_DEPLOY_KEY"] = deploy_key
    
    print(f"Deploy key loaded ({len(deploy_key)} characters)")
    print("Installing edsl-autostudy plugin...")
    
    try:
        # Using SSH URL format for GitHub
        repo_url = "git@github.com:expectedparrot/edsl-autostudy.git"
        success = install_plugin_from_github(repo_url, debug=True)
        
        if success:
            print("Successfully installed the plugin!")
            # List installed plugins
            try:
                import subprocess
                print("\nVerifying installation:")
                result = subprocess.run(
                    ["edsl", "plugins", "list"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                print(result.stdout)
            except Exception as e:
                print(f"Warning: Could not verify installation: {e}")
        return 0
    except Exception as e:
        print(f"Error installing plugin: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())