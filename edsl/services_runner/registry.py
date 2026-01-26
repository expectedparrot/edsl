"""
Service Registry - Discovers and manages installed EDSL services.

This module provides a registry for ExternalService classes that can be
discovered via Python entry points or registered manually.

Services are keyed by (service_name, extends_type) allowing multiple services
with the same name as long as they extend different EDSL types. For example,
both ScenarioList and Results can have a "vibes" service.

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

from typing import Dict, List, Type, Optional, Tuple
import sys
import logging

logger = logging.getLogger("edsl.services")

# Entry point group name for EDSL services
ENTRY_POINT_GROUP = "edsl.services"


def _get_type_name(t) -> str:
    """Get the string name of a type."""
    if hasattr(t, "__name__"):
        return t.__name__
    return str(t)


class ServiceRegistry:
    """
    Registry for ExternalService classes.

    Maintains a mapping of (service_name, extends_type) to service classes,
    allowing multiple services with the same name as long as they extend
    different types.
    """

    def __init__(self):
        # Nested dict: service_name -> {extends_type -> service_class}
        self._services: Dict[str, Dict[str, Type]] = {}
        self._discovered: bool = False

    def register(self, service_cls: Type) -> None:
        """
        Register a service class.

        A service is registered for each type it extends. Multiple services
        can share the same name if they extend different types.

        Args:
            service_cls: An ExternalService subclass to register

        Raises:
            ValueError: If service_cls doesn't have service_name or extends
            ValueError: If a service with the same (name, extends) is already registered
        """
        if not hasattr(service_cls, "service_name"):
            raise ValueError(
                f"Service class {service_cls.__name__} must have a 'service_name' attribute"
            )

        if not hasattr(service_cls, "extends"):
            raise ValueError(
                f"Service class {service_cls.__name__} must have an 'extends' attribute"
            )

        name = service_cls.service_name
        extends_types = service_cls.extends

        if not extends_types:
            raise ValueError(
                f"Service class {service_cls.__name__} must extend at least one type"
            )

        # Initialize nested dict for this service name if needed
        if name not in self._services:
            self._services[name] = {}

        # Register for each type it extends
        for extends_type in extends_types:
            type_name = _get_type_name(extends_type)

            if type_name in self._services[name]:
                existing = self._services[name][type_name]
                if existing is not service_cls:
                    raise ValueError(
                        f"Service '{name}' for type '{type_name}' is already registered "
                        f"by {existing.__name__}. Cannot register {service_cls.__name__}."
                    )
                # Already registered with same class, no-op
                continue

            self._services[name][type_name] = service_cls

    def unregister(self, service_name: str, extends_type: Optional[str] = None) -> bool:
        """
        Unregister a service.

        Args:
            service_name: The name of the service to unregister
            extends_type: If specified, only unregister for this type.
                         If None, unregister all services with this name.

        Returns:
            True if any service was unregistered, False otherwise
        """
        if service_name not in self._services:
            return False

        if extends_type is not None:
            if extends_type in self._services[service_name]:
                del self._services[service_name][extends_type]
                # Clean up empty service name entry
                if not self._services[service_name]:
                    del self._services[service_name]
                return True
            return False

        # Unregister all services with this name
        del self._services[service_name]
        return True

    def get(self, service_name: str, extends_type: Optional[str] = None) -> Optional[Type]:
        """
        Get a service class by name and optionally by extends type.

        Args:
            service_name: The name of the service to retrieve
            extends_type: If specified, get service for this specific type.
                         If None, returns the first registered service with this name.

        Returns:
            The service class, or None if not found

        Raises:
            ValueError: If extends_type is provided but not found in registered services
        """
        self._ensure_discovered()

        if service_name not in self._services:
            logger.debug(f"REGISTRY GET: Service '{service_name}' not found in registry")
            return None

        type_map = self._services[service_name]
        available_types = list(type_map.keys())

        logger.info(
            f"REGISTRY GET: service='{service_name}', extends_type={extends_type!r}, "
            f"available_types={available_types}"
        )

        if extends_type is not None:
            service_cls = type_map.get(extends_type)
            if service_cls is not None:
                logger.info(
                    f"REGISTRY GET: Found exact match {service_cls.__name__} "
                    f"for type '{extends_type}'"
                )
                return service_cls
            else:
                # extends_type was explicitly provided but not found - this is an error
                # Don't silently fall back to first available as this leads to
                # hard-to-debug bugs when multiple services share the same name
                error_msg = (
                    f"Service '{service_name}' does not extend type '{extends_type}'. "
                    f"Available types: {available_types}"
                )
                logger.error(f"REGISTRY GET: {error_msg}")
                raise ValueError(error_msg)

        # No extends_type specified - return first available (for backwards compatibility)
        if type_map:
            if len(type_map) > 1:
                logger.warning(
                    f"REGISTRY GET: Service '{service_name}' has multiple type variants "
                    f"{available_types} but no extends_type specified - using first available. "
                    f"This may cause incorrect behavior."
                )
            first_cls = next(iter(type_map.values()))
            logger.info(f"REGISTRY GET: Returning first available: {first_cls.__name__}")
            return first_cls
        return None

    def get_for_type(self, service_name: str, extends_type: str) -> Optional[Type]:
        """
        Get a service class that extends a specific type.

        Args:
            service_name: The name of the service
            extends_type: The type name the service should extend

        Returns:
            The service class, or None if not found
        """
        return self.get(service_name, extends_type)

    def get_all(self) -> Dict[str, Type]:
        """
        Get all registered services.

        For services with the same name extending multiple types, returns
        one entry per service class (deduplicated).

        Returns:
            Dict mapping service names to service classes
        """
        self._ensure_discovered()
        result = {}
        seen_classes = set()

        for name, type_map in self._services.items():
            for service_cls in type_map.values():
                if service_cls not in seen_classes:
                    result[name] = service_cls
                    seen_classes.add(service_cls)

        return result

    def get_all_with_types(self) -> List[Tuple[str, str, Type]]:
        """
        Get all registered services with their type information.

        Returns:
            List of (service_name, extends_type, service_class) tuples
        """
        self._ensure_discovered()
        result = []

        for name, type_map in self._services.items():
            for type_name, service_cls in type_map.items():
                result.append((name, type_name, service_cls))

        return result

    def list_names(self) -> List[str]:
        """
        List all registered service names (unique).

        Returns:
            List of service names
        """
        self._ensure_discovered()
        return list(self._services.keys())

    def list_for_type(self, extends_type: str) -> List[str]:
        """
        List service names that extend a specific type.

        Args:
            extends_type: The type name to filter by

        Returns:
            List of service names that extend the given type
        """
        self._ensure_discovered()
        return [
            name
            for name, type_map in self._services.items()
            if extends_type in type_map
        ]

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
                if not hasattr(service_cls, "service_name"):
                    print(
                        f"Warning: Entry point '{ep.name}' does not have service_name, skipping"
                    )
                    continue

                if not hasattr(service_cls, "extends"):
                    print(
                        f"Warning: Entry point '{ep.name}' does not have extends, skipping"
                    )
                    continue

                service_name = service_cls.service_name
                was_new = service_name not in self._services

                try:
                    self.register(service_cls)
                    if was_new:
                        discovered.append(service_name)
                except ValueError as e:
                    print(f"Warning: Could not register '{ep.name}': {e}")

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


def unregister_service(service_name: str, extends_type: Optional[str] = None) -> bool:
    """
    Unregister a service from the global registry.

    Args:
        service_name: The name of the service to unregister
        extends_type: If specified, only unregister for this type

    Returns:
        True if unregistered, False if not found
    """
    return _registry.unregister(service_name, extends_type)


def get_service(service_name: str, extends_type: Optional[str] = None) -> Optional[Type]:
    """
    Get a service class from the global registry.

    Args:
        service_name: The name of the service
        extends_type: If specified, get service for this specific type

    Returns:
        The service class, or None if not found
    """
    return _registry.get(service_name, extends_type)


def get_service_for_type(service_name: str, extends_type: str) -> Optional[Type]:
    """
    Get a service class that extends a specific type.

    Args:
        service_name: The name of the service
        extends_type: The type name the service should extend

    Returns:
        The service class, or None if not found
    """
    return _registry.get_for_type(service_name, extends_type)


def get_all_services() -> Dict[str, Type]:
    """
    Get all registered services from the global registry.

    Returns:
        Dict mapping service names to service classes
    """
    return _registry.get_all()


def get_all_services_with_types() -> List[Tuple[str, str, Type]]:
    """
    Get all registered services with their type information.

    Returns:
        List of (service_name, extends_type, service_class) tuples
    """
    return _registry.get_all_with_types()


def list_service_names() -> List[str]:
    """
    List all registered service names.

    Returns:
        List of service names
    """
    return _registry.list_names()


def list_services_for_type(extends_type: str) -> List[str]:
    """
    List service names that extend a specific type.

    Args:
        extends_type: The type name to filter by

    Returns:
        List of service names that extend the given type
    """
    return _registry.list_for_type(extends_type)


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
