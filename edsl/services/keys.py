"""
KEYS: Standardized credential access for external service workers.

Provides a unified interface for workers to access API keys and credentials.
Keys can come from environment variables, configuration files, or be passed
directly.

Example:
    >>> from edsl.services import KEYS
    >>> 
    >>> # Get a specific key
    >>> api_key = KEYS.get("EXA_API_KEY")
    >>> 
    >>> # Get all keys as a dict (for passing to workers)
    >>> keys_dict = KEYS.to_dict()
    >>> 
    >>> # Check if a key is available
    >>> if KEYS.has("FIRECRAWL_API_KEY"):
    ...     print("Firecrawl is configured")
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Any

# Load .env file if present
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


class KEYS:
    """
    Standardized credential access for workers.

    Workers use this class to access API keys for external services.
    Keys are resolved in order:
    1. Explicitly set values (via set())
    2. Environment variables
    3. EDSL configuration (if available)

    Common key names:
        - EXA_API_KEY: Exa web search API
        - FIRECRAWL_API_KEY: Firecrawl web scraping API
        - HUGGINGFACE_TOKEN: Hugging Face Hub access
        - REDUCTO_API_KEY: Reducto PDF processing API
        - OPENAI_API_KEY: OpenAI API (for AI-based services)
    """

    # Explicitly set keys (override everything)
    _explicit: Dict[str, str] = {}

    # Known key names for documentation/validation
    KNOWN_KEYS: List[str] = [
        "EXA_API_KEY",
        "FIRECRAWL_API_KEY",
        "HUGGINGFACE_TOKEN",
        "REDUCTO_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "MANUS_API_KEY",
        "PERPLEXITY_API_KEY",
    ]

    @classmethod
    def get(cls, key_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a key by name.

        Resolution order:
        1. Explicitly set values
        2. Environment variables
        3. EDSL configuration

        Args:
            key_name: The key name (e.g., "EXA_API_KEY")
            default: Default value if key not found

        Returns:
            The key value, or default if not found
        """
        # 1. Check explicit values
        if key_name in cls._explicit:
            return cls._explicit[key_name]

        # 2. Check environment variables
        env_value = os.getenv(key_name)
        if env_value is not None:
            return env_value

        # 3. Check EDSL configuration
        config_value = cls._from_config(key_name)
        if config_value is not None:
            return config_value

        return default

    @classmethod
    def _from_config(cls, key_name: str) -> Optional[str]:
        """
        Get a key from EDSL configuration.

        Args:
            key_name: The key name

        Returns:
            The key value, or None if not found
        """
        try:
            from edsl.config import CONFIG

            # Try to get from CONFIG
            # Keys might be stored with different naming conventions
            if hasattr(CONFIG, key_name):
                return getattr(CONFIG, key_name)

            # Try lowercase
            lower_name = key_name.lower()
            if hasattr(CONFIG, lower_name):
                return getattr(CONFIG, lower_name)

            # Try getting from expected_parrot_api_key for common keys
            # This handles the EDSL-specific key storage

        except ImportError:
            pass
        except Exception:
            pass

        return None

    @classmethod
    def set(cls, key_name: str, value: str) -> None:
        """
        Explicitly set a key value.

        This overrides environment variables and configuration.

        Args:
            key_name: The key name
            value: The key value
        """
        cls._explicit[key_name] = value

    @classmethod
    def unset(cls, key_name: str) -> bool:
        """
        Remove an explicitly set key.

        Args:
            key_name: The key name

        Returns:
            True if key was removed, False if not found
        """
        if key_name in cls._explicit:
            del cls._explicit[key_name]
            return True
        return False

    @classmethod
    def has(cls, key_name: str) -> bool:
        """
        Check if a key is available.

        Args:
            key_name: The key name

        Returns:
            True if key is available (from any source)
        """
        return cls.get(key_name) is not None

    @classmethod
    def to_dict(cls, keys: Optional[List[str]] = None) -> Dict[str, str]:
        """
        Get multiple keys as a dictionary.

        Args:
            keys: List of key names to get. If None, gets all known keys
                  that have values.

        Returns:
            Dict mapping key name to value (only includes available keys)
        """
        if keys is None:
            keys = cls.KNOWN_KEYS

        result = {}
        for key_name in keys:
            value = cls.get(key_name)
            if value is not None:
                result[key_name] = value

        return result

    @classmethod
    def for_service(cls, service_name: str) -> Dict[str, str]:
        """
        Get keys required by a specific service.

        Args:
            service_name: Name of the service

        Returns:
            Dict of keys required by the service
        """
        from .registry import ServiceRegistry

        service = ServiceRegistry.get(service_name)
        if service is None:
            return {}

        required = service.get_required_keys()
        return cls.to_dict(required)

    @classmethod
    def validate_for_service(cls, service_name: str) -> tuple[bool, List[str]]:
        """
        Validate that all required keys for a service are available.

        Args:
            service_name: Name of the service

        Returns:
            Tuple of (all_available, missing_keys)
        """
        from .registry import ServiceRegistry

        service = ServiceRegistry.get(service_name)
        if service is None:
            return True, []

        required = service.get_required_keys()
        missing = [key for key in required if not cls.has(key)]

        return len(missing) == 0, missing

    @classmethod
    def clear_explicit(cls) -> None:
        """
        Clear all explicitly set keys.

        Primarily for testing.
        """
        cls._explicit.clear()

    @classmethod
    def require(cls, key_name: str) -> str:
        """
        Get a key, raising if not available.

        Args:
            key_name: The key name

        Returns:
            The key value

        Raises:
            ValueError: If key is not available
        """
        value = cls.get(key_name)
        if value is None:
            raise ValueError(
                f"Required key '{key_name}' not found. "
                f"Set it via environment variable or KEYS.set('{key_name}', 'value')"
            )
        return value
