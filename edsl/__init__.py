"""
EDSL: Experimental Design Specification Language

EDSL is a Python library for conducting virtual social science experiments, surveys, 
and interviews with large language models.
"""

import os
import time
import importlib
import pkgutil

from edsl.language_models import Model

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)

from edsl.__version__ import __version__
from edsl.config import Config, CONFIG

# NOTE: `ext` is lazily imported below via __getattr__ to avoid circular-import issues.

# Initialize and expose logger
from edsl import logger

# Set up logger with configuration from environment/config
# (We'll configure the logger after CONFIG is initialized below)

__all__ = ["logger", "Config", "CONFIG", "__version__"]

# Define modules for lazy loading
_LAZY_MODULES = {
    "dataset",
    "agents",
    "surveys",
    "questions",
    "scenarios",
    "language_models",
    "results",
    "caching",
    "notebooks",
    "coop",
    "instructions",
    "jobs",
    "base",
    "conversation",
    "extensions",
    "app",
    "comparisons",
}

# Cache for lazy-loaded modules
_module_cache = {}


def __getattr__(name):
    """Lazy loading of EDSL modules and their exports."""
    # First check if the attribute exists in the current module's globals
    # This handles functions/classes defined directly in __init__.py
    import sys
    current_module = sys.modules[__name__]
    current_module_dict = object.__getattribute__(current_module, '__dict__')
    if name in current_module_dict:
        return current_module_dict[name]
    
    # Check if it's a module we should lazy-load
    for module_name in _LAZY_MODULES:
        try:
            module = _module_cache.get(module_name)
            if module is None:
                module = importlib.import_module(f".{module_name}", package="edsl")
                _module_cache[module_name] = module

            # Check if the requested name is in this module
            if hasattr(module, name):
                return getattr(module, name)
        except ImportError:
            continue

    # Special handling for 'ext'
    if name == "ext":
        try:
            from edsl.extensions import ext

            return ext
        except Exception as e:
            logger.warning("Failed to import edsl.extensions.ext: %s", e)
            raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Configure logging from the config
logger.configure_from_config()

# Installs a custom exception handling routine for edsl exceptions
from .base.base_exception import BaseException

BaseException.install_exception_hook()

# Log the total number of items in __all__ for debugging
logger.debug(f"EDSL initialization complete with {len(__all__)} items in __all__")


def check_for_updates(silent: bool = False) -> dict:
    """
    Check if there's a newer version of EDSL available.

    Args:
        silent: If True, don't print any messages to console

    Returns:
        dict with version info if update is available, None otherwise
    """
    from edsl.coop import Coop

    coop = Coop()
    return coop.check_for_updates(silent=silent)


def _is_notebook_environment() -> bool:
    """
    Detect if we're running in a Jupyter/IPython notebook environment.
    
    Returns:
        bool: True if running in a notebook, False otherwise
    """
    try:
        # Check if IPython is available and we're in a notebook
        from IPython import get_ipython
        ipython = get_ipython()
        
        if ipython is None:
            return False
            
        # Check if we're in a notebook (has 'kernel' attribute)
        return hasattr(ipython, 'kernel')
    except ImportError:
        return False


def _display_notebook_login(login_url: str):
    """
    Display login interface for notebook environments.
    
    Args:
        login_url: The login URL to display
    """
    try:
        from IPython.display import display, HTML
        
        # Display as a styled HTML button interface
        html_content = f"""
        <div id="edsl-login-container" style="border: 2px solid #38bdf8; border-radius: 8px; padding: 20px; margin: 10px 0; background-color: #f8fafc;">
            <h3 style="color: #38bdf8; margin-top: 0;">E[🦜] Expected Parrot Login</h3>
            <p>Click the button below to log in and automatically store your API key:</p>
            <a href="{login_url}" target="_blank" 
               style="display: inline-block; background-color: #38bdf8; color: white; padding: 12px 24px; 
                      text-decoration: none; border-radius: 6px; font-weight: bold; margin: 10px 0;">
               🚀 Log in to Expected Parrot
            </a>
            <p style="font-size: 0.9em; color: #64748b;">
               Logging in will activate remote inference and other Expected Parrot features.
            </p>
            <div id="edsl-status" style="margin-top: 10px; font-weight: bold; color: #38bdf8;"></div>
        </div>
        """
        
        display(HTML(html_content))
        
    except ImportError:
        # Fallback to regular print if IPython is not available
        print(f"Please visit this URL to log in: {login_url}")


def _update_notebook_status(message: str, is_success: bool = False):
    """
    Update the status message in the notebook login interface.
    
    Args:
        message: Status message to display
        is_success: Whether this is a success message (changes color)
    """
    try:
        from IPython import get_ipython
        from IPython.display import display, Javascript
        
        ipython = get_ipython()
        if ipython and hasattr(ipython, 'kernel'):
            color = "#10b981" if is_success else "#38bdf8"  # green for success, blue for waiting
            
            js_code = f"""
            var statusDiv = document.getElementById('edsl-status');
            if (statusDiv) {{
                statusDiv.innerHTML = '{message}';
                statusDiv.style.color = '{color}';
            }}
            """
            
            # Simple approach: just use display(Javascript()) 
            # Accept that this creates a newline but only for final messages
            display(Javascript(js_code))
            
        else:
            # Not in notebook, fallback to print
            print(message)
        
    except (ImportError, AttributeError, Exception):
        # Fallback to regular print
        print(message)


