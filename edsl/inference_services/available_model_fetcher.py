from typing import List, Tuple, Optional, Dict, Union, Type
from concurrent.futures import ThreadPoolExecutor, as_completed

from .service_availability import ServiceAvailability
from .inference_service_abc import InferenceServiceABC
from ..enums import InferenceServiceLiteral

from .data_structures import ModelNamesList, LanguageModelInfo, AvailableModels

from .available_model_cache_handler import AvailableModelCacheHandler


class ServiceResolver:
    """Handles service lookup and validation logic."""
    
    def __init__(self, service_map: Dict[str, Type[InferenceServiceABC]]):
        self._service_map = service_map
    
    def resolve_service(self, service: Union[InferenceServiceABC, InferenceServiceLiteral]) -> InferenceServiceABC:
        """Resolve service from string name or return service instance.
        
        >>> from edsl.inference_services.inference_service_abc import InferenceServiceABC
        >>> ExampleService = InferenceServiceABC.example(return_class=True)
        >>> service_map = {"test_service": ExampleService}
        >>> resolver = ServiceResolver(service_map)
        >>> resolved_service = resolver.resolve_service("test_service")
        >>> resolved_service.get_service_name()
        'test_service'
        """
        if isinstance(service, str):
            return self._fetch_service_by_service_name(service)
        return service
    
    def _fetch_service_by_service_name(self, service_name: InferenceServiceLiteral) -> InferenceServiceABC:
        """The service name is the _inference_service_ attribute of the service."""
        if service_name in self._service_map:
            return self._service_map[service_name]
        from .exceptions import InferenceServiceValueError
        raise InferenceServiceValueError(f"Service {service_name} not found")


