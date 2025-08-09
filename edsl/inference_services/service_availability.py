from enum import Enum
from typing import List, Optional, TYPE_CHECKING, Type
from functools import partial
import warnings

from .data_structures import AvailableModels, ModelNamesList
from .inference_service_abc import InferenceServiceABC

if TYPE_CHECKING:
    from .inference_service_abc import InferenceServiceABC


class ModelSource(Enum):
    """Sources for fetching model lists.
    
    Attributes:
        LOCAL: Fetch from the inference service directly
        COOP: Fetch from the Expected Parrot cooperative service
        CACHE: Fetch from local static cache
    """
    LOCAL = "local"
    COOP = "coop"
    CACHE = "cache"


class ServiceAvailability:
    """Fetches available models from multiple sources with fallback ordering.
    
    Tries sources in order until one succeeds. Caches successful results
    on the service instance.
    
    Attributes:
        source_order (List[ModelSource]): Order of sources to try
        _coop_model_list (AvailableModels): Class-level cache for Coop data    
    """

    _coop_model_list = None

    def __init__(self, source_order: Optional[List[ModelSource]] = None, verbose: bool = True):
        """Initialize with source ordering.
        
        Args:
            source_order: Order of sources to try. 
                         Defaults to [LOCAL, COOP, CACHE]
        """
        self.source_order = source_order or [
            ModelSource.LOCAL,
            ModelSource.COOP,
            ModelSource.CACHE,
        ]

        # Map sources to their fetch functions
        self._source_fetchers = {
            ModelSource.LOCAL: self._fetch_from_local_service,
            ModelSource.COOP: self._fetch_from_coop,
            ModelSource.CACHE: self._fetch_from_cache,
        }
        self.verbose = verbose

    @classmethod
    def models_from_coop(cls) -> AvailableModels:
        """Get models from Coop service with class-level caching.
        
        Returns:
            AvailableModels: Dictionary mapping service names to model lists
            
        Note:
            Result is cached at class level to avoid repeated network calls.
        """
        if not cls._coop_model_list:
            from ..coop.coop import Coop

            c = Coop()
            coop_model_list = c.fetch_models()
            cls._coop_model_list = coop_model_list
        return cls._coop_model_list

    def get_service_available(
        self, service: Type["InferenceServiceABC"], warn: bool = True
    ) -> ModelNamesList:
        """Get available models for a service by trying sources in order.
        
        Args:
            service: Inference service class to get models for
            warn: Whether to emit warnings when sources fail
            
        Returns:
            ModelNamesList: List of available model names
            
        Raises:
            InferenceServiceRuntimeError: If all sources fail
                                        
        Note:
            Caches successful result on service._models_list_cache class attribute
        """
        # Check if service already has cached models
        if hasattr(service, '_models_list_cache') and service._models_list_cache is not None:
            if self.verbose:
                print(f"Using cached models for {service.get_service_name()}: {service._models_list_cache}")
            return service._models_list_cache

        last_error = None

        for source in self.source_order:
            # try:
            if self.verbose:
                print(f"Fetching models from {source} using ServiceAvailability class for {service.get_service_name()}")
            fetch_func = partial(self._source_fetchers[source], service)
            try:
                result = fetch_func()
            except Exception as e:
                last_error = e
                if warn:
                    self._warn_source_failed(service, source)
                print(f"Method {source} failed, moving on to next source...")
                continue

            if self.verbose:
                print(f"Got models from {source}: {result} using ServiceAvailability class for {service.get_service_name()}")

            # Cache successful result on the service class
            service._models_list_cache = result
            return result

            # except Exception as e:
            #     last_error = e
            #     if warn:
            #         self._warn_source_failed(service, source)
            #     continue

        # If we get here, all sources failed
        from .exceptions import InferenceServiceRuntimeError

        raise InferenceServiceRuntimeError(
            f"All sources failed to fetch models. Last error: {last_error}"
        )

    @staticmethod
    def _fetch_from_local_service(service: Type["InferenceServiceABC"]) -> ModelNamesList:
        """Fetch models by calling service.available().
        
        Args:
            service: Service class to query
            
        Returns:
            ModelNamesList: Models returned by service
            
        Raises:
            Various exceptions from the service (auth, network, API errors)
        """
        return service.available()

    @classmethod
    def _fetch_from_coop(cls, service: Type["InferenceServiceABC"]) -> ModelNamesList:
        """Fetch models from Coop registry.
        
        Args:
            service: Service class to get models for
            
        Returns:
            ModelNamesList: Models for this service from Coop, or empty list
                           if service not found
        """
        models_from_coop = cls.models_from_coop()
        return models_from_coop.get(service.get_service_name(), [])

    @staticmethod
    def _fetch_from_cache(service: Type["InferenceServiceABC"]) -> ModelNamesList:
        """Fetch models from local cache file. This is the method of last resort.
        
        Args:
            service: Service class to get cached models for
            
        Returns:
            ModelNamesList: Cached models for this service, or empty list
                           if service not found
                           
        Note:
            Cache data may be outdated compared to live sources.
        """
        from .models_available_cache import models_available

        return models_available.get(service.get_service_name(), [])

    def _warn_source_failed(self, service: Type["InferenceServiceABC"], source: ModelSource):
        """Emit warning when a source fails.
        
        Args:
            service: Service class that failed
            source: Source that encountered an error
        """
        service_name = service.get_service_name()
        messages = {
            ModelSource.LOCAL: f"""Error getting models for {service_name}. 
                Check that you have properly stored your Expected Parrot API key and activated remote inference, 
                or stored your own API keys for the language models that you want to use.
                See https://docs.expectedparrot.com/en/latest/api_keys.html for instructions on storing API keys.
                Trying next source.""",
            ModelSource.COOP: f"Error getting models from Coop for {service_name}. Trying next source.",
            ModelSource.CACHE: f"Error getting models from cache for {service_name}.",
        }
        warnings.warn(messages[source], UserWarning)


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    sa = ServiceAvailability()
    from edsl.inference_services.services import OpenAIService
    print(sa.get_service_available(service=OpenAIService))

    # coop only 
    print("coop only")
    new_fetch = ServiceAvailability(source_order=[ModelSource.COOP])
    print(new_fetch.get_service_available(service=OpenAIService))
