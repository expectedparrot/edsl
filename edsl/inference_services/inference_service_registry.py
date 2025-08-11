from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import fnmatch


class InferenceServiceRegistry:
    """
    Registry for managing inference service classes with serialization support.
    
    Args:
        verbose: Enable verbose logging output
        model_source: Source for model discovery ("services" or "coop")
        service_preferences: Optional ordered tuple of preferred service names
    """

    _default_service_preferences = ('anthropic', 'bedrock', 'azure', 'openai', 'deep_infra', 'deepseek', 'google', 'groq', 'mistral', 'ollama', 'openai_v2', 'perplexity', 'test', 'together', 'xai', 'open_router')
    
    def _infer_service_from_model_name_fallback(self, model_name: str) -> Optional[str]:
        """
        TEMPORARY FALLBACK: Infer service from model name patterns.
        
        This is a temporary solution for deserialization compatibility.
        TODO: Remove this function once we have proper service info in serialized data.
        
        Args:
            model_name: The model name to infer service for
            
        Returns:
            Service name if pattern matches, None otherwise
        """
        # Only handle well-known patterns to minimize risk
        if model_name.startswith(('gpt-', 'text-davinci', 'text-curie', 'text-babbage', 'text-ada', 'davinci', 'curie', 'babbage', 'ada', 'chatgpt-', 'o1')):
            return 'openai'
        elif model_name.startswith('claude'):
            return 'anthropic'
        elif model_name.startswith('gemini'):
            return 'google'
        elif model_name == 'test':
            return 'test'
        
        # Don't try to guess other services - too risky
        return None
    
    def __init__(self, verbose: bool = False, model_source: Optional[str] = None, service_preferences: Optional[Tuple[str, ...]] = None):
        self._services = {}
        self._registration_times = {}  # Track when services were registered
        self._model_cache = {}  # Cache model lists to avoid repeated API calls
        self._model_to_services = defaultdict(list)  # Map model names to service names
        self._service_to_models = {}  # Map service names to model lists
        self._cache_valid = False  # Whether the model cache is up to date
        self._model_source = model_source  # No default - must be explicitly set
        self.verbose = verbose  # Enable verbose logging
        self._service_preferences = service_preferences if service_preferences else self._default_service_preferences  # Ordered tuple of preferred services
        
        if self.verbose:
            print(f"[REGISTRY] Initialized new InferenceServiceRegistry with verbose={verbose}")
            if self._service_preferences:
                print(f"[REGISTRY] Initial service preferences: {self._service_preferences}")
    
    def register(self, service_name: str, service_class):
        """Register a service class with the given name."""
        if self.verbose:
            print(f"[REGISTRY] Registering service '{service_name}' -> {service_class}")
            
        self._services[service_name] = service_class
        self._registration_times[service_name] = datetime.now()
        self._cache_valid = False  # Invalidate cache when new service is registered
        
        if self.verbose:
            print(f"[REGISTRY] Service '{service_name}' registered successfully. Total services: {len(self._services)}")
            print("[REGISTRY] Cache invalidated due to new service registration")
    
    def get_registry(self) -> dict:
        """Returns a copy of all registered services."""
        if self.verbose:
            print(f"[REGISTRY] get_registry() called - returning {len(self._services)} services")
        return self._services.copy()
    
    def get_service_class(self, service_name: str):
        """Returns the class for a given service name."""
        if self.verbose:
            print(f"[REGISTRY] get_service_class('{service_name}') called")
            
        if service_name not in self._services:
            if self.verbose:
                print(f"[REGISTRY] ERROR: Service '{service_name}' not found. Available: {list(self._services.keys())}")
            raise KeyError(f"Service '{service_name}' not found in registry. Available services: {list(self._services.keys())}")
        
        service_entry = self._services[service_name]
        
        # If it's a dictionary (from deserialization without classes), raise an error
        if isinstance(service_entry, dict):
            if self.verbose:
                print(f"[REGISTRY] ERROR: Service '{service_name}' is info-only (no actual class)")
            raise ValueError(f"Service '{service_name}' was loaded from serialized data without the actual class. Only service information is available.")
        
        if self.verbose:
            print(f"[REGISTRY] Returning service class for '{service_name}': {service_entry}")
        return service_entry
    
    def list_registered_services(self) -> list[str]:
        """Returns a list of all registered service names."""
        return list(self._services.keys())
    
    def get_all_model_lists(self, skip_errors: bool = True) -> Dict[str, List[Any]]:
        """Get model lists from all registered services."""
        result = {}
        
        for service_name, service_entry in self._services.items():
            try:
                # Skip if this is just info data (not an actual class)
                if isinstance(service_entry, dict):
                    if skip_errors:
                        result[service_name] = []  # Empty list for info-only services
                        continue
                    else:
                        raise ValueError(f"Service '{service_name}' has no actual class loaded")
                
                # It's an actual service class
                model_list = service_entry.get_model_list()
                result[service_name] = model_list
            except Exception as e:
                if skip_errors:
                    result[service_name] = []  # Empty list for failed services
                else:
                    raise e
                    
        return result
    
    def _build_model_mappings(self, force_refresh: bool = False):
        """Build the model-to-service and service-to-model mappings."""
        if self.verbose:
            print(f"[REGISTRY] _build_model_mappings() called with force_refresh={force_refresh}")
            print(f"[REGISTRY] Cache valid: {self._cache_valid}")
            print(f"[REGISTRY] Current model source: {self._model_source}")
            
        if self._cache_valid and not force_refresh:
            if self.verbose:
                print("[REGISTRY] Using cached model mappings")
            return
            
        if self.verbose:
            print(f"[REGISTRY] Building fresh model mappings using {self._model_source} source...")
            print("[REGISTRY] Clearing existing mappings")
            
        self._model_to_services.clear()
        self._service_to_models.clear()
        
        # Get model data based on the current source
        if self._model_source is None:
            if self.verbose:
                print("[REGISTRY] No model source set - cannot build model mappings")
            raise ValueError("No model source set. Call set_model_source('coop') or set_model_source('services') first.")
        elif self._model_source == "coop":
            all_models = self._fetch_models_from_coop_internal()
        elif self._model_source == "services":
            all_models = self._fetch_models_from_services_internal()
        else:
            raise ValueError(f"Unknown model source: {self._model_source}")
        
        if self.verbose:
            print(f"[REGISTRY] Got model lists from {len(all_models)} services")
        
        total_models = 0
        for service_name, models in all_models.items():
            if self.verbose:
                print(f"[REGISTRY] Processing {len(models)} models from service '{service_name}'")
                
            # Convert ModelInfo objects to model names if needed
            model_names = []
            for model in models:
                if hasattr(model, 'model_name'):
                    model_names.append(model.model_name)
                elif hasattr(model, 'id'):
                    model_names.append(model.id)
                elif isinstance(model, str):
                    model_names.append(model)
                else:
                    model_names.append(str(model))
            
            self._service_to_models[service_name] = model_names
            total_models += len(model_names)
            
            if self.verbose:
                print(f"[REGISTRY] Service '{service_name}' provides {len(model_names)} models")
            
            # Build reverse mapping
            for model_name in model_names:
                self._model_to_services[model_name].append(service_name)
        
        self._cache_valid = True
        
        if self.verbose:
            print("[REGISTRY] Model mapping complete!")
            print(f"[REGISTRY] Total unique models: {len(self._model_to_services)}")
            print(f"[REGISTRY] Total model instances: {total_models}")
            print("[REGISTRY] Cache marked as valid")
    
    def _fetch_models_from_coop_internal(self) -> Dict[str, List[Any]]:
        """Internal method to fetch models from Coop."""
        try:
            if self.verbose:
                print("[REGISTRY] Fetching models from Coop API...")
                
            from edsl.coop import Coop
            
            c = Coop()
            coop_model_list = c.fetch_models()
            
            if self.verbose:
                print(f"[REGISTRY] Coop returned model data for {len(coop_model_list)} services")
                
            return coop_model_list
            
        except Exception as e:
            if self.verbose:
                print(f"[REGISTRY] Error fetching from Coop: {e}")
                print("[REGISTRY] Falling back to service APIs...")
            # Fall back to service APIs
            return self._fetch_models_from_services_internal()
    
    def fetch_working_models(self, return_type: str = "list"):
        """
        Fetch a list of working models from Coop with pricing and capability information.
        
        Args:
            return_type: Either "list" for List[dict] or "scenario_list" for ScenarioList
        
        Returns:
            Either a List of dictionaries or a ScenarioList containing:
                - service: The service name (e.g., "openai")
                - model: The model name (e.g., "gpt-4o")
                - works_with_text: Boolean indicating text capability
                - works_with_images: Boolean indicating image capability
                - usd_per_1M_input_tokens: Cost per million input tokens
                - usd_per_1M_output_tokens: Cost per million output tokens
        
        Example:
            >>> registry = InferenceServiceRegistry()
            >>> models_list = registry.fetch_working_models("list")
            >>> models_scenarios = registry.fetch_working_models("scenario_list")
        """
        try:
            if self.verbose:
                print("[REGISTRY] Fetching working models from Coop API...")
                
            from edsl.coop import Coop
            
            c = Coop()
            working_models = c.fetch_working_models()
            
            if self.verbose:
                print(f"[REGISTRY] Coop returned {len(working_models)} working models")
                
            if return_type == "list":
                return working_models
            elif return_type == "scenario_list":
                from ..scenarios import ScenarioList, Scenario
                scenarios = [Scenario(model_data) for model_data in working_models]
                return ScenarioList(scenarios)
            else:
                raise ValueError(f"Invalid return_type '{return_type}'. Must be 'list' or 'scenario_list'")
                
        except Exception as e:
            if self.verbose:
                print(f"[REGISTRY] Error fetching working models from Coop: {e}")
            raise e
    
    def _fetch_models_from_services_internal(self) -> Dict[str, List[Any]]:
        """Internal method to fetch models from service APIs."""
        if self.verbose:
            print("[REGISTRY] Fetching models from service APIs...")
            
        return self.get_all_model_lists(skip_errors=True)
    
    def get_service_for_model(self, model_name: str) -> Optional[str]:
        """Get the preferred service for a given model name based on user preferences."""
        if self.verbose:
            print(f"[REGISTRY] get_service_for_model('{model_name}') called")
            
        self._build_model_mappings()
        services = self._model_to_services.get(model_name, [])
        
        if not services:
            if self.verbose:
                print(f"[REGISTRY] Model '{model_name}' not found in any service")
            
            # TEMPORARY: Try fallback heuristic (TODO: remove once serialization includes service info)
            fallback_service = self._infer_service_from_model_name_fallback(model_name)
            if fallback_service:
                if self.verbose:
                    print(f"[REGISTRY] Using FALLBACK heuristic service '{fallback_service}' for model '{model_name}'")
                return fallback_service
            
            return None
        
        if self.verbose:
            print(f"[REGISTRY] Model '{model_name}' found in services: {services}")
            print(f"[REGISTRY] Service preferences: {self._service_preferences}")
        
        # Find the first preferred service that provides this model
        for preferred_service in self._service_preferences:
            if preferred_service in services:
                if self.verbose:
                    print(f"[REGISTRY] Using preferred service: {preferred_service}")
                return preferred_service
        
        # Fall back to first available service if no preferences match
        selected_service = services[0]
        if self.verbose:
            if self._service_preferences:
                print(f"[REGISTRY] No preferred services found for model '{model_name}', using fallback: {selected_service}")
            else:
                print(f"[REGISTRY] No service preferences set, using first available: {selected_service}")
                
        return selected_service
    
    def get_services_for_model(self, model_name: str) -> List[str]:
        """Get all services that provide a given model name."""
        self._build_model_mappings()
        return list(self._model_to_services.get(model_name, []))
    
    def get_models_for_service(self, service_name: str) -> List[str]:
        """Get all model names for a given service."""
        if self.verbose:
            print(f"[REGISTRY] get_models_for_service('{service_name}') called")
            
        self._build_model_mappings()
        models = self._service_to_models.get(service_name, [])
        
        if self.verbose:
            print(f"[REGISTRY] Service '{service_name}' has {len(models)} models")
            
        return models
    
    def find_services(self, pattern: str) -> List[str]:
        """Find services matching a wildcard pattern."""
        if self.verbose:
            print(f"[REGISTRY] find_services('{pattern}') called")
            
        matches = [
            service_name for service_name in self._services.keys()
            if fnmatch.fnmatch(service_name, pattern)
        ]
        
        if self.verbose:
            print(f"[REGISTRY] Pattern '{pattern}' matched {len(matches)} services: {matches}")
            
        return matches
    
    def find_models(self, pattern: str, service_name: Optional[str] = None) -> List[str]:
        """Find models matching a wildcard pattern, optionally within a specific service."""
        if self.verbose:
            if service_name:
                print(f"[REGISTRY] find_models('{pattern}', service='{service_name}') called")
            else:
                print(f"[REGISTRY] find_models('{pattern}') called - searching all services")
                
        self._build_model_mappings()
        
        if service_name:
            # Search within a specific service
            service_models = self._service_to_models.get(service_name, [])
            matches = [
                model for model in service_models
                if fnmatch.fnmatch(model, pattern)
            ]
            
            if self.verbose:
                print(f"[REGISTRY] Service '{service_name}' has {len(service_models)} models")
                print(f"[REGISTRY] Pattern '{pattern}' matched {len(matches)} models in service '{service_name}'")
                
            return matches
        else:
            # Search across all services
            matches = [
                model for model in self._model_to_services.keys()
                if fnmatch.fnmatch(model, pattern)
            ]
            
            if self.verbose:
                print(f"[REGISTRY] Pattern '{pattern}' matched {len(matches)} models across all services")
                
            return matches
    
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
        self._build_model_mappings()
        
        # Filter services
        if service_pattern:
            services_to_check = self.find_services(service_pattern)
        else:
            services_to_check = list(self._service_to_models.keys())
        
        result = {}
        for service_name in services_to_check:
            if model_pattern:
                # Filter models within this service
                matching_models = self.find_models(model_pattern, service_name)
            else:
                # All models from this service
                matching_models = self._service_to_models.get(service_name, [])
            
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
        else:
            # Use the explicitly provided service name
            if self.verbose:
                print(f"[REGISTRY] Using explicitly provided service '{service_name}' for model '{model_name}'")
            
        service_class = self.get_service_class(service_name)
        service_instance = service_class()
        return service_instance.create_model(model_name, *args, **kwargs)
    
    def refresh_model_cache(self):
        """Force refresh of the model cache."""
        self._build_model_mappings(force_refresh=True)
    
    def ensure_model_mappings(self):
        """Ensure model mappings are built (public method to replace _build_model_mappings)."""
        self._build_model_mappings()
    
    def get_all_model_names(self) -> List[str]:
        """Get a list of all known model names."""
        self._build_model_mappings()
        return list(self._model_to_services.keys())
    
    def get_model_to_services_mapping(self) -> Dict[str, List[str]]:
        """Get the complete mapping of models to their available services."""
        self._build_model_mappings()
        return dict(self._model_to_services)
    
    def get_service_instances(self):
        """Get service class instances for all registered services."""
        service_instances = []
        for service_name, service_class in self._services.items():
            if not isinstance(service_class, dict):  # Skip info-only entries
                try:
                    service_instances.append(service_class())
                except Exception:
                    # Skip services that can't be instantiated
                    pass
        return service_instances
    
    def load_models_from_coop(self):
        """
        Load model information from Coop as an alternative to direct service APIs.
        This can be faster and more reliable than querying each service individually.
        """
        if self.verbose:
            print("[REGISTRY] Switching to Coop model source...")
            
        self._model_source = "coop"
        self._cache_valid = False  # Invalidate cache to force refresh
        
        # Build mappings using Coop data
        self._build_model_mappings(force_refresh=True)
    
    def load_models_from_services(self):
        """
        Load model information directly from service APIs.
        This is the default method that queries each service individually.
        """
        if self.verbose:
            print("[REGISTRY] Switching to service APIs model source...")
            
        self._model_source = "services"
        self._cache_valid = False  # Invalidate cache to force refresh
        
        # Build mappings using service APIs
        self._build_model_mappings(force_refresh=True)
    
    def set_model_source(self, source: str = "services"):
        """
        Set the source for model discovery.
        
        Args:
            source (str): Either "services" (default) or "coop"
        """
        if self.verbose:
            print(f"[REGISTRY] Setting model source to: {source}")
            
        if source == "coop":
            self.load_models_from_coop()
        elif source == "services":
            self.load_models_from_services()
        else:
            raise ValueError(f"Invalid model source: {source}. Must be 'services' or 'coop'")
            
        if self.verbose:
            print(f"[REGISTRY] Model source set to {source} successfully")
    
    def get_model_source(self) -> str:
        """Get the current model source."""
        if self._model_source is None:
            return "not_set"
        return self._model_source
    
    def set_service_preferences(self, preferences: Tuple[str, ...]):
        """
        Set the ordered tuple of preferred services.
        
        When multiple services provide the same model, the service that appears
        first in this preference tuple will be selected.
        
        Args:
            preferences: Tuple of service names in order of preference (highest to lowest)
        """
        if self.verbose:
            print(f"[REGISTRY] Setting service preferences: {preferences}")
            
        # Validate that all specified services exist
        invalid_services = [s for s in preferences if s not in self._services]
        if invalid_services:
            available_services = list(self._services.keys())
            raise ValueError(f"Invalid service(s): {invalid_services}. Available services: {available_services}")
        
        self._service_preferences = preferences
        
        if self.verbose:
            print("[REGISTRY] Service preferences updated successfully")
    
    def add_service_preference(self, service_name: str, position: Optional[int] = None):
        """
        Add a service to the preference order.
        
        Args:
            service_name: Name of the service to add
            position: Position to insert at (0=highest priority). If None, appends to end.
        """
        if self.verbose:
            print(f"[REGISTRY] Adding service preference: {service_name} at position {position}")
            
        if service_name not in self._services:
            available_services = list(self._services.keys())
            raise ValueError(f"Service '{service_name}' not found. Available services: {available_services}")
        
        # Convert to list, modify, convert back to tuple
        prefs_list = list(self._service_preferences)
        
        # Remove if already in list
        if service_name in prefs_list:
            prefs_list.remove(service_name)
        
        # Insert at specified position or append
        if position is None:
            prefs_list.append(service_name)
        else:
            prefs_list.insert(position, service_name)
            
        self._service_preferences = tuple(prefs_list)
            
        if self.verbose:
            print(f"[REGISTRY] Updated service preferences: {self._service_preferences}")
    
    def remove_service_preference(self, service_name: str):
        """Remove a service from the preference order."""
        if self.verbose:
            print(f"[REGISTRY] Removing service preference: {service_name}")
            
        if service_name in self._service_preferences:
            prefs_list = list(self._service_preferences)
            prefs_list.remove(service_name)
            self._service_preferences = tuple(prefs_list)
            if self.verbose:
                print(f"[REGISTRY] Updated service preferences: {self._service_preferences}")
        else:
            if self.verbose:
                print(f"[REGISTRY] Service '{service_name}' was not in preferences tuple")
    
    def clear_service_preferences(self):
        """Clear all service preferences."""
        if self.verbose:
            print("[REGISTRY] Clearing all service preferences")
            
        self._service_preferences = ()
        
        if self.verbose:
            print("[REGISTRY] Service preferences cleared")
    
    def get_service_preferences(self) -> Tuple[str, ...]:
        """Get the current service preferences as an ordered tuple."""
        return self._service_preferences
    
    def reorder_service_preference(self, service_name: str, new_position: int):
        """
        Move a service to a new position in the preference order.
        
        Args:
            service_name: Name of the service to move
            new_position: New position (0=highest priority)
        """
        if self.verbose:
            print(f"[REGISTRY] Moving service '{service_name}' to position {new_position}")
            
        if service_name not in self._service_preferences:
            raise ValueError(f"Service '{service_name}' is not in the preference tuple")
        
        # Convert to list, remove and re-insert at new position, convert back to tuple
        prefs_list = list(self._service_preferences)
        prefs_list.remove(service_name)
        prefs_list.insert(new_position, service_name)
        self._service_preferences = tuple(prefs_list)
        
        if self.verbose:
            print(f"[REGISTRY] Updated service preferences: {self._service_preferences}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the registry to a dictionary.
        
        Returns:
            Dict containing service names, class information, and metadata
        """
        services_info = {}
        
        for service_name, service_class in self._services.items():
            # Get basic class information that can be serialized
            class_info = {
                'class_name': service_class.__name__,
                'module_name': service_class.__module__,
                'service_name': service_name,
                'registration_time': self._registration_times.get(service_name, datetime.now()).isoformat(),
            }
            
            # Add service-specific attributes if they exist
            if hasattr(service_class, '_inference_service_'):
                class_info['inference_service'] = service_class._inference_service_
            if hasattr(service_class, 'key_sequence'):
                class_info['key_sequence'] = service_class.key_sequence
            if hasattr(service_class, 'model_exclude_list'):
                class_info['model_exclude_list'] = service_class.model_exclude_list
            if hasattr(service_class, 'usage_sequence'):
                class_info['usage_sequence'] = service_class.usage_sequence
            if hasattr(service_class, 'input_token_name'):
                class_info['input_token_name'] = service_class.input_token_name
            if hasattr(service_class, 'output_token_name'):
                class_info['output_token_name'] = service_class.output_token_name
                
            services_info[service_name] = class_info
        
        return {
            'services': services_info,
            'service_preferences': self._service_preferences,
            'total_services': len(self._services),
            'export_time': datetime.now().isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], service_classes: Dict[str, type] = None) -> 'InferenceServiceRegistry':
        """
        Create a registry from a dictionary.
        
        Args:
            data: Dictionary containing serialized registry data
            service_classes: Optional mapping of service names to actual class objects
                           If not provided, service info is preserved but classes aren't available
        
        Returns:
            New InferenceServiceRegistry instance
        """
        registry = cls()
        
        if 'services' in data:
            for service_name, service_info in data['services'].items():
                # If we have the actual class, register it
                if service_classes and service_name in service_classes:
                    registry.register(service_name, service_classes[service_name])
                else:
                    # Store service info even without the class for informational purposes
                    registry._services[service_name] = service_info  # Store info dict instead of class
                    
                # Update registration time if available
                if 'registration_time' in service_info:
                    try:
                        registry._registration_times[service_name] = datetime.fromisoformat(service_info['registration_time'])
                    except (ValueError, TypeError):
                        pass  # Use current time if parsing fails
        
        # Restore service preferences if available
        if 'service_preferences' in data:
            # Only include preferences for services that are actually loaded
            valid_preferences = tuple(
                service for service in data['service_preferences'] 
                if service in registry._services
            )
            registry._service_preferences = valid_preferences
            
            if registry.verbose and valid_preferences:
                print(f"[REGISTRY] Restored service preferences: {valid_preferences}")
        
        return registry
    
    def get_service_info(self, service_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific service."""
        if service_name not in self._services:
            raise KeyError(f"Service '{service_name}' not found in registry")
            
        service_entry = self._services[service_name]
        
        # If it's already a dictionary (from deserialization), return it
        if isinstance(service_entry, dict):
            return service_entry.copy()
        
        # It's an actual service class - extract info
        info = {
            'service_name': service_name,
            'class_name': service_entry.__name__,
            'module_name': service_entry.__module__,
            'registration_time': self._registration_times.get(service_name, datetime.now()).isoformat(),
        }
        
        # Add any available attributes
        for attr in ['_inference_service_', 'key_sequence', 'model_exclude_list', 
                    'usage_sequence', 'input_token_name', 'output_token_name']:
            if hasattr(service_entry, attr):
                info[attr] = getattr(service_entry, attr)
                
        return info
    
    def __len__(self) -> int:
        """Return the number of registered services."""
        return len(self._services)
    
    def __contains__(self, service_name: str) -> bool:
        """Check if a service is registered."""
        return service_name in self._services
    
    def __iter__(self):
        """Iterate over service names."""
        return iter(self._services)
    
    def __repr__(self) -> str:
        """String representation of the registry."""
        num_services = len(self._services)
        
        # Try to get model count if cache is built
        if self._cache_valid:
            num_models = len(self._model_to_services)
            return f"InferenceServiceRegistry({num_services} services, {num_models} models)"
        else:
            return f"InferenceServiceRegistry({num_services} services: {list(self._services.keys())})"
