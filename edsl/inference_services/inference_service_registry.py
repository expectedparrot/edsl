from typing import Dict, List, Optional, TYPE_CHECKING, Tuple
from datetime import datetime
from collections import defaultdict
import fnmatch

from .source_preference_handler import SourcePreferenceHandler

if TYPE_CHECKING:
    from .inference_service_abc import InferenceServiceABC
    from .model_info import ModelInfo

import importlib
import pkgutil
from . import services


def discover_service_modules():
    """Discover service modules without importing them (fast)."""
    service_module_map = {}

    # Iterate through all modules in the services package
    for importer, modname, ispkg in pkgutil.iter_modules(
        services.__path__, services.__name__ + "."
    ):
        # Skip __init__ and message_builder modules
        if modname.endswith(".__init__") or modname.endswith(".message_builder"):
            continue

        # Extract service name from module name
        # e.g., "edsl.inference_services.services.open_ai_service" -> "openai"
        module_basename = modname.split(".")[-1]

        # Handle special case for open_ai_service_v2 first (doesn't end with _service)
        if module_basename == "open_ai_service_v2":
            service_name = "openai_v2"
        elif module_basename.endswith("_service"):
            service_name = module_basename[:-8]  # Remove "_service" suffix
            # Handle special naming cases for modules ending with _service
            if service_name == "open_ai":
                service_name = "openai"
            elif service_name == "open_ai_v2":
                service_name = "openai_v2"
            elif service_name == "deep_infra":
                service_name = "deep_infra"
            elif service_name == "mistral_ai":
                service_name = "mistral"
            elif service_name == "together_ai":
                service_name = "together"
            elif service_name == "open_router":
                service_name = "open_router"
            elif service_name == "deep_seek":
                service_name = "deepseek"
        else:
            # Handle modules that don't end with _service
            if module_basename == "aws_bedrock":
                service_name = "bedrock"
            elif module_basename == "azure_ai":
                service_name = "azure"
            else:
                service_name = module_basename

        service_module_map[service_name] = modname

    return service_module_map


def load_all_service_classes():
    """Dynamically load all service classes from the services module (for backward compatibility)."""
    from .inference_service_abc import InferenceServiceABC

    service_classes = []
    service_module_map = discover_service_modules()

    for service_name, modname in service_module_map.items():
        try:
            # Import the module
            module = importlib.import_module(modname)

            # Look for classes that are subclasses of InferenceServiceABC
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                # Check if it's a class, is a subclass of InferenceServiceABC, and is defined in this module
                if (
                    isinstance(attr, type)
                    and issubclass(attr, InferenceServiceABC)
                    and attr is not InferenceServiceABC  # Exclude the base class itself
                    and attr.__module__ == modname
                ):
                    service_classes.append(attr)

        except ImportError:
            # Skip modules that can't be imported (might have missing dependencies)
            continue

    return service_classes


