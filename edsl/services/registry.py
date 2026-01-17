"""
ServiceRegistry: Central registry for external services.

Provides registration, discovery, and lookup of external services.
Services can be registered via decorator or explicit call.

Example:
    >>> from edsl.services import ServiceRegistry, ExternalService
    >>> 
    >>> # Register via decorator with metadata
    >>> @ServiceRegistry.register(
    ...     "firecrawl",
    ...     aliases=["fc"],
    ...     dependencies=["firecrawl-py>=1.0"],
    ...     extends=["ScenarioList"],
    ... )
    >>> class FirecrawlService(ExternalService):
    ...     pass
    >>> 
    >>> # Lookup
    >>> service = ServiceRegistry.get("firecrawl")
    >>> 
    >>> # List services that extend ScenarioList
    >>> for name in ServiceRegistry.list_for("ScenarioList"):
    ...     print(name)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .base import ExternalService


@dataclass
class OperationSchema:
    """Schema for a service operation."""

    input_param: Optional[str] = None  # Maps first positional arg to this param name
    defaults: Dict[str, Any] = field(default_factory=dict)  # Default values to merge
    # Per-operation result parsing (overrides service-level defaults)
    result_pattern: Optional[str] = None
    result_field: Optional[str] = None
    # If True, this operation modifies data and should use replace_with()
    # to create a new versioned instance instead of returning raw result
    modifying: bool = False


@dataclass
class ServiceMetadata:
    """Metadata about a registered service."""

    name: str
    service_class: Type["ExternalService"]
    aliases: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    extends: List[str] = field(default_factory=list)
    # Service-level default: if True, all operations use replace_with().
    # Operations can override this with their own `modifying` flag.
    versioned: bool = False
    operations: Dict[str, OperationSchema] = field(
        default_factory=dict
    )  # Operation schemas
    # Pattern for parsing results on client side without edsl-services
    result_pattern: str = "dict_passthrough"
    # Optional field to extract from result (e.g., "rows", "data")
    result_field: Optional[str] = None
    # Class docstring for self-documenting services
    docstring: Optional[str] = None


class ServiceRegistry:
    """
    Singleton registry for external services.

    All registered services are stored at the class level, making them
    available throughout the application.

    Services can declare:
    - aliases: Alternative names for lookup
    - dependencies: Pip packages required (registered with DependencyManager)
    - extends: Classes this service extends (for PluggableMixin discovery)
    """

    _services: Dict[str, Type["ExternalService"]] = {}
    _metadata: Dict[str, ServiceMetadata] = {}
    _aliases: Dict[str, str] = {}  # alias -> canonical name
    _extends_index: Dict[str, List[str]] = {}  # class_name -> [service_names]

    @classmethod
    def register(
        cls,
        name: str,
        service_class: Optional[Type["ExternalService"]] = None,
        *,
        aliases: Optional[List[str]] = None,
        dependencies: Optional[List[str]] = None,
        extends: Optional[List[str]] = None,
        versioned: bool = False,
        operations: Optional[Dict[str, Dict[str, Any]]] = None,
        result_pattern: str = "dict_passthrough",
        result_field: Optional[str] = None,
    ) -> Union[
        Type["ExternalService"],
        Callable[[Type["ExternalService"]], Type["ExternalService"]],
    ]:
        """
        Register an external service.

        Can be used as a decorator or called directly:

            # As decorator with full metadata
            @ServiceRegistry.register(
                "firecrawl",
                aliases=["fc"],
                dependencies=["firecrawl-py>=1.0"],
                extends=["ScenarioList"],
            )
            class FirecrawlService(ExternalService):
                pass

            # Versioned service (uses replace_with for results)
            @ServiceRegistry.register(
                "survey_vibes",
                extends=["Survey"],
                versioned=True,  # Results become new versions
            )
            class SurveyVibesService(ExternalService):
                pass

            # Direct call
            ServiceRegistry.register("myservice", MyService, dependencies=["pkg"])

        Args:
            name: Canonical service name (e.g., "exa", "firecrawl")
            service_class: Service class to register (optional if used as decorator)
            aliases: Optional list of alternative names for the service
            dependencies: Optional list of pip packages required by this service
            extends: Optional list of class names this service extends
                     (e.g., ["ScenarioList", "Results"])
            versioned: If True, results are applied via instance.replace_with()
                      creating a new version on the same branch. The instance
                      must have a replace_with() method.
            operations: Optional dict mapping operation names to schemas.
                       Each schema can have:
                       - input_param: str - maps first positional arg to this param
                       - defaults: dict - default values to merge into params
                       Example:
                           operations={
                               "search": {"input_param": "query", "defaults": {"mode": "search"}},
                               "tables": {"input_param": "url", "defaults": {"mode": "tables"}},
                           }
            result_pattern: Pattern for parsing results on client side without
                           edsl-services installed. Options: "scenario_list",
                           "filestore_base64", "dict_passthrough", "string_field",
                           "results_from_dict". Default: "dict_passthrough"
            result_field: Optional field to extract from result dict (e.g., "rows")

        Returns:
            The service class (for decorator chaining)

        Raises:
            ValueError: If name is already registered
        """

        def decorator(svc_cls: Type["ExternalService"]) -> Type["ExternalService"]:
            if name in cls._services:
                raise ValueError(f"Service '{name}' is already registered")

            # Set the service name on the class
            svc_cls.name = name

            # Parse operation schemas
            parsed_operations = {}
            if operations:
                for op_name, op_config in operations.items():
                    parsed_operations[op_name] = OperationSchema(
                        input_param=op_config.get("input_param"),
                        defaults=op_config.get("defaults", {}),
                        result_pattern=op_config.get("result_pattern"),
                        result_field=op_config.get("result_field"),
                        modifying=op_config.get("modifying", False),
                    )
            else:
                # Auto-extract operations from class attributes if not provided
                # First check OPERATION_SCHEMAS (preferred - has full metadata)
                if hasattr(svc_cls, "OPERATION_SCHEMAS"):
                    for op_name, op_config in svc_cls.OPERATION_SCHEMAS.items():
                        if isinstance(op_config, dict):
                            parsed_operations[op_name] = OperationSchema(
                                input_param=op_config.get("input_param"),
                                defaults=op_config.get("defaults", {}),
                                result_pattern=op_config.get("result_pattern"),
                                result_field=op_config.get("result_field"),
                                modifying=op_config.get("modifying", False),
                            )
                        else:
                            parsed_operations[op_name] = OperationSchema()
                # Fall back to OPERATIONS list (just operation names)
                elif hasattr(svc_cls, "OPERATIONS"):
                    for op_name in svc_cls.OPERATIONS:
                        parsed_operations[op_name] = OperationSchema()

            # Create metadata
            meta = ServiceMetadata(
                name=name,
                service_class=svc_cls,
                aliases=aliases or [],
                dependencies=dependencies or [],
                extends=extends or [],
                versioned=versioned,
                operations=parsed_operations,
                result_pattern=result_pattern,
                result_field=result_field,
                docstring=svc_cls.__doc__,
            )

            # Register the service and metadata
            cls._services[name] = svc_cls
            cls._metadata[name] = meta

            # Register aliases
            if aliases:
                for alias in aliases:
                    if alias in cls._aliases or alias in cls._services:
                        raise ValueError(
                            f"Alias '{alias}' conflicts with existing name"
                        )
                    cls._aliases[alias] = name

            # Update extends index for quick lookup
            for class_name in extends or []:
                if class_name not in cls._extends_index:
                    cls._extends_index[class_name] = []
                cls._extends_index[class_name].append(name)

            # Register dependencies with DependencyManager
            if dependencies:
                from .dependency_manager import DependencyManager

                DependencyManager.register_dependencies(name, dependencies)

            return svc_cls

        if service_class is not None:
            return decorator(service_class)
        return decorator

    @classmethod
    def get(cls, name: str) -> Optional[Type["ExternalService"]]:
        """
        Get a service by name or alias.

        Args:
            name: Service name or alias

        Returns:
            Service class, or None if not found
        """
        # Ensure builtin services are loaded
        from . import _ensure_builtin_services

        _ensure_builtin_services()

        # Check canonical name first
        if name in cls._services:
            return cls._services[name]

        # Check aliases
        if name in cls._aliases:
            return cls._services[cls._aliases[name]]

        return None

    @classmethod
    def get_or_raise(cls, name: str) -> Type["ExternalService"]:
        """
        Get a service by name, raising if not found.

        Args:
            name: Service name or alias

        Returns:
            Service class

        Raises:
            ValueError: If service not found
        """
        service = cls.get(name)
        if service is None:
            available = ", ".join(cls.list())
            raise ValueError(
                f"Service '{name}' not found. Available services: {available}"
            )
        return service

    @classmethod
    def list(cls) -> List[str]:
        """
        List all registered service names (canonical names only).

        Returns:
            List of service names
        """
        return list(cls._services.keys())

    @classmethod
    def list_with_aliases(cls) -> Dict[str, List[str]]:
        """
        List all services with their aliases.

        Returns:
            Dict mapping canonical name to list of aliases
        """
        result = {name: [] for name in cls._services}
        for alias, canonical in cls._aliases.items():
            result[canonical].append(alias)
        return result

    @classmethod
    def exists(cls, name: str) -> bool:
        """
        Check if a service exists.

        Args:
            name: Service name or alias

        Returns:
            True if service exists
        """
        return cls.get(name) is not None

    @classmethod
    def unregister(cls, name: str) -> bool:
        """
        Unregister a service.

        Args:
            name: Service name (not alias)

        Returns:
            True if unregistered, False if not found
        """
        if name not in cls._services:
            return False

        # Get metadata before removing
        meta = cls._metadata.get(name)

        # Remove from extends index
        if meta:
            for class_name in meta.extends:
                if class_name in cls._extends_index:
                    cls._extends_index[class_name] = [
                        n for n in cls._extends_index[class_name] if n != name
                    ]

        # Remove aliases pointing to this service
        cls._aliases = {
            alias: canonical
            for alias, canonical in cls._aliases.items()
            if canonical != name
        }

        # Remove service and metadata
        del cls._services[name]
        cls._metadata.pop(name, None)
        return True

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered services.

        Primarily for testing.
        """
        cls._services.clear()
        cls._metadata.clear()
        cls._aliases.clear()
        cls._extends_index.clear()

    @classmethod
    def list_for(cls, class_name: str) -> List[str]:
        """
        List services that extend a specific class.

        Args:
            class_name: Name of the class (e.g., "ScenarioList", "Results")

        Returns:
            List of service names that extend the given class

        Example:
            >>> ServiceRegistry.list_for("ScenarioList")
            ['firecrawl', 'exa', 'huggingface', ...]
        """
        return cls._extends_index.get(class_name, [])

    @classmethod
    def get_metadata(cls, name: str) -> Optional[ServiceMetadata]:
        """
        Get full metadata for a service.

        Args:
            name: Service name or alias

        Returns:
            ServiceMetadata object, or None if not found
        """
        # Resolve alias to canonical name
        if name in cls._aliases:
            name = cls._aliases[name]

        return cls._metadata.get(name)

    @classmethod
    def get_dependencies(cls, name: str) -> List[str]:
        """
        Get dependencies for a service.

        Args:
            name: Service name or alias

        Returns:
            List of pip package requirements
        """
        meta = cls.get_metadata(name)
        return meta.dependencies if meta else []

    @classmethod
    def get_operation_schema(
        cls, name: str, operation: str
    ) -> Optional[OperationSchema]:
        """
        Get the schema for a specific operation on a service.

        Args:
            name: Service name or alias
            operation: Operation/method name (e.g., "search", "scrape")

        Returns:
            OperationSchema if defined, None otherwise
        """
        meta = cls.get_metadata(name)
        if meta and meta.operations:
            return meta.operations.get(operation)
        return None

    @classmethod
    def get_operations(cls, name: str) -> Dict[str, OperationSchema]:
        """
        Get all operation schemas for a service.

        Args:
            name: Service name or alias

        Returns:
            Dict mapping operation names to their schemas
        """
        meta = cls.get_metadata(name)
        if meta:
            return meta.operations
        return {}

    @classmethod
    def info(cls, name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a service.

        Args:
            name: Service name or alias

        Returns:
            Dict with name, description, version, required_keys, dependencies, extends
        """
        service = cls.get(name)
        if service is None:
            return None

        meta = cls.get_metadata(name)

        return {
            "name": service.name,
            "description": service.description,
            "docstring": meta.docstring if meta else None,
            "version": service.version,
            "required_keys": service.get_required_keys(),
            "dependencies": meta.dependencies if meta else [],
            "extends": meta.extends if meta else [],
            "aliases": meta.aliases if meta else [],
            "operations": (
                list(meta.operations.keys()) if meta and meta.operations else []
            ),
        }

    # Track whether entry points have been discovered
    _entry_points_discovered: bool = False

    @classmethod
    def _discover_entry_points(cls) -> None:
        """
        Discover services registered via Python entry points.

        This enables a plugin architecture where external packages can register
        services by declaring entry points in their pyproject.toml:

            [project.entry-points."edsl.services"]
            myservice = "mypackage.services:MyService"

        Services discovered via entry points are registered with the same
        mechanisms as builtin services, making them available through
        ServiceRegistry.get() and the accessor pattern.

        This method is idempotent - it only discovers entry points once.
        """
        if cls._entry_points_discovered:
            return

        cls._entry_points_discovered = True

        try:
            from importlib.metadata import entry_points
        except ImportError:
            # Python < 3.10 fallback
            try:
                from importlib_metadata import entry_points
            except ImportError:
                return  # No entry points support available

        try:
            # Get entry points for the edsl.services group
            # Python 3.10+ returns a SelectableGroups, earlier versions return dict
            eps = entry_points(group="edsl.services")

            # Handle both dict-style (Python < 3.10) and SelectableGroups (Python 3.10+)
            if isinstance(eps, dict):
                eps = eps.get("edsl.services", [])

            for ep in eps:
                try:
                    # Load the service class
                    service_class = ep.load()

                    # Only register if not already registered
                    # (builtin services take precedence)
                    if ep.name not in cls._services:
                        # Check if it's a valid service class
                        from .base import ExternalService

                        if isinstance(service_class, type) and issubclass(
                            service_class, ExternalService
                        ):
                            cls.register(ep.name, service_class)

                except Exception as e:
                    # Log but don't fail - service may have missing dependencies
                    # This allows partial installation of service packages
                    import sys

                    print(
                        f"[edsl.services] Warning: Could not load entry point '{ep.name}': {e}",
                        file=sys.stderr,
                    )

        except Exception as e:
            # Entry points discovery failed entirely - not fatal
            import sys

            print(
                f"[edsl.services] Warning: Entry point discovery failed: {e}",
                file=sys.stderr,
            )

    @classmethod
    def reset_entry_points(cls) -> None:
        """
        Reset entry point discovery state.

        Primarily for testing - allows re-discovery of entry points.
        """
        cls._entry_points_discovered = False