class _SuppressOutput:
    """Context manager to completely suppress all output."""
    def __enter__(self):
        import sys
        import os
        import logging
        from io import StringIO
        
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        self._original_log_level = logging.getLogger().level
        
        # Redirect to devnull instead of StringIO to be extra sure
        devnull = open(os.devnull, 'w')
        sys.stdout = devnull
        sys.stderr = devnull
        logging.getLogger().setLevel(logging.CRITICAL)
        
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        import sys
        import logging
        
        sys.stdout.close() if hasattr(sys.stdout, 'close') else None
        sys.stderr.close() if hasattr(sys.stderr, 'close') else None
        
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
        logging.getLogger().setLevel(self._original_log_level)


def _poll_for_api_key_notebook(coop, edsl_auth_token: str, timeout: int = 120):
    """
    Poll for API key in notebook environment with HTML status updates instead of stdout spinner.
    
    Args:
        coop: Coop instance
        edsl_auth_token: The auth token to poll with
        timeout: Maximum time to wait
        
    Returns:
        str or None: API key if successful, None if timeout
    """
    import time
    from datetime import datetime
    
    start_poll_time = time.time()
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    frame_idx = 0
    
    while True:
        elapsed_time = time.time() - start_poll_time
        if elapsed_time > timeout:
            return None
            
        # Check for API key with complete output suppression
        with _SuppressOutput():
            api_key = coop._get_api_key(edsl_auth_token)
            if api_key is not None:
                return api_key
            
        # Skip dynamic updates to avoid newlines - just poll silently
        frame_idx += 1
        
        # Wait before next check
        time.sleep(1)  # Check every second instead of 5 seconds for better UX


def login(timeout: int = 120) -> None:
    """
    Start the Expected Parrot login process to obtain and store an API key.
    
    This function creates a Coop instance and initiates the login flow, which will:
    1. Generate a temporary authentication token
    2. Display a login URL for the user to visit (with enhanced notebook UI)
    3. Poll for the API key once the user completes the login
    4. Store the API key locally for future use
    
    In Jupyter/IPython notebooks, this will display a styled HTML interface
    with a clickable button that opens the login page in a new tab.
    
    Args:
        timeout: Maximum time to wait for login completion, in seconds (default: 120)
        
    Raises:
        CoopTimeoutError: If login times out
        CoopServerResponseError: If there are server communication issues
        
    Example:
        >>> from edsl import login
        >>> login()  # Shows styled button interface in notebooks
    """
    from edsl.coop import Coop
    import secrets
    from edsl.config import CONFIG
    from dotenv import load_dotenv

    # If we're in a notebook, handle the UI specially
    if _is_notebook_environment():
        # Generate auth token and URL (mirroring Coop._display_login_url logic)
        edsl_auth_token = secrets.token_urlsafe(16)
        login_url = f"{CONFIG.EXPECTED_PARROT_URL}/login?edsl_auth_token={edsl_auth_token}"
        
        # Display the enhanced notebook interface
        _display_notebook_login(login_url)
        
        # Show initial status
        _update_notebook_status("⏳ Waiting for login...")
        
        # Create Coop instance and poll for API key (notebook-friendly)
        coop = Coop()
        try:
            # Use notebook-specific polling to avoid stdout spinner
            api_key = _poll_for_api_key_notebook(coop, edsl_auth_token, timeout=timeout)
            if api_key:
                # Store the key
                coop.ep_key_handler.store_ep_api_key(api_key)
                os.environ["EXPECTED_PARROT_API_KEY"] = api_key

                _update_notebook_status("✅ Successfully logged in and stored API key!", is_success=True)
            else:
                _update_notebook_status("❌ Login timed out. Please try again.")
        except Exception as e:
            _update_notebook_status(f"❌ Login failed: {e}")
    else:
        # Use standard Coop login for non-notebook environments
        coop = Coop()
        coop.login()


# Add login to exports
__all__.append("login")


# Perform version check on import (non-blocking)
def _check_version_on_import():
    """Check for updates on package import in a non-blocking way."""
    import threading
    import os

    # Check if version check is disabled
    if os.getenv("EDSL_DISABLE_VERSION_CHECK", "").lower() in ["1", "true", "yes"]:
        return

    # Check if we've already checked recently (within 24 hours)
    cache_file = os.path.join(os.path.expanduser("~"), ".edsl_version_check")
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "r") as f:
                last_check = float(f.read().strip())
                if time.time() - last_check < 86400:  # 24 hours
                    return
    except Exception:
        pass

    def check_in_background():
        try:
            # Update cache file
            with open(cache_file, "w") as f:
                f.write(str(time.time()))

            # Perform the check
            from edsl.coop import Coop

            coop = Coop()
            coop.check_for_updates(silent=False)
        except Exception:
            # Silently fail
            pass

    # Run in a separate thread to avoid blocking imports
    thread = threading.Thread(target=check_in_background, daemon=True)
    thread.start()


# Run version check on import
# _check_version_on_import()  # Disabled to avoid triggering registry initialization during basic imports
