import textwrap
from random import random
from typing import Optional, TYPE_CHECKING, Any, Union, Set


from ..config import CONFIG
from .exceptions import LanguageModelValueError

# Import only what's needed initially to avoid circular imports
from ..inference_services import (
    InferenceServiceError,
)

# The 'default' import will be imported lazily when needed

from ..enums import InferenceServiceLiteral

if TYPE_CHECKING:
    from ..dataset import Dataset
    from ..scenarios import ScenarioList
    from .model_list import ModelList


class Meta(type):
    """Metaclass for Model that provides helpful representation and usage information."""
    
    def __repr__(cls) -> str:
        """Return a helpful string representation with usage examples.
        
        Returns:
            A formatted string with usage examples.
        """
        return textwrap.dedent(
            """\
        To create an instance, you can do: 
        >>> m = Model('gpt-4-1106-preview', temperature=0.5, ...)
        
        To get the default model, you can leave out the model name. 
        To see the available models, you can do:
        >>> Model.available()

        Or to see the models for a specific service, you can do:
        >>> Model.available(service='openai')
        """
        )


class Model(metaclass=Meta):
    """Factory class for creating language model instances.
    
    The Model class provides a unified interface for instantiating language models
    from various inference services. It uses a registry-based approach to manage
    model creation and service discovery.
    
    Attributes:
        default_model: The default model name to use when none is specified.
        
    Examples:
        >>> model = Model()  # Uses default model
        >>> model = Model('gpt-4', temperature=0.7)
        >>> model = Model('claude-3', service_name='anthropic')
    """
    default_model = CONFIG.get("EDSL_DEFAULT_MODEL")

    _inference_service_registry = None  # Class-level registry storage

    @classmethod
    def get_inference_service_registry(cls) -> Any:
        """Get the current inference service registry or initialize with default if None.
        
        Returns:
            The current inference service registry instance. If none exists, 
            initializes with the default registry.
        """
        if cls._inference_service_registry is None:
            # Import lazily only when needed to avoid circular imports
            from edsl.inference_services import inference_service_registry
            cls._inference_service_registry = inference_service_registry
        return cls._inference_service_registry

    @classmethod
    def set_inference_service_registry(cls, registry: Any) -> None:
        """Set a new inference service registry.
        
        Args:
            registry: The new inference service registry to use.
        """
        cls._inference_service_registry = registry

    @classmethod
    def _handle_model_error(cls, model_name: str, error: Exception) -> Optional[Any]:
        """Handle errors from model creation and execution with notebook-aware behavior.
        
        Args:
            model_name: The name of the model that caused the error.
            error: The exception that was raised.
            
        Returns:
            None if in a notebook environment (error is printed), 
            otherwise raises the appropriate exception.
            
        Raises:
            InferenceServiceError: If the error is service-related and not in a notebook.
            Exception: Re-raises the original error if not in a notebook.
        """
        if isinstance(error, InferenceServiceError):
            registry = cls.get_inference_service_registry()
            service_instances = registry.get_service_instances()
            services = [getattr(s, '_inference_service_', s.__class__.__name__) for s in service_instances]
            message = (
                f"Model '{model_name}' not found in any services.\n"
                "It is likely that our registry is just out of date.\n"
                "Simply adding the service name to your model call should fix this.\n"
                f"Available services are: {services}\n"
                f"To specify a model with a service, use:\n"
                f'Model("{model_name}", service_name="<service_name>")'
            )
        else:
            message = f"An error occurred: {str(error)}"

        # Check if we're in a notebook environment
        try:
            get_ipython()
            print(message)
            return None
        except NameError:
            # Not in a notebook, raise the exception
            if isinstance(error, InferenceServiceError):
                raise InferenceServiceError(message)
            raise error

    def __new__(
        cls,
        model_name: Optional[str] = None,
        service_name: Optional[InferenceServiceLiteral] = None,
        *args: Any,
        **kwargs: Any,
    ) -> Optional[Any]:
        """Instantiate a new language model.
        
        Args:
            model_name: The name of the model to instantiate. If None, uses the default model.
            service_name: Optional service name to use for the model.
            *args: Additional positional arguments passed to the model constructor.
            **kwargs: Additional keyword arguments passed to the model constructor.
            
        Returns:
            A language model instance, or None if an error occurs in notebook environment.
            
        Examples:
            >>> Model()
            Model(...)
            >>> Model('gpt-4', temperature=0.5)
            Model(...)
        """
        # Map index to the respective subclass
        if model_name is None:
            model_name = cls.default_model
            # Hard-wire service name for default model to avoid lookup issues
            if service_name is None:
                service_name = "openai"

        registry = cls.get_inference_service_registry()
        factory = registry.create_language_model(model_name, service_name=service_name)
        try:
            return factory(*args, **kwargs)
        except (InferenceServiceError, Exception) as e:
            return cls._handle_model_error(model_name, e)
      
    @classmethod
    def services(cls) -> "ScenarioList":
        """Returns a ScenarioList of services excluding 'test', sorted alphabetically.
        
        Returns:
            A ScenarioList containing available service names, excluding the 'test' service,
            sorted in alphabetical order.

        Examples:
            >>> Model.services()
            ScenarioList([...])
        """
        from ..scenarios import ScenarioList
        
        registry = cls.get_inference_service_registry()
        all_services = registry.list_registered_services()
        
        # Exclude 'test' service and sort alphabetically
        filtered_services = sorted([s for s in all_services if s != 'test'])
        
        return ScenarioList.from_list("service", filtered_services)
 
    @classmethod
    def services_with_local_keys(cls) -> Set[str]:
        """Returns a set of services for which the user has local API keys configured.
        
        Returns:
            A set of service names that have local API keys available.
        """
        return set(cls.key_info().select("service").to_list())

    @classmethod
    def key_info(cls, obscure_api_key: bool = True) -> "Dataset":
        """Returns a dataset of local API key information.
        
        Args:
            obscure_api_key: If True, obscures API keys by showing only first and last 4 characters.
            
        Returns:
            A Dataset containing service information and API key details.
        """
        from ..key_management import KeyLookupCollection
        from ..scenarios import Scenario, ScenarioList

        klc = KeyLookupCollection()
        klc.add_key_lookup(fetch_order=None)
        sl = ScenarioList()
        for service, entry in list(klc.data.values())[0].items():
            sl.append(Scenario({"service": service} | entry.to_dict()))
        if obscure_api_key:
            for service in sl:
                service["api_token"] = (
                    service["api_token"][:4] + "..." + service["api_token"][-4:]
                )
        return sl.to_dataset()

    @classmethod
    def search_models(cls, search_term: str, output_format: str = "model_list") -> Union["ModelList", "ScenarioList"]:
        """Search for models matching a pattern.
        
        Args:
            search_term: Wildcard pattern to search for (e.g., 'gpt*', '*claude*')
            output_format: Output format, either "model_list" (default) or "scenario_list"
            
        Returns:
            ModelList or ScenarioList with model_name and service_name fields
            
        Raises:
            ValueError: If output_format is not "model_list" or "scenario_list"
        """
        from ..scenarios import ScenarioList
        from .model_list import ModelList
        
        registry = cls.get_inference_service_registry()
        matches = registry.find_models(search_term)
        
        # Add service information for each model
        model_service_pairs = []
        for model_name in matches:
            preferred_service = registry.get_service_for_model(model_name)
            if preferred_service:
                model_service_pairs.append([model_name, preferred_service])
        
        if not model_service_pairs:
            if output_format == "scenario_list":
                return ScenarioList([])
            else:
                return ModelList([])
            
        model_names = [pair[0] for pair in model_service_pairs]
        service_names = [pair[1] for pair in model_service_pairs]
        
        scenario_list = ScenarioList.from_list("model_name", model_names).add_list("service_name", service_names)
        
        if output_format == "scenario_list":
            return scenario_list
        elif output_format == "model_list":
            return ModelList.from_scenario_list(scenario_list)
        else:
            raise ValueError(f"Invalid output_format: {output_format}. Must be 'model_list' or 'scenario_list'")

    @classmethod
    def all_known_models(cls, output_format: str = "model_list") -> Union["ModelList", "ScenarioList"]:
        """Get all available models from the inference service registry.
        
        Args:
            output_format: Output format, either "model_list" (default) or "scenario_list"
        
        Returns:
            ModelList or ScenarioList with model_name and service_name fields for all known models
            
        Raises:
            ValueError: If output_format is not "model_list" or "scenario_list"
        """
        from ..scenarios import ScenarioList
        from .model_list import ModelList
        
        registry = cls.get_inference_service_registry()
        registry.ensure_model_mappings()  # Ensure mappings are built
        
        # Build lists of model names and their preferred services
        model_names = []
        service_names = []
        
        for model_name, service_list in registry.get_model_to_services_mapping().items():
            # Use the preferred service for each model
            preferred_service = registry.get_service_for_model(model_name)
            if preferred_service:
                model_names.append(model_name)
                service_names.append(preferred_service)
        
        if not model_names:
            if output_format == "scenario_list":
                return ScenarioList([])
            else:
                return ModelList([])
            
        scenario_list = ScenarioList.from_list("model_name", model_names).add_list("service_name", service_names)
        
        if output_format == "scenario_list":
            return scenario_list
        elif output_format == "model_list":
            return ModelList.from_scenario_list(scenario_list)
        else:
            raise ValueError(f"Invalid output_format: {output_format}. Must be 'model_list' or 'scenario_list'")

    @classmethod
    def available_with_local_keys(cls, output_format: str = "model_list") -> Union["ModelList", "ScenarioList"]:
        """Get models available for services that have local API keys configured.
        
        Args:
            output_format: Output format, either "model_list" (default) or "scenario_list"
        
        Returns:
            ModelList or ScenarioList of models from services with local keys
            
        Raises:
            ValueError: If output_format is not "model_list" or "scenario_list"
        """
        services_with_local_keys = set(cls.key_info().select("service").to_list())
        all_models = cls.all_known_models(output_format="scenario_list")  # Always get as scenario_list first
        
        # Filter the ScenarioList by services with local keys
        filtered_scenario_list = all_models.filter(lambda scenario: scenario["service_name"] in services_with_local_keys)
        
        if output_format == "scenario_list":
            return filtered_scenario_list
        elif output_format == "model_list":
            from .model_list import ModelList
            return ModelList.from_scenario_list(filtered_scenario_list)
        else:
            raise ValueError(f"Invalid output_format: {output_format}. Must be 'model_list' or 'scenario_list'")

    @classmethod
    def available(
        cls,
        search_term: Optional[str] = None,
        service_name: Optional[str] = None,
        force_refresh: bool = False,
        local_only: bool = False,
        output_format: str = "model_list",
    ) -> Union["ModelList", "ScenarioList"]:
        """Get available models as a ModelList or ScenarioList.

        Args:
            search_term: Optional search pattern to filter models (e.g., 'gpt*', '*claude*').
                Will match models containing this string.
            service_name: Optional service name to filter by (e.g., 'openai', 'anthropic').
            force_refresh: Whether to force refresh the model cache from services.
            local_only: If True, only return models from services with local API keys configured.
            output_format: Output format, either "model_list" (default) or "scenario_list".

        Returns:
            ModelList or ScenarioList with model_name and service_name fields

        Raises:
            LanguageModelValueError: If the specified service_name is not available.
            ValueError: If output_format is not "model_list" or "scenario_list".

        Examples:
            >>> Model.available()
            ModelList([...])
            >>> Model.available(service_name='openai')
            ModelList([...])
            >>> Model.available(local_only=True)
            ModelList([...])
            >>> Model.available(output_format="scenario_list")
            ScenarioList([...])
        """
        from ..scenarios import ScenarioList
        
        registry = cls.get_inference_service_registry()
        
        if force_refresh:
            registry.refresh_model_cache()

        # Validate service_name if provided
        if service_name is not None:
            if service_name not in registry:
                available_services = list(registry.list_registered_services())
                raise LanguageModelValueError(
                    f"Service {service_name} not found in available services. Available services are: {available_services}"
                )

        # Get filtered model list from registry
        if service_name:
            # Get models for specific service
            models_for_service = registry.get_models_for_service(service_name)
            if search_term:
                # Further filter by search term
                filtered_models = [
                    model for model in models_for_service
                    if search_term in model
                ]
            else:
                filtered_models = models_for_service
                
            # Always return model name and service name
            result = ScenarioList.from_list("model_name", filtered_models).add_list("service_name", [service_name] * len(filtered_models))
        else:
            # Get all models and filter by search term if provided
            if search_term:
                matching_models = registry.find_models(f"*{search_term}*")
            else:
                # Get all models
                matching_models = registry.get_all_model_names()
            
            # Build result with service info
            model_service_pairs = []
            for model_name in matching_models:
                preferred_service = registry.get_service_for_model(model_name)
                if preferred_service:
                    model_service_pairs.append([model_name, preferred_service])
            
            model_names = [pair[0] for pair in model_service_pairs]
            service_names = [pair[1] for pair in model_service_pairs]
            result = ScenarioList.from_list("model_name", model_names).add_list("service_name", service_names)
        
        # Apply local_only filter if requested
        if local_only:
            services_with_local_keys = cls.services_with_local_keys()
            services_filter = " or ".join([f'service_name == "{service}"' for service in services_with_local_keys])
            if services_filter:
                result = result.filter(services_filter)
        
        if output_format == "scenario_list":
            return result
        elif output_format == "model_list":
            from .model_list import ModelList
            return ModelList.from_scenario_list(result)
        else:
            raise ValueError(f"Invalid output_format: {output_format}. Must be 'model_list' or 'scenario_list'")

    @classmethod
    def check_models(cls, verbose: bool = False) -> None:
        """Check model availability and status.
        
        Note:
            This method is deprecated and not supported in the new registry architecture.
            
        Args:
            verbose: Whether to provide verbose output.
            
        Raises:
            NotImplementedError: Always raised as this functionality is deprecated.
        """
        raise NotImplementedError("Service classes are not supported in the new registry.")

    @classmethod
    def check_working_models(
        cls,
        service: Optional[str] = None,
        works_with_text: Optional[bool] = None,
        works_with_images: Optional[bool] = None,
        output_format: str = "model_list",
    ) -> Union["ModelList", "ScenarioList"]:
        """Check working models from Coop with optional filtering.
        
        Args:
            service: Filter by service name (e.g., 'openai', 'anthropic').
            works_with_text: Filter by text processing capability.
            works_with_images: Filter by image processing capability.
            output_format: Output format, either "model_list" (default) or "scenario_list".
            
        Returns:
            ModelList or ScenarioList of working models with their details including
            service, model name, capabilities, and pricing information.
            
        Raises:
            ValueError: If output_format is not "model_list" or "scenario_list".
        """
        from ..coop import Coop
        from ..scenarios import ScenarioList
        
        c = Coop()
        working_models = c.fetch_working_models()

        if service is not None:
            working_models = [m for m in working_models if m["service"] == service]
        if works_with_text is not None:
            working_models = [
                m for m in working_models if m["works_with_text"] == works_with_text
            ]
        if works_with_images is not None:
            working_models = [
                m for m in working_models if m["works_with_images"] == works_with_images
            ]

        if len(working_models) == 0:
            if output_format == "scenario_list":
                return ScenarioList([])
            else:
                from .model_list import ModelList
                return ModelList([])
        else:
            # Create ScenarioList from working models data
            sl = ScenarioList.from_list("service", [m["service"] for m in working_models])
            sl = sl.add_list("model", [m["model"] for m in working_models])
            sl = sl.add_list("works_with_text", [m["works_with_text"] for m in working_models])
            sl = sl.add_list("works_with_images", [m["works_with_images"] for m in working_models])
            sl = sl.add_list("usd_per_1M_input_tokens", [m["usd_per_1M_input_tokens"] for m in working_models])
            sl = sl.add_list("usd_per_1M_output_tokens", [m["usd_per_1M_output_tokens"] for m in working_models])
            
            if output_format == "scenario_list":
                return sl
            elif output_format == "model_list":
                from .model_list import ModelList
                # Create a proper scenario list with model_name and service_name for ModelList conversion
                model_sl = ScenarioList.from_list("model_name", [m["model"] for m in working_models])
                model_sl = model_sl.add_list("service_name", [m["service"] for m in working_models])
                # Add additional metadata that might be useful
                model_sl = model_sl.add_list("works_with_text", [m["works_with_text"] for m in working_models])
                model_sl = model_sl.add_list("works_with_images", [m["works_with_images"] for m in working_models])
                model_sl = model_sl.add_list("usd_per_1M_input_tokens", [m["usd_per_1M_input_tokens"] for m in working_models])
                model_sl = model_sl.add_list("usd_per_1M_output_tokens", [m["usd_per_1M_output_tokens"] for m in working_models])
                return ModelList.from_scenario_list(model_sl)
            else:
                raise ValueError(f"Invalid output_format: {output_format}. Must be 'model_list' or 'scenario_list'")

    @classmethod
    def example(cls, randomize: bool = False) -> "Model":
        """Returns an example Model instance for testing and demonstration purposes.

        Args:
            randomize: If True, the temperature is set to a random decimal between 0 and 1.
                      If False, uses a fixed temperature of 0.5.

        Returns:
            A Model instance using the default model with specified temperature.
            
        Examples:
            >>> Model.example()
            Model(...)
            >>> Model.example(randomize=True)
            Model(...)
        """
        temperature = 0.5 if not randomize else round(random(), 2)
        model_name = cls.default_model
        return cls(model_name, service_name="openai", temperature=temperature)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