class ModelFetchingLogger:
    """Handles logging and warning functionality for model fetching."""
    
    @staticmethod
    def warn_no_models_found(service_name: str):
        """Issue a warning when no models are found for a service."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # Ignores the warning
            warnings.warn(f"No models found for service {service_name}")


class AdditionalModelHandler:
    """Handles additional/supplementary models functionality."""
    
    def __init__(self, added_models: Dict[str, List[str]]):
        self.added_models = added_models
    
    def add_supplementary_models(self, models: List[LanguageModelInfo], service_name: str) -> List[LanguageModelInfo]:
        """Add any additional models for the specified service.
        
        >>> handler = AdditionalModelHandler({"test_service": ["custom_model_1", "custom_model_2"]})
        >>> models = [LanguageModelInfo(model_name="base_model", service_name="test_service")]
        >>> result = handler.add_supplementary_models(models, "test_service")
        >>> len(result)
        3
        >>> result[1].model_name
        'custom_model_1'
        >>> result[2].model_name
        'custom_model_2'
        """
        result = models.copy()
        for model in self.added_models.get(service_name, []):
            result.append(
                LanguageModelInfo(
                    model_name=model, 
                    service_name=service_name
                )
            )
        return result


class CachedModelFetcher:
    """Handles cache-first model fetching strategy."""
    
    def __init__(self, cache_handler: Optional[AvailableModelCacheHandler], verbose: bool = True):
        self.cache_handler = cache_handler
        self.verbose = verbose
    
    def fetch_models(self, service: InferenceServiceABC, force_refresh: bool = False) -> Optional[AvailableModels]:
        """Attempt to fetch models from cache.
        
        Returns None if cache miss or force_refresh is True.
        """
        if force_refresh or not self.cache_handler:
            if self.verbose:
                print(f"No cache handler or force refresh, returning None for {service.get_service_name()}")
            return None
            
        models_from_cache = self.cache_handler.models(service=service._inference_service_)
        
        if self.verbose:
            print("Searching cache for models with service name:", service._inference_service_)
            print("Got models from cache:", models_from_cache)
        
        return models_from_cache


class FreshModelFetcher:
    """Handles fresh API model fetching strategy."""
    
    def __init__(self, service_availability: ServiceAvailability, cache_handler: Optional[AvailableModelCacheHandler], verbose: bool = False):
        self.service_availability = service_availability
        self.cache_handler = cache_handler
        self.verbose = verbose
    
    def fetch_models(self, service: InferenceServiceABC, force_refresh: bool = False) -> Tuple[AvailableModels, str]:
        """Fetch fresh models from service API.
        
        >>> from edsl.inference_services.inference_service_abc import InferenceServiceABC
        >>> ExampleService = InferenceServiceABC.example(return_class=True)
        >>> service_availability = ServiceAvailability()
        >>> fetcher = FreshModelFetcher(service_availability, None, verbose=False)
        >>> models, service_name = fetcher.fetch_models(ExampleService)
        >>> service_name
        'test_service'
        >>> len(models) >= 1
        True
        """
        if self.verbose:
            print("Fetching fresh models using ServiceAvailability class")
            print("Service:", service)
        service_models: ModelNamesList = (
            self.service_availability.get_service_available(service, warn=False, force_refresh=force_refresh)
        )
        
        if self.verbose:
            print("Found service_models", service_models)
            
        service_name = service.get_service_name()

        if not service_models:
            ModelFetchingLogger.warn_no_models_found(service_name)
            return [], service_name

        models_list = AvailableModels([
            LanguageModelInfo(
                model_name=model_name,
                service_name=service_name,
            )
            for model_name in service_models
        ])
        
        if self.cache_handler:
            self.cache_handler.add_models_to_cache(models_list)  # update the cache
            
        return models_list, service_name


class ConcurrentModelFetcher:
    """Handles concurrent fetching of models from multiple services."""
    
    def __init__(self, additional_model_handler: AdditionalModelHandler, verbose: bool = False):
        self.additional_model_handler = additional_model_handler
        self.verbose = verbose
    
    def fetch_all_models_concurrently(self, services: List[Type[InferenceServiceABC]], 
                                     fetcher_func, force_refresh: bool = False) -> List[LanguageModelInfo]:
        """Fetch models from all services concurrently using thread pool.
        
        >>> from edsl.inference_services.inference_service_abc import InferenceServiceABC
        >>> ExampleService = InferenceServiceABC.example(return_class=True)
        >>> handler = AdditionalModelHandler({"test_service": ["extra_model"]})
        >>> fetcher = ConcurrentModelFetcher(handler, verbose=False)
        >>> def mock_fetcher(service, force_refresh=False):
        ...     return [LanguageModelInfo(model_name="base_model", service_name="test_service")], "test_service"
        >>> result = fetcher.fetch_all_models_concurrently([ExampleService], mock_fetcher, False)
        >>> len(result)
        2
        >>> result[1].model_name
        'extra_model'
        """
        all_models = []
        
        with ThreadPoolExecutor(max_workers=min(len(services), 10)) as executor:
            future_to_service = {
                executor.submit(fetcher_func, service, force_refresh): service
                for service in services
            }

            for future in as_completed(future_to_service):
                service = future_to_service[future]
                try:
                    models, service_name = future.result()
                    all_models.extend(models)

                    # Add any additional models for this service
                    additional_models = self.additional_model_handler.add_supplementary_models(
                        [], service_name
                    )
                    all_models.extend(additional_models)

                except Exception as exc:
                    service_name = service.get_service_name() if hasattr(service, 'get_service_name') else str(service)
                    if self.verbose:
                        print(f"Service query failed for service {service_name}: {exc}")
                    continue

        return AvailableModels(all_models)


class AvailableModelFetcher:
    """Fetches available models from the various services with JSON caching."""

    CACHE_VALIDITY_HOURS = 48  # Cache validity period in hours

    def __init__(
        self,
        services: List[Type["InferenceServiceABC"]],
        added_models: Dict[str, List[str]],
        verbose: bool = False,
        use_cache: bool = True,
    ):
        self.services = services
        self.added_models = added_models
        self.verbose = verbose
        self.use_cache = use_cache
        
        # Initialize service availability (moved from class attribute to instance)
        self.service_availability = ServiceAvailability()
        
        # Initialize cache handler
        if use_cache:
            self.cache_handler = AvailableModelCacheHandler()
        else:
            self.cache_handler = None
        
        # Initialize helper classes
        self._service_map = {
            service.get_service_name(): service for service in services
        }
        self.service_resolver = ServiceResolver(self._service_map)
        self.additional_model_handler = AdditionalModelHandler(added_models)
        self.cached_model_fetcher = CachedModelFetcher(self.cache_handler, verbose)
        self.fresh_model_fetcher = FreshModelFetcher(self.service_availability, self.cache_handler, verbose)
        self.concurrent_model_fetcher = ConcurrentModelFetcher(self.additional_model_handler, verbose)

    def __repr__(self):
        return f"<AvailableModelFetcher(services={self.services}, added_models={self.added_models}, verbose={self.verbose}, use_cache={self.use_cache})>"

    @property
    def num_cache_entries(self):
        if not self.cache_handler:
            raise ValueError("Cache handler not initialized")
        return self.cache_handler.num_cache_entries

    @property
    def path_to_db(self):
        if not self.cache_handler:
            raise ValueError("Cache handler not initialized")
        return self.cache_handler.path_to_db

    def reset_cache(self):
        if not self.cache_handler:
            raise ValueError("Cache handler not initialized")
        self.cache_handler.reset_cache()

    def available(
        self,
        service: Optional[Union[Type["InferenceServiceABC"], InferenceServiceLiteral]] = None,
        force_refresh: bool = False,    
    ) -> List[LanguageModelInfo]:
        """
        Get available models from all services passed in, using cached data when available.

        :param service: Optional[InferenceServiceABC] - If specified, only fetch models for this service.

        >>> from .services.open_ai_service import OpenAIService
        >>> af = AvailableModelFetcher([OpenAIService()], {})
        >>> af.available(service="openai")
        [LanguageModelInfo(model_name='...', service_name='openai'), ...]

        Returns a list of [model, service_name, index] entries.
        """
        if service:
            service = self.service_resolver.resolve_service(service)
            
            # Force refresh for certain services
            if service.get_service_name() in ["azure", "bedrock"]:
                force_refresh = True  # Azure models are listed inside the .env AZURE_ENDPOINT_URL_AND_KEY variable

            matching_models, service_name = self.get_available_models_by_service(
                service=service, force_refresh=force_refresh
            )
            
            # Add any additional models for this service
            return self.additional_model_handler.add_supplementary_models(
                matching_models, service_name
            )

        # Fetch all models from all services
        return self._get_all_models(force_refresh)

    def get_available_models_by_service(
        self,
        service: Union["InferenceServiceABC", InferenceServiceLiteral],
        force_refresh: bool = False,
    ) -> Tuple[AvailableModels, InferenceServiceLiteral]:
        """Get models for a single service.

        :param service: InferenceServiceABC - e.g., OpenAIService or "openai"
        :return: Tuple[List[LanguageModelInfo], InferenceServiceLiteral]
        """
        service = self.service_resolver.resolve_service(service)

        # Try cache first
        models_from_cache = self.cached_model_fetcher.fetch_models(service, force_refresh)
        
        if models_from_cache is not None:
            return models_from_cache, service._inference_service_
        else:
            if self.verbose:
                print("No models found in cache, fetching fresh models")
            return self.get_available_models_by_service_fresh(service, force_refresh=force_refresh)

    def get_available_models_by_service_fresh(
        self, service: Union["InferenceServiceABC", InferenceServiceLiteral], force_refresh: bool = False
    ) -> Tuple[AvailableModels, InferenceServiceLiteral]:
        """Get models for a single service. This method always fetches fresh data.

        :param service: InferenceServiceABC - e.g., OpenAIService or "openai"
        :return: Tuple[List[LanguageModelInfo], InferenceServiceLiteral]


        >>> from edsl.inference_services.inference_service_abc import InferenceServiceABC
        >>> ExampleService = InferenceServiceABC.example(return_class=True)
        >>> af = AvailableModelFetcher(services=[ExampleService], added_models={}, verbose=False)
        >>> af.get_available_models_by_service_fresh(service="test_service")
        ([LanguageModelInfo(model_name='test_model_1', service_name='test_service'), LanguageModelInfo(model_name='test_model_2', service_name='test_service')], 'test_service')
        """
        service = self.service_resolver.resolve_service(service)
        return self.fresh_model_fetcher.fetch_models(service, force_refresh=force_refresh)

    def _fetch_service_by_service_name(
        self, service_name: InferenceServiceLiteral
    ) -> "InferenceServiceABC":
        """The service name is the _inference_service_ attribute of the service.
        
        >>> from edsl.inference_services.inference_service_abc import InferenceServiceABC
        >>> ExampleService = InferenceServiceABC.example(return_class=True)
        >>> af = AvailableModelFetcher(services=[ExampleService], added_models={}, verbose=False)
        >>> fetched_service = af._fetch_service_by_service_name(service_name="test_service")
        >>> fetched_service.get_service_name()
        'test_service'
        """
        return self.service_resolver._fetch_service_by_service_name(service_name)

    def _get_all_models(self, force_refresh=False) -> List[LanguageModelInfo]:
        """Get models from all services concurrently."""
        if self.verbose:
            print("Fetching all models from all services")
        return self.concurrent_model_fetcher.fetch_all_models_concurrently(
            self.services, 
            self.get_available_models_by_service,
            force_refresh
        )


def main():
    from .services.open_ai_service import OpenAIService

    # Create fetcher without assigning to unused variable
    all_models = AvailableModelFetcher([OpenAIService()], {})._get_all_models(
        force_refresh=True
    )
    print(all_models)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
    # main()

    from edsl.inference_services.inference_service_abc import InferenceServiceABC
    ExampleService = InferenceServiceABC.example(return_class=True)

    af = AvailableModelFetcher(services=[ExampleService], added_models={}, verbose=True)
    print(af.available(service="test_service"))


    #from edsl.inference_services.services import OpenAIService
    #from edsl.inference_services.available_model_fetcher import AvailableModelFetcher
    #af = AvailableModelFetcher([OpenAIService], {}, verbose=True)
    #print(af.available(service="openai"))

