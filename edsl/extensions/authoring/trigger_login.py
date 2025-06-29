"""Trigger login functionality for EDSL authoring."""

import os
from pathlib import Path
from dotenv import dotenv_values

from edsl.jobs.jobs_checks import JobsChecks
from edsl.jobs import Jobs


def _check_existing_ep_key() -> bool:
    """Check if an Expected Parrot API key already exists in .env file."""
    env_paths = [
        Path.cwd() / ".env",
        Path.home() / ".env",
    ]
    
    for env_path in env_paths:
        if env_path.exists():
            env_vars = dotenv_values(env_path)
            if env_vars.get("EXPECTED_PARROT_API_KEY"):
                return True
    
    # Also check if it's already loaded in environment
    return bool(os.getenv("EXPECTED_PARROT_API_KEY"))


def trigger_login(refresh: bool = False) -> None:
    """Trigger the login process by running the key process check.
    
    Args:
        refresh: If True, force a new login even if EP key already exists.
                If False, skip login if EP key is already available.
    """
    if not refresh and _check_existing_ep_key():
        print("Expected Parrot API key already exists. Use refresh=True to get a new key.")
        return
    
    JobsChecks(Jobs.example()).key_process()