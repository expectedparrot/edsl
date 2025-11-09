"""
Utilities for creating and managing OpenAI clients with proper error handling.

This module provides helper functions for creating OpenAI clients that
properly handle missing API keys and provide user-friendly error messages.
"""

import os
from typing import Optional
from openai import OpenAI, OpenAIError


def create_openai_client(api_key: Optional[str] = None, **kwargs) -> OpenAI:
    """
    Create an OpenAI client with proper error handling for missing API keys.

    This function checks for the presence of an OpenAI API key before attempting
    to create a client. If the key is not found, it raises a user-friendly
    KeyManagementMissingKeyError instead of the raw OpenAI error.

    Parameters
    ----------
    api_key : str, optional
        The OpenAI API key. If not provided, will attempt to read from
        the OPENAI_API_KEY environment variable.
    **kwargs
        Additional keyword arguments to pass to the OpenAI client constructor.

    Returns
    -------
    OpenAI
        An initialized OpenAI client instance.

    Raises
    ------
    KeyManagementMissingKeyError
        If no API key is found in the environment or provided as an argument.

    Examples
    --------
    >>> # With API key in environment
    >>> client = create_openai_client()

    >>> # With explicit API key
    >>> client = create_openai_client(api_key="sk-...")

    >>> # With additional options
    >>> client = create_openai_client(timeout=30.0)
    """
    from ..key_management.exceptions import KeyManagementMissingKeyError

    # Check if API key is available
    effective_api_key = api_key or os.environ.get("OPENAI_API_KEY")

    if not effective_api_key:
        raise KeyManagementMissingKeyError(service="OpenAI", env_var="OPENAI_API_KEY")

    try:
        # Create the client
        if api_key:
            kwargs["api_key"] = api_key
        return OpenAI(**kwargs)
    except OpenAIError as e:
        # If we get an OpenAI error about the API key even though we checked,
        # wrap it in our custom exception
        if "api_key" in str(e).lower():
            raise KeyManagementMissingKeyError(
                service="OpenAI", env_var="OPENAI_API_KEY"
            ) from e
        # Otherwise, re-raise the original error
        raise
