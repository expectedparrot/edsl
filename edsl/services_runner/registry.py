"""
Service Registry - Discovers and manages installed EDSL services.

This module provides a registry for ExternalService classes that can be
discovered via Python entry points or registered manually.

Entry Point Discovery:
    Extensions can register services by adding an entry point in their
    pyproject.toml or setup.py:

    # pyproject.toml
    [project.entry-points."edsl.services"]
    firecrawl = "my_extension.service:FirecrawlService"
    another = "my_extension.service:AnotherService"

    # setup.py (legacy)
    entry_points={
        'edsl.services': [
            'firecrawl = my_extension.service:FirecrawlService',
        ],
    }

Manual Registration:
    from edsl.services_runner import register_service
    from my_extension.service import MyService

    register_service(MyService)
"""

from typing import Dict, List, Type, Optional
import sys

# Entry point group name for EDSL services
ENTRY_POINT_GROUP = "edsl.services"


class ServiceRegistry:
    """
    Registry for ExternalService classes.

    Maintains a mapping of service names to service classes, with support
    for automatic discovery via entry points.
    """

    def __init__(self):
        self._services: Dict[str, Type] = {}
        self._discovered: bool = False

    def register(self, service_cls: Type) -> None:
        """
        Register a service class.

        Args:
            service_cls: An ExternalService subclass to register

        Raises:
            ValueError: If service_cls doesn't have a service_name attribute
            ValueError: If a service with the same name is already registered
        """
        if not hasattr(service_cls, 'service_name'):
            raise ValueError(
                f"Service class {service_cls.__name__} must have a 'service_name' attribute"
            )

        name = service_cls.service_name

        if name in self._services:
            existing = self._services[name]
            if existing is not service_cls:
                raise ValueError(
                    f"Service '{name}' is already registered by {existing.__name__}. "
                    f"Cannot register {service_cls.__name__} with the same name."
                )
            # Already registered with same class, no-op
            return

        self._services[name] = service_cls

    def unregister(self, service_name: str) -> bool:
        """
        Unregister a service by name.

        Args:
            service_name: The name of the service to unregister

        Returns:
            True if the service was unregistered, False if it wasn't registered
        """
        if service_name in self._services:
            del self._services[service_name]
            return True
        return False

    def get(self, service_name: str) -> Optional[Type]:
        """
        Get a service class by name.

        Args:
            service_name: The name of the service to retrieve

        Returns:
            The service class, or None if not found
        """
        self._ensure_discovered()
        return self._services.get(service_name)

    def get_all(self) -> Dict[str, Type]:
        """
        Get all registered services.

        Returns:
            Dict mapping service names to service classes
        """
        self._ensure_discovered()
        return dict(self._services)

    def list_names(self) -> List[str]:
        """
        List all registered service names.

        Returns:
            List of service names
        """
        self._ensure_discovered()
        return list(self._services.keys())

    def _ensure_discovered(self) -> None:
        """Ensure entry points have been discovered."""
        if not self._discovered:
            self.discover_entry_points()

    def discover_entry_points(self) -> List[str]:
        """
        Discover and register services from entry points.

        Scans for entry points in the 'edsl.services' group and registers
        any ExternalService subclasses found.

        Returns:
            List of newly discovered service names
        """
        discovered = []

        # Use importlib.metadata for entry point discovery (Python 3.9+)
        if sys.version_info >= (3, 10):
            from importlib.metadata import entry_points
            eps = entry_points(group=ENTRY_POINT_GROUP)
        else:
            # Python 3.9 compatibility
            from importlib.metadata import entry_points as get_entry_points
            all_eps = get_entry_points()
            eps = all_eps.get(ENTRY_POINT_GROUP, [])

        for ep in eps:
            try:
                service_cls = ep.load()

                # Validate it's a proper service
                if not hasattr(service_cls, 'service_name'):
                    print(f"Warning: Entry point '{ep.name}' does not have service_name, skipping")
                    continue

                if not hasattr(service_cls, 'extends'):
                    print(f"Warning: Entry point '{ep.name}' does not have extends, skipping")
                    continue

                # Register if not already registered
                if service_cls.service_name not in self._services:
                    self.register(service_cls)
                    discovered.append(service_cls.service_name)

            except Exception as e:
                print(f"Warning: Failed to load service entry point '{ep.name}': {e}")

        self._discovered = True
        return discovered

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._discovered = False


# Global registry instance
_registry = ServiceRegistry()


def register_service(service_cls: Type) -> None:
    """
    Register a service class with the global registry.

    Args:
        service_cls: An ExternalService subclass to register

    Example:
        from edsl.services_runner import register_service
        from my_extension import MyService

        register_service(MyService)
    """
    _registry.register(service_cls)


def unregister_service(service_name: str) -> bool:
    """
    Unregister a service from the global registry.

    Args:
        service_name: The name of the service to unregister

    Returns:
        True if unregistered, False if not found
    """
    return _registry.unregister(service_name)


def get_service(service_name: str) -> Optional[Type]:
    """
    Get a service class from the global registry.

    Args:
        service_name: The name of the service

    Returns:
        The service class, or None if not found
    """
    return _registry.get(service_name)


def get_all_services() -> Dict[str, Type]:
    """
    Get all registered services from the global registry.

    Returns:
        Dict mapping service names to service classes
    """
    return _registry.get_all()


def list_service_names() -> List[str]:
    """
    List all registered service names.

    Returns:
        List of service names
    """
    return _registry.list_names()


def discover_services() -> List[str]:
    """
    Discover services from entry points.

    Returns:
        List of newly discovered service names
    """
    return _registry.discover_entry_points()


def get_registry() -> ServiceRegistry:
    """
    Get the global service registry instance.

    Returns:
        The global ServiceRegistry
    """
    return _registry
