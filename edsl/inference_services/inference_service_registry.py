from typing import Dict, List, Any, Optional, Tuple, TYPE_CHECKING, Type, Tuple
from datetime import datetime
from collections import defaultdict
import fnmatch
from .model_info_fetcher import ModelInfoCoopRegular, ModelInfoCoopWorking, ModelInfoServices


class InferenceServiceRegistry:
    """
    Registry for managing inference service classes with serialization support.
    
    Args:
        verbose: Enable verbose logging output
        model_source: Source for model discovery ("services" or "coop")
        service_preferences: Optional ordered tuple of preferred service names
    """

    _default_service_preferences = ('anthropic', 'bedrock', 'azure', 'openai', 'deep_infra', 'deepseek', 'google', 'groq', 'mistral', 'ollama', 'openai_v2', 'perplexity', 'together', 'xai', 'open_router')
        
    def __init__(self, verbose: bool = False, service_preferences: Optional[Tuple[str, ...]] = None):
        self._services = {}
        self._registration_times = {}  # Track when services were registered

        self._model_info_data = None

        self._model_to_services = None  # Map model names to service names
        self._service_to_models = None
     
        self.verbose = verbose  # Enable verbose logging
        self._service_preferences = service_preferences if service_preferences else self._default_service_preferences  # Ordered tuple of preferred services

        #if source_preference is None:
        #    source_preference = ('coop', 'local', 'archive')
        self._source_preference = ['coop','local', 'archive']


    @property
    def model_to_services(self) -> Dict[str, List[str]]:
        if self._model_to_services is None:
            self._build_model_mappings()
        return self._model_to_services
    
    @property
    def services(self) -> List[str]:
        return self._services
    
    @property
    def service_to_models(self) -> Dict[str, List[str]]:
        if self._service_to_models is None:
            self._build_model_mappings()
        return self._service_to_models
        
    def get_service_to_class(self) -> Dict[str, type['InferenceServiceABC']]:
        return self._services
        
    def register(self, service_name: str, service_class: type['InferenceServiceABC']):
        """Register a service class with the given name."""
        if service_name == "test":
            return
        self._services[service_name] = service_class
        self._registration_times[service_name] = datetime.now()
                
    def get_service_class(self, service_name: str) -> type['InferenceServiceABC']:
        """Returns the class for a given service name."""           
        if service_name not in self._services:
            raise KeyError(f"Service '{service_name}' not found in registry. Available services: {list(self._services.keys())}")

        return self._services[service_name]
    
    def list_registered_services(self) -> list[str]:
        """Returns a list of all registered service names."""
        return list(self._services.keys())
        
    @property
    def model_info_data(self) -> dict:
        """Get the model data from the model info fetcher."""
        if self._model_info_data is None:
            from .model_info_fetcher import ModelInfoFetcherABC
            fetchers = ModelInfoFetcherABC.get_registered_fetchers()
            for source in self._source_preference:
                if source in fetchers:
                    model_info_fetcher = fetchers[source](self)
                    try:
                        model_info_fetcher.fetch()
                    except Exception as e:
                        if self.verbose:
                            print(f"Error fetching model info from {source}: {e}")
                        continue
                    
                    if len(model_info_fetcher) > 0:
                        self._model_info_data = dict(model_info_fetcher)
                    else:
                        if self.verbose:
                            print("Came back empty") 
                        continue

                    break
                else:
                    raise ValueError(f"No fetcher registered with name '{source}'. Available: {list(fetchers.keys())}")
                
        if self._model_info_data is None: 
            raise ValueError("Could not build info from any source")    

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
            
            # Build reverse mapping
            for model_name in models:
                self._model_to_services[model_name].append(service_name)
          
    def get_service_for_model(self, model_name: str) -> Optional[str]:
        """Get the preferred service for a given model name based on user preferences."""
        # Early check for test models to avoid API calls
        if model_name == 'test':
            return 'test'
                    
        services = self.model_to_services.get(model_name, [])
        if not services:
            raise ValueError(f"Model '{model_name}' not found in any service. Available models: {list(self.model_to_services.keys())}")
                    
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
        return self.service_to_models.get(service_name, [])
    
    def find_services(self, pattern: str) -> List[str]:
        """Find services matching a wildcard pattern."""         
        return [
            service_name for service_name in self._services.keys()
            if fnmatch.fnmatch(service_name, pattern)
        ]
           
    def find_models(self, pattern: str, service_name: Optional[str] = None) -> List[str]:
        """Find models matching a wildcard pattern, optionally within a specific service."""
        
        if service_name:
            # Search within a specific service
            service_models = self.service_to_models.get(service_name, [])
            return [
                model for model in service_models
                if fnmatch.fnmatch(model, pattern)
            ]
        else:
            return [
                model for model in self._model_to_services.keys()
                if fnmatch.fnmatch(model, pattern)
            ]
            
    def get_filtered_model_list(
        self, 
        service_pattern: Optional[str] = None,
        model_pattern: Optional[str] = None,
        skip_errors: bool = True
    ) -> Dict[str, List[str]]:
        """
        Get a filtered list of models based on service and model patterns.
        
        Args:
            service_pattern: Wildcard pattern for service names (e.g., 'openai*')
            model_pattern: Wildcard pattern for model names (e.g., 'gpt*')
            skip_errors: Whether to skip services that fail to load models
            
        Returns:
            Dict mapping service names to lists of matching model names
        """        
        # Filter services
        if service_pattern:
            services_to_check = self.find_services(service_pattern)
        else:
            services_to_check = list(self.service_to_models.keys())
        
        result = {}
        for service_name in services_to_check:
            if model_pattern:
                # Filter models within this service
                matching_models = self.find_models(model_pattern, service_name)
            else:
                # All models from this service
                matching_models = self.service_to_models.get(service_name, [])
            
            if matching_models:  # Only include services with matching models
                result[service_name] = matching_models
        
        return result
    
    def create_language_model(self, model_name: str, service_name: Optional[str] = None, *args, **kwargs):
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
                raise ValueError(f"No service found for model '{model_name}'", 
                                 f"Available services: {list(self._services.keys())}")
            
        if model_name == 'test':
            from .services import TestService
            service_class = TestService 
        else:              
            service_class = self.get_service_class(service_name)
        
        service_instance = service_class()
        return service_instance.create_model(model_name, *args, **kwargs)
    
            
