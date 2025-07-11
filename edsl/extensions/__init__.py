# from .external_services import extensions as _extensions
# from .authoring import register_service
# from .services_model import ServicesRegistry

# services_registry = ServicesRegistry.from_config()
# _extensions = services_registry.services

# # edsl/extensions/__init__.py
# # Public handle to the loaded service registry
# # Expose the *ExternalServices* singleton directly so callers can use
# # its helper methods such as ``list()``.
# extensions = _extensions  # type: ignore[assignment]

# class _ExtensionsProxy:
#     """Attribute-access proxy exposing all registered extension helpers.

#     Examples
#     --------
#     >>> from edsl.extensions import ext
#     >>> ext.create_survey(...)
#     """

#     def __getattr__(self, name: str):
#         try:
#             return _extensions[name]
#         except KeyError as exc:
#             raise AttributeError(
#                 f"Extension '{name}' is not registered. "
#                 f"Known extensions: {list(_extensions)}"
#             ) from exc

#     def __dir__(self):
#         # Include built-in helper names in dir() output
#         return list(_extensions) + ["list"]

#     # Convenient helper to show available services
#     def list(self):  # noqa: D401 – simple method
#         """Return a list of available service names."""
#         return list(_extensions)

# # Export a singleton proxy instance so users can do `from edsl.extensions import ext`
# ext = _ExtensionsProxy()

# def __getattr__(name: str):
#     """Allow `edsl.extensions.create_survey(...)`."""
#     try:
#         return _extensions[name]
#     except KeyError as exc:
#         raise AttributeError(
#             f"Extension '{name}' is not registered. "
#             f"Known extensions: {list(_extensions)}"
#         ) from exc

# # Convenience re-export so users can do `from edsl.extensions import compute_price`.
# from .price_calculation import compute_price  # noqa: F401

# Extension discovery and interaction tools
from .available_extensions import ServiceFetcher, get_service_definition_by_name


class Extensions:
    """Main interface for discovering and using extensions."""

    def __init__(self):
        self._fetcher = ServiceFetcher()

    def list(self):
        """List all available extensions."""
        return self._fetcher.list_service_definitions()

    def get(self, service_name):
        """
        Get a callable service by name.

        Args:
            service_name: Name of the service to retrieve

        Returns:
            ServiceDefinition: A callable service definition

        Raises:
            ValueError: If the service is not found

        Examples:
            >>> service = extensions.get('create_automated_survey')
            >>> result = service(question="...", population="...")
        """
        service_def = get_service_definition_by_name(service_name)
        if service_def is None:
            raise ValueError(f"Extension '{service_name}' not found")
        return service_def

    def __repr__(self):
        return "Extensions(use .list() to see available services)"


# Main interface - users import this
extensions = Extensions()
