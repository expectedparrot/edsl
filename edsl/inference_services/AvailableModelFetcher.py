from typing import Any, List, Tuple, Optional, TYPE_CHECKING
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from edsl.inference_services.ServiceAvailability import ServiceAvailability
from functools import lru_cache

if TYPE_CHECKING:
    from edsl.inference_services.InferenceServiceABC import InferenceServiceABC


class AvailableModelFetcher:
    """Fetches available models from the various services."""

    service_availability = ServiceAvailability()

    def __init__(self, services, added_models):
        self.services: List["InferenceServiceABC"] = services
        self.added_models = added_models

    def fetch_service_by_service_name(self, service_name: str) -> "InferenceServiceABC":
        """The service name is the _inference_service_ attribute of the service."""
        for service in self.services:
            if service._inference_service_ == service_name:
                return service
        raise ValueError(f"Service {service_name} not found")

    @classmethod
    @lru_cache(maxsize=128)
    def _get_service_available(
        cls, service: "InferenceServiceABC", warn: bool = False
    ) -> list[str]:
        """
        Gets the available models for a single service.
        It service *not* the name of the service but rather the service object.
        """
        return cls.service_availability.get_service_available(service, warn)

    @lru_cache(maxsize=128)
    def get_service_models(
        self, service: "InferenceServiceABC"
    ) -> Tuple[List[List[Any]], str]:
        """Helper function to get models for a single service."""
        service_models = self._get_service_available(service)
        return (
            [[model, service._inference_service_, -1] for model in service_models],
            service._inference_service_,
        )

    def available(self, service: Optional[str] = None) -> List[List[Any]]:
        """
        Get available models from all services using parallel execution.
        Returns a list of [model, service_name, -1] entries.
        """
        if service:
            service = self.fetch_service_by_service_name(service)
            total_models = self.get_service_models(service=service)[
                0
            ]  # don't need to the service name b/c we already know it
            sorted_models = sorted(total_models)
            for i, model in enumerate(sorted_models):
                model[2] = "NA"
                model = tuple(model)
            return sorted_models

        total_models = []

        # Use a ThreadPoolExecutor to parallel process the services
        with ThreadPoolExecutor(max_workers=min(len(self.services), 10)) as executor:
            # Submit all service queries to the thread pool
            future_to_service = {
                executor.submit(self.get_service_models, service): service
                for service in self.services
            }

            # Collect results as they complete
            for future in as_completed(future_to_service):
                try:
                    models, service_name = future.result()
                    total_models.extend(models)

                    # Add any additional models for this service
                    for model in self.added_models.get(service_name, []):
                        total_models.append([model, service_name, -1])

                except Exception as exc:
                    print(f"Service query failed: {exc}")
                    # Optionally handle the error more gracefully
                    continue

        sorted_models = sorted(total_models)
        for i, model in enumerate(sorted_models):
            model[2] = i
            model = tuple(model)
        return sorted_models
