from enum import Enum
from typing import List, Optional, TYPE_CHECKING
from functools import partial
import warnings

if TYPE_CHECKING:
    from edsl.inference_services.InferenceServiceABC import InferenceServiceABC


class ModelSource(Enum):
    LOCAL = "local"
    COOP = "coop"
    CACHE = "cache"


class ServiceAvailability:
    """This class is responsible for fetching available models from different sources."""

    _coop_model_list = None

    @classmethod
    def models_from_coop(cls):
        if not cls._coop_model_list:
            from edsl import Coop

            c = Coop()
            coop_model_list = c.fetch_models()
            cls._coop_model_list = coop_model_list
        return cls._coop_model_list

    def __init__(self, source_order: Optional[List[ModelSource]] = None):
        """
        Initialize with custom source order.
        Default order is LOCAL -> COOP -> CACHE
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

    def get_service_available(
        self, service: "InferenceServiceABC", warn: bool = False
    ) -> list[str]:
        """
        Try to fetch available models from sources in specified order.
        Returns first successful result.
        """
        last_error = None

        for source in self.source_order:
            try:
                fetch_func = partial(self._source_fetchers[source], service)
                result = fetch_func()

                # Cache successful result
                service._models_list_cache = result
                return result

            except Exception as e:
                last_error = e
                if warn:
                    self._warn_source_failed(service, source)
                continue

        # If we get here, all sources failed
        raise RuntimeError(
            f"All sources failed to fetch models. Last error: {last_error}"
        )

    @staticmethod
    def _fetch_from_local_service(service) -> list[str]:
        """Attempt to fetch models directly from the service."""
        return service.available()

    @classmethod
    def _fetch_from_coop(cls, service: "InferenceServiceABC") -> list[str]:
        """Fetch models from Coop."""
        models_from_coop = cls.models_from_coop()
        return models_from_coop.get(service._inference_service_, [])

    @staticmethod
    def _fetch_from_cache(service: "InferenceServiceABC") -> list[str]:
        """Fetch models from local cache."""
        from edsl.inference_services.models_available_cache import models_available

        return models_available.get(service._inference_service_, [])

    def _warn_source_failed(self, service: "InferenceServiceABC", source: ModelSource):
        """Display appropriate warning message based on failed source."""
        messages = {
            ModelSource.LOCAL: f"""Error getting models for {service._inference_service_}. 
                Check that you have properly stored your Expected Parrot API key and activated remote inference, 
                or stored your own API keys for the language models that you want to use.
                See https://docs.expectedparrot.com/en/latest/api_keys.html for instructions on storing API keys.
                Trying next source.""",
            ModelSource.COOP: f"Error getting models from Coop for {service._inference_service_}. Trying next source.",
            ModelSource.CACHE: f"Error getting models from cache for {service._inference_service_}.",
        }
        warnings.warn(messages[source], UserWarning)


# Example usage:
"""
# Default order (LOCAL -> COOP -> CACHE)
availability = ServiceAvailability()

# Custom order (COOP -> LOCAL -> CACHE)
availability_coop_first = ServiceAvailability([
    ModelSource.COOP,
    ModelSource.LOCAL,
    ModelSource.CACHE
])

# Get available models using custom order
models = availability_coop_first.get_service_available(service, warn=True)
"""