class InferenceServiceRegistry:
    """
    Registry for managing inference service classes with serialization support.

    Args:
        verbose: Enable verbose logging output
        model_source: Source for model discovery ("services" or "coop")
        service_preferences: Optional ordered tuple of preferred service names
    """

    _default_service_preferences = (
        "anthropic",
        "openai",
        "deep_infra",
        "deepseek",
        "google",
        "groq",
        "mistral",
        "openai_v2",
        "perplexity",
        "together",
        "xai",
        "open_router",
        "bedrock",
        "azure",
        "ollama",
    )
    # Use lazy loading - discover service modules without importing them
    _default_service_module_map = discover_service_modules()
    _default_source_preferences = (
        "coop_working",
        "coop",
        "archive",
        "local",
        "default_models",
    )

    def __init__(
        self,
        verbose: bool = False,
        service_preferences: Optional[Tuple[str, ...]] = None,
        source_preferences: Optional[Tuple[str, ...]] = None,
        service_module_map: Optional[Dict[str, str]] = None,
        classes_to_register: Optional[List[type["InferenceServiceABC"]]] = None,
    ):
        # Lazy loading: store service modules without importing them
        # If classes_to_register=[] is explicitly passed, don't use discovery
        if classes_to_register is not None and len(classes_to_register) == 0:
            self._service_module_map = (
                service_module_map if service_module_map is not None else {}
            )
        else:
            self._service_module_map = (
                service_module_map
                if service_module_map is not None
                else self._default_service_module_map.copy()
            )
        self._loaded_service_classes = {}  # Cache for imported service classes
        self._services = {}  # For backward compatibility
        self._registration_times = {}  # Track when services were registered

        self._model_info_data: Optional[Dict[str, List["ModelInfo"]]] = None
        self._model_to_services: Optional[Dict[str, List[str]]] = None
        self._service_to_models: Optional[Dict[str, List["ModelInfo"]]] = None

        self.verbose = verbose  # Enable verbose logging
        self._service_preferences = (
            service_preferences
            if service_preferences
            else self._default_service_preferences
        )  # Ordered tuple of preferred services

        # Initialize source preference handler
        if source_preferences is None:
            source_preferences = self._default_source_preferences

        self._source_handler = SourcePreferenceHandler(
            registry=self, source_preferences=source_preferences, verbose=verbose
        )

        # Support backward compatibility: if classes_to_register is provided, register them immediately
        if classes_to_register is not None:
            for cls in classes_to_register:
                self.register(cls._inference_service_, cls)

    def _find_service_class_in_module(self, module) -> type["InferenceServiceABC"]:
        """Find the service class in a module."""
        from .inference_service_abc import InferenceServiceABC

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, InferenceServiceABC)
                and attr is not InferenceServiceABC
                and attr.__module__ == module.__name__
            ):
                return attr
        raise ValueError(f"No service class found in module {module.__name__}")

    def get_service_class(self, service_name: str) -> type["InferenceServiceABC"]:
        """Get service class (supports both lazy loading and manual registration)."""
        # First check if service was manually registered
        if service_name in self._services:
            return self._services[service_name]

        # Then check if service can be lazy-loaded
        if service_name in self._loaded_service_classes:
            return self._loaded_service_classes[service_name]

        # Try to lazy-load the service
        if service_name in self._service_module_map:
            # Import module only when needed
            module_name = self._service_module_map[service_name]
            if self.verbose:
                print(
                    f"[LAZY_LOADING] Loading service '{service_name}' from {module_name}"
                )

            try:
                module = importlib.import_module(module_name)
                service_class = self._find_service_class_in_module(module)
                self._loaded_service_classes[service_name] = service_class

                # Also register in the services dict for backward compatibility
                self._services[service_name] = service_class
                self._registration_times[service_name] = datetime.now()

                return service_class
            except ImportError as e:
                raise ImportError(
                    f"Failed to import service '{service_name}' from {module_name}: {e}"
                )

        # Service not found anywhere
        available_services = list(
            set(self._service_module_map.keys()) | set(self._services.keys())
        )
        raise KeyError(
            f"Service '{service_name}' not found in registry. Available services: {available_services}"
        )

    @property
    def model_to_services(self) -> Dict[str, List[str]]:
        if self._model_to_services is None:
            self._build_model_mappings()
        return self._model_to_services

    @property
    def services(self) -> Dict[str, type["InferenceServiceABC"]]:
        return self._services

    @property
    def service_to_models(self) -> Dict[str, List["ModelInfo"]]:
        if self._service_to_models is None:
            self._build_model_mappings()
        return self._service_to_models

    def get_service_to_class(self) -> Dict[str, type["InferenceServiceABC"]]:
        return self._services

    def register(self, service_name: str, service_class: type["InferenceServiceABC"]):
        """Register a service class with the given name."""
        if service_name == "test":
            return
        self._services[service_name] = service_class
        self._registration_times[service_name] = datetime.now()

    def list_registered_services(self) -> list[str]:
        """Returns a list of all discoverable service names."""
        # Return all discoverable services (both loaded and not-yet-loaded)
        all_services = set(self._service_module_map.keys())
        all_services.update(
            self._services.keys()
        )  # Include explicitly registered services
        return list(all_services)

    def fetch_model_info_data(
        self, source_preferences: Optional[List[str]] = None
    ) -> Dict[str, List["ModelInfo"]]:
        """
        Refreshes the model info data and rebuilds the model-to-service and service-to-model mappings, taking source preferences into account.

        Args:
            source_preferences: Optional list of source preferences to override the default

        Returns:
            Dictionary mapping service names to lists of ModelInfo objects
        """
        if self._model_info_data is None:
            self._model_info_data = self._source_handler.fetch_model_info_data(
                source_preferences
            )

        return self._model_info_data

    @property
    def model_info_data(self) -> Dict[str, List["ModelInfo"]]:
        """Get the model data from the model info fetcher."""
        if self._model_info_data is None:
            self._model_info_data = self._source_handler.fetch_model_info_data()

        return self._model_info_data

    def get_all_model_names(self):
        "Gets all known models"
        return list(self.model_to_services.keys())

    def _build_model_mappings(self, force_refresh: bool = False):
        """Build the model-to-service and service-to-model mappings."""

        self._model_to_services = defaultdict(list)
        self._service_to_models = dict()

        total_models = 0
        for service_name, models in self.model_info_data.items():
            self._service_to_models[service_name] = models
            total_models += len(models)

            # Build reverse mapping - all fetchers now return ModelInfo objects
            for model_info in models:
                self._model_to_services[model_info.id].append(service_name)

    def get_service_for_model(self, model_name: str) -> Optional[str]:
        """Get the preferred service for a given model name based on user preferences."""
        # Early check for test models to avoid API calls
        if model_name == "test":
            return "test"

        services = self.model_to_services.get(model_name, [])
        if not services:
            raise ValueError(
                f"""Model '{model_name}' not found in any service. 
                             Available models: {list(self.model_to_services.keys())}. 
                             Available services: {list(self.service_to_models.keys())}
                            Used source: {self._source_handler.used_source}"""
            )

        # Find the first preferred service that provides this model
        for preferred_service in self._service_preferences:
            if preferred_service in services:
                return preferred_service

        # Fall back to first available service if no preferences match
        return services[0]

    def get_services_for_model(self, model_name: str) -> List[str]:
        """Get all services that provide a given model name."""
        return list(self.model_to_services.get(model_name, []))

    def get_models_for_service(self, service_name: str) -> List[str]:
        """Get all model names for a given service."""
        model_infos = self.service_to_models.get(service_name, [])
        return [model_info.id for model_info in model_infos]

    def find_services(self, pattern: str) -> List[str]:
        """Find services matching a wildcard pattern."""
        return [
            service_name
            for service_name in self.list_registered_services()
            if fnmatch.fnmatch(service_name, pattern)
        ]

    def find_models(
        self, pattern: str, service_name: Optional[str] = None
    ) -> List[str]:
        """Find models matching a wildcard pattern, optionally within a specific service."""

        if service_name:
            # Search within a specific service
            service_models = self.service_to_models.get(service_name, [])
            return [
                model_info.id
                for model_info in service_models
                if fnmatch.fnmatch(model_info.id, pattern)
            ]
        else:
            return [
                model
                for model in self.model_to_services.keys()
                if fnmatch.fnmatch(model, pattern)
            ]

    def create_language_model(
        self, model_name: str, service_name: Optional[str] = None, *args, **kwargs
    ):
        """Create a language model instance for the given model name.

        Args:
            model_name: The name of the model to create
            service_name: Optional service name to use. If None, will lookup the preferred service for the model.
            *args: Additional positional arguments to pass to the model constructor
            **kwargs: Additional keyword arguments to pass to the model constructor

        Returns:
            A language model class that can be instantiated

        Raises:
            ValueError: If no service is found for the model (when service_name is None)
            KeyError: If the specified service_name is not registered
        """
        if service_name is None:
            # Use automatic lookup as before
            service_name = self.get_service_for_model(model_name)
            if not service_name:
                raise ValueError(
                    f"No service found for model '{model_name}'",
                    f"Available services: {self.list_registered_services()}",
                )

        if model_name == "test":
            from .services.test_service import TestService

            service_class = TestService
        else:
            service_class = self.get_service_class(service_name)

        service_instance = service_class()
        return service_instance.create_model(model_name, *args, **kwargs)

    def get_used_source(self) -> Optional[str]:
        """Get the source that was used to fetch model information."""
        return self._source_handler.used_source

    def get_source_preferences(self) -> List[str]:
        """Get the current source preferences."""
        return self._source_handler.get_source_preferences()

    def add_source_preference(
        self, source: str, position: Optional[int] = None
    ) -> None:
        """Add a new source to the preference list."""
        self._source_handler.add_source_preference(source, position)

    def remove_source_preference(self, source: str) -> bool:
        """Remove a source from the preference list."""
        return self._source_handler.remove_source_preference(source)

    def refresh_model_info(self) -> None:
        """Force refresh of model information from sources."""
        self._model_info_data = None
        self._model_to_services = None
        self._service_to_models = None
        self._source_handler.reset_used_source()
