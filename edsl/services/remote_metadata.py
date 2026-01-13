"""
Remote metadata cache for service information.

When edsl-services is not installed, this module fetches and caches
service metadata from the remote server to enable result parsing.

This allows clients to dispatch tasks and parse results without
having the service class installed locally.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RemoteServiceInfo:
    """Cached info about a remote service."""

    name: str
    result_pattern: str
    result_field: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    version: str = "1.0.0"
    required_keys: List[str] = field(default_factory=list)
    operations: List[str] = field(default_factory=list)
    extends: List[str] = field(default_factory=list)
    fetched_at: float = 0.0


class RemoteMetadataCache:
    """
    Caches service metadata from remote server.

    This allows clients to parse results without having
    the service class installed locally.

    Example:
        >>> cache = RemoteMetadataCache.get_instance()
        >>> info = cache.get("firecrawl")
        >>> if info:
        ...     print(f"Pattern: {info.result_pattern}")
    """

    _instance: Optional["RemoteMetadataCache"] = None

    def __init__(self):
        self._cache: Dict[str, RemoteServiceInfo] = {}
        self._aliases: Dict[str, str] = {}  # alias -> canonical name
        self._cache_ttl: float = 3600.0  # 1 hour
        self._last_full_fetch: float = 0.0
        self._client = None

    @classmethod
    def get_instance(cls) -> "RemoteMetadataCache":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for testing)."""
        cls._instance = None

    def _get_client(self):
        """Get HTTP client for remote server."""
        if self._client is not None:
            return self._client

        url = os.getenv("EXPECTED_PARROT_SERVICE_RUNNER_URL")
        if not url:
            return None

        from edsl.services_runner.client import TaskQueueClient

        self._client = TaskQueueClient(url)
        return self._client

    def _get_server_url(self) -> Optional[str]:
        """Get the remote server URL if configured."""
        return os.getenv("EXPECTED_PARROT_SERVICE_RUNNER_URL")

    def fetch_all_services(self, force: bool = False) -> Dict[str, RemoteServiceInfo]:
        """
        Fetch all service metadata from remote server.

        Args:
            force: If True, bypass cache TTL

        Returns:
            Dict of service name -> RemoteServiceInfo
        """
        now = time.time()

        # Check cache freshness
        if not force and (now - self._last_full_fetch) < self._cache_ttl:
            return self._cache

        client = self._get_client()
        if client is None:
            return self._cache

        try:
            response = client._request("GET", "/api/services")
            services = response.get("services", {})

            self._cache.clear()
            self._aliases.clear()

            for name, info in services.items():
                self._cache[name] = RemoteServiceInfo(
                    name=name,
                    result_pattern=info.get("result_pattern", "dict_passthrough"),
                    result_field=info.get("result_field"),
                    aliases=info.get("aliases", []),
                    description=info.get("description", ""),
                    version=info.get("version", "1.0.0"),
                    required_keys=info.get("required_keys", []),
                    operations=info.get("operations", []),
                    extends=info.get("extends", []),
                    fetched_at=now,
                )
                # Index aliases
                for alias in info.get("aliases", []):
                    self._aliases[alias] = name

            self._last_full_fetch = now

        except Exception as e:
            # Log but don't fail - use cached data
            import sys

            print(
                f"Warning: Failed to fetch service metadata: {e}",
                file=sys.stderr,
            )

        return self._cache

    def get(self, service_name: str) -> Optional[RemoteServiceInfo]:
        """
        Get metadata for a specific service.

        Args:
            service_name: Service name or alias

        Returns:
            RemoteServiceInfo or None if not found
        """
        # First check local cache
        if service_name in self._cache:
            info = self._cache[service_name]
            if (time.time() - info.fetched_at) < self._cache_ttl:
                return info

        # Check aliases
        if service_name in self._aliases:
            canonical = self._aliases[service_name]
            if canonical in self._cache:
                return self._cache[canonical]

        # Fetch all and try again
        self.fetch_all_services()

        if service_name in self._cache:
            return self._cache[service_name]
        if service_name in self._aliases:
            return self._cache.get(self._aliases[service_name])

        return None

    def clear(self):
        """Clear the cache."""
        self._cache.clear()
        self._aliases.clear()
        self._last_full_fetch = 0.0

    def list_services(self) -> List[str]:
        """
        List all known service names.

        Returns:
            List of canonical service names
        """
        self.fetch_all_services()
        return list(self._cache.keys())

    def is_remote_configured(self) -> bool:
        """Check if remote server is configured."""
        return self._get_server_url() is not None
