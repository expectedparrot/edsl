# Import only the exceptions first to avoid circular imports
from .exceptions import InferenceServiceError

# Import the classes directly here for external use
# While avoiding circular imports with other modules
from .inference_service_abc import InferenceServiceABC
from .data_structures import AvailableModels
from .inference_services_collection import InferenceServicesCollection

# Define __all__ without default - we'll add it later
__all__ = [
    "InferenceServicesCollection",
    "InferenceServiceABC",
    "AvailableModels",
    "InferenceServiceError",
]

# Better approach: import the default instance immediately in a try/except
# If it fails, we'll define the default variable later to make imports work
try:
    from .registry import default
except ImportError:
    # This allows all imports to still work, while deferring the actual
    # import of registry.default to when it's accessed
    from types import SimpleNamespace

    # Global placeholder for default registry instance
    _default_instance = None

    def _get_default():
        """Load the default registry instance the first time it's needed"""
        global _default_instance
        if _default_instance is None:
            from .registry import default as registry_default

            _default_instance = registry_default
        return _default_instance

    # Define a simple proxy class for default
    class DefaultProxy(SimpleNamespace):
        def __getattr__(self, name):
            # Forward all attribute access to the real default instance
            return getattr(_get_default(), name)

    # Create the proxy instance that stands in for default
    default = DefaultProxy()

# Add default to __all__ now that we've defined it
__all__.append("default")
